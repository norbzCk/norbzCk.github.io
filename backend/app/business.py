import secrets
import uuid
from datetime import datetime, timedelta, date
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Header, Request, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import (
    BusinessUser,
    BusinessMetrics,
    BusinessVerification,
    ConversationMessage,
    ConversationThread,
    Order,
    OrderItem,
    Product,
    Sale,
    DeliveryOrder,
    LogisticsUser,
    User,
    PaymentTransaction,
)
from backend.app.schemas import (
    BusinessRegister, BusinessLogin, BusinessProfile,
    BusinessUpdate, BusinessVerificationSubmit
)
from backend.app.auth import hash_password, verify_password, verify_and_upgrade_password, create_access_token as create_token, create_refresh_token, set_auth_cookies, decode_token, _normalize_phone, _phone_matches, get_current_user, security
from backend.app.notification_service import build_login_email, create_notification, list_notifications_for_subject, resolve_subject, serialize_notification
from backend.app.order_runtime import (
    ensure_order_thread,
    log_order_status,
    record_audit,
    record_shipment_event,
    update_reservation_status,
)
from backend.app.marketplace_intelligence import (
    compute_seller_badges,
    coords_for_location,
    haversine_km,
    refresh_business_metrics,
)

from backend.analysis import sales_analysis

router = APIRouter(prefix="/business", tags=["Business"])
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def get_current_business_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> BusinessUser:
    user = get_current_user(request, credentials, db)
    if not isinstance(user, BusinessUser):
        raise HTTPException(status_code=403, detail="Not a business account")
    return user


