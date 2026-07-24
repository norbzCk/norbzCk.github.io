from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_roles
from backend.app.marketplace_intelligence import build_tracking_payload, refresh_business_metrics
from backend.app.notification_service import create_notification, resolve_subject
from backend.app.order_runtime import (
    ensure_order_thread,
    log_order_status,
    record_audit,
    reserve_inventory,
    update_reservation_status,
)
from backend.database import get_db
from backend.models import (
    BusinessUser,
    DeliveryOrder,
    LogisticsUser,
    Order,
    OrderItem,
    PaymentTransaction,
    Product,
    Provider,
    Sale,
    User,
)

router = APIRouter(tags=["Sales", "Orders"])

ORDER_STATUSES = {
    "Pending",
    "Confirmed",
    "Packed",
    "Ready For Shipping",
    "Shipped",
    "Delivery Failed",
    "Received",
    "Cancelled",
}
ADMIN_TRANSITIONS = {
    "Pending": {"Confirmed", "Cancelled"},
    "Confirmed": {"Packed", "Cancelled"},
    "Packed": {"Ready For Shipping", "Cancelled"},
    "Ready For Shipping": {"Shipped", "Cancelled"},
    "Shipped": set(),
    "Delivery Failed": set(),
    "Received": set(),
    "Cancelled": set(),
}
CANCELLABLE_BY_CUSTOMER = {"Pending", "Confirmed"}
DELIVERY_METHODS = {"Standard", "Express", "Pickup"}


def _normalized_delivery_method(value: str | None) -> str:
    method = (value or "").strip().title()
    if method in DELIVERY_METHODS:
        return method
    return "Standard"


def _sales_query_for_current_user(db: Session, current: User):
    query = db.query(Sale)
    if current.role == "user":
        # Keep compatibility with legacy databases where created_by is varchar.
        query = query.filter(cast(Sale.created_by, String) == str(current.id))
    elif current.role == "seller":
        business_name = getattr(current, "business_name", None)
        query = query.filter(
            (Sale.seller_id == current.id) |
            ((Sale.seller_id.is_(None)) & (Sale.provider_name == business_name))
        )
    return query


def _normalized_status(raw_status: str | None) -> str:
    status = (raw_status or "").strip().title()
    if status == "Delivered":
        # Keep compatibility with old records.
        return "Received"
    if status in ORDER_STATUSES:
        return status
    return "Received"


def _requested_status(raw_status: str | None) -> str | None:
    status = (raw_status or "").strip().title()
    if status == "Delivered":
        return "Received"
    if status in ORDER_STATUSES:
        return status
    return None


def _linked_order(db: Session, sale: Sale) -> Order | None:
    if sale.order_id:
        order = db.query(Order).filter(Order.id == sale.order_id).first()
        if order:
            return order
    return db.query(Order).filter(Order.legacy_sale_id == sale.id).first()


def _linked_order_item(db: Session, sale: Sale) -> OrderItem | None:
    if sale.order_item_id:
        item = db.query(OrderItem).filter(OrderItem.id == sale.order_item_id).first()
        if item:
            return item
    return db.query(OrderItem).filter(OrderItem.legacy_sale_id == sale.id).first()


def _linked_order_items(db: Session, sale: Sale, linked_order: Order | None = None) -> list[OrderItem]:
    order = linked_order or _linked_order(db, sale)
    if order:
        return db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

    item = _linked_order_item(db, sale)
    return [item] if item else []


def _restore_sale_inventory(db: Session, sale: Sale) -> Order | None:
    linked_order = _linked_order(db, sale)
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


def _sync_order_state(
    db: Session,
    sale: Sale,
    *,
    status: str,
    reason: str | None,
    actor: User | BusinessUser | LogisticsUser | None,
    metadata: dict | None = None,
) -> None:
    linked_order = _linked_order(db, sale)
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


