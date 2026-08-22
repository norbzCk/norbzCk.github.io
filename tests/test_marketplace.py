import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, RFQ, PaymentTransaction
from backend.app.auth import hash_password
from datetime import date


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


class TestMarketplaceTrends:
    def test_marketplace_trends(self, client, db, admin_user, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=admin_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        response = client.get("/marketplace/trends")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestSuperadminOverview:
    def test_superadmin_overview(self, client, db, admin_user, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=admin_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/stats", headers=auth_header(token))
        assert response.status_code == 200


class TestSellerDashboardOverview:
    def test_business_dashboard_overview(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/dashboard/overview", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "business" in data
        assert "summary" in data


class TestBusinessInventoryOverview:
    def test_inventory_overview(self, client, db, seller_user, product):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/inventory/overview", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data


class TestBusinessInventoryForecast:
    def test_inventory_forecast(self, client, db, seller_user, product):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/inventory/forecast", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestBusinessMarketShare:
    def test_market_share(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/market-share", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "market_share_percent" in data
        assert "rank" in data


class TestBusinessOrders:
    def test_business_orders(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Pending",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/orders", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestBusinessAnalytics:
    def test_business_analytics(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Received",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/analytics", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "revenue_timeline" in data
        assert "revenue_by_product" in data
        assert "demand_by_category" in data


class TestBusinessOrderDecision:
    def test_business_accept_order(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Pending",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/business/orders/{sale.id}/decision", json={
            "decision": "accept",
        }, headers=auth_header(token))
        assert response.status_code == 200

    def test_business_reject_order(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Pending",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/business/orders/{sale.id}/decision", json={
            "decision": "reject",
            "reason": "Out of stock",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "order" in data


class TestBusinessUpdateOrderStatus:
    def test_business_status_transition(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/business/orders/{sale.id}/status", json={
            "status": "Packed",
        }, headers=auth_header(token))
        assert response.status_code == 200


class TestBusinessAssignDelivery:
    def test_assign_delivery(self, client, db, seller_user, product):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Confirmed",
            created_by=1,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        payment = PaymentTransaction(
            transaction_id="TXN-ASSIGN-TEST",
            order_id=sale.id,
            payer_type="user",
            payer_id=1,
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

        response = client.post(f"/business/orders/{sale.id}/assign-delivery", json={
            "logistics_id": 1,
        }, headers=auth_header(token))
        assert response.status_code in (200, 404)


class TestBusinessLogisticsOptions:
    def test_get_logistics_options(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/logistics-options", headers=auth_header(token))
        assert response.status_code == 200


class TestBusinessChangePassword:
    def test_change_password(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/business/change-password", json={
            "current_password": "TestPass1!",
            "new_password": "NewPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 200


class TestBusinessProfile:
    def test_get_my_profile(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/business/me", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["business_name"] == "Test Seller"

    def test_update_my_profile(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put("/business/me", json={
            "business_name": "Updated Business Name",
        }, headers=auth_header(token))
        assert response.status_code == 200


class TestBusinessVerification:
    def test_submit_verification(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/business/verify", json={
            "document_type": "national_id",
            "document_url": "/uploads/id_doc.pdf",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"