@router.get("/inventory/forecast")
def get_business_inventory_forecast(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    forecasts = sales_analysis.calculate_inventory_forecast(db, user.id)
    return {"items": forecasts}


@router.get("/market-share")
def get_market_share(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    """Get market share data for the current seller's category and region"""
    user = current_user
    
    # If user doesn't have category or region, return empty data
    if not user.category or not user.region:
        return {
            "category": user.category or "Unknown",
            "region": user.region or "Unknown",
            "seller_revenue": 0,
            "total_category_revenue": 0,
            "market_share_percent": 0,
            "rank": 0,
            "total_sellers": 0,
            "percentile": 0
        }
    
    # Calculate total revenue for this seller in their category and region
    seller_revenue = db.query(
        func.sum(Sale.quantity * Sale.unit_price)
    ).filter(
        Sale.seller_id == user.id,
        Sale.category == user.category,
        # Note: We don't have region directly on Sale, so we'll need to join with BusinessUser
        # For now, we'll filter by category only and note this limitation
    ).scalar() or 0
    
    # Calculate total revenue for all sellers in this category
    total_category_revenue = db.query(
        func.sum(Sale.quantity * Sale.unit_price)
    ).join(
        BusinessUser, Sale.seller_id == BusinessUser.id
    ).filter(
        BusinessUser.category == user.category,
        BusinessUser.region == user.region,
        BusinessUser.is_active == True
    ).scalar() or 0
    
    # Calculate market share percentage
    market_share_percent = 0
    if total_category_revenue > 0:
        market_share_percent = round((seller_revenue / total_category_revenue) * 100, 2)
    
    # Get rank among sellers in this category/region
    # We'll calculate revenue for each seller and rank them
    seller_revenues = db.query(
        BusinessUser.id,
        func.sum(Sale.quantity * Sale.unit_price).label("revenue")
    ).join(
        Sale, BusinessUser.id == Sale.seller_id
    ).filter(
        BusinessUser.category == user.category,
        BusinessUser.region == user.region,
        BusinessUser.is_active == True,
        Sale.date.isnot(None)
    ).group_by(
        BusinessUser.id
    ).order_by(
        func.sum(Sale.quantity * Sale.unit_price).desc()
    ).all()
    
    # Find the current seller's rank
    rank = 0
    total_sellers = len(seller_revenues)
    for i, (seller_id, revenue) in enumerate(seller_revenues):
        if seller_id == user.id:
            rank = i + 1
            break
    
    # Calculate percentile (what percentage of sellers they're better than)
    percentile = 0
    if total_sellers > 0:
        percentile = round(((total_sellers - rank) / total_sellers) * 100, 1)
    
    return {
        "category": user.category,
        "region": user.region,
        "seller_revenue": round(seller_revenue, 2),
        "total_category_revenue": round(total_category_revenue, 2),
        "market_share_percent": market_share_percent,
        "rank": rank,
        "total_sellers": total_sellers,
        "percentile": percentile
    }


def _load_business_analysis_modules():
    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
        return pd, np
    except Exception:
        return None, None


def _load_business_graph_modules():
    try:
        os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt  # type: ignore
        return plt
    except Exception:
        return None


def _business_graph_output_paths(user: BusinessUser, suffix: str) -> tuple[Path, str]:
    directory = Path(__file__).resolve().parents[1] / "uploads" / "graphs"
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"business-{user.id}-{suffix}.svg"
    return directory / filename, f"/uploads/graphs/{filename}"


def _write_business_revenue_time_graph(points: list[dict], user: BusinessUser) -> str | None:
    plt = _load_business_graph_modules()
    if plt is None:
        return None

    output_path, public_path = _business_graph_output_paths(user, "revenue-time")
    labels = [str(point["date"]) for point in points] or ["No data"]
    values = [float(point["revenue"]) for point in points] or [0.0]
    x_positions = list(range(len(values)))

    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(x_positions, values, color="#15803d", linewidth=3.2, marker="o", markersize=5.2)
    ax.fill_between(x_positions, values, color="#22c55e", alpha=0.18)
    ax.set_title("Revenue per time", fontsize=16, fontweight="bold", loc="left")
    ax.set_ylabel("Revenue (TZS)")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.grid(axis="y", color="#d1fae5", linewidth=1)
    ax.set_facecolor("#f7fff8")
    fig.patch.set_facecolor("#ffffff")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#86efac")
    ax.spines["bottom"].set_color("#86efac")
    ax.tick_params(axis="x", rotation=25, labelsize=9, colors="#166534")
    ax.tick_params(axis="y", labelsize=9, colors="#166534")
    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return public_path


def _write_business_revenue_product_graph(points: list[dict], user: BusinessUser) -> str | None:
    plt = _load_business_graph_modules()
    if plt is None:
        return None

    output_path, public_path = _business_graph_output_paths(user, "revenue-product")
    labels = [str(point["product"]) for point in points] or ["No data"]
    values = [float(point["revenue"]) for point in points] or [0.0]

    fig, ax = plt.subplots(figsize=(9.4, 4.8))
    bars = ax.barh(labels, values, color="#22c55e", edgecolor="#15803d", linewidth=1.1)
    ax.set_title("Revenue per product", fontsize=16, fontweight="bold", loc="left")
    ax.set_xlabel("Revenue (TZS)")
    ax.grid(axis="x", color="#d1fae5", linewidth=1)
    ax.set_facecolor("#f7fff8")
    fig.patch.set_facecolor("#ffffff")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#86efac")
    ax.spines["bottom"].set_color("#86efac")
    ax.tick_params(axis="x", labelsize=9, colors="#166534")
    ax.tick_params(axis="y", labelsize=9, colors="#166534")
    ax.bar_label(bars, labels=[f"TZS {value:,.0f}" for value in values], padding=6, fontsize=8, color="#166534")
    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return public_path


def _serialize_business(user: BusinessUser, include_email: bool = True) -> dict:
    return {
        "id": user.id,
        "business_name": user.business_name,
        "owner_name": user.owner_name,
        "phone": user.phone,
        "email": user.email if include_email else None,
        "business_type": user.business_type,
        "category": user.category,
        "description": user.description,
        "region": user.region,
        "area": user.area,
        "street": user.street,
        "shop_number": user.shop_number,
        "operating_hours": user.operating_hours,
        "shop_logo_url": user.shop_logo_url,
        "shop_images": user.shop_images,
        "profile_photo": user.profile_photo,
        "auto_confirm": user.auto_confirm,
        "verification_status": user.verification_status,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _validate_new_password(current_password: str, new_password: str, password_hash: str):
    if not verify_password(current_password, password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")


def _get_business_user(db: Session, phone: str = None, email: str = None):
    if phone:
        user = db.query(BusinessUser).filter(BusinessUser.phone == phone).first()
        if user:
            return user
        normalized_phone = _normalize_phone(phone)
        if normalized_phone:
            candidates = db.query(BusinessUser).filter(BusinessUser.phone.isnot(None)).all()
            for candidate in candidates:
                if _phone_matches(candidate.phone, normalized_phone):
                    return candidate
    if email:
        return db.query(BusinessUser).filter(func.lower(BusinessUser.email) == email.lower()).first()
    return None


@router.post("/register")
def register_business(
    payload: BusinessRegister,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    existing = _get_business_user(db, payload.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    pw_hash = hash_password(payload.password)
    
    user = BusinessUser(
        business_name=payload.business_name.strip(),
        owner_name=payload.owner_name.strip(),
        phone=payload.phone.strip(),
        email=(payload.email or "").strip().lower() or None,
        password_hash=pw_hash,
        business_type=payload.business_type,
        category=payload.category,
        description=payload.description,
        region=payload.region,
        area=payload.area,
        street=payload.street,
        shop_number=payload.shop_number,
        operating_hours=payload.operating_hours,
        shop_logo_url=payload.shop_logo_url,
        shop_images=payload.shop_images,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    metrics = BusinessMetrics(business_id=user.id)
    db.add(metrics)
    db.commit()
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Welcome to SokoLnk seller tools",
        message="Your business account is ready. Add products, track orders, and manage deliveries from your dashboard.",
        notification_type="system",
        severity="success",
        action_href="/app/seller",
        send_email=bool(recipient_email),
        email_subject="Welcome to SokoLnk seller tools",
        email_body=f"Hello {recipient_name},\n\nYour business account has been created successfully.\n\nSokoLnk Team",
        background_tasks=background_tasks,
    )
    db.commit()
    
    token = create_token({
        "sub": user.id,
        "user_id": user.id,
        "phone": user.phone,
        "role": user.role,
        "user_type": "business"
    })
    refresh_token = create_refresh_token(user.id, "business", db)
    set_auth_cookies(response, token, refresh_token)
    
    return {
        "message": "Business account created successfully",
        "access_token": token,
        "token_type": "bearer",
        "userType": "business",
        "user": _serialize_business(user)
    }


@router.post("/login")
def login_business(
    payload: BusinessLogin,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    phone = (payload.phone or "").strip() or None
    email = (payload.email or "").strip().lower() or None
    
    if not phone and not email:
        raise HTTPException(status_code=400, detail="Phone or email is required")
    
    user = _get_business_user(db, phone=phone, email=email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_and_upgrade_password(payload.password, user):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
    subject, body = build_login_email(
        recipient_name,
        "seller",
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Seller login detected",
        message="A login was recorded on your business account.",
        notification_type="security",
        severity="info",
        action_href="/app/seller",
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
        "role": user.role,
        "user_type": "business"
    })
    
    return {
        "message": "Login successful",
        "token": token,
        "user": _serialize_business(user)
    }


@router.get("/me")
def get_my_profile(
    current_user: BusinessUser = Depends(get_current_business_user),
):
    return _serialize_business(current_user)


@router.post("/upload-profile-photo")
async def upload_business_profile_photo(
    file: UploadFile = File(...),
    current_user: BusinessUser = Depends(get_current_business_user),
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
    filename = f"business-{user.id}-{uuid.uuid4().hex}{suffix}"
    destination = uploads_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    destination.write_bytes(content)
    return {"image_url": f"/uploads/{filename}"}


@router.put("/me")
def update_my_profile(
    payload: BusinessUpdate,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    
    if payload.business_name:
        user.business_name = payload.business_name.strip()
    if payload.owner_name:
        user.owner_name = payload.owner_name.strip()
    if payload.business_type:
        user.business_type = payload.business_type.strip()
    if payload.email is not None:
        user.email = payload.email.strip().lower() if payload.email else None
    if payload.phone is not None:
        next_phone = payload.phone.strip() if payload.phone else None
        if next_phone and next_phone != user.phone:
            existing = db.query(BusinessUser).filter(BusinessUser.phone == next_phone, BusinessUser.id != user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Phone number already in use")
        if next_phone:
            user.phone = next_phone
    if payload.category is not None:
        user.category = payload.category
    if payload.description is not None:
        user.description = payload.description
    if payload.region is not None:
        user.region = payload.region
    if payload.area is not None:
        user.area = payload.area
    if payload.street is not None:
        user.street = payload.street
    if payload.shop_number is not None:
        user.shop_number = payload.shop_number
    if payload.operating_hours is not None:
        user.operating_hours = payload.operating_hours
    if payload.shop_logo_url is not None:
        user.shop_logo_url = payload.shop_logo_url
    if payload.shop_images is not None:
        user.shop_images = payload.shop_images
    if payload.profile_photo is not None:
        user.profile_photo = payload.profile_photo
    if payload.auto_confirm is not None:
        user.auto_confirm = payload.auto_confirm
    
    db.commit()
    db.refresh(user)
    
    return {
        "message": "Profile updated",
        "user": _serialize_business(user)
    }


@router.post("/change-password")
def change_business_password(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
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
        title="Business password changed",
        message="Your seller account password was changed successfully.",
        notification_type="security",
        severity="success",
        action_href="/app/seller/profile",
        send_email=bool(recipient_email),
        email_subject="SokoLnk seller password changed",
        email_body=f"Hello {recipient_name},\n\nYour seller password was changed successfully.\n\nSokoLnk Security",
        background_tasks=background_tasks,
    )
    db.commit()

    return {"message": "Password updated"}


@router.post("/verify")
def submit_verification(
    payload: BusinessVerificationSubmit,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    
    existing = db.query(BusinessVerification).filter(
        BusinessVerification.business_id == user.id,
        BusinessVerification.status == "pending"
    ).first()
    
    if existing:
        existing.document_type = payload.document_type
        existing.document_url = payload.document_url
    else:
        verification = BusinessVerification(
            business_id=user.id,
            document_type=payload.document_type,
            document_url=payload.document_url,
            status="pending"
        )
        db.add(verification)
    
    user.verification_status = "pending"
    db.commit()
    
    return {
        "message": "Verification documents submitted",
        "status": "pending"
    }


def _seller_products_query(db: Session, user: BusinessUser):
    return db.query(Product).filter(Product.seller_id == user.id)


def _seller_sales_query(db: Session, user: BusinessUser):
    # Keep compatibility with older records where seller_id was not populated yet.
    return db.query(Sale).filter(
        or_(Sale.seller_id == user.id, Sale.provider_name == user.business_name)
    )


def _serialize_seller_order(
    order: Sale,
    *,
    buyer: User | None = None,
    payment: PaymentTransaction | None = None,
    delivery: DeliveryOrder | None = None,
    logistics: LogisticsUser | None = None,
) -> dict:
    priority = "normal"
    order_status = str(order.status or "Pending").strip().title()
    if order_status == "Pending" and order.delivery_method == "Express":
        priority = "urgent"
    elif order_status == "Pending" and order.date and (date.today() - order.date).days >= 2:
        priority = "delayed"
    elif order_status in {"Packed", "Ready For Shipping"} and order.delivery_method == "Express":
        priority = "urgent"

    return {
        "id": order.id,
        "order_date": order.date.isoformat() if order.date else None,
        "product": order.product,
        "category": order.category,
        "quantity": order.quantity,
        "unit_price": float(order.unit_price or 0),
        "total": float((order.quantity or 0) * (order.unit_price or 0)),
        "status": order.status or "Pending",
        "status_reason": order.status_reason,
        "provider_name": order.provider_name,
        "seller_id": order.seller_id,
        "customer_id": order.created_by,
        "created_by": order.created_by,
        "delivery_address": order.delivery_address,
        "delivery_phone": order.delivery_phone,
        "delivery_notes": order.delivery_notes,
        "delivery_method": order.delivery_method or "Standard",
        "product_id": order.product_id,
        "customer_name": buyer.name if buyer else None,
        "customer_email": buyer.email if buyer else None,
        "customer_phone": buyer.phone if buyer else None,
        "payment_status": payment.status if payment else "not_started",
        "payment_method": payment.payment_method if payment else None,
        "payment_transaction_id": payment.transaction_id if payment else None,
        "delivery_id": delivery.id if delivery else None,
        "delivery_status": delivery.status if delivery else None,
        "delivery_price": delivery.price if delivery else None,
        "logistics_id": logistics.id if logistics else (delivery.logistics_id if delivery else None),
        "logistics_name": logistics.name if logistics else None,
        "estimated_distance_km": delivery.estimated_distance_km if delivery else None,
        "priority": priority,
    }


def _serialize_seller_orders(db: Session, orders: list[Sale]) -> list[dict]:
    if not orders:
        return []

    buyer_ids = []
    for item in orders:
        try:
            if item.created_by is not None:
                buyer_ids.append(int(item.created_by))
        except (TypeError, ValueError):
            continue

    buyers = (
        db.query(User).filter(User.id.in_(buyer_ids)).all()
        if buyer_ids
        else []
    )
    buyer_map = {buyer.id: buyer for buyer in buyers}

    order_ids = [item.id for item in orders]
    payments = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.order_id.in_(order_ids))
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        .all()
    )
    payment_map: dict[int, PaymentTransaction] = {}
    for payment in payments:
        payment_map.setdefault(payment.order_id, payment)

    deliveries = (
        db.query(DeliveryOrder).filter(DeliveryOrder.order_id.in_(order_ids)).all()
        if order_ids
        else []
    )
    delivery_map = {delivery.order_id: delivery for delivery in deliveries}

    logistics_ids = [delivery.logistics_id for delivery in deliveries if delivery.logistics_id]
    logistics_users = (
        db.query(LogisticsUser).filter(LogisticsUser.id.in_(logistics_ids)).all()
        if logistics_ids
        else []
    )
    logistics_map = {logistics.id: logistics for logistics in logistics_users}

    serialized: list[dict] = []
    for order in orders:
        buyer = None
        try:
            buyer = buyer_map.get(int(order.created_by)) if order.created_by is not None else None
        except (TypeError, ValueError):
            buyer = None
        delivery = delivery_map.get(order.id)
        logistics = logistics_map.get(delivery.logistics_id) if delivery and delivery.logistics_id else None
        serialized.append(
            _serialize_seller_order(
                order,
                buyer=buyer,
                payment=payment_map.get(order.id),
                delivery=delivery,
                logistics=logistics,
            )
        )
    return serialized


def _ensure_order_owner(order: Sale, user: BusinessUser):
    if order.seller_id == user.id:
        return
    if (order.provider_name or "").strip().lower() == (user.business_name or "").strip().lower():
        return
    raise HTTPException(status_code=403, detail="Order does not belong to this business account")


def _find_order_buyer(db: Session, order: Sale) -> User | None:
    try:
        buyer_id = int(order.created_by) if order.created_by is not None else None
    except (TypeError, ValueError):
        buyer_id = None
    if not buyer_id:
        return None
    return db.query(User).filter(User.id == buyer_id).first()


def _linked_order_model(db: Session, sale: Sale) -> Order | None:
    if sale.order_id:
        order = db.query(Order).filter(Order.id == sale.order_id).first()
        if order:
            return order
    return db.query(Order).filter(Order.legacy_sale_id == sale.id).first()


def _linked_order_item_model(db: Session, sale: Sale) -> OrderItem | None:
    if sale.order_item_id:
        item = db.query(OrderItem).filter(OrderItem.id == sale.order_item_id).first()
        if item:
            return item
    return db.query(OrderItem).filter(OrderItem.legacy_sale_id == sale.id).first()


def _linked_order_items(db: Session, sale: Sale, linked_order: Order | None = None) -> list[OrderItem]:
    order = linked_order or _linked_order_model(db, sale)
    if order:
        return db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

    item = _linked_order_item_model(db, sale)
    return [item] if item else []


def _restore_order_inventory(db: Session, sale: Sale) -> Order | None:
    linked_order = _linked_order_model(db, sale)
    linked_items = _linked_order_items(db, sale, linked_order)

    if linked_items:
        product_ids = sorted({int(item.product_id) for item in linked_items if item.product_id is not None})
        products = (
            db.query(Product)
            .filter(Product.id.in_(product_ids))
            .with_for_update()
            .all()
            if product_ids
            else []
        )
        product_map = {product.id: product for product in products}
        for item in linked_items:
            if item.product_id is None:
                continue
            product = product_map.get(int(item.product_id))
            if not product:
                continue
            product.stock = int(product.stock or 0) + int(item.quantity or 0)
            db.add(product)
    elif sale.product_id:
        product = db.query(Product).filter(Product.id == sale.product_id).with_for_update().first()
        if product:
            product.stock = int(product.stock or 0) + int(sale.quantity or 0)
            db.add(product)

    if linked_order:
        update_reservation_status(db, order_id=linked_order.id, status="released")

    return linked_order


def _sync_business_order_state(
    db: Session,
    *,
    sale: Sale,
    status: str,
    reason: str | None,
    actor: BusinessUser | LogisticsUser | User | None,
    metadata: dict | None = None,
) -> None:
    linked_order = _linked_order_model(db, sale)
    linked_items = _linked_order_items(db, sale, linked_order)
    for linked_item in linked_items:
        linked_item.status = status
        db.add(linked_item)
    if linked_order:
        linked_order.status = status
        linked_order.status_reason = reason
        db.add(linked_order)
        log_order_status(
            db,
            order_id=linked_order.id,
            sale_id=sale.id,
            status=status,
            reason=reason,
            actor=actor,
            metadata=metadata,
        )
        record_audit(
            db,
            actor=actor,
            entity_type="order",
            entity_id=linked_order.id,
            action=f"order.status.{status.lower().replace(' ', '_')}",
            details={"sale_id": sale.id, "reason": reason, **(metadata or {})},
        )


def _notify_order_participants(
    db: Session,
    background_tasks: BackgroundTasks,
    *,
    order: Sale,
    seller: BusinessUser,
    buyer_title: str,
    buyer_message: str,
    seller_title: str,
    seller_message: str,
    notification_type: str = "order",
    severity: str = "info",
) -> None:
    buyer = _find_order_buyer(db, order)
    if buyer:
        buyer_type, buyer_id, buyer_email, buyer_name = resolve_subject(buyer)
        create_notification(
            db,
            recipient_type=buyer_type,
            recipient_id=buyer_id,
            recipient_email=buyer_email,
            title=buyer_title,
            message=buyer_message,
            notification_type=notification_type,
            severity=severity,
            action_href="/app/orders",
            metadata={"order_id": order.id},
            send_email=bool(buyer_email),
            email_subject=buyer_title,
            email_body=f"Hello {buyer_name},\n\n{buyer_message}\n\nSokoLnk Orders",
            background_tasks=background_tasks,
        )

    seller_type, seller_id, seller_email, seller_name = resolve_subject(seller)
    create_notification(
        db,
        recipient_type=seller_type,
        recipient_id=seller_id,
        recipient_email=seller_email,
        title=seller_title,
        message=seller_message,
        notification_type=notification_type,
        severity=severity,
        action_href="/app/orders",
        metadata={"order_id": order.id},
        send_email=bool(seller_email),
        email_subject=seller_title,
        email_body=f"Hello {seller_name},\n\n{seller_message}\n\nSokoLnk Orders",
        background_tasks=background_tasks,
    )


def _inventory_overview(db: Session, user: BusinessUser) -> dict:
    products = _seller_products_query(db, user).all()
    total_products = len(products)
    total_value = 0.0
    out_of_stock = 0
    low_stock = 0
    alerts = []

    for product in products:
        stock = int(product.stock or 0)
        total_value += float(stock * float(product.price or 0))
        if stock == 0:
            out_of_stock += 1
        elif stock < 5:
            low_stock += 1
            alerts.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "current_stock": stock,
                    "low_stock_threshold": 5,
                }
            )

    return {
        "total_products": total_products,
        "total_value": round(total_value, 2),
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
        "alerts": alerts[:12],
    }


@router.get("/dashboard/overview")
def business_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    sales_query = _seller_sales_query(db, user)
    all_sales = sales_query.all()
    today_sales = [item for item in all_sales if item.date == today]
    week_sales = [item for item in all_sales if item.date and item.date >= week_start]
    month_sales = [item for item in all_sales if item.date and item.date >= month_start]

    def revenue(rows: list[Sale]) -> float:
        return round(sum(float((row.quantity or 0) * (row.unit_price or 0)) for row in rows), 2)

    pending_orders = [item for item in all_sales if (item.status or "Pending") in {"Pending", "Confirmed", "Packed"}]
    completed_orders = [item for item in all_sales if (item.status or "") in {"Received", "Delivered"}]
    cancelled_orders = [item for item in all_sales if (item.status or "") == "Cancelled"]

    top_products = (
        db.query(
            Sale.product,
            func.sum(Sale.quantity).label("units"),
            func.sum(Sale.quantity * Sale.unit_price).label("revenue"),
        )
        .filter(or_(Sale.seller_id == user.id, Sale.provider_name == user.business_name))
        .group_by(Sale.product)
        .order_by(func.sum(Sale.quantity).desc())
        .limit(5)
        .all()
    )

    deliveries_query = db.query(DeliveryOrder).filter(DeliveryOrder.seller_id == user.id)
    ongoing_deliveries = deliveries_query.filter(DeliveryOrder.status.in_(["assigned", "picked_up", "in_transit"])).count()
    completed_deliveries = deliveries_query.filter(DeliveryOrder.status == "delivered").count()

    inventory = _inventory_overview(db, user)
    metrics = refresh_business_metrics(db, user.id)
    forecast = sales_analysis.calculate_inventory_forecast(db, user.id)[:6]
    db.commit()
    return {
        "business": _serialize_business(user),
        "performance_badges": compute_seller_badges(db, user, metrics),
        "summary": {
            "revenue_today": revenue(today_sales),
            "revenue_week": revenue(week_sales),
            "revenue_month": revenue(month_sales),
            "revenue_total": revenue(all_sales),
            "orders_total": len(all_sales),
            "orders_pending": len(pending_orders),
            "orders_completed": len(completed_orders),
            "orders_cancelled": len(cancelled_orders),
            "ongoing_deliveries": ongoing_deliveries,
            "completed_deliveries": completed_deliveries,
            "inventory_low_stock": inventory["low_stock"],
            "inventory_out_of_stock": inventory["out_of_stock"],
        },
        "top_products": [
            {
                "product": row[0] or "-",
                "units": int(row[1] or 0),
                "revenue": float(row[2] or 0),
            }
            for row in top_products
        ],
        "inventory": inventory,
        "inventory_forecast": forecast,
    }


@router.get("/inventory/overview")
def business_inventory_overview(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    return _inventory_overview(db, user)


@router.get("/analytics")
def business_analytics(
    range_days: int = 30,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    days = max(7, min(180, int(range_days or 30)))
    start_date = date.today() - timedelta(days=days - 1)

    base_query = _seller_sales_query(db, user).filter(Sale.date >= start_date)

    rows = (
        base_query
        .with_entities(Sale.date, func.sum(Sale.quantity * Sale.unit_price))
        .group_by(Sale.date)
        .order_by(Sale.date.asc())
        .all()
    )
    revenue_timeline = [{"date": row[0].isoformat(), "revenue": float(row[1] or 0)} for row in rows if row[0]]

    demand_rows = (
        base_query
        .with_entities(Sale.category, func.sum(Sale.quantity))
        .group_by(Sale.category)
        .order_by(func.sum(Sale.quantity).desc())
        .all()
    )
    demand = [{"category": row[0] or "Uncategorized", "units": int(row[1] or 0)} for row in demand_rows]

    product_rows = (
        base_query
        .with_entities(Sale.product, func.sum(Sale.quantity * Sale.unit_price).label("revenue"))
        .group_by(Sale.product)
        .order_by(func.sum(Sale.quantity * Sale.unit_price).desc())
        .limit(8)
        .all()
    )
    revenue_by_product = [{"product": row[0] or "Unspecified product", "revenue": float(row[1] or 0)} for row in product_rows]

    pd, np = _load_business_analysis_modules()
    if pd is not None and np is not None and revenue_timeline:
        revenue_frame = pd.DataFrame.from_records(revenue_timeline)
        revenue_frame["revenue"] = pd.to_numeric(revenue_frame["revenue"], errors="coerce").fillna(0.0)
        revenue_timeline = [
            {"date": str(row["date"]), "revenue": float(np.round(row["revenue"], 2))}
            for _, row in revenue_frame.iterrows()
        ]
    if pd is not None and np is not None and revenue_by_product:
        product_frame = pd.DataFrame.from_records(revenue_by_product)
        product_frame["revenue"] = pd.to_numeric(product_frame["revenue"], errors="coerce").fillna(0.0)
        revenue_by_product = [
            {"product": str(row["product"]), "revenue": float(np.round(row["revenue"], 2))}
            for _, row in product_frame.iterrows()
        ]

    return {
        "range_days": days,
        "revenue_timeline": revenue_timeline,
        "revenue_by_product": revenue_by_product,
        "demand_by_category": demand,
        "graphs": {
            "revenueOverTime": _write_business_revenue_time_graph(revenue_timeline, user),
            "revenueByProduct": _write_business_revenue_product_graph(revenue_by_product, user),
        },
    }


@router.get("/orders")
def get_business_orders(
    status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    query = _seller_sales_query(db, user)
    if status:
        query = query.filter(Sale.status == status)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Sale.product.ilike(term), Sale.category.ilike(term), Sale.delivery_address.ilike(term)))
    orders = query.order_by(Sale.date.desc(), Sale.id.desc()).limit(250).all()
    return {"items": _serialize_seller_orders(db, orders)}


@router.get("/logistics-options")
def get_business_logistics_options(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    # Ensure only authenticated business users can access assignment options.
    rows = (
        db.query(LogisticsUser)
        .filter(LogisticsUser.is_active == True)
        .order_by(LogisticsUser.name.asc(), LogisticsUser.id.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "vehicle_type": item.vehicle_type,
                "base_area": item.base_area,
                "status": item.status,
                "availability": item.availability,
                "verification_status": item.verification_status,
            }
            for item in rows
        ]
    }


@router.patch("/orders/{order_id}/decision")
def business_order_decision(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    order = db.query(Sale).filter(Sale.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _ensure_order_owner(order, user)

    decision = (payload.get("decision") or "").strip().lower()
    reason = (payload.get("reason") or "").strip() or None
    if decision not in {"accept", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be accept or reject")

    if decision == "accept":
        order.status = "Confirmed"
        order.status_reason = reason
    else:
        order.status = "Cancelled"
        order.status_reason = reason or "Rejected by seller"
        _restore_order_inventory(db, order)

    db.add(order)
    _sync_business_order_state(
        db,
        sale=order,
        status=order.status,
        reason=order.status_reason,
        actor=user,
        metadata={"source": "business.decision", "decision": decision},
    )
    _notify_order_participants(
        db,
        background_tasks,
        order=order,
        seller=user,
        buyer_title=f"Order #{order.id} {order.status}",
        buyer_message=(
            f"Your order for {order.product} was confirmed by {user.business_name}."
            if decision == "accept"
            else f"Your order for {order.product} was cancelled by {user.business_name}."
        ),
        seller_title=f"Order #{order.id} decision saved",
        seller_message=(
            f"You confirmed order #{order.id} for {order.product}."
            if decision == "accept"
            else f"You rejected order #{order.id} for {order.product}."
        ),
        severity="warning" if decision == "reject" else "success",
    )
    db.commit()
    db.refresh(order)
    return {"message": "Order decision recorded", "order": _serialize_seller_orders(db, [order])[0]}


@router.patch("/orders/{order_id}/status")
def business_update_order_status(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    order = db.query(Sale).filter(Sale.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _ensure_order_owner(order, user)

    target = (payload.get("status") or "").strip().title()
    reason = (payload.get("reason") or "").strip() or None
    valid = {
        "Pending": {"Confirmed", "Cancelled"},
        "Confirmed": {"Packed", "Cancelled"},
        "Packed": {"Ready For Shipping", "Cancelled"},
        "Ready For Shipping": {"Shipped", "Cancelled"},
        "Shipped": set(),
        "Delivery Failed": {"Ready For Shipping", "Cancelled"},
        "Received": set(),
        "Cancelled": set(),
    }
    current = (order.status or "Pending").strip().title()
    if target not in valid.get(current, set()):
        raise HTTPException(status_code=400, detail=f"Cannot move order from {current} to {target}")

    order.status = target
    order.status_reason = reason
    if target == "Cancelled":
        _restore_order_inventory(db, order)
    db.add(order)
    _sync_business_order_state(
        db,
        sale=order,
        status=target,
        reason=reason,
        actor=user,
        metadata={"source": "business.status.patch"},
    )
    _notify_order_participants(
        db,
        background_tasks,
        order=order,
        seller=user,
        buyer_title=f"Order #{order.id} moved to {target}",
        buyer_message=f"Your order for {order.product} is now {target}.",
        seller_title=f"Order #{order.id} status updated",
        seller_message=f"You moved order #{order.id} to {target}.",
        severity="warning" if target == "Cancelled" else "info",
    )
    db.commit()
    db.refresh(order)
    return {"message": "Order status updated", "order": _serialize_seller_orders(db, [order])[0]}


@router.post("/orders/{order_id}/assign-delivery")
def business_assign_delivery(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    order = db.query(Sale).filter(Sale.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _ensure_order_owner(order, user)

    if (order.status or "").strip().title() in {"Cancelled", "Received"}:
        raise HTTPException(status_code=400, detail="Delivery cannot be assigned to a finalized order.")

    paid = db.query(PaymentTransaction).filter(
        PaymentTransaction.order_id == order.id,
        PaymentTransaction.status == "completed"
    ).first()
    if not paid:
        raise HTTPException(status_code=400, detail="Delivery can only be assigned after payment is completed.")

    logistics_id = payload.get("logistics_id")
    if logistics_id:
        logistics = (
            db.query(LogisticsUser)
            .filter(LogisticsUser.id == int(logistics_id), LogisticsUser.is_active == True)
            .with_for_update()
            .first()
        )
    else:
        logistics = (
            db.query(LogisticsUser)
            .filter(
                LogisticsUser.is_active == True,
                LogisticsUser.status == "online",
                LogisticsUser.availability == "available",
            )
            .with_for_update(skip_locked=True)
            .order_by(LogisticsUser.id.asc())
            .first()
        )
    if not logistics:
        raise HTTPException(status_code=404, detail="No logistics partner available")

    if logistics.status != "online":
        raise HTTPException(status_code=400, detail="Selected logistics partner is offline")

    selected_seller = user
    selected_seller_id = payload.get("seller_id")
    if selected_seller_id:
        try:
            parsed_seller_id = int(selected_seller_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid seller_id")
        candidate = (
            db.query(BusinessUser)
            .filter(BusinessUser.id == parsed_seller_id, BusinessUser.is_active == True)
            .first()
        )
        if candidate:
            selected_seller = candidate

    delivery = db.query(DeliveryOrder).filter(DeliveryOrder.order_id == order.id).with_for_update().first()
    previous_logistics = None
    if delivery and delivery.logistics_id and delivery.logistics_id != logistics.id:
        previous_logistics = (
            db.query(LogisticsUser)
            .filter(LogisticsUser.id == delivery.logistics_id)
            .with_for_update()
            .first()
        )
    if delivery and logistics.availability == "busy" and delivery.logistics_id != logistics.id:
        raise HTTPException(status_code=400, detail="Selected logistics partner is already busy")
    if not delivery:
        delivery = DeliveryOrder(
            order_id=order.id,
            seller_id=selected_seller.id,
            buyer_id=order.created_by,
            logistics_id=logistics.id,
            pickup_location=payload.get("pickup_location") or f"{selected_seller.area or ''} {selected_seller.street or ''}".strip() or "Seller location",
            delivery_location=payload.get("delivery_location") or order.delivery_address,
            pickup_phone=payload.get("pickup_phone") or selected_seller.phone,
            delivery_phone=payload.get("delivery_phone") or order.delivery_phone,
            status="assigned",
            price=float(payload.get("price") or 0) or None,
            special_instructions=(payload.get("special_instructions") or "").strip() or None,
            verification_code=secrets.token_hex(4).upper(),
        )
        pickup_coords = coords_for_location(delivery.pickup_location, selected_seller.area, selected_seller.region)
        destination_coords = coords_for_location(delivery.delivery_location, order.delivery_address)
        delivery.pickup_lat = pickup_coords[0]
        delivery.pickup_lng = pickup_coords[1]
        delivery.destination_lat = destination_coords[0]
        delivery.destination_lng = destination_coords[1]
        delivery.current_lat = pickup_coords[0]
        delivery.current_lng = pickup_coords[1]
        delivery.last_location_name = delivery.pickup_location or "Seller location"
        delivery.estimated_distance_km = round(haversine_km(pickup_coords, destination_coords), 1)
        delivery.tracking_updated_at = datetime.utcnow()
        db.add(delivery)
    else:
        delivery.seller_id = selected_seller.id
        delivery.logistics_id = logistics.id
        delivery.status = "assigned"
        delivery.special_instructions = (payload.get("special_instructions") or delivery.special_instructions or "").strip() or None
        if payload.get("pickup_location"):
            delivery.pickup_location = payload.get("pickup_location")
        elif not delivery.pickup_location:
            delivery.pickup_location = f"{selected_seller.area or ''} {selected_seller.street or ''}".strip() or "Seller location"
        if payload.get("pickup_phone"):
            delivery.pickup_phone = payload.get("pickup_phone")
        elif not delivery.pickup_phone:
            delivery.pickup_phone = selected_seller.phone
        if payload.get("delivery_location"):
            delivery.delivery_location = payload.get("delivery_location")
        if payload.get("price") is not None:
            delivery.price = float(payload.get("price") or 0) or None
        pickup_coords = coords_for_location(delivery.pickup_location, selected_seller.area, selected_seller.region)
        destination_coords = coords_for_location(delivery.delivery_location, order.delivery_address)
        delivery.pickup_lat = pickup_coords[0]
        delivery.pickup_lng = pickup_coords[1]
        delivery.destination_lat = destination_coords[0]
        delivery.destination_lng = destination_coords[1]
        if delivery.current_lat is None or delivery.current_lng is None:
            delivery.current_lat = pickup_coords[0]
            delivery.current_lng = pickup_coords[1]
        delivery.last_location_name = delivery.last_location_name or delivery.pickup_location or "Seller location"
        delivery.estimated_distance_km = round(haversine_km(pickup_coords, destination_coords), 1)
        delivery.tracking_updated_at = datetime.utcnow()

    order.status = "Ready For Shipping"
    logistics.availability = "busy"
    if previous_logistics and previous_logistics.id != logistics.id:
        previous_logistics.availability = "available"
        db.add(previous_logistics)

    db.add(order)
    db.add(logistics)
    db.flush()
    _sync_business_order_state(
        db,
        sale=order,
        status="Ready For Shipping",
        reason="Delivery assigned",
        actor=user,
        metadata={"source": "business.assign_delivery", "logistics_id": logistics.id},
    )
    linked_order = _linked_order_model(db, order)
    buyer = _find_order_buyer(db, order)
    ensure_order_thread(
        db,
        order=linked_order,
        sale=order,
        seller=selected_seller,
        buyer=buyer,
        logistics=logistics,
    )
    record_shipment_event(
        db,
        delivery_id=delivery.id,
        order_id=linked_order.id if linked_order else None,
        sale_id=order.id,
        status="assigned",
        actor=user,
        message=f"Delivery assigned to {logistics.name}",
        lat=delivery.current_lat,
        lng=delivery.current_lng,
    )
    _notify_order_participants(
        db,
        background_tasks,
        order=order,
        seller=selected_seller,
        buyer_title=f"Delivery assigned for order #{order.id}",
        buyer_message=f"Your order for {order.product} now has a delivery partner assigned.",
        seller_title=f"Delivery assigned for order #{order.id}",
        seller_message=f"Delivery has been assigned to {logistics.name} for order #{order.id}.",
        notification_type="delivery",
        severity="info",
    )
    logistics_type, logistics_recipient_id, logistics_email, logistics_name = resolve_subject(logistics)
    create_notification(
        db,
        recipient_type=logistics_type,
        recipient_id=logistics_recipient_id,
        recipient_email=logistics_email,
        title=f"New delivery assignment: order #{order.id}",
        message=f"Pickup {order.product} from {selected_seller.business_name} and deliver to {order.delivery_address or 'customer address'}.",
        notification_type="delivery",
        severity="info",
        action_href="/app/logistics",
        metadata={"order_id": order.id},
        send_email=bool(logistics_email),
        email_subject=f"New SokoLnk delivery assignment #{order.id}",
        email_body=f"Hello {logistics_name},\n\nA new delivery has been assigned to you for order #{order.id}.\n\nSokoLnk Logistics",
        background_tasks=background_tasks,
    )
    db.commit()
    db.refresh(delivery)
    return {
        "message": "Delivery assigned",
        "delivery": {
            "id": delivery.id,
            "order_id": delivery.order_id,
            "logistics_id": delivery.logistics_id,
            "status": delivery.status,
            "verification_code": delivery.verification_code,
        },
    }


@router.get("/deliveries")
def business_deliveries(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    query = db.query(DeliveryOrder).filter(DeliveryOrder.seller_id == user.id)
    if status:
        query = query.filter(DeliveryOrder.status == status)
    items = query.order_by(DeliveryOrder.created_at.desc()).limit(200).all()
    return {
        "items": [
            {
                "id": item.id,
                "order_id": item.order_id,
                "seller_id": item.seller_id,
                "buyer_id": item.buyer_id,
                "logistics_id": item.logistics_id,
                "pickup_location": item.pickup_location,
                "delivery_location": item.delivery_location,
                "status": item.status,
                "price": item.price,
                "special_instructions": item.special_instructions,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "picked_at": item.picked_at.isoformat() if item.picked_at else None,
                "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
            }
            for item in items
        ]
    }


@router.patch("/deliveries/{delivery_id}/instructions")
def business_update_delivery_instructions(
    delivery_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    delivery = db.query(DeliveryOrder).filter(DeliveryOrder.id == delivery_id, DeliveryOrder.seller_id == user.id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    delivery.special_instructions = (payload.get("special_instructions") or "").strip() or None
    if payload.get("delivery_location"):
        delivery.delivery_location = payload.get("delivery_location")
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return {"message": "Delivery instructions updated"}


@router.get("/notifications")
def business_notifications(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    recipient_type, recipient_id, _, _ = resolve_subject(user)
    stored_items = list_notifications_for_subject(db, recipient_type, recipient_id, limit=15)
    low_stock = _inventory_overview(db, user)["alerts"][:5]
    pending_orders = (
        _seller_sales_query(db, user)
        .filter(Sale.status.in_(["Pending", "Confirmed"]))
        .order_by(Sale.date.desc(), Sale.id.desc())
        .limit(8)
        .all()
    )
    in_transit = (
        db.query(DeliveryOrder)
        .filter(DeliveryOrder.seller_id == user.id, DeliveryOrder.status.in_(["assigned", "picked_up", "in_transit"]))
        .order_by(DeliveryOrder.created_at.desc())
        .limit(8)
        .all()
    )

    alerts = [serialize_notification(item) for item in stored_items]
    for item in pending_orders:
        alerts.append(
            {
                "id": f"order-{item.id}",
                "type": "order",
                "title": f"Order #{item.id} needs attention",
                "message": f"{item.product} x{item.quantity} is currently {item.status or 'Pending'}",
                "created_at": item.date.isoformat() if item.date else None,
            }
        )
    for item in in_transit:
        alerts.append(
            {
                "id": f"delivery-{item.id}",
                "type": "delivery",
                "title": f"Delivery #{item.id} in progress",
                "message": f"Status: {item.status}. Destination: {item.delivery_location or '-'}",
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    for item in low_stock:
        alerts.append(
            {
                "id": f"inventory-{item['product_id']}",
                "type": "inventory",
                "title": f"Low stock: {item['product_name']}",
                "message": f"Only {item['current_stock']} units left",
                "created_at": None,
            }
        )
    return {"items": alerts[:20]}


@router.post("/products/bulk")
def business_bulk_create_products(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="items must be a non-empty list")

    created = []
    skipped = []
    for idx, item in enumerate(items):
        name = str(item.get("name") or "").strip()
        category = str(item.get("category") or "").strip()
        description = str(item.get("description") or "").strip()
        try:
            price = float(item.get("price") or 0)
            stock = int(item.get("stock") or 0)
        except (TypeError, ValueError):
            skipped.append({"index": idx, "reason": "price/stock must be numeric"})
            continue

        if not name or not category or price <= 0 or stock < 0:
            skipped.append({"index": idx, "reason": "invalid required fields"})
            continue

        product = Product(
            name=name,
            category=category,
            price=price,
            stock=stock,
            description=description,
            image_url=str(item.get("image_url") or "").strip() or None,
            seller_id=user.id,
            is_active=True,
        )
        db.add(product)
        created.append(product)

    db.commit()
    return {
        "message": "Bulk product upload completed",
        "created_count": len(created),
        "skipped": skipped,
    }


@router.get("/communication/feed")
def business_communication_feed(
    db: Session = Depends(get_db),
    current_user: BusinessUser = Depends(get_current_business_user),
):
    user = current_user
    orders = _seller_sales_query(db, user).order_by(Sale.id.desc()).limit(30).all()
    order_ids = [item.id for item in orders]
    threads = (
        db.query(ConversationThread)
        .filter(ConversationThread.sale_id.in_(order_ids))
        .all()
        if order_ids
        else []
    )
    thread_map = {thread.sale_id: thread for thread in threads if thread.sale_id is not None}
    thread_ids = [thread.id for thread in threads]
    latest_messages = {}
    if thread_ids:
        rows = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.thread_id.in_(thread_ids))
            .order_by(ConversationMessage.thread_id.asc(), ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .all()
        )
        for row in rows:
            latest_messages.setdefault(row.thread_id, row)
    threads = []
    for order in orders:
        thread = thread_map.get(order.id)
        latest_message = latest_messages.get(thread.id) if thread else None
        threads.append(
            {
                "thread_id": str(thread.id) if thread else f"order-{order.id}",
                "order_id": order.id,
                "customer_id": order.created_by,
                "subject": f"Order #{order.id} - {order.product}",
                "latest_message": latest_message.text if latest_message else f"Current status: {order.status or 'Pending'}",
                "delivery_address": order.delivery_address,
                "last_message_at": latest_message.created_at.isoformat() if latest_message and latest_message.created_at else None,
            }
        )
    return {"items": threads}


@router.get("/{business_id}")
def get_business_public_profile(
    business_id: int,
    db: Session = Depends(get_db)
):
    user = db.query(BusinessUser).filter(BusinessUser.id == business_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")
    
    metrics = db.query(BusinessMetrics).filter(BusinessMetrics.business_id == business_id).first()
    
    return {
        "id": user.id,
        "business_name": user.business_name,
        "owner_name": user.owner_name,
        "business_type": user.business_type,
        "category": user.category,
        "description": user.description,
        "region": user.region,
        "area": user.area,
        "street": user.street,
        "shop_number": user.shop_number,
        "operating_hours": user.operating_hours,
        "shop_logo_url": user.shop_logo_url,
        "shop_images": user.shop_images,
        "profile_photo": user.profile_photo,
        "auto_confirm": user.auto_confirm,
        "verification_status": user.verification_status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "metrics": {
            "rating": metrics.rating if metrics else 0,
            "total_sales": metrics.total_sales if metrics else 0,
            "reviews_count": metrics.reviews_count if metrics else 0
        } if metrics else {"rating": 0, "total_sales": 0, "reviews_count": 0}
    }


@router.get("/")
def list_businesses(
    category: str | None = None,
    area: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(BusinessUser).filter(BusinessUser.is_active == True, BusinessUser.role == "seller")
    
    if category:
        query = query.filter(BusinessUser.category == category)
    if area:
        query = query.filter(BusinessUser.area == area)
    
    total = query.count()
    businesses = query.offset(offset).limit(limit).all()
    
    return {
        "items": [_serialize_business(b, include_email=False) for b in businesses],
        "total": total,
        "limit": limit,
        "offset": offset
    }