def _serialize_order(s: Sale) -> dict:
    status = _normalized_status(s.status)
    return {
        "id": s.id,
        "order_date": s.date.isoformat() if s.date else None,
        "product": s.product,
        "category": s.category,
        "provider_id": s.provider_id,
        "provider_name": s.provider_name,
        "seller_id": s.seller_id,
        "quantity": s.quantity,
        "unit_price": s.unit_price,
        "total": (s.quantity or 0) * (s.unit_price or 0),
        "status": status,
        "status_reason": s.status_reason,
        "rating": s.rating,
        "created_by": s.created_by,
        "product_id": s.product_id,
        "delivery_address": s.delivery_address,
        "delivery_phone": s.delivery_phone,
        "delivery_notes": s.delivery_notes,
        "delivery_method": _normalized_delivery_method(s.delivery_method),
    }


def _normalized_checkout_items(payload: dict) -> list[dict[str, int]]:
    raw_items = payload.get("items")
    entries = raw_items if isinstance(raw_items, list) and raw_items else [
        {
            "product_id": payload.get("product_id"),
            "quantity": payload.get("quantity", 0),
        }
    ]

    merged: dict[int, int] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Each checkout item must be an object")

        product_id = item.get("product_id")
        quantity = item.get("quantity", 0)
        try:
            parsed_product_id = int(product_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="product_id must be an integer")

        try:
            parsed_quantity = int(quantity)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="quantity must be an integer")

        if parsed_quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

        merged[parsed_product_id] = merged.get(parsed_product_id, 0) + parsed_quantity

    if not merged:
        raise HTTPException(status_code=400, detail="At least one checkout item is required")

    return [
        {"product_id": product_id, "quantity": quantity}
        for product_id, quantity in sorted(merged.items())
    ]


def _apply_product_rating_stats(db: Session, product_id: int | None) -> None:
    if not product_id:
        return
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return

    avg_rating, rating_count = (
        db.query(func.avg(Sale.rating), func.count(Sale.id))
        .filter(
            Sale.product_id == product_id,
            Sale.status.in_(["Received", "Delivered"]),
            Sale.rating.isnot(None),
        )
        .first()
    )
    product.rating_avg = float(avg_rating or 0)
    product.rating_count = int(rating_count or 0)
    db.add(product)


def _ensure_owner_or_admin(order: Sale, current: User) -> None:
    if current.role == "user":
        if str(order.created_by) != str(current.id):
            raise HTTPException(status_code=403, detail="You can only access your own orders")
    elif current.role == "seller":
        business_name = getattr(current, "business_name", None)
        owns = str(order.seller_id or "") == str(current.id) or (
            order.seller_id is None and business_name and (order.provider_name or "") == business_name
        )
        if not owns:
            raise HTTPException(status_code=403, detail="You can only access your own sales orders")


def _find_buyer_and_seller(db: Session, order: Sale) -> tuple[User | None, BusinessUser | None]:
    buyer = None
    seller = None

    if order.created_by is not None:
        try:
            buyer = db.query(User).filter(User.id == int(order.created_by)).first()
        except (TypeError, ValueError):
            buyer = None

    if order.seller_id is not None:
        seller = db.query(BusinessUser).filter(BusinessUser.id == order.seller_id).first()
    elif order.provider_name:
        seller = db.query(BusinessUser).filter(BusinessUser.business_name == order.provider_name).first()

    return buyer, seller


def _notify_order_event(
    db: Session,
    background_tasks: BackgroundTasks,
    order: Sale,
    *,
    buyer_title: str,
    buyer_message: str,
    seller_title: str | None = None,
    seller_message: str | None = None,
    notification_type: str = "order",
    severity: str = "info",
) -> None:
    buyer, seller = _find_buyer_and_seller(db, order)
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
            background_tasks=background_tasks,
            send_email=bool(buyer_email),
            email_subject=buyer_title,
            email_body=f"Hello {buyer_name},\n\n{buyer_message}\n\nSokoLnk Orders",
        )

    if seller:
        seller_type, seller_id, seller_email, seller_name = resolve_subject(seller)
        create_notification(
            db,
            recipient_type=seller_type,
            recipient_id=seller_id,
            recipient_email=seller_email,
            title=seller_title or buyer_title,
            message=seller_message or buyer_message,
            notification_type=notification_type,
            severity=severity,
            action_href="/app/orders",
            metadata={"order_id": order.id},
            background_tasks=background_tasks,
            send_email=bool(seller_email),
            email_subject=seller_title or buyer_title,
            email_body=f"Hello {seller_name},\n\n{seller_message or buyer_message}\n\nSokoLnk Orders",
        )


