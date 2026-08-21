import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_user_from_token
from backend.app.notification_service import (
    list_notifications_for_subject,
    mark_notification_as_read,
    resolve_subject,
    serialize_notification,
    unread_count_for_subject,
)
from backend.app.order_runtime import (
    ensure_order_thread,
    list_thread_messages,
    serialize_conversation_message,
    update_message_receipt,
    create_conversation_message,
)
from backend.database import get_db, SessionLocal
from backend.models import (
    BusinessUser,
    ConversationParticipant,
    MessageReceipt,
    Notification,
    Order,
    User,
    DeliveryOrder,
    LogisticsUser,
    Sale,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# --- Real-time WebSocket Manager ---

class ConnectionManager:
    def __init__(self):
        # order_id -> set of active websockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.connection_subjects: Dict[WebSocket, dict] = {}

    async def connect(
        self,
        websocket: WebSocket,
        order_id: int,
        *,
        subject_type: str,
        subject_id: int,
        name: str,
        role: str,
    ):
        await websocket.accept()
        if order_id not in self.active_connections:
            self.active_connections[order_id] = set()
        self.active_connections[order_id].add(websocket)
        self.connection_subjects[websocket] = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "name": name,
            "role": role,
        }

    def disconnect(self, websocket: WebSocket, order_id: int):
        if order_id in self.active_connections:
            self.active_connections[order_id].remove(websocket)
            if not self.active_connections[order_id]:
                del self.active_connections[order_id]
        self.connection_subjects.pop(websocket, None)

    async def broadcast_to_order(self, order_id: int, message: dict, exclude: WebSocket | None = None):
        if order_id in self.active_connections:
            targets = list(self.active_connections[order_id])
            for connection in targets:
                if exclude is not None and connection is exclude:
                    continue
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(connection, order_id)

manager = ConnectionManager()


def _schedule_broadcast(order_id: int, payload: dict, exclude: WebSocket | None = None):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(manager.broadcast_to_order(order_id, payload, exclude=exclude))


def broadcast_order_status(order_id: int, payload: dict, exclude: WebSocket | None = None):
    _schedule_broadcast(order_id, payload, exclude=exclude)


def enqueue_broadcast(background_tasks: BackgroundTasks, order_id: int, payload: dict, exclude: WebSocket | None = None):
    background_tasks.add_task(_schedule_broadcast, order_id, payload, exclude)


# --- WebSocket Endpoint ---

