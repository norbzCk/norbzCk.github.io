import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import (
    User, BusinessUser, LogisticsUser, Product, Provider, Sale,
    Order, OrderItem, DeliveryOrder, BusinessMetrics, LogisticsMetrics,
    InventoryReservation, OrderStatusHistory, ShipmentEvent, AuditLog,
    ConversationThread, ConversationMessage, ConversationParticipant, MessageReceipt,
)
from backend.app.auth import hash_password
from backend.app.order_runtime import (
    reserve_inventory, update_reservation_status, log_order_status,
    record_audit, record_shipment_event, ensure_order_thread,
    create_conversation_message, list_thread_messages,
    update_message_receipt, serialize_conversation_message,
)
from backend.app.notification_service import resolve_subject
from datetime import datetime, date


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def seller_user(db):
    seller = BusinessUser(
        business_name="Test Seller",
        owner_name="Seller Owner",
        phone="+255700000200",
        email="seller@test.com",
        password_hash=hash_password("TestPass1!"),
        business_type="individual",
        category="Groceries",
        region="Dar es Salaam",
        role="seller",
        is_active=True,
        verification_status="verified",
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)
    metrics = BusinessMetrics(business_id=seller.id)
    db.add(metrics)
    db.commit()
    return seller


@pytest.fixture
def buyer_user(db):
    buyer = User(
        name="Buyer User",
        email="buyer@test.com",
        phone="+255700000300",
        password_hash=hash_password("TestPass1!"),
        role="user",
        is_active=True,
        is_verified=True,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


@pytest.fixture
def product(db, seller_user):
    product = Product(
        name="Test Product",
        category="Groceries",
        price=5000.0,
        stock=100,
        description="A test product",
        seller_id=seller_user.id,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def sale(db, seller_user, buyer_user, product):
    sale = Sale(
        date=date.today(),
        product=product.name,
        category=product.category,
        product_id=product.id,
        seller_id=seller_user.id,
        quantity=2,
        unit_price=product.price,
        status="Pending",
        created_by=buyer_user.id,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


class TestReserveInventory:
    def test_reserve_inventory_creates_record(self, db, sale, product):
        reservation = reserve_inventory(
            db,
            order_id=1,
            order_item_id=1,
            product_id=product.id,
            quantity=2,
        )
        assert reservation is not None
        assert reservation.reserved_quantity == 2
        assert reservation.status == "reserved"
        assert reservation.product_id == product.id

    def test_reserve_inventory_multiple_items(self, db, product):
        r1 = reserve_inventory(db, order_id=1, order_item_id=1, product_id=product.id, quantity=3)
        r2 = reserve_inventory(db, order_id=1, order_item_id=2, product_id=product.id, quantity=5)
        assert r1 is not None
        assert r2 is not None


class TestUpdateReservationStatus:
    def test_update_reservation_to_released(self, db, sale, product):
        reserve_inventory(db, order_id=1, order_item_id=1, product_id=product.id, quantity=2)
        update_reservation_status(db, order_id=1, status="released")

        reservations = db.query(InventoryReservation).filter(
            InventoryReservation.order_id == 1
        ).all()
        for r in reservations:
            assert r.status == "released"
            assert r.released_at is not None

    def test_update_reservation_to_consumed(self, db, sale, product):
        reserve_inventory(db, order_id=2, order_item_id=1, product_id=product.id, quantity=2)
        update_reservation_status(db, order_id=2, status="consumed")

        reservations = db.query(InventoryReservation).filter(
            InventoryReservation.order_id == 2
        ).all()
        for r in reservations:
            assert r.status == "consumed"


class TestLogOrderStatus:
    def test_log_order_status_creates_record(self, db, sale, seller_user):
        entry = log_order_status(
            db,
            order_id=1,
            sale_id=sale.id,
            status="Pending",
            reason="Order created",
            actor=seller_user,
        )
        assert entry is not None
        assert entry.order_id == 1
        assert entry.sale_id == sale.id
        assert entry.status == "Pending"


class TestRecordAudit:
    def test_record_audit_creates_entry(self, db, sale, seller_user):
        entry = record_audit(
            db,
            actor=seller_user,
            entity_type="order",
            entity_id=1,
            action="order.created",
            details={"sale_id": sale.id},
        )
        assert entry is not None
        assert entry.entity_type == "order"
        assert entry.action == "order.created"


class TestRecordShipmentEvent:
    def test_record_shipment_event(self, db, sale, seller_user):
        event = record_shipment_event(
            db,
            delivery_id=1,
            order_id=1,
            sale_id=sale.id,
            status="assigned",
            actor=seller_user,
            message="Delivery assigned",
        )
        assert event is not None
        assert event.delivery_id == 1
        assert event.status == "assigned"


class TestEnsureOrderThread:
    def test_ensure_order_thread_creates_new(self, db, sale, seller_user, buyer_user):
        thread = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        assert thread is not None
        assert thread.sale_id == sale.id

    def test_ensure_order_thread_reuses_existing(self, db, sale, seller_user, buyer_user):
        thread1 = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        thread2 = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        assert thread1.id == thread2.id


class TestCreateConversationMessage:
    def test_create_message_in_thread(self, db, sale, seller_user, buyer_user):
        thread = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        msg = create_conversation_message(
            db,
            thread=thread,
            sender=seller_user,
            text="Hello, your order is confirmed.",
        )
        assert msg is not None
        assert msg.text == "Hello, your order is confirmed."
        assert msg.sender_type == "business"


class TestListThreadMessages:
    def test_list_messages_empty_thread(self, db):
        thread = ConversationThread(
            subject="Empty thread",
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)

        messages = list_thread_messages(db, thread_id=thread.id)
        assert messages == []

    def test_list_messages_returns_ordered(self, db, sale, seller_user, buyer_user):
        thread = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        create_conversation_message(db, thread=thread, sender=seller_user, text="First message")
        create_conversation_message(db, thread=thread, sender=buyer_user, text="Second message")

        messages = list_thread_messages(db, thread_id=thread.id)
        assert len(messages) == 2


class TestUpdateMessageReceipt:
    def test_update_receipt_new(self, db, sale, seller_user, buyer_user):
        thread = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        msg = create_conversation_message(db, thread=thread, sender=seller_user, text="Test")

        receipt = update_message_receipt(
            db,
            message_id=msg.id,
            recipient_type="user",
            recipient_id=buyer_user.id,
            status="delivered",
        )
        assert receipt is not None
        assert receipt.status == "delivered"

    def test_update_receipt_upgrades_status(self, db, sale, seller_user, buyer_user):
        thread = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        msg = create_conversation_message(db, thread=thread, sender=seller_user, text="Test")

        update_message_receipt(db, message_id=msg.id, recipient_type="user", recipient_id=buyer_user.id, status="delivered")
        receipt = update_message_receipt(db, message_id=msg.id, recipient_type="user", recipient_id=buyer_user.id, status="read")
        assert receipt.status == "read"


class TestSerializeConversationMessage:
    def test_serialize_message(self, db, sale, seller_user, buyer_user):
        thread = ensure_order_thread(
            db,
            sale=sale,
            seller=seller_user,
            buyer=buyer_user,
        )
        msg = create_conversation_message(db, thread=thread, sender=seller_user, text="Hello")

        serialized = serialize_conversation_message(msg, current_type="business", current_id=seller_user.id)
        assert serialized["text"] == "Hello"
        assert serialized["sender_role"] == "self"


class TestActorPayload:
    def test_actor_payload_with_user(self, db, buyer_user):
        from backend.app.order_runtime import actor_payload
        actor_type, actor_id, display_name, role = actor_payload(buyer_user)
        assert actor_type == "user"
        assert actor_id == buyer_user.id
        assert display_name == "Buyer User"
        assert role == "user"

    def test_actor_payload_with_none(self, db):
        from backend.app.order_runtime import actor_payload
        actor_type, actor_id, display_name, role = actor_payload(None)
        assert actor_type == "system"
        assert actor_id is None
        assert display_name == "System"