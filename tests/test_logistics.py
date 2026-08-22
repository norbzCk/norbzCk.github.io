import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, LogisticsUser, Product, Provider, Sale, BusinessMetrics, LogisticsMetrics, DeliveryOrder
from backend.app.auth import hash_password
from datetime import date, datetime


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


def login_as(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestLogisticsRegister:
    def test_register_logistics_success(self, client, db):
        response = client.post("/logistics/register", json={
            "name": "New Rider",
            "phone": "+255700000500",
            "email": "newrider@test.com",
            "password": "TestPass1!",
            "account_type": "individual",
            "vehicle_type": "motorcycle",
            "plate_number": "ABC123",
            "license_number": "LIC123",
            "base_area": "Kariakoo",
            "coverage_areas": "Kariakoo,Ilala",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["userType"] == "logistics"

    def test_register_logistics_duplicate_phone(self, client, db, logistics_user):
        response = client.post("/logistics/register", json={
            "name": "Another Rider",
            "phone": "+255700000400",
            "email": "another@test.com",
            "password": "TestPass1!",
            "account_type": "individual",
            "vehicle_type": "motorcycle",
        })
        assert response.status_code == 400


class TestLogisticsLogin:
    def test_login_logistics_success(self, client, db, logistics_user):
        response = client.post("/logistics/login", json={
            "email": "logistics@test.com",
            "password": "TestPass1!",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data

    def test_login_logistics_wrong_password(self, client, db, logistics_user):
        response = client.post("/logistics/login", json={
            "email": "logistics@test.com",
            "password": "WrongPass1!",
        })
        assert response.status_code == 401


class TestCreateDeliveryOrder:
    def test_logistics_creates_delivery(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/logistics/deliveries", json={
            "order_id": sale.id,
            "seller_id": seller_user.id,
            "buyer_id": buyer_user.id,
            "pickup_location": "Kariakoo Market",
            "delivery_location": "Ubungo, Dar es Salaam",
            "pickup_phone": "+255700000200",
            "delivery_phone": "+255700000300",
            "price": 2000.0,
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "delivery" in data
        assert data["delivery"]["status"] == "assigned"


class TestUpdateDeliveryStatus:
    def test_logistics_updates_status_to_picked_up(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="assigned",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put(f"/logistics/deliveries/{delivery.id}/status", json={
            "status": "picked_up",
            "current_location": "Kariakoo Market",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["delivery"]["status"] == "picked_up"

    def test_logistics_cannot_update_invalid_transition(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="assigned",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put(f"/logistics/deliveries/{delivery.id}/status", json={
            "status": "delivered",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_delivery_rating_after_delivered(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="delivered",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/logistics/deliveries/{delivery.id}/rating", json={
            "rating": 4,
            "comment": "Good delivery service",
        }, headers=auth_header(token))
        assert response.status_code == 200


class TestGetMyDeliveries:
    def test_logistics_sees_own_deliveries(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="assigned",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/logistics/deliveries", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "deliveries" in data
        assert len(data["deliveries"]) >= 1


class TestGetDeliveryTracking:
    def test_logistics_tracks_own_delivery(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="in_transit",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get(f"/logistics/deliveries/{delivery.id}/tracking", headers=auth_header(token))
        assert response.status_code == 200


class TestPublicTrackDelivery:
    def test_public_track_by_order_id(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="delivered",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        response = client.get("/logistics/track", params={"order_id": sale.id})
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_public_track_by_verification_code(self, client, db, logistics_user, product, seller_user, buyer_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            logistics_id=logistics_user.id,
            pickup_location="Kariakoo Market",
            delivery_location="Ubungo, Dar es Salaam",
            status="delivered",
            verification_code="TEST1234",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        response = client.get("/logistics/track", params={"code": "TEST1234"})
        assert response.status_code == 200

    def test_public_track_invalid_order(self, client, db):
        response = client.get("/logistics/track", params={"order_id": 99999})
        assert response.status_code == 404


class TestLogisticsProfile:
    def test_get_my_profile(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/logistics/me", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Rider"

    def test_update_my_profile(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put("/logistics/me", json={
            "name": "Updated Rider",
            "vehicle_type": "van",
        }, headers=auth_header(token))
        assert response.status_code == 200

    def test_update_logistics_status(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put("/logistics/status", json={
            "status": "offline",
        }, headers=auth_header(token))
        assert response.status_code == 200
        assert response.json()["status"] == "offline"

    def test_update_logistics_availability(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put("/logistics/availability", json={
            "availability": "busy",
        }, headers=auth_header(token))
        assert response.status_code == 200


class TestAvailableLogistics:
    def test_get_available_logistics(self, client, db, logistics_user):
        response = client.get("/logistics/available")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestLogisticsChangePassword:
    def test_change_password_success(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/logistics/change-password", json={
            "current_password": "TestPass1!",
            "new_password": "NewPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 200

    def test_change_password_wrong_current(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/logistics/change-password", json={
            "current_password": "WrongPass1!",
            "new_password": "NewPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestLogisticsVerification:
    def test_request_verification(self, client, db, logistics_user):
        login = login_as(client, "logistics@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/logistics/verify", json={
            "document_type": "national_id",
            "document_url": "/uploads/id_document.pdf",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"