@router.websocket("/ws/delivery/{order_id}")
async def delivery_websocket(websocket: WebSocket, order_id: int, token: str = None):
    """
    WebSocket for live chat and location tracking.
    Usage: ws://host/notifications/ws/delivery/123?token=XYZ
    """
    user = None
    if token:
        user = get_user_from_token(token)
    
    if not user:
        await websocket.close(code=1008) # Policy Violation
        return

    db = SessionLocal()
    try:
        delivery = db.query(DeliveryOrder).filter(DeliveryOrder.order_id == order_id).first()
        sale = db.query(Sale).filter(Sale.id == order_id).first()
        
        if not sale:
            await websocket.close(code=1007) # Invalid Data
            return
            
        buyer_id = getattr(sale, "buyer_id", None) or getattr(sale, "created_by", None) or getattr(delivery, "buyer_id", None)
        seller_id = getattr(sale, "seller_id", None) or getattr(delivery, "seller_id", None)
        buyer = db.query(User).filter(User.id == int(buyer_id)).first() if buyer_id is not None else None
        seller = db.query(BusinessUser).filter(BusinessUser.id == int(seller_id)).first() if seller_id is not None else None
        logistics = (
            db.query(LogisticsUser).filter(LogisticsUser.id == int(delivery.logistics_id)).first()
            if delivery and delivery.logistics_id is not None
            else None
        )
        linked_order = None
        if getattr(sale, "order_id", None):
            linked_order = db.query(Order).filter(Order.id == sale.order_id).first()
        if linked_order is None:
            linked_order = db.query(Order).filter(Order.legacy_sale_id == sale.id).first()
        
        is_buyer = buyer_id is not None and int(buyer_id) == user.id and user.role == "user"
        is_rider = delivery and delivery.logistics_id == user.id and user.role == "logistics"
        is_seller = seller_id is not None and int(seller_id) == user.id and user.role == "seller"
        
        # Only buyer, rider or seller can join
        if not (is_buyer or is_rider or is_seller):
            await websocket.close(code=1008)
            return

        subject_type, subject_id, _, display_name = resolve_subject(user)
        role = str(getattr(user, "role", "") or subject_type).strip().lower() or subject_type
        thread = ensure_order_thread(
            db,
            order=linked_order,
            sale=sale,
            seller=seller,
            buyer=buyer,
            logistics=logistics,
        )
        db.flush()
        await manager.connect(
            websocket,
            order_id,
            subject_type=subject_type,
            subject_id=subject_id,
            name=display_name,
            role=role,
        )

        history = list_thread_messages(db, thread_id=thread.id, limit=80)
        history_message_ids = [item.id for item in history]
        for item in history:
            if item.sender_type != subject_type or item.sender_id != subject_id:
                update_message_receipt(
                    db,
                    message_id=item.id,
                    recipient_type=subject_type,
                    recipient_id=subject_id,
                    status="read",
                )
        db.commit()
        receipts = (
            db.query(MessageReceipt)
            .filter(MessageReceipt.message_id.in_(history_message_ids))
            .all()
            if history_message_ids
            else []
        )
        await websocket.send_json(
            {
                "type": "history",
                "messages": [
                    serialize_conversation_message(
                        item,
                        current_type=subject_type,
                        current_id=subject_id,
                        receipts=receipts,
                    )
                    for item in history
                ],
            }
        )
        
        await manager.broadcast_to_order(order_id, {
            "type": "presence",
            "user": subject_id,
            "name": display_name,
            "role": role,
            "state": "online",
            "status": "online",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get("type")
                
                if msg_type == "chat":
                    text = str(message.get("text") or "").strip()
                    if not text:
                        continue
                    stored = create_conversation_message(
                        db,
                        thread=thread,
                        sender=user,
                        text=text,
                        client_id=(message.get("client_id") or "").strip() or None,
                    )
                    db.commit()
                    receipts = db.query(MessageReceipt).filter(MessageReceipt.message_id == stored.id).all()
                    await manager.broadcast_to_order(order_id, {
                        **serialize_conversation_message(stored, receipts=receipts),
                        "type": "chat",
                    })
                
                elif msg_type == "typing":
                    await manager.broadcast_to_order(
                        order_id,
                        {
                            "type": "typing",
                            "user": subject_id,
                            "name": display_name,
                            "role": role,
                            "is_typing": bool(message.get("is_typing")),
                        },
                        exclude=websocket,
                    )
                
                elif msg_type == "location" and user.role == "logistics":
                    lat = message.get("lat")
                    lng = message.get("lng")
                    
                    if lat and lng:
                        if delivery:
                            delivery.current_lat = lat
                            delivery.current_lng = lng
                            delivery.last_location_name = (message.get("current_location") or delivery.last_location_name or "Live location")
                            delivery.tracking_updated_at = datetime.now(timezone.utc)
                            db.add(delivery)
                            db.commit()
                        
                        await manager.broadcast_to_order(order_id, {
                            "type": "location",
                            "lat": lat,
                            "lng": lng,
                            "rider_name": user.name
                        })
                elif msg_type == "receipt":
                    message_id = message.get("message_id")
                    receipt_status = str(message.get("status") or "read").strip().lower() or "read"
                    try:
                        message_id = int(message_id)
                    except (TypeError, ValueError):
                        continue
                    update_message_receipt(
                        db,
                        message_id=message_id,
                        recipient_type=subject_type,
                        recipient_id=subject_id,
                        status="read" if receipt_status == "read" else "delivered",
                    )
                    participant = (
                        db.query(ConversationParticipant)
                        .filter(
                            ConversationParticipant.thread_id == thread.id,
                            ConversationParticipant.participant_type == subject_type,
                            ConversationParticipant.participant_id == subject_id,
                        )
                        .first()
                    )
                    if participant:
                        participant.last_read_message_id = message_id
                        db.add(participant)
                    db.commit()
                    await manager.broadcast_to_order(
                        order_id,
                        {
                            "type": "receipt",
                            "message_id": str(message_id),
                            "status": "read" if receipt_status == "read" else "delivered",
                            "recipient_id": subject_id,
                        },
                        exclude=websocket,
                    )

        except WebSocketDisconnect:
            manager.disconnect(websocket, order_id)
            await manager.broadcast_to_order(order_id, {
                "type": "presence",
                "user": subject_id,
                "name": display_name,
                "role": role,
                "state": "offline",
                "status": "offline",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
    finally:
        db.close()

# --- Standard Notification Routes ---

@router.get("/")
def get_notifications(
    limit: int = 50,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient_type, recipient_id, _, _ = resolve_subject(current)
    items = list_notifications_for_subject(db, recipient_type, recipient_id, limit=limit, unread_only=unread_only)
    return {
        "items": [serialize_notification(item) for item in items],
        "unread_count": unread_count_for_subject(db, recipient_type, recipient_id),
    }


@router.get("/summary")
def get_notification_summary(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient_type, recipient_id, _, _ = resolve_subject(current)
    return {"unread_count": unread_count_for_subject(db, recipient_type, recipient_id)}


@router.post("/{notification_id}/read")
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient_type, recipient_id, _, _ = resolve_subject(current)
    item = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.recipient_type == recipient_type,
            Notification.recipient_id == recipient_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")

    mark_notification_as_read(db, item)
    db.commit()
    db.refresh(item)
    return {"item": serialize_notification(item)}


@router.post("/read-all")
def read_all_notifications(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient_type, recipient_id, _, _ = resolve_subject(current)
    items = list_notifications_for_subject(db, recipient_type, recipient_id, limit=100, unread_only=True)
    for item in items:
        mark_notification_as_read(db, item)
    db.commit()
    return {"updated": len(items)}
