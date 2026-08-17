import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, Notification
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


class TestDashboardStats:
    def test_dashboard_stats_admin(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/stats", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "total_revenue" in data
        assert "total_orders" in data
        assert "total_units" in data


class TestDashboardRevenueProduct:
    def test_revenue_by_product(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/revenue-product", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestDashboardRevenueTime:
    def test_revenue_over_time(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/revenue-time", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestDashboardRecentSales:
    def test_recent_sales(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/recent-sales", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestDashboardAnalytics:
    def test_dashboard_analytics(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/analytics", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert "revenueByProduct" in data
        assert "revenueOverTime" in data


class TestDashboardMarketInsights:
    def test_market_insights(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/market-insights", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "market" in data
        assert "pricing" in data
        assert "demand" in data


class TestDashboardExportSales:
    def test_export_sales_csv(self, client, db, admin_user, seller_user, product):
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

        response = client.get("/dashboard/export-sales", headers=auth_header(token))
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")


class TestSuperadminEndpoints:
    def test_superadmin_stats(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/stats", headers=auth_header(token))
        assert response.status_code == 200

    def test_superadmin_me(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/me", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "super_admin"

    def test_superadmin_businessmen_list(self, client, db, admin_user, seller_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/businessmen", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_superadmin_verifications(self, client, db, admin_user, seller_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/verifications", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "businessmen" in data
        assert "logistics" in data

    def test_update_business_verification(self, client, db, admin_user, seller_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/superadmin/businessmen/{seller_user.id}/verification", json={
            "status": "verified",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["verification_status"] == "verified"

    def test_delete_businessman(self, client, db, admin_user, seller_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.delete(f"/superadmin/businessmen/{seller_user.id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower() or "Business account deleted" in data["message"]