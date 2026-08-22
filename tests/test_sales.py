import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, Order, OrderItem, PaymentTransaction, DeliveryOrder
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
def admin_user(db):
    admin = User(
        name="Admin User",
        email="admin@test.com",
        phone="+255700000100",
        password_hash=hash_password("AdminPass1!"),
        role="super_admin",
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


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
def provider(db):
    provider = Provider(
        name="Test Provider",
        location="Dar es Salaam",
        email="provider@test.com",
        phone="+255700000400",
        verified=True,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


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


class TestGetSales:
    def test_admin_lists_sales(self, client, db, admin_user):
        sale = Sale(
            date=date.today(),
            product="Test Sale",
            category="Groceries",
            quantity=2,
            unit_price=5000.0,
            status="Received",
            created_by=admin_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/sales/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_seller_sees_own_sales(self, client, db, seller_user):
        sale = Sale(
            date=date.today(),
            product="Seller Sale",
            category="Groceries",
            quantity=3,
            unit_price=5000.0,
            status="Received",
            seller_id=seller_user.id,
            created_by=seller_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/orders/", headers=auth_header(token))
        assert response.status_code == 200


class TestCreateSale:
    def test_admin_creates_sale(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/sales/", json={
            "date": date.today().isoformat(),
            "product": "Manual Sale",
            "category": "Groceries",
            "quantity": 5,
            "unit_price": 3000.0,
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert data["product"] == "Manual Sale"
        assert data["quantity"] == 5


class TestGetOrders:
    def test_user_sees_own_orders(self, client, db, buyer_user, product, seller_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/orders/", headers=auth_header(token))
        assert response.status_code == 200


class TestCreateOrder:
    def test_user_creates_order(self, client, db, buyer_user, product):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/orders/", json={
            "items": [
                {"product_id": product.id, "quantity": 2},
            ],
            "delivery_address": "Test Address, Dar es Salaam",
            "delivery_phone": "+255700000300",
            "delivery_method": "Standard",
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert "orders" in data
        assert data["created_group_count"] >= 1

    def test_order_insufficient_stock(self, client, db, buyer_user, product):
        product.stock = 1
        db.commit()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/orders/", json={
            "items": [
                {"product_id": product.id, "quantity": 5},
            ],
            "delivery_address": "Test Address",
            "delivery_method": "Standard",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_order_idempotency_key(self, client, db, buyer_user, product):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/orders/", json={
            "items": [
                {"product_id": product.id, "quantity": 1},
            ],
            "delivery_address": "Test Address",
            "delivery_method": "Standard",
        }, headers={
            **auth_header(token),
            "Idempotency-Key": "test-idempotency-key",
        })
        assert response.status_code == 201
        first_order = response.json()

        response2 = client.post("/orders/", json={
            "items": [
                {"product_id": product.id, "quantity": 1},
            ],
            "delivery_address": "Test Address",
            "delivery_method": "Standard",
        }, headers={
            **auth_header(token),
            "Idempotency-Key": "test-idempotency-key",
        })
        assert response2.status_code == 201
        second_order = response2.json()
        assert second_order.get("reused") is True


class TestUpdateOrderStatus:
    def test_seller_updates_order_status(self, client, db, seller_user, buyer_user, product):
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

        payment = PaymentTransaction(
            transaction_id="TXN-STATUS-TEST",
            order_id=sale.id,
            payer_type="user",
            payer_id=buyer_user.id,
            amount=product.price * 2,
            payment_method="mpesa",
            provider="mpesa",
            phone_number="+255700000300",
            status="completed",
            message="Payment completed",
        )
        db.add(payment)
        db.commit()

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/orders/{sale.id}/status", json={
            "status": "Confirmed",
        }, headers=auth_header(token))
        assert response.status_code == 200

    def test_invalid_status_transition(self, client, db, seller_user, buyer_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/orders/{sale.id}/status", json={
            "status": "Cancelled",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestCancelOrder:
    def test_user_cancels_pending_order(self, client, db, buyer_user, product, seller_user):
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

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/orders/{sale.id}/cancel", headers=auth_header(token))
        assert response.status_code == 200

        db.expire_all()
        updated = db.query(Sale).filter(Sale.id == sale.id).first()
        assert updated.status == "Cancelled"


class TestReceiveOrder:
    def test_user_receives_shipped_order(self, client, db, buyer_user, product, seller_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Shipped",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/orders/{sale.id}/receive", headers=auth_header(token))
        assert response.status_code == 200

        db.expire_all()
        updated = db.query(Sale).filter(Sale.id == sale.id).first()
        assert updated.status == "Received"


class TestRateOrder:
    def test_user_rates_received_order(self, client, db, buyer_user, product, seller_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/orders/{sale.id}/rating", json={
            "rating": 5,
        }, headers=auth_header(token))
        assert response.status_code == 200

        db.expire_all()
        updated = db.query(Sale).filter(Sale.id == sale.id).first()
        assert updated.rating == 5

    def test_user_cannot_rate_already_rated_order(self, client, db, buyer_user, product, seller_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=buyer_user.id,
            rating=4,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/orders/{sale.id}/rating", json={
            "rating": 5,
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_user_cannot_rate_non_received_order(self, client, db, buyer_user, product, seller_user):
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

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/orders/{sale.id}/rating", json={
            "rating": 5,
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestOrderTracking:
    def test_tracking_with_delivery_order(self, client, db, buyer_user, product, seller_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Shipped",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        delivery = DeliveryOrder(
            order_id=sale.id,
            seller_id=seller_user.id,
            buyer_id=buyer_user.id,
            pickup_location="Seller Location",
            delivery_location="Buyer Location",
            status="in_transit",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get(f"/orders/{sale.id}/tracking", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checkpoints" in data


class TestExportSales:
    def test_export_sales_report(self, client, db, admin_user):
        sale = Sale(
            date=date.today(),
            product="Export Test",
            category="Groceries",
            quantity=3,
            unit_price=5000.0,
            status="Received",
            created_by=admin_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/dashboard/export-sales", headers=auth_header(token))
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")


class TestOrderOwnership:
    def test_user_cannot_access_other_users_tracking(self, client, db, buyer_user, product, seller_user):
        other_buyer = User(
            name="Other Buyer",
            email="other_buyer@test.com",
            phone="+255700000800",
            password_hash=hash_password("TestPass1!"),
            role="user",
            is_active=True,
            is_verified=True,
        )
        db.add(other_buyer)
        db.commit()
        db.refresh(other_buyer)

        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Pending",
            created_by=other_buyer.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get(f"/orders/{sale.id}/tracking", headers=auth_header(token))
        assert response.status_code == 403