@router.get("/sales/")
def get_sales(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("super_admin", "owner")),
):
    query = _sales_query_for_current_user(db, current)
    sales = query.order_by(Sale.date.desc(), Sale.id.desc()).all()
    return [
        {
            "id": s.id,
            "date": s.date.isoformat() if s.date else None,
            "product": s.product,
            "category": s.category,
            "quantity": s.quantity,
            "unit_price": s.unit_price,
            "revenue": (s.quantity or 0) * (s.unit_price or 0),
            "status": _normalized_status(s.status),
            "created_by": s.created_by,
        }
        for s in sales
    ]


@router.post("/sales/", status_code=201)
def create_sale(
    payload: dict,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("super_admin", "owner")),
):
    sale_date = payload.get("date")
    model = Sale(
        date=(datetime.fromisoformat(sale_date.replace('Z', '+00:00')).date() if sale_date else date.today()) if isinstance(sale_date, str) else (sale_date or date.today()),
        product=payload.get("product"),
        category=payload.get("category"),
        quantity=int(payload.get("quantity", 0)),
        unit_price=float(payload.get("unit_price", 0)),
        status="Received",
        created_by=current.id,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return {
        "id": model.id,
        "date": model.date.isoformat() if model.date else None,
        "product": model.product,
        "category": model.category,
        "quantity": model.quantity,
        "unit_price": model.unit_price,
        "revenue": (model.quantity or 0) * (model.unit_price or 0),
        "status": model.status,
        "created_by": model.created_by,
    }


@router.get("/orders/")
def get_orders(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    query = _sales_query_for_current_user(db, current)
    sales = query.order_by(Sale.date.desc(), Sale.id.desc()).all()
    return [_serialize_order(s) for s in sales]


@router.post("/orders/", status_code=201)
def create_order(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("user")),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    sale_date = payload.get("order_date")
    checkout_items = _normalized_checkout_items(payload)
    normalized_idempotency_key = (idempotency_key or "").strip() or None

    if normalized_idempotency_key:
        existing_orders = (
            db.query(Order)
            .filter(Order.customer_id == current.id)
            .filter(
                or_(
                    Order.idempotency_key == normalized_idempotency_key,
                    Order.idempotency_key.like(f"{normalized_idempotency_key}:%"),
                )
            )
            .order_by(Order.id.asc())
            .all()
        )
        if existing_orders:
            existing_sales = (
                db.query(Sale)
                .filter(Sale.order_id.in_([order.id for order in existing_orders]))
                .order_by(Sale.id.asc())
                .all()
            )
            if existing_sales:
                return {
                    "orders": [_serialize_order(item) for item in existing_sales],
                    "created_group_count": len(existing_sales),
                    "reused": True,
                }

    product_ids = [item["product_id"] for item in checkout_items]
    products = (
        db.query(Product)
        .filter(Product.id.in_(product_ids))
        .order_by(Product.id.asc())
        .with_for_update()
        .all()
    )
    product_map = {product.id: product for product in products}

    missing_product_ids = [product_id for product_id in product_ids if product_id not in product_map]
    if missing_product_ids:
        raise HTTPException(status_code=404, detail=f"Product not found: {missing_product_ids[0]}")

    for item in checkout_items:
        product = product_map[item["product_id"]]
        if (product.stock or 0) < item["quantity"]:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

    delivery_address = (payload.get("delivery_address") or "").strip() or None
    delivery_phone = (payload.get("delivery_phone") or current.phone or "").strip() or None
    delivery_notes = (payload.get("delivery_notes") or "").strip() or None
    delivery_method = _normalized_delivery_method(payload.get("delivery_method"))
    if delivery_method != "Pickup" and not delivery_address:
        raise HTTPException(status_code=400, detail="Delivery address is required unless you select Pickup")
    seller_ids = sorted({int(product.seller_id) for product in products if getattr(product, "seller_id", None) is not None})
    sellers = (
        db.query(BusinessUser)
        .filter(BusinessUser.id.in_(seller_ids))
        .all()
        if seller_ids
        else []
    )
    seller_map = {seller.id: seller for seller in sellers}

    provider_ids = sorted({int(product.provider_id) for product in products if getattr(product, "provider_id", None) is not None})
    providers = (
        db.query(Provider)
        .filter(Provider.id.in_(provider_ids))
        .all()
        if provider_ids
        else []
    )
    provider_map = {provider.id: provider for provider in providers}

    initial_status = "Pending"
    order_date = (
        (datetime.fromisoformat(sale_date.replace("Z", "+00:00")).date() if sale_date else date.today())
        if isinstance(sale_date, str)
        else (sale_date or date.today())
    )

    grouped_items: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for item in checkout_items:
        product = product_map[item["product_id"]]
        if getattr(product, "seller_id", None) is not None:
            group_key = ("seller", int(product.seller_id))
        elif getattr(product, "provider_id", None) is not None:
            group_key = ("provider", int(product.provider_id))
        else:
            group_key = ("product", int(product.id))
        grouped_items[group_key].append(
            {
                "product": product,
                "quantity": item["quantity"],
            }
        )

    created_sales: list[Sale] = []
    total_groups = len(grouped_items)
    for index, ((group_type, group_id), items) in enumerate(sorted(grouped_items.items(), key=lambda item: item[0]), start=1):
        seller = seller_map.get(group_id) if group_type == "seller" else None
        provider = provider_map.get(group_id) if group_type == "provider" else None
        provider_name = (
            seller.business_name
            if seller
            else (provider.name if provider else None)
        )
        primary_product = items[0]["product"]
        total_quantity = sum(int(item["quantity"]) for item in items)
        total_amount = round(
            sum(float(item["product"].price or 0) * int(item["quantity"]) for item in items),
            2,
        )
        item_count = len(items)
        average_unit_price = round(total_amount / total_quantity, 4) if total_quantity else 0.0
        categories = sorted({str(item["product"].category or "").strip() for item in items if item["product"].category})
        product_summary = (
            primary_product.name
            if item_count == 1
            else f"{primary_product.name} + {item_count - 1} more items"
        )
        category_summary = categories[0] if len(categories) == 1 else "Mixed"
        derived_idempotency_key = None
        if normalized_idempotency_key:
            derived_idempotency_key = (
                normalized_idempotency_key
                if total_groups == 1
                else f"{normalized_idempotency_key}:{index}:{group_type}:{group_id}"
            )

        linked_order = Order(
            customer_id=current.id,
            primary_seller_id=getattr(primary_product, "seller_id", None),
            status=initial_status,
            total_amount=total_amount,
            item_count=item_count,
            delivery_address=delivery_address,
            delivery_phone=delivery_phone,
            delivery_notes=delivery_notes,
            delivery_method=delivery_method,
            idempotency_key=derived_idempotency_key,
        )
        db.add(linked_order)
        db.flush()

        linked_items: list[OrderItem] = []
        for entry in items:
            product = entry["product"]
            quantity = int(entry["quantity"])
            line_total = round(float(product.price or 0) * quantity, 2)
            linked_item = OrderItem(
                order_id=linked_order.id,
                product_id=product.id,
                seller_id=getattr(product, "seller_id", None),
                product_name=product.name,
                category=product.category,
                quantity=quantity,
                unit_price=float(product.price or 0),
                total_amount=line_total,
                status=initial_status,
            )
            db.add(linked_item)
            db.flush()
            reserve_inventory(
                db,
                order_id=linked_order.id,
                order_item_id=linked_item.id,
                product_id=product.id,
                quantity=quantity,
            )
            product.stock = int(product.stock or 0) - quantity
            db.add(product)
            linked_items.append(linked_item)

        model = Sale(
            date=order_date,
            product=product_summary,
            category=category_summary,
            product_id=primary_product.id if item_count == 1 else None,
            seller_id=getattr(primary_product, "seller_id", None),
            provider_id=getattr(primary_product, "provider_id", None) if item_count == 1 else None,
            provider_name=provider_name,
            quantity=total_quantity,
            unit_price=average_unit_price,
            status=initial_status,
            created_by=current.id,
            order_id=linked_order.id,
            order_item_id=linked_items[0].id if item_count == 1 else None,
            delivery_address=delivery_address,
            delivery_phone=delivery_phone,
            delivery_notes=delivery_notes,
            delivery_method=delivery_method,
        )
        db.add(model)
        db.flush()

        linked_order.legacy_sale_id = model.id
        db.add(linked_order)
        if item_count == 1:
            linked_items[0].legacy_sale_id = model.id
            db.add(linked_items[0])

        ensure_order_thread(db, order=linked_order, sale=model, seller=seller, buyer=current)
        log_order_status(
            db,
            order_id=linked_order.id,
            sale_id=model.id,
            status=initial_status,
            reason="Order created",
            actor=current,
            metadata={
                "item_count": item_count,
                "items": [
                    {
                        "product_id": item.product_id,
                        "product_name": item.product_name,
                        "quantity": item.quantity,
                    }
                    for item in linked_items
                ],
            },
        )
        record_audit(
            db,
            actor=current,
            entity_type="order",
            entity_id=linked_order.id,
            action="order.created",
            details={
                "sale_id": model.id,
                "item_count": item_count,
                "total_amount": total_amount,
            },
        )
        _notify_order_event(
            db,
            background_tasks,
            model,
            buyer_title=f"Order #{model.id} created successfully",
            buyer_message=f"Your order for {model.product} has been created and is now awaiting payment.",
            seller_title=f"New order #{model.id} requires attention",
            seller_message=f"You received a new order for {model.product} x{model.quantity}.",
            severity="info",
        )
        created_sales.append(model)

    db.commit()
    for item in created_sales:
        db.refresh(item)
    return {
        "orders": [_serialize_order(item) for item in created_sales],
        "created_group_count": len(created_sales),
        "reused": False,
    }


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    target_status = _requested_status(payload.get("status"))
    if not target_status:
        raise HTTPException(status_code=400, detail="Invalid status")

    order = db.query(Sale).filter(Sale.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current.role == "seller":
        _ensure_owner_or_admin(order, current)

    current_status = _normalized_status(order.status)
    if target_status == current_status:
        return _serialize_order(order)

    if target_status not in ADMIN_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move order from {current_status} to {target_status}",
        )

    # Require completed payment before processing the order beyond a customer draft.
    if target_status != "Cancelled":
        payment = db.query(PaymentTransaction).filter(
            PaymentTransaction.order_id == order_id,
            PaymentTransaction.status == "completed"
        ).first()
        if not payment:
            raise HTTPException(
                status_code=400,
                detail="Payment must be completed before the order can be processed."
            )

    # Keep explicit shipping guard for clarity.
    if target_status == "Shipped" and payment is None:
        payment = db.query(PaymentTransaction).filter(
            PaymentTransaction.order_id == order_id,
            PaymentTransaction.status == "completed"
        ).first()
        if not payment:
            raise HTTPException(
                status_code=400,
                detail="Payment must be completed before order can be shipped."
            )

    order.status = target_status
    order.status_reason = (payload.get("reason") or "").strip() or None
    if target_status == "Cancelled":
        _restore_sale_inventory(db, order)

    db.add(order)
    _sync_order_state(
        db,
        order,
        status=target_status,
        reason=order.status_reason,
        actor=current,
        metadata={"source": "sales.status.patch"},
    )
    _notify_order_event(
        db,
        background_tasks,
        order,
        buyer_title=f"Order #{order.id} moved to {target_status}",
        buyer_message=f"Your order for {order.product} is now {target_status}.",
        seller_title=f"Order #{order.id} updated",
        seller_message=f"Order #{order.id} is now {target_status}.",
        severity="warning" if target_status == "Cancelled" else "info",
    )
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.post("/orders/{order_id}/receive")
def confirm_received(
    order_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("user")),
):
    order = db.query(Sale).filter(Sale.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    _ensure_owner_or_admin(order, current)
    current_status = _normalized_status(order.status)
    if current_status != "Shipped":
        raise HTTPException(status_code=400, detail="Only shipped orders can be marked received")

    order.status = "Received"
    db.add(order)
    linked_order = _linked_order(db, order)
    if linked_order:
        update_reservation_status(db, order_id=linked_order.id, status="consumed")
    _sync_order_state(
        db,
        order,
        status="Received",
        reason="Customer confirmed receipt",
        actor=current,
        metadata={"source": "sales.receive"},
    )
    _notify_order_event(
        db,
        background_tasks,
        order,
        buyer_title=f"Order #{order.id} marked as received",
        buyer_message=f"You confirmed receipt of {order.product}.",
        seller_title=f"Order #{order.id} received by customer",
        seller_message=f"The customer confirmed receipt of {order.product}.",
        severity="success",
    )
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("user")),
):
    order = db.query(Sale).filter(Sale.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    _ensure_owner_or_admin(order, current)
    current_status = _normalized_status(order.status)
    if current_status not in CANCELLABLE_BY_CUSTOMER:
        raise HTTPException(status_code=400, detail="Order can no longer be cancelled")

    order.status = "Cancelled"
    _restore_sale_inventory(db, order)

    db.add(order)
    _sync_order_state(
        db,
        order,
        status="Cancelled",
        reason="Cancelled by customer",
        actor=current,
        metadata={"source": "sales.cancel"},
    )
    _notify_order_event(
        db,
        background_tasks,
        order,
        buyer_title=f"Order #{order.id} cancelled",
        buyer_message=f"Your order for {order.product} has been cancelled.",
        seller_title=f"Order #{order.id} cancelled by customer",
        seller_message=f"The customer cancelled the order for {order.product}.",
        severity="warning",
    )
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.post("/orders/{order_id}/rating")
def rate_order(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("user")),
):
    try:
        rating = int(payload.get("rating", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="rating must be an integer")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    order = db.query(Sale).filter(Sale.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    _ensure_owner_or_admin(order, current)
    if _normalized_status(order.status) != "Received":
        raise HTTPException(status_code=400, detail="Only received orders can be rated")
    if order.rating is not None:
        raise HTTPException(status_code=400, detail="Order already rated")

    order.rating = rating
    order.rated_at = datetime.utcnow()
    db.add(order)

    _apply_product_rating_stats(db, order.product_id)
    refresh_business_metrics(db, order.seller_id)
    _notify_order_event(
        db,
        background_tasks,
        order,
        buyer_title=f"Rating saved for order #{order.id}",
        buyer_message=f"Thanks for rating {order.product} {rating}/5.",
        seller_title=f"New rating for order #{order.id}",
        seller_message=f"Your order for {order.product} received a rating of {rating}/5.",
        notification_type="rating",
        severity="success",
    )

    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.get("/orders/{order_id}/tracking")
def get_order_tracking(
    order_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    order = db.query(Sale).filter(Sale.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    _ensure_owner_or_admin(order, current)
    delivery = db.query(DeliveryOrder).filter(DeliveryOrder.order_id == order.id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Tracking is not available for this order yet")

    logistics = db.query(LogisticsUser).filter(LogisticsUser.id == delivery.logistics_id).first() if delivery.logistics_id else None
    return build_tracking_payload(delivery, order=order, logistics=logistics)
