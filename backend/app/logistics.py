import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Header, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.app.marketplace_intelligence import (
    build_tracking_payload,
    coords_for_location,
    haversine_km,
    interpolate_coords,
)
from backend.models import LogisticsUser, LogisticsMetrics, DeliveryOrder, BusinessUser, Order, Sale, User, PaymentTransaction
from backend.app.schemas import (
    LogisticsRegister, LogisticsLogin, LogisticsProfile,
    DeliveryOrderCreate, DeliveryOrderResponse, DeliveryStatusUpdate
)
from backend.app.auth import hash_password, verify_password, verify_and_upgrade_password, create_access_token as create_token, decode_token, _normalize_phone, _phone_matches, get_current_user, security
from backend.app.business import get_current_business_user
from backend.app.notification_service import build_login_email, create_notification, resolve_subject
from backend.app.order_runtime import ensure_order_thread, log_order_status, record_audit, record_shipment_event, update_reservation_status

router = APIRouter(prefix="/logistics", tags=["Logistics"])
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _serialize_logistics(user: LogisticsUser, include_email: bool = True) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email if include_email else None,
        "role": "logistics",
        "account_type": user.account_type,
        "vehicle_type": user.vehicle_type,
        "plate_number": user.plate_number,
        "license_number": user.license_number,
        "base_area": user.base_area,
        "coverage_areas": user.coverage_areas,
        "status": user.status,
        "availability": user.availability,
        "profile_photo": user.profile_photo,
        "verification_status": user.verification_status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _get_logistics_user(db: Session, phone: str = None, email: str = None):
    if phone:
        user = db.query(LogisticsUser).filter(LogisticsUser.phone == phone).first()
        if user:
            return user
        normalized_phone = _normalize_phone(phone)
        if normalized_phone:
            candidates = db.query(LogisticsUser).filter(LogisticsUser.phone.isnot(None)).all()
            for candidate in candidates:
                if _phone_matches(candidate.phone, normalized_phone):
                    return candidate
    if email:
        return db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == email.lower()).first()
    return None


