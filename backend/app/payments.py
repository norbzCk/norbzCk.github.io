import json
import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from backend.app.auth import get_current_user, require_roles
from backend.app.notification_service import create_notification, resolve_subject
from backend.app.schemas import PaymentRequest, PaymentResponse, PaymentMethod
from backend.database import get_db
from backend.models import BusinessUser, Order, PaymentAttempt, PaymentTransaction, Sale, User

router = APIRouter(prefix="/payments", tags=["Payments"])


PAYMENT_METHODS = [
    {
        "id": "mpesa",
        "name": "M-Pesa",
        "type": "mobile_money",
        "enabled": True,
        "instructions": "Enter your M-Pesa phone number. You will receive a prompt on your phone."
    },
    {
        "id": "airtel_money",
        "name": "Airtel Money",
        "type": "mobile_money",
        "enabled": True,
        "instructions": "Enter your Airtel Money phone number. You will receive a prompt on your phone."
    },
    {
        "id": "tigopesa",
        "name": "Tigo Pesa",
        "type": "mobile_money",
        "enabled": True,
        "instructions": "Enter your Tigo Pesa phone number."
    },
    {
        "id": "bank_transfer",
        "name": "Bank Transfer",
        "type": "bank",
        "enabled": True,
        "instructions": "Transfer to our business account. Upload receipt after payment."
    },
    {
        "id": "cash",
        "name": "Cash on Delivery",
        "type": "cash",
        "enabled": True,
        "instructions": "Pay with cash when receiving your order."
    },
    {
        "id": "credit",
        "name": "Credit Account",
        "type": "credit",
        "enabled": False,
        "instructions": "Available for approved business accounts only."
    }
]


def _payment_instructions(method_id: str) -> str | None:
    return next((m["instructions"] for m in PAYMENT_METHODS if m["id"] == method_id), None)


def _serialize_transaction(txn: PaymentTransaction) -> dict:
    return {
        "transaction_id": txn.transaction_id,
        "status": txn.status,
        "amount": txn.amount,
        "message": txn.message,
        "timestamp": txn.confirmed_at.isoformat() if txn.confirmed_at else (txn.created_at.isoformat() if txn.created_at else None),
        "order_id": txn.order_id,
        "instructions": txn.instructions,
        "payment_method": txn.payment_method,
        "provider": txn.provider,
    }


def _notify_payment_parties(
    db: Session,
    background_tasks: BackgroundTasks,
    order: Sale,
    buyer: User,
    *,
    title: str,
    buyer_message: str,
    seller_message: str | None = None,
    notification_type: str = "payment",
    severity: str = "info",
):
    buyer_type, buyer_id, buyer_email, buyer_name = resolve_subject(buyer)
    create_notification(
        db,
        recipient_type=buyer_type,
        recipient_id=buyer_id,
        recipient_email=buyer_email,
        title=title,
        message=buyer_message,
        notification_type=notification_type,
        severity=severity,
        action_href="/app/payments",
        background_tasks=background_tasks,
        send_email=bool(buyer_email),
        email_subject=title,
        email_body=f"Hello {buyer_name},\n\n{buyer_message}\n\nSokoLnk Payments",
        metadata={"order_id": order.id},
    )

    if order.seller_id:
        seller = db.query(BusinessUser).filter(BusinessUser.id == order.seller_id).first()
        if seller:
            seller_type, seller_id, seller_email, seller_name = resolve_subject(seller)
            create_notification(
                db,
                recipient_type=seller_type,
                recipient_id=seller_id,
                recipient_email=seller_email,
                title=title,
                message=seller_message or buyer_message,
                notification_type=notification_type,
                severity=severity,
                action_href="/app/orders",
                background_tasks=background_tasks,
                send_email=bool(seller_email),
                email_subject=title,
                email_body=f"Hello {seller_name},\n\n{seller_message or buyer_message}\n\nSokoLnk Payments",
                metadata={"order_id": order.id},
            )


