import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.notification_service import resolve_subject
from backend.models import (
    AuditLog,
    BusinessUser,
    ConversationMessage,
    ConversationParticipant,
    ConversationThread,
    InventoryReservation,
    LogisticsUser,
    MessageReceipt,
    Order,
    OrderStatusHistory,
    Sale,
    ShipmentEvent,
    User,
)


SUBJECT_PRIORITY = {
    "sent": 1,
    "delivered": 2,
    "read": 3,
}


def actor_payload(actor: User | BusinessUser | LogisticsUser | None) -> tuple[str, int | None, str, str]:
    if actor is None:
        return "system", None, "System", "system"

    subject_type, subject_id, _, display_name = resolve_subject(actor)
    role = str(getattr(actor, "role", "") or subject_type).strip().lower() or subject_type
    return subject_type, subject_id, display_name, role


def record_audit(
    db: Session,
    *,
    actor: User | BusinessUser | LogisticsUser | None,
    entity_type: str,
    entity_id: int | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    actor_type, actor_id, _, _ = actor_payload(actor)
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details_json=json.dumps(details) if details else None,
    )
    db.add(entry)
    return entry


def log_order_status(
    db: Session,
    *,
    order_id: int,
    sale_id: int | None,
    status: str,
    reason: str | None,
    actor: User | BusinessUser | LogisticsUser | None,
    metadata: dict[str, Any] | None = None,
) -> OrderStatusHistory:
    actor_type, actor_id, _, _ = actor_payload(actor)
    entry = OrderStatusHistory(
        order_id=order_id,
        sale_id=sale_id,
        status=status,
        reason=reason,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(entry)
    return entry


def reserve_inventory(
    db: Session,
    *,
    order_id: int,
    order_item_id: int,
    product_id: int,
    quantity: int,
) -> InventoryReservation:
    reservation = InventoryReservation(
        order_id=order_id,
        order_item_id=order_item_id,
        product_id=product_id,
        reserved_quantity=quantity,
        status="reserved",
    )
    db.add(reservation)
    return reservation


def update_reservation_status(
    db: Session,
    *,
    order_id: int,
    status: str,
) -> None:
    now = datetime.now(timezone.utc)
    items = (
        db.query(InventoryReservation)
        .filter(InventoryReservation.order_id == order_id, InventoryReservation.status != status)
        .all()
    )
    for item in items:
        item.status = status
        if status in {"released", "consumed"}:
            item.released_at = now
        db.add(item)


def record_shipment_event(
    db: Session,
    *,
    delivery_id: int,
    order_id: int | None,
    sale_id: int | None,
    status: str,
    actor: User | BusinessUser | LogisticsUser | None,
    message: str | None = None,
    event_type: str = "status_change",
    lat: float | None = None,
    lng: float | None = None,
) -> ShipmentEvent:
    actor_type, actor_id, _, _ = actor_payload(actor)
    event = ShipmentEvent(
        delivery_id=delivery_id,
        order_id=order_id,
        sale_id=sale_id,
        status=status,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        message=message,
        lat=lat,
        lng=lng,
    )
    db.add(event)
    return event


def ensure_order_thread(
    db: Session,
    *,
    order: Order | None = None,
    sale: Sale | None = None,
    seller: BusinessUser | None = None,
    buyer: User | None = None,
    logistics: LogisticsUser | None = None,
) -> ConversationThread:
    thread = None
    if order is not None:
        thread = db.query(ConversationThread).filter(ConversationThread.order_id == order.id).first()
    if thread is None and sale is not None:
        thread = db.query(ConversationThread).filter(ConversationThread.sale_id == sale.id).first()

    if thread is None:
        subject = None
        if sale is not None:
            subject = f"Order #{sale.id} - {sale.product or 'Order'}"
        elif order is not None:
            subject = f"Order #{order.id}"
        thread = ConversationThread(
            order_id=order.id if order else None,
            sale_id=sale.id if sale else None,
            subject=subject,
        )
        db.add(thread)
        db.flush()

    participants: list[tuple[str, int]] = []
    if buyer is not None:
        subject_type, subject_id, _, _ = resolve_subject(buyer)
        participants.append((subject_type, subject_id))
    if seller is not None:
        subject_type, subject_id, _, _ = resolve_subject(seller)
        participants.append((subject_type, subject_id))
    if logistics is not None:
        subject_type, subject_id, _, _ = resolve_subject(logistics)
        participants.append((subject_type, subject_id))

    for participant_type, participant_id in participants:
        existing = (
            db.query(ConversationParticipant)
            .filter(
                ConversationParticipant.thread_id == thread.id,
                ConversationParticipant.participant_type == participant_type,
                ConversationParticipant.participant_id == participant_id,
            )
            .first()
        )
        if existing is None:
            db.add(
                ConversationParticipant(
                    thread_id=thread.id,
                    participant_type=participant_type,
                    participant_id=participant_id,
                )
            )

    return thread


def create_conversation_message(
    db: Session,
    *,
    thread: ConversationThread,
    sender: User | BusinessUser | LogisticsUser,
    text: str,
    client_id: str | None = None,
    message_type: str = "chat",
) -> ConversationMessage:
    sender_type, sender_id, sender_name, sender_role = actor_payload(sender)
    message = ConversationMessage(
        thread_id=thread.id,
        sender_type=sender_type,
        sender_id=sender_id or 0,
        sender_name=sender_name,
        sender_role=sender_role,
        message_type=message_type,
        client_id=client_id,
        text=text,
    )
    db.add(message)
    db.flush()

    participants = (
        db.query(ConversationParticipant)
        .filter(ConversationParticipant.thread_id == thread.id)
        .all()
    )
    for participant in participants:
        if participant.participant_type == sender_type and participant.participant_id == sender_id:
            continue
        db.add(
            MessageReceipt(
                message_id=message.id,
                recipient_type=participant.participant_type,
                recipient_id=participant.participant_id,
                status="delivered",
            )
        )

    thread.last_message_at = datetime.now(timezone.utc)
    db.add(thread)
    return message


def update_message_receipt(
    db: Session,
    *,
    message_id: int,
    recipient_type: str,
    recipient_id: int,
    status: str,
) -> MessageReceipt | None:
    receipt = (
        db.query(MessageReceipt)
        .filter(
            MessageReceipt.message_id == message_id,
            MessageReceipt.recipient_type == recipient_type,
            MessageReceipt.recipient_id == recipient_id,
        )
        .first()
    )
    if receipt is None:
        receipt = MessageReceipt(
            message_id=message_id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            status=status,
        )
        db.add(receipt)
        return receipt

    if SUBJECT_PRIORITY.get(status, 0) >= SUBJECT_PRIORITY.get(receipt.status, 0):
        receipt.status = status
        db.add(receipt)
    return receipt


def serialize_conversation_message(
    message: ConversationMessage,
    *,
    current_type: str | None = None,
    current_id: int | None = None,
    receipts: list[MessageReceipt] | None = None,
) -> dict[str, Any]:
    status = "sent"
    if receipts:
        relevant_receipts = [
            item for item in receipts if item.message_id == message.id
        ]
        if any(item.status == "read" for item in relevant_receipts):
            status = "read"
        elif any(item.status == "delivered" for item in relevant_receipts):
            status = "delivered"

    sender_role = message.sender_role
    if current_type is not None and current_id is not None:
        if message.sender_type == current_type and message.sender_id == current_id:
            sender_role = "self"

    return {
        "id": str(message.id),
        "client_id": message.client_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender_name,
        "sender_role": sender_role,
        "text": message.text,
        "timestamp": message.created_at.isoformat() if message.created_at else None,
        "status": status,
        "type": message.message_type,
    }


def list_thread_messages(
    db: Session,
    *,
    thread_id: int,
    limit: int = 50,
) -> list[ConversationMessage]:
    rows = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.thread_id == thread_id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    rows.reverse()
    return rows