def _validate_new_password(current_password: str, new_password: str, password_hash: str):
    if not verify_password(current_password, password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")


def _mask_phone(phone: str | None) -> str | None:
    raw = str(phone or "").strip()
    if len(raw) <= 4:
        return raw or None
    return f"{raw[:3]}{'*' * max(2, len(raw) - 5)}{raw[-2:]}"


def _notify_delivery_event(
    db: Session,
    background_tasks: BackgroundTasks,
    delivery: DeliveryOrder,
    *,
    title: str,
    message: str,
    buyer_message: str | None = None,
    seller_message: str | None = None,
    severity: str = "info",
):
    recipients: list[tuple[BusinessUser | User, str, str]] = []
    if delivery.seller_id:
        seller = db.query(BusinessUser).filter(BusinessUser.id == delivery.seller_id).first()
        if seller:
            recipients.append((seller, "/app/seller/deliveries", seller_message or message))
    if delivery.buyer_id:
        buyer = db.query(User).filter(User.id == delivery.buyer_id).first()
        if buyer:
            recipients.append((buyer, "/app/orders", buyer_message or message))

    for recipient, action_href, body_message in recipients:
        recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(recipient)
        create_notification(
            db,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_email=recipient_email,
            title=title,
            message=body_message,
            notification_type="delivery",
            severity=severity,
            action_href=action_href,
            metadata={"order_id": delivery.order_id, "delivery_id": delivery.id},
            send_email=bool(recipient_email),
            email_subject=title,
            email_body=f"Hello {recipient_name},\n\n{body_message}\n\nSokoLnk Delivery",
            background_tasks=background_tasks,
        )


def _linked_order_model(db: Session, sale: Sale | None) -> Order | None:
    if sale is None:
        return None
    if sale.order_id:
        order = db.query(Order).filter(Order.id == sale.order_id).first()
        if order:
            return order
    return db.query(Order).filter(Order.legacy_sale_id == sale.id).first()


def get_current_logistics_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> LogisticsUser:
    user = get_current_user(request, credentials, db)
    if not isinstance(user, LogisticsUser):
        raise HTTPException(status_code=403, detail="Not a logistics account")
    return user


@router.post("/register")
def register_logistics(
    payload: LogisticsRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    existing = _get_logistics_user(db, payload.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    pw_hash = hash_password(payload.password)
    
    user = LogisticsUser(
        name=payload.name.strip(),
        phone=payload.phone.strip(),
        email=(payload.email or "").strip().lower() or None,
        password_hash=pw_hash,
        account_type=payload.account_type,
        vehicle_type=payload.vehicle_type,
        plate_number=payload.plate_number,
        license_number=payload.license_number,
        base_area=payload.base_area,
        coverage_areas=payload.coverage_areas,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    metrics = LogisticsMetrics(logistics_id=user.id)
    db.add(metrics)
    db.commit()
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Welcome to SokoLnk delivery operations",
        message="Your logistics account is ready. Go online, accept deliveries, and manage order fulfillment.",
        notification_type="system",
        severity="success",
        action_href="/app/logistics",
        send_email=bool(recipient_email),
        email_subject="Welcome to SokoLnk delivery operations",
        email_body=f"Hello {recipient_name},\n\nYour logistics account has been created successfully.\n\nSokoLnk Team",
        background_tasks=background_tasks,
    )
    db.commit()
    
    token = create_token({
        "sub": user.id,
        "user_id": user.id,
        "phone": user.phone,
        "user_type": "logistics"
    })
    
    return {
        "message": "Logistics account created successfully",
        "token": token,
        "user": _serialize_logistics(user)
    }


@router.post("/login")
def login_logistics(
    payload: LogisticsLogin,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    phone = (payload.phone or "").strip() or None
    email = (payload.email or "").strip().lower() or None
    
    if not phone and not email:
        raise HTTPException(status_code=400, detail="Phone or email is required")
    
    user = _get_logistics_user(db, phone=phone, email=email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_and_upgrade_password(payload.password, user):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
    subject, body = build_login_email(
        recipient_name,
        "delivery",
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Delivery login detected",
        message="A login was recorded on your logistics account.",
        notification_type="security",
        severity="info",
        action_href="/app/logistics",
        send_email=bool(recipient_email),
        email_subject=subject,
        email_body=body,
        background_tasks=background_tasks,
    )
    db.commit()
    
    token = create_token({
        "sub": user.id,
        "user_id": user.id,
        "phone": user.phone,
        "user_type": "logistics"
    })
    
    return {
        "message": "Login successful",
        "token": token,
        "user": _serialize_logistics(user)
    }


@router.get("/me")
def get_my_logistics_profile(
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    metrics = db.query(LogisticsMetrics).filter(LogisticsMetrics.logistics_id == user.id).first()
    
    data = _serialize_logistics(user)
    data["metrics"] = {
        "rating": metrics.rating if metrics else 0,
        "total_deliveries": metrics.total_deliveries if metrics else 0,
        "success_rate": metrics.success_rate if metrics else 0,
        "cancel_rate": metrics.cancel_rate if metrics else 0
    } if metrics else {"rating": 0, "total_deliveries": 0, "success_rate": 0, "cancel_rate": 0}
    
    return data


@router.put("/me")
def update_my_logistics_profile(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user

    if payload.get("name") is not None:
        next_name = str(payload.get("name") or "").strip()
        if len(next_name) < 2:
            raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
        user.name = next_name

    if payload.get("email") is not None:
        next_email = str(payload.get("email") or "").strip().lower() or None
        if next_email and "@" not in next_email:
            raise HTTPException(status_code=400, detail="Invalid email")
        if next_email and next_email != (user.email or "").lower():
            existing = db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == next_email, LogisticsUser.id != user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
        user.email = next_email

    if payload.get("phone") is not None:
        next_phone = str(payload.get("phone") or "").strip()
        if not next_phone:
            raise HTTPException(status_code=400, detail="Phone is required")
        if next_phone != user.phone:
            existing = db.query(LogisticsUser).filter(LogisticsUser.phone == next_phone, LogisticsUser.id != user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Phone number already in use")
        user.phone = next_phone

    if payload.get("vehicle_type") is not None:
        user.vehicle_type = str(payload.get("vehicle_type") or "").strip() or None
    if payload.get("plate_number") is not None:
        user.plate_number = str(payload.get("plate_number") or "").strip() or None
    if payload.get("license_number") is not None:
        user.license_number = str(payload.get("license_number") or "").strip() or None
    if payload.get("base_area") is not None:
        user.base_area = str(payload.get("base_area") or "").strip() or None
    if payload.get("coverage_areas") is not None:
        user.coverage_areas = str(payload.get("coverage_areas") or "").strip() or None
    if payload.get("profile_photo") is not None:
        user.profile_photo = str(payload.get("profile_photo") or "").strip() or None

    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Logistics profile updated", "user": _serialize_logistics(user)}


@router.post("/verify")
def request_logistics_verification(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    user.verification_status = "pending"
    db.add(user)
    db.commit()
    return {
        "message": "Verification request submitted",
        "status": user.verification_status,
        "document_type": (payload.get("document_type") or "").strip() or None,
        "document_url": (payload.get("document_url") or "").strip() or None,
    }


@router.post("/upload-profile-photo")
async def upload_logistics_profile_photo(
    file: UploadFile = File(...),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
    db: Session = Depends(get_db),
):
    user = current_user
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"logistics-{user.id}-{uuid.uuid4().hex}{suffix}"
    destination = uploads_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    destination.write_bytes(content)
    return {"image_url": f"/uploads/{filename}"}


@router.post("/change-password")
def change_logistics_password(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    current_password = payload.get("current_password") or ""
    new_password = payload.get("new_password") or ""

    _validate_new_password(current_password, new_password, user.password_hash)

    user.password_hash = hash_password(new_password)
    db.add(user)
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Logistics password changed",
        message="Your delivery account password was changed successfully.",
        notification_type="security",
        severity="success",
        action_href="/app/logistics",
        send_email=bool(recipient_email),
        email_subject="SokoLnk logistics password changed",
        email_body=f"Hello {recipient_name},\n\nYour delivery account password was changed successfully.\n\nSokoLnk Security",
        background_tasks=background_tasks,
    )
    db.commit()

    return {"message": "Password updated"}


@router.put("/status")
def update_status(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    
    status = (payload.get("status") or "").strip().lower()
    if status not in ["online", "offline"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    user.status = status
    if status == "offline":
        user.availability = "unavailable"
    
    db.commit()
    
    return {
        "message": f"Status updated to {status}",
        "status": user.status
    }


@router.put("/availability")
def update_availability(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    
    availability = (payload.get("availability") or "").strip().lower()
    if availability not in ["available", "busy"]:
        raise HTTPException(status_code=400, detail="Invalid availability")
    
    user.availability = availability
    db.commit()
    
    return {
        "message": f"Availability updated to {availability}",
        "availability": user.availability
    }


@router.post("/deliveries")
def create_delivery_order(
    payload: DeliveryOrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    
    verification_code = secrets.token_hex(4).upper()
    
    delivery = DeliveryOrder(
        order_id=payload.order_id,
        seller_id=payload.seller_id,
        buyer_id=payload.buyer_id,
        logistics_id=user.id,
        pickup_location=payload.pickup_location,
        delivery_location=payload.delivery_location,
        pickup_phone=payload.pickup_phone,
        delivery_phone=payload.delivery_phone,
        price=payload.price,
        status="assigned",
        verification_code=verification_code,
    )
    pickup_coords = coords_for_location(payload.pickup_location)
    destination_coords = coords_for_location(payload.delivery_location)
    delivery.pickup_lat = pickup_coords[0]
    delivery.pickup_lng = pickup_coords[1]
    delivery.destination_lat = destination_coords[0]
    delivery.destination_lng = destination_coords[1]
    delivery.current_lat = pickup_coords[0]
    delivery.current_lng = pickup_coords[1]
    delivery.last_location_name = payload.pickup_location or "Pickup point"
    delivery.estimated_distance_km = round(haversine_km(pickup_coords, destination_coords), 1)
    delivery.tracking_updated_at = datetime.utcnow()
    db.add(delivery)
    db.flush()
    order = db.query(Sale).filter(Sale.id == payload.order_id).first() if payload.order_id else None
    linked_order = _linked_order_model(db, order)
    buyer = db.query(User).filter(User.id == payload.buyer_id).first() if payload.buyer_id else None
    seller = db.query(BusinessUser).filter(BusinessUser.id == payload.seller_id).first() if payload.seller_id else None
    ensure_order_thread(db, order=linked_order, sale=order, seller=seller, buyer=buyer, logistics=user)
    record_shipment_event(
        db,
        delivery_id=delivery.id,
        order_id=linked_order.id if linked_order else None,
        sale_id=order.id if order else None,
        status="assigned",
        actor=user,
        message="Delivery order created",
        lat=delivery.current_lat,
        lng=delivery.current_lng,
    )
    record_audit(
        db,
        actor=user,
        entity_type="delivery_order",
        entity_id=delivery.id,
        action="delivery.created",
        details={"sale_id": order.id if order else None, "order_id": linked_order.id if linked_order else None},
    )
    db.commit()
    db.refresh(delivery)
    
    user.availability = "busy"
    _notify_delivery_event(
        db,
        background_tasks,
        delivery,
        title=f"Delivery assigned for order #{delivery.order_id or delivery.id}",
        message=f"A logistics partner has been assigned. Pickup: {delivery.pickup_location or '-'}; destination: {delivery.delivery_location or '-'}.",
        severity="info",
    )
    db.commit()
    
    return {
        "message": "Delivery assigned",
        "delivery": {
            "id": delivery.id,
            "pickup_location": delivery.pickup_location,
            "delivery_location": delivery.delivery_location,
            "status": delivery.status,
            "verification_code": delivery.verification_code
        }
    }


@router.get("/deliveries")
def get_my_deliveries(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    
    query = db.query(DeliveryOrder).filter(DeliveryOrder.logistics_id == user.id)
    
    if status:
        query = query.filter(DeliveryOrder.status == status)
    
    deliveries = query.order_by(DeliveryOrder.created_at.desc()).limit(50).all()

    order_ids = [d.order_id for d in deliveries if d.order_id]
    orders = db.query(Sale).filter(Sale.id.in_(order_ids)).all() if order_ids else []
    order_map = {order.id: order for order in orders}

    buyer_ids = {
        d.buyer_id for d in deliveries if d.buyer_id
    } | {
        order.created_by for order in orders if order.created_by
    }
    buyers = db.query(User).filter(User.id.in_(buyer_ids)).all() if buyer_ids else []
    buyer_map = {buyer.id: buyer for buyer in buyers}

    payments = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.order_id.in_(order_ids))
        .order_by(PaymentTransaction.created_at.desc())
        .all()
        if order_ids
        else []
    )
    payment_map: dict[int, PaymentTransaction] = {}
    for payment in payments:
        if payment.order_id not in payment_map:
            payment_map[payment.order_id] = payment
    
    return {
        "deliveries": [
            {
                **{
                    "id": d.id,
                    "order_id": d.order_id,
                    "pickup_location": d.pickup_location,
                    "delivery_location": d.delivery_location,
                    "delivery_address": (order_map.get(d.order_id).delivery_address if d.order_id and order_map.get(d.order_id) else None) or d.delivery_location,
                    "pickup_phone": d.pickup_phone,
                    "delivery_phone": d.delivery_phone,
                    "customer_phone": (
                        (order_map.get(d.order_id).delivery_phone if d.order_id and order_map.get(d.order_id) else None)
                        or d.delivery_phone
                        or (buyer_map.get(d.buyer_id).phone if d.buyer_id and buyer_map.get(d.buyer_id) else None)
                    ),
                    "customer_phone_masked": _mask_phone(
                        (order_map.get(d.order_id).delivery_phone if d.order_id and order_map.get(d.order_id) else None)
                        or d.delivery_phone
                        or (buyer_map.get(d.buyer_id).phone if d.buyer_id and buyer_map.get(d.buyer_id) else None)
                    ),
                    "customer_name": (
                        buyer_map.get(d.buyer_id).name if d.buyer_id and buyer_map.get(d.buyer_id)
                        else (
                            buyer_map.get(order_map.get(d.order_id).created_by).name
                            if d.order_id and order_map.get(d.order_id) and order_map.get(d.order_id).created_by and buyer_map.get(order_map.get(d.order_id).created_by)
                            else None
                        )
                    ),
                    "status": d.status,
                    "price": d.price,
                    "payment_method": payment_map.get(d.order_id).payment_method if d.order_id and payment_map.get(d.order_id) else None,
                    "payment_status": payment_map.get(d.order_id).status if d.order_id and payment_map.get(d.order_id) else None,
                    "cod_amount": (
                        payment_map.get(d.order_id).amount
                        if d.order_id and payment_map.get(d.order_id)
                        else (
                            round(float(order_map.get(d.order_id).quantity or 0) * float(order_map.get(d.order_id).unit_price or 0), 2)
                            if d.order_id and order_map.get(d.order_id)
                            else None
                        )
                    ),
                    "delivery_notes": (
                        (order_map.get(d.order_id).delivery_notes if d.order_id and order_map.get(d.order_id) else None)
                        or d.special_instructions
                    ),
                    "verification_code": d.verification_code,
                    "special_instructions": d.special_instructions,
                    "estimated_distance_km": d.estimated_distance_km,
                    "pickup_lat": d.pickup_lat,
                    "pickup_lng": d.pickup_lng,
                    "destination_lat": d.destination_lat,
                    "destination_lng": d.destination_lng,
                    "current_lat": d.current_lat,
                    "current_lng": d.current_lng,
                    "last_location_name": d.last_location_name,
                    "tracking_updated_at": d.tracking_updated_at.isoformat() if d.tracking_updated_at else None,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "accepted_at": d.accepted_at.isoformat() if d.accepted_at else None,
                    "picked_at": d.picked_at.isoformat() if d.picked_at else None,
                    "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
                    "failed_at": d.failed_at.isoformat() if d.failed_at else None,
                    "failure_reason": d.failure_reason,
                    "proof_type": d.proof_type,
                    "proof_note": d.proof_note,
                    "cod_amount_received": d.cod_amount_received,
                }
            }
            for d in deliveries
        ]
    }


@router.put("/deliveries/{delivery_id}/status")
def update_delivery_status(
    delivery_id: int,
    payload: DeliveryStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    
    delivery = db.query(DeliveryOrder).filter(
        DeliveryOrder.id == delivery_id,
        DeliveryOrder.logistics_id == user.id
    ).first()
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    valid_transitions = {
        "assigned": {"picked_up", "failed"},
        "picked_up": {"in_transit", "failed"},
        "in_transit": {"delivered", "failed"},
    }
    
    if delivery.status not in valid_transitions or payload.status not in valid_transitions[delivery.status]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    if payload.status == "delivered":
        if delivery.verification_code and not payload.verification_code:
            raise HTTPException(status_code=400, detail="Verification code is required")
        if payload.verification_code and payload.verification_code != delivery.verification_code:
            raise HTTPException(status_code=400, detail="Invalid verification code")
    
    if payload.status == "failed" and not (payload.failure_reason or "").strip():
        raise HTTPException(status_code=400, detail="Failure reason is required")
    
    order = db.query(Sale).filter(Sale.id == delivery.order_id).first() if delivery.order_id else None
    linked_order = _linked_order_model(db, order)

    delivery.status = payload.status
    pickup_coords = (
        float(delivery.pickup_lat) if delivery.pickup_lat is not None else coords_for_location(delivery.pickup_location)[0],
        float(delivery.pickup_lng) if delivery.pickup_lng is not None else coords_for_location(delivery.pickup_location)[1],
    )
    destination_coords = (
        float(delivery.destination_lat) if delivery.destination_lat is not None else coords_for_location(delivery.delivery_location)[0],
        float(delivery.destination_lng) if delivery.destination_lng is not None else coords_for_location(delivery.delivery_location)[1],
    )
    
    if payload.status == "picked_up":
        if not delivery.accepted_at:
            delivery.accepted_at = datetime.utcnow()
        delivery.picked_at = datetime.utcnow()
        delivery.failed_at = None
        delivery.failure_reason = None
        current_coords = interpolate_coords(pickup_coords, destination_coords, 0.28)
        delivery.current_lat = current_coords[0]
        delivery.current_lng = current_coords[1]
        delivery.last_location_name = payload.current_location or "Package collected"
        if order and (order.status or "").strip().title() not in {"Cancelled", "Received"}:
            order.status = "Shipped"
            db.add(order)
            if linked_order:
                linked_order.status = "Shipped"
                linked_order.status_reason = "Picked up by logistics partner"
                db.add(linked_order)
                log_order_status(
                    db,
                    order_id=linked_order.id,
                    sale_id=order.id,
                    status="Shipped",
                    reason="Picked up by logistics partner",
                    actor=user,
                    metadata={"source": "logistics.status", "delivery_id": delivery.id},
                )
    elif payload.status == "in_transit":
        current_coords = interpolate_coords(pickup_coords, destination_coords, 0.7)
        delivery.current_lat = payload.current_lat if payload.current_lat is not None else current_coords[0]
        delivery.current_lng = payload.current_lng if payload.current_lng is not None else current_coords[1]
        delivery.last_location_name = payload.current_location or "In transit"
        if order and (order.status or "").strip().title() not in {"Cancelled", "Received"}:
            order.status = "Shipped"
            db.add(order)
            if linked_order:
                linked_order.status = "Shipped"
                linked_order.status_reason = "Shipment in transit"
                db.add(linked_order)
                log_order_status(
                    db,
                    order_id=linked_order.id,
                    sale_id=order.id,
                    status="Shipped",
                    reason="Shipment in transit",
                    actor=user,
                    metadata={"source": "logistics.status", "delivery_id": delivery.id},
                )
    elif payload.status == "delivered":
        delivery.delivered_at = datetime.utcnow()
        delivery.failed_at = None
        delivery.failure_reason = None
        user.availability = "available"
        delivery.current_lat = destination_coords[0]
        delivery.current_lng = destination_coords[1]
        delivery.last_location_name = payload.current_location or delivery.delivery_location or "Delivered"
        delivery.proof_type = (payload.proof_type or "").strip() or "otp"
        delivery.proof_note = (payload.proof_note or "").strip() or None
        delivery.cod_amount_received = payload.cod_amount_received
        if order and (order.status or "").strip().title() != "Cancelled":
            order.status = "Received"
            order.status_reason = "Delivered by logistics partner"
            db.add(order)
            if linked_order:
                linked_order.status = "Received"
                linked_order.status_reason = "Delivered by logistics partner"
                db.add(linked_order)
                update_reservation_status(db, order_id=linked_order.id, status="consumed")
                log_order_status(
                    db,
                    order_id=linked_order.id,
                    sale_id=order.id,
                    status="Received",
                    reason="Delivered by logistics partner",
                    actor=user,
                    metadata={"source": "logistics.status", "delivery_id": delivery.id},
                )
        
        metrics = db.query(LogisticsMetrics).filter(LogisticsMetrics.logistics_id == user.id).first()
        if metrics:
            metrics.total_deliveries += 1
            metrics.success_rate = (metrics.total_deliveries / (metrics.total_deliveries + metrics.cancel_rate)) * 100
    elif payload.status == "failed":
        delivery.failed_at = datetime.utcnow()
        delivery.failure_reason = (payload.failure_reason or "").strip()
        delivery.proof_type = (payload.proof_type or "").strip() or None
        delivery.proof_note = (payload.proof_note or "").strip() or None
        delivery.cod_amount_received = payload.cod_amount_received
        user.availability = "available"
        delivery.current_lat = payload.current_lat if payload.current_lat is not None else delivery.current_lat or pickup_coords[0]
        delivery.current_lng = payload.current_lng if payload.current_lng is not None else delivery.current_lng or pickup_coords[1]
        delivery.last_location_name = payload.current_location or "Delivery issue reported"
        if order and (order.status or "").strip().title() != "Cancelled":
            order.status = "Delivery Failed"
            order.status_reason = delivery.failure_reason
            db.add(order)
            if linked_order:
                linked_order.status = "Delivery Failed"
                linked_order.status_reason = delivery.failure_reason
                db.add(linked_order)
                log_order_status(
                    db,
                    order_id=linked_order.id,
                    sale_id=order.id,
                    status="Delivery Failed",
                    reason=delivery.failure_reason,
                    actor=user,
                    metadata={"source": "logistics.status", "delivery_id": delivery.id},
                )

        metrics = db.query(LogisticsMetrics).filter(LogisticsMetrics.logistics_id == user.id).first()
        if metrics:
            metrics.cancel_rate += 1
            total_attempts = metrics.total_deliveries + metrics.cancel_rate
            metrics.success_rate = (metrics.total_deliveries / total_attempts) * 100 if total_attempts else 0
    else:
        delivery.current_lat = payload.current_lat if payload.current_lat is not None else pickup_coords[0]
        delivery.current_lng = payload.current_lng if payload.current_lng is not None else pickup_coords[1]
        delivery.last_location_name = payload.current_location or delivery.pickup_location or "Awaiting pickup"

    delivery.tracking_updated_at = datetime.utcnow()
    record_shipment_event(
        db,
        delivery_id=delivery.id,
        order_id=linked_order.id if linked_order else None,
        sale_id=delivery.order_id,
        status=delivery.status,
        actor=user,
        message=delivery.last_location_name,
        lat=delivery.current_lat,
        lng=delivery.current_lng,
    )
    record_audit(
        db,
        actor=user,
        entity_type="delivery_order",
        entity_id=delivery.id,
        action=f"delivery.status.{delivery.status}",
        details={"sale_id": delivery.order_id, "failure_reason": delivery.failure_reason},
    )

    _notify_delivery_event(
        db,
        background_tasks,
        delivery,
        title=f"Delivery update for order #{delivery.order_id or delivery.id}",
        message=f"The delivery status is now {delivery.status}.",
        buyer_message=(
            "Delivery completed successfully. Thank you for using SokoLnk."
            if payload.status == "delivered"
            else (
                f"We could not complete your delivery: {delivery.failure_reason}."
                if payload.status == "failed"
                else f"Your delivery is now {delivery.status}."
            )
        ),
        seller_message=(
            "Delivery completed and order marked as delivered."
            if payload.status == "delivered"
            else (
                f"Delivery failed: {delivery.failure_reason}."
                if payload.status == "failed"
                else f"Order delivery is now {delivery.status}."
            )
        ),
        severity="success" if payload.status == "delivered" else ("warning" if payload.status == "failed" else "info"),
    )
    
    db.commit()
    
    return {
        "message": f"Delivery status updated to {payload.status}",
        "delivery": {
            "id": delivery.id,
            "status": delivery.status,
            "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            "failed_at": delivery.failed_at.isoformat() if delivery.failed_at else None,
            "failure_reason": delivery.failure_reason,
        }
    }


@router.get("/deliveries/{delivery_id}/tracking")
def get_delivery_tracking(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: LogisticsUser = Depends(get_current_logistics_user),
):
    user = current_user
    delivery = db.query(DeliveryOrder).filter(
        DeliveryOrder.id == delivery_id,
        DeliveryOrder.logistics_id == user.id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    order = db.query(Sale).filter(Sale.id == delivery.order_id).first() if delivery.order_id else None
    return build_tracking_payload(delivery, order=order, logistics=user)


@router.get("/available")
def get_available_logistics(
    area: str | None = None,
    vehicle_type: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(LogisticsUser).filter(
        LogisticsUser.is_active == True,
        LogisticsUser.status == "online",
        LogisticsUser.availability == "available",
        LogisticsUser.verification_status == "verified"
    )
    
    if area:
        query = query.filter(LogisticsUser.coverage_areas.ilike(f"%{area}%"))
    if vehicle_type:
        query = query.filter(LogisticsUser.vehicle_type == vehicle_type)
    
    logistics = query.order_by(LogisticsUser.id.desc()).limit(20).all()
    
    return {
        "items": [_serialize_logistics(l, include_email=False) for l in logistics]
    }


@router.get("/{logistics_id}")
def get_logistics_public_profile(
    logistics_id: int,
    db: Session = Depends(get_db)
):
    user = db.query(LogisticsUser).filter(LogisticsUser.id == logistics_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Logistics provider not found")
    
    metrics = db.query(LogisticsMetrics).filter(LogisticsMetrics.logistics_id == logistics_id).first()
    
    return {
        "id": user.id,
        "name": user.name,
        "account_type": user.account_type,
        "vehicle_type": user.vehicle_type,
        "plate_number": user.plate_number,
        "base_area": user.base_area,
        "coverage_areas": user.coverage_areas,
        "verification_status": user.verification_status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "metrics": {
            "rating": metrics.rating if metrics else 0,
            "total_deliveries": metrics.total_deliveries if metrics else 0,
         "success_rate": metrics.success_rate if metrics else 0
         } if metrics else {"rating": 0, "total_deliveries": 0, "success_rate": 0}
     }


@router.get("/track")
def public_track_delivery(
    order_id: Optional[str] = None,
    code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Public endpoint: customers can track delivery by order ID or verification code.
    No authentication required.
    """
    if not order_id and not code:
        raise HTTPException(status_code=400, detail="Provide order_id or verification code")
    
    query = db.query(DeliveryOrder)
    if order_id:
        try:
            oid = int(order_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid order ID format")
        query = query.filter(DeliveryOrder.order_id == oid)
    else:
        query = query.filter(DeliveryOrder.verification_code == code)
    
    delivery = query.first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Load related objects for tracking payload
    order = db.query(Sale).filter(Sale.id == delivery.order_id).first() if delivery.order_id else None
    logistics = db.query(LogisticsUser).filter(LogisticsUser.id == delivery.logistics_id).first() if delivery.logistics_id else None
    
    return build_tracking_payload(delivery, order, logistics)


@router.post("/deliveries/{delivery_id}/rating")
def rate_delivery(
    delivery_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Buyer can rate a delivered delivery experience (logistics partner).
    """
    try:
        rating_val = int(payload.get("rating", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="rating must be an integer")
    
    if rating_val < 1 or rating_val > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    delivery = db.query(DeliveryOrder).filter(DeliveryOrder.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Verify the current user is the buyer
    buyer_id = delivery.buyer_id
    if buyer_id is None and delivery.order_id:
        order = db.query(Sale).filter(Sale.id == delivery.order_id).first()
        buyer_id = order.created_by if order else None
    
    if buyer_id is None or current.id != buyer_id:
        raise HTTPException(status_code=403, detail="Only the buyer can rate this delivery")
    
    if delivery.status != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered orders can be rated")
    
    if delivery.rating is not None:
        raise HTTPException(status_code=400, detail="This delivery has already been rated")
    
    delivery.rating = rating_val
    delivery.rated_at = datetime.utcnow()
    delivery.rating_comment = payload.get("comment", "").strip() or None
    db.add(delivery)
    
    # Update logistics partner average rating
    if delivery.logistics_id:
        metrics = db.query(LogisticsMetrics).filter(LogisticsMetrics.logistics_id == delivery.logistics_id).first()
        if not metrics:
            metrics = LogisticsMetrics(logistics_id=delivery.logistics_id)
            db.add(metrics)
        # Recalculate average
        all_ratings = db.query(DeliveryOrder).filter(
            DeliveryOrder.logistics_id == delivery.logistics_id,
            DeliveryOrder.rating.isnot(None)
        ).all()
        ratings = [r.rating for r in all_ratings if r.rating]
        if ratings:
            metrics.rating = round(sum(ratings) / len(ratings), 2)
            metrics.total_deliveries = len(ratings)
        db.add(metrics)
    
    db.commit()
    db.refresh(delivery)
    return {"message": "Rating submitted", "delivery_id": delivery.id, "rating": delivery.rating}
