import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, LogisticsUser, Notification, BusinessMetrics, LogisticsMetrics
from backend.app.auth import hash_password
from backend.app.notification_service import create_notification, resolve_subject


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
    metrics = BusinessMetrics(business_id=seller.id)
    db.add(metrics)
    db.commit()
    return seller


@pytest.fixture
def logistics_user(db):
    logistics = LogisticsUser(
        name="Test Rider",
        phone="+255700000400",
        email="logistics@test.com",
        password_hash=hash_password("TestPass1!"),
        account_type="individual",
        vehicle_type="motorcycle",
        status="online",
        availability="available",
        verification_status="verified",
        is_active=True,
    )
    db.add(logistics)
    db.commit()
    db.refresh(logistics)
    metrics = LogisticsMetrics(logistics_id=logistics.id)
    db.add(metrics)
    db.commit()
    return logistics


def login_as(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestGetNotifications:
    def test_user_gets_notifications(self, client, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Test Notification",
            message="This is a test notification",
            notification_type="system",
            severity="info",
        )
        db.commit()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/notifications/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "unread_count" in data

    def test_notifications_unread_only(self, client, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Unread Test",
            message="This is unread",
            notification_type="system",
            severity="info",
        )
        db.commit()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/notifications/?unread_only=true", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] >= 1


class TestNotificationSummary:
    def test_notification_summary(self, client, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Summary Test",
            message="Test notification for summary",
            notification_type="system",
            severity="info",
        )
        db.commit()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/notifications/summary", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "unread_count" in data


class TestReadNotification:
    def test_read_notification(self, client, db, buyer_user):
        create_notification(
            db,
            recipient_type="user",
            recipient_id=buyer_user.id,
            recipient_email=buyer_user.email,
            title="Read Test",
            message="Test notification to mark as read",
            notification_type="system",
            severity="info",
        )
        db.commit()

        notification = db.query(Notification).filter(
            Notification.recipient_id == buyer_user.id
        ).first()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/notifications/{notification.id}/read", headers=auth_header(token))
        assert response.status_code == 200

    def test_read_nonexistent_notification(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/notifications/99999/read", headers=auth_header(token))
        assert response.status_code == 404


class TestReadAllNotifications:
    def test_read_all_notifications(self, client, db, buyer_user):
        for i in range(3):
            create_notification(
                db,
                recipient_type="user",
                recipient_id=buyer_user.id,
                recipient_email=buyer_user.email,
                title=f"Batch Notification {i}",
                message=f"Test notification {i}",
                notification_type="system",
                severity="info",
            )
        db.commit()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/notifications/read-all", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "updated" in data


class TestWebSocketConnection:
    @pytest.mark.skip(reason="WebSocket test requires live server; testserver host does not resolve in CI/container")
    def test_websocket_connection_rejected_without_token(self, client):
        import asyncio
        from websockets.sync.client import connect

        with connect("ws://testserver/notifications/ws/delivery/1?token=") as ws:
            pass


class TestNotificationPermissions:
    def test_unauthenticated_cannot_access_notifications(self, client):
        response = client.get("/notifications/")
        assert response.status_code == 401

    def test_unauthenticated_cannot_mark_read(self, client):
        response = client.post("/notifications/1/read")
        assert response.status_code == 401

    def test_unauthenticated_cannot_read_all(self, client):
        response = client.post("/notifications/read-all")
        assert response.status_code == 401