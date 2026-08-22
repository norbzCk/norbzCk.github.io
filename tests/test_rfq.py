import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, RFQ
from backend.app.auth import hash_password


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


def login_as(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestCreateRFQ:
    def test_create_rfq_success(self, client, db):
        response = client.post("/rfq/", json={
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "email": "rfq@test.com",
            "phone": "+255700000100",
            "product_interest": "Bulk Rice",
            "quantity": 100,
            "target_budget": "5000000",
            "notes": "Need delivery within 2 weeks",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["company_name"] == "Test Company"
        assert data["status"] == "New"

    def test_create_rfq_invalid_email(self, client, db):
        response = client.post("/rfq/", json={
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "email": "not-an-email",
            "phone": "+255700000100",
            "product_interest": "Bulk Rice",
            "quantity": 100,
        })
        assert response.status_code == 400

    def test_create_rfq_invalid_quantity(self, client, db):
        response = client.post("/rfq/", json={
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "email": "rfq@test.com",
            "phone": "+255700000100",
            "product_interest": "Bulk Rice",
            "quantity": 0,
        })
        assert response.status_code == 400

    def test_create_rfq_negative_quantity(self, client, db):
        response = client.post("/rfq/", json={
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "email": "rfq@test.com",
            "phone": "+255700000100",
            "product_interest": "Bulk Rice",
            "quantity": -5,
        })
        assert response.status_code == 400


class TestListRFQs:
    def test_admin_lists_rfqs(self, client, db, admin_user):
        rfq = RFQ(
            company_name="Test Company",
            contact_name="John Doe",
            email="rfq@test.com",
            phone="+255700000100",
            product_interest="Bulk Rice",
            quantity=100,
            status="New",
        )
        db.add(rfq)
        db.commit()
        db.refresh(rfq)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/rfq/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_rfqs_empty(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/rfq/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestFilterRFQsByStatus:
    def test_filter_rfqs_by_status(self, client, db, admin_user):
        rfq_new = RFQ(
            company_name="New Company",
            contact_name="New Contact",
            email="new@test.com",
            phone="+255700000200",
            product_interest="New Product",
            quantity=50,
            status="New",
        )
        db.add(rfq_new)

        rfq_quoted = RFQ(
            company_name="Quoted Company",
            contact_name="Quoted Contact",
            email="quoted@test.com",
            phone="+255700000201",
            product_interest="Quoted Product",
            quantity=30,
            status="Quoted",
        )
        db.add(rfq_quoted)
        db.commit()

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/rfq/?status=New", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert all(rfq["status"] == "New" for rfq in data)

    def test_filter_rfqs_invalid_status(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/rfq/?status=invalid", headers=auth_header(token))
        assert response.status_code == 400


class TestUpdateRFQStatus:
    def test_update_rfq_status(self, client, db, admin_user):
        rfq = RFQ(
            company_name="Test Company",
            contact_name="John Doe",
            email="rfq@test.com",
            phone="+255700000100",
            product_interest="Bulk Rice",
            quantity=100,
            status="New",
        )
        db.add(rfq)
        db.commit()
        db.refresh(rfq)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/rfq/{rfq.id}/status", json={
            "status": "Quoted",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Quoted"

    def test_update_rfq_invalid_status(self, client, db, admin_user):
        rfq = RFQ(
            company_name="Test Company",
            contact_name="John Doe",
            email="rfq@test.com",
            phone="+255700000100",
            product_interest="Bulk Rice",
            quantity=100,
            status="New",
        )
        db.add(rfq)
        db.commit()
        db.refresh(rfq)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.patch(f"/rfq/{rfq.id}/status", json={
            "status": "invalid",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_update_nonexistent_rfq(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.patch("/rfq/99999/status", json={
            "status": "Quoted",
        }, headers=auth_header(token))
        assert response.status_code == 404