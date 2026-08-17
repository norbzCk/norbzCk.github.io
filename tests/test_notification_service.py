import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Notification
from backend.app.auth import hash_password
from backend.app.notification_service import (
    resolve_subject, create_notification, send_email_message,
    build_login_email, build_password_reset_email,
    list_notifications_for_subject, unread_count_for_subject,
    mark_notification_as_read, serialize_notification,
)
from backend.app.notification_service import smtp_enabled


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
def buyer_user(db):
    buyer = User(
        name="Buyer User",
        email="buyer@test.com",
        phone="+255700000300",
        password_hash=hash_password("TestPass1!"),
        role="user",
        is_active=True,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


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
    return seller


class TestResolveSubject:
    def test_resolve_user_subject(self, db, buyer_user):
        recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(buyer_user)
        assert recipient_type == "user"
        assert recipient_id == buyer_user.id
        assert recipient_email == "buyer@test.com"
        assert recipient_name == "Buyer User"

    def test_resolve_business_subject(self, db, seller_user):
        recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(seller_user)
        assert recipient_type == "business"
        assert recipient_id == seller_user.id
        assert recipient_name == "Test Seller"


class TestCreateNotification:
    def test_create_notification_with_email(self, db, buyer_user):
        notification = create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Test Title",
            message="Test message body",
            notification_type="system",
            severity="info",
            send_email=False,
        )
        db.commit()
        db.refresh(notification)
        assert notification is not None
        assert notification.id is not None
        assert notification.title == "Test Title"
        assert notification.recipient_type == "user"

    def test_create_notification_without_email(self, db, buyer_user):
        notification = create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=None,
            title="No Email Title",
            message="No email message",
            notification_type="system",
            severity="info",
            send_email=False,
        )
        assert notification is not None
        assert notification.email_status == "not_requested"


class TestListNotifications:
    def test_list_notifications_for_subject(self, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="List Test",
            message="Test notification for listing",
            notification_type="system",
            severity="info",
        )
        db.commit()

        items = list_notifications_for_subject(db, "user", buyer_user.id, limit=10)
        assert len(items) >= 1

    def test_list_unread_notifications(self, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Unread Test",
            message="This should be unread",
            notification_type="system",
            severity="info",
        )
        db.commit()

        items = list_notifications_for_subject(db, "user", buyer_user.id, unread_only=True, limit=10)
        assert len(items) >= 1
        for item in items:
            assert item.is_read is False


class TestUnreadCount:
    def test_unread_count(self, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Count Test",
            message="Test for unread count",
            notification_type="system",
            severity="info",
        )
        db.commit()

        count = unread_count_for_subject(db, "user", buyer_user.id)
        assert count >= 1


class TestMarkNotificationAsRead:
    def test_mark_notification_read(self, db, buyer_user):
        notification = create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Read Test",
            message="Test marking as read",
            notification_type="system",
            severity="info",
        )
        db.commit()

        assert notification.is_read is False
        updated = mark_notification_as_read(db, notification)
        assert updated.is_read is True
        assert updated.read_at is not None


class TestSerializeNotification:
    def test_serialize_notification(self, db, buyer_user):
        notification = create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Serialize Test",
            message="Test serialization",
            notification_type="system",
            severity="info",
            metadata={"order_id": 123},
        )
        db.commit()

        serialized = serialize_notification(notification)
        assert serialized["id"] == notification.id
        assert serialized["title"] == "Serialize Test"
        assert serialized["type"] == "system"
        assert serialized["severity"] == "info"
        assert serialized["is_read"] is False
        assert serialized["metadata"] == {"order_id": 123}


class TestBuildLoginEmail:
    def test_build_login_email(self, db):
        subject, body = build_login_email("Test User", "buyer", "127.0.0.1", "Mozilla/5.0")
        assert "SokoLnk login alert" in subject
        assert "Test User" in body
        assert "127.0.0.1" in body


class TestBuildPasswordResetEmail:
    def test_build_password_reset_email(self, db):
        subject, body = build_password_reset_email("Test User", "reset-token-xyz")
        assert "password reset" in subject.lower()
        assert "reset-token-xyz" in body


class TestSMTPEnabled:
    def test_smtp_disabled_by_default(self, db):
        enabled = smtp_enabled()
        assert enabled is False


class TestSendEmailMessage:
    def test_send_email_without_smtp(self, db):
        send_email_message("test@example.com", "Test Subject", "Test body")

    def test_send_email_with_invalid_recipient(self, db):
        send_email_message("", "Test Subject", "Test body")