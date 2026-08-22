import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, Dispute
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


class TestListDisputes:
    def test_admin_lists_disputes(self, client, db, admin_user, product, buyer_user, seller_user):
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

        dispute = Dispute(
            sale_id=sale.id,
            buyer_id=buyer_user.id,
            seller_id=seller_user.id,
            status="open",
            resolution_details="Product not as described",
        )
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/disputes/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestGetDispute:
    def test_get_dispute_exists(self, client, db, admin_user, product, buyer_user, seller_user):
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

        dispute = Dispute(
            sale_id=sale.id,
            buyer_id=buyer_user.id,
            seller_id=seller_user.id,
            status="open",
            resolution_details="Product not as described",
        )
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get(f"/disputes/{dispute.id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["sale_id"] == sale.id

    def test_get_nonexistent_dispute(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/disputes/99999", headers=auth_header(token))
        assert response.status_code == 404


class TestCreateDispute:
    def test_admin_creates_dispute(self, client, db, admin_user, product, buyer_user, seller_user):
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

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/disputes/", json={
            "sale_id": sale.id,
            "buyer_id": buyer_user.id,
            "seller_id": seller_user.id,
            "status": "open",
            "resolution_details": "Item damaged during delivery",
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert data["sale_id"] == sale.id
        assert data["status"] == "open"

    def test_create_dispute_invalid_sale(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/disputes/", json={
            "sale_id": 99999,
            "buyer_id": 1,
            "seller_id": 1,
            "status": "open",
        }, headers=auth_header(token))
        assert response.status_code == 404


class TestUpdateDispute:
    def test_admin_resolves_dispute(self, client, db, admin_user, product, buyer_user, seller_user):
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

        dispute = Dispute(
            sale_id=sale.id,
            buyer_id=buyer_user.id,
            seller_id=seller_user.id,
            status="open",
            resolution_details="Item damaged during delivery",
        )
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/disputes/{dispute.id}", json={
            "status": "resolved_mutual",
            "resolution_details": "Refund issued to buyer",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved_mutual"

    def test_update_dispute_invalid_status(self, client, db, admin_user, product, buyer_user, seller_user):
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

        dispute = Dispute(
            sale_id=sale.id,
            buyer_id=buyer_user.id,
            seller_id=seller_user.id,
            status="open",
        )
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/disputes/{dispute.id}", json={
            "status": "invalid_status",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestDeleteDispute:
    def test_admin_deletes_dispute(self, client, db, admin_user, product, buyer_user, seller_user):
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

        dispute = Dispute(
            sale_id=sale.id,
            buyer_id=buyer_user.id,
            seller_id=seller_user.id,
            status="open",
        )
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        dispute_id = dispute.id
        response = client.delete(f"/disputes/{dispute_id}", headers=auth_header(token))
        assert response.status_code == 204

        db.expire_all()
        deleted = db.query(Dispute).filter(Dispute.id == dispute_id).first()
        assert deleted is None