def _linked_order_model(db: Session, sale: Sale) -> Order | None:
    if sale.order_id:
        order = db.query(Order).filter(Order.id == sale.order_id).first()
        if order:
            return order
    return db.query(Order).filter(Order.legacy_sale_id == sale.id).first()


def _payable_order_total(db: Session, sale: Sale) -> float:
    linked_order = _linked_order_model(db, sale)
    if linked_order:
        return round(float(linked_order.total_amount or 0), 2)
    return round(float((sale.unit_price or 0) * (sale.quantity or 0)), 2)


def _reused_payment_transaction(
    db: Session,
    *,
    sale: Sale,
    buyer_id: int,
    payment_method: str,
    amount: float,
    idempotency_key: str | None,
) -> PaymentTransaction | None:
    normalized_key = (idempotency_key or "").strip() or None
    if normalized_key:
        attempt = (
            db.query(PaymentAttempt)
            .filter(
                PaymentAttempt.sale_id == sale.id,
                PaymentAttempt.buyer_id == buyer_id,
                PaymentAttempt.idempotency_key == normalized_key,
            )
            .order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
            .first()
        )
        if attempt:
            if attempt.provider_reference:
                txn = (
                    db.query(PaymentTransaction)
                    .filter(PaymentTransaction.transaction_id == attempt.provider_reference)
                    .first()
                )
                if txn:
                    return txn
            txn = (
                db.query(PaymentTransaction)
                .filter(
                    PaymentTransaction.order_id == sale.id,
                    PaymentTransaction.payer_id == buyer_id,
                    PaymentTransaction.payment_method == payment_method,
                    PaymentTransaction.amount == amount,
                )
                .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
                .first()
            )
            if txn:
                return txn

    return (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.order_id == sale.id,
            PaymentTransaction.payer_id == buyer_id,
            PaymentTransaction.payment_method == payment_method,
            PaymentTransaction.amount == amount,
            PaymentTransaction.status.in_(["pending", "pending_delivery", "completed"]),
        )
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        .first()
    )


@router.get("/methods")
def get_payment_methods(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {"payment_methods": PAYMENT_METHODS}


@router.get("/methods/public")
def get_public_payment_methods(
    db: Session = Depends(get_db),
):
    return {"payment_methods": [m for m in PAYMENT_METHODS if m.get("enabled", True)]}


@router.post("/initiate")
def initiate_payment(
    payload: PaymentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("user")),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    order = db.query(Sale).filter(Sale.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order.created_by) != str(current.id):
        raise HTTPException(status_code=403, detail="You can only pay for your own orders")

    order_status = (order.status or "").strip().title()
    if order_status in {"Cancelled", "Received"}:
        raise HTTPException(status_code=400, detail="Cannot pay for an order that is already finalized")

    expected_total = _payable_order_total(db, order)
    if abs(expected_total - payload.amount) > 0.01:
        raise HTTPException(status_code=400, detail="Amount does not match order total")

    reused_txn = _reused_payment_transaction(
        db,
        sale=order,
        buyer_id=current.id,
        payment_method=payload.payment_method,
        amount=payload.amount,
        idempotency_key=idempotency_key,
    )
    if reused_txn:
        return _serialize_transaction(reused_txn)

    existing_payment = db.query(PaymentTransaction).filter(
        PaymentTransaction.order_id == order.id,
        PaymentTransaction.status == "completed"
    ).first()
    if existing_payment:
        raise HTTPException(status_code=400, detail="Order has already been paid")

    transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    instructions = _payment_instructions(payload.payment_method)
    payer_type, payer_id, _, _ = resolve_subject(current)
    status = "pending" if payload.payment_method != "cash" else "pending_delivery"

    txn = PaymentTransaction(
        transaction_id=transaction_id,
        order_id=payload.order_id,
        payer_type=payer_type,
        payer_id=payer_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        provider=payload.payment_method,
        phone_number=payload.phone_number,
        status=status,
        message=f"Payment initiated via {payload.payment_method}. Awaiting confirmation.",
        instructions=instructions,
        metadata_json=json.dumps({"notes": payload.notes} if payload.notes else {}),
    )
    db.add(txn)
    linked_order = _linked_order_model(db, order)
    db.add(
        PaymentAttempt(
            order_id=linked_order.id if linked_order else None,
            sale_id=order.id,
            buyer_id=current.id,
            idempotency_key=(idempotency_key or "").strip() or None,
            amount=payload.amount,
            payment_method=payload.payment_method,
            provider=payload.payment_method,
            status=status,
            provider_reference=transaction_id,
            message=f"Payment initiated via {payload.payment_method}",
        )
    )

    # Auto-progress order status for immediate payment methods (e.g., cash on delivery)
    if status != "pending":
        current_status = (order.status or "").strip().title()
        if current_status == "Pending":
            order.status = "Confirmed"
            db.add(order)

    _notify_payment_parties(
        db,
        background_tasks,
        order,
        current,
        title=f"Payment started for order #{order.id}",
        buyer_message=f"Your payment request for {order.product} has been created with transaction {transaction_id}.",
        seller_message=f"A buyer started a payment for order #{order.id}. Transaction: {transaction_id}.",
        severity="info",
    )
    db.commit()
    db.refresh(txn)
    
    return _serialize_transaction(txn)


@router.post("/mobile-money/stk-push")
def stk_push_payment(
    phone_number: str,
    amount: float,
    order_id: int,
    background_tasks: BackgroundTasks,
    provider: str = "mpesa",
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("user")),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    if provider not in ["mpesa", "airtel_money", "tigopesa"]:
        raise HTTPException(status_code=400, detail="Invalid mobile money provider")
    
    order = db.query(Sale).filter(Sale.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order.created_by) != str(current.id):
        raise HTTPException(status_code=403, detail="You can only pay for your own orders")

    order_status = (order.status or "").strip().title()
    if order_status in {"Cancelled", "Received"}:
        raise HTTPException(status_code=400, detail="Cannot pay for an order that is already finalized")

    expected_total = _payable_order_total(db, order)
    if abs(expected_total - amount) > 0.01:
        raise HTTPException(status_code=400, detail="Amount does not match order total")

    reused_txn = _reused_payment_transaction(
        db,
        sale=order,
        buyer_id=current.id,
        payment_method=provider,
        amount=amount,
        idempotency_key=idempotency_key,
    )
    if reused_txn:
        return _serialize_transaction(reused_txn)

    existing_payment = db.query(PaymentTransaction).filter(
        PaymentTransaction.order_id == order.id,
        PaymentTransaction.status == "completed"
    ).first()
    if existing_payment:
        raise HTTPException(status_code=400, detail="Order has already been paid")

    transaction_id = f"STK-{uuid.uuid4().hex[:10].upper()}"
    payer_type, payer_id, _, _ = resolve_subject(current)
    txn = PaymentTransaction(
        transaction_id=transaction_id,
        order_id=order_id,
        payer_type=payer_type,
        payer_id=payer_id,
        amount=amount,
        payment_method=provider,
        provider=provider,
        phone_number=phone_number,
        status="completed",
        message=f"STK Push completed successfully for {provider}.",
        instructions=_payment_instructions(provider),
        confirmed_at=datetime.utcnow(),
        metadata_json=json.dumps({"channel": "stk_push"}),
    )
    db.add(txn)
    linked_order = _linked_order_model(db, order)
    db.add(
        PaymentAttempt(
            order_id=linked_order.id if linked_order else None,
            sale_id=order.id,
            buyer_id=current.id,
            idempotency_key=(idempotency_key or "").strip() or None,
            amount=amount,
            payment_method=provider,
            provider=provider,
            status="completed",
            provider_reference=transaction_id,
            message=f"STK Push completed successfully for {provider}.",
        )
    )
    # Automatically progress order status after payment
    current_status = (order.status or "").strip().title()
    if current_status == "Pending":
        order.status = "Confirmed"
    elif current_status == "Confirmed":
        order.status = "Packed"  # Auto-progress to packing after payment
    db.add(order)

    _notify_payment_parties(
        db,
        background_tasks,
        order,
        current,
        title=f"Payment confirmed for order #{order.id}",
        buyer_message=f"Your {provider} payment for order #{order.id} was confirmed successfully.",
        seller_message=f"Payment for order #{order.id} has been confirmed via {provider}.",
        notification_type="payment",
        severity="success",
    )
    db.commit()
    db.refresh(txn)
    
    return _serialize_transaction(txn)


@router.get("/transaction/{transaction_id}")
def get_transaction_status(
    transaction_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _serialize_transaction(txn)


@router.post("/transaction/{transaction_id}/confirm")
def confirm_transaction(
    transaction_id: str,
    background_tasks: BackgroundTasks,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    order = db.query(Sale).filter(Sale.id == txn.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    status = str((payload or {}).get("status") or "completed").strip().lower()
    if status not in {"completed", "failed"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    txn.status = status
    txn.message = (payload or {}).get("message") or ("Payment confirmed successfully" if status == "completed" else "Payment failed")
    txn.confirmed_at = datetime.utcnow() if status == "completed" else None
    db.add(txn)
    linked_order = _linked_order_model(db, order)
    db.add(
        PaymentAttempt(
            order_id=linked_order.id if linked_order else None,
            sale_id=order.id,
            buyer_id=int(order.created_by) if order.created_by is not None else None,
            amount=float(txn.amount or 0),
            payment_method=txn.payment_method,
            provider=txn.provider,
            status=status,
            provider_reference=txn.transaction_id,
            message=txn.message,
        )
    )

    buyer = db.query(User).filter(User.id == int(order.created_by)).first() if order.created_by is not None else None
    if status == "completed":
        # Automatically progress order status after payment
        current_status = (order.status or "").strip().title()
        if current_status == "Pending":
            order.status = "Confirmed"
        elif current_status == "Confirmed":
            order.status = "Packed"  # Auto-progress to packing after payment
        db.add(order)

    if buyer:
        _notify_payment_parties(
            db,
            background_tasks,
            order,
            buyer,
            title=f"Payment {status} for order #{order.id}",
            buyer_message=f"Payment transaction {txn.transaction_id} is now {status}.",
            seller_message=f"Payment transaction {txn.transaction_id} for order #{order.id} is now {status}.",
            severity="success" if status == "completed" else "warning",
        )

    db.commit()
    db.refresh(txn)
    return _serialize_transaction(txn)


@router.get("/history")
def get_payment_history(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    payer_type, payer_id, _, _ = resolve_subject(current)
    transactions = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.payer_type == payer_type, PaymentTransaction.payer_id == payer_id)
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        .limit(50)
        .all()
    )
    order_ids = [txn.order_id for txn in transactions]
    orders = db.query(Sale).filter(Sale.id.in_(order_ids)).all() if order_ids else []
    order_map = {order.id: order for order in orders}
    
    return {
        "payments": [
            {
                "transaction_id": txn.transaction_id,
                "order_id": txn.order_id,
                "product": order_map.get(txn.order_id).product if order_map.get(txn.order_id) else None,
                "amount": float(txn.amount or 0),
                "status": txn.status,
                "date": txn.created_at.isoformat() if txn.created_at else None,
                "payment_method": txn.payment_method,
            }
            for txn in transactions
        ]
    }


@router.post("/webhook/mpesa")
def mpesa_webhook(
    db: Session = Depends(get_db),
):
    return {"status": "received"}
