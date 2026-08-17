import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, Customer
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
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def login_as(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestListCustomers:
    def test_admin_lists_customers(self, client, db, admin_user):
        customer = User(
            name="Customer User",
            email="customer@test.com",
            phone="+255700000300",
            password_hash=hash_password("TestPass1!"),
            role="user",
            is_active=True,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/customers", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestCreateCustomer:
    def test_admin_creates_customer(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/superadmin/customers", json={
            "name": "New Customer",
            "email": "newcustomer@test.com",
            "phone": "+255700000400",
            "password": "TestPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Customer"
        assert data["email"] == "newcustomer@test.com"

    def test_admin_creates_customer_missing_name(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/superadmin/customers", json={
            "name": "",
            "email": "badcustomer@test.com",
            "phone": "+255700000401",
            "password": "TestPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_admin_creates_customer_invalid_email(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/superadmin/customers", json={
            "name": "Bad Email Customer",
            "email": "not-an-email",
            "phone": "+255700000402",
            "password": "TestPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_admin_creates_customer_duplicate_email(self, client, db, admin_user):
        existing = User(
            name="Existing",
            email="existing@test.com",
            phone="+255700000403",
            password_hash=hash_password("TestPass1!"),
            role="user",
            is_active=True,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/superadmin/customers", json={
            "name": "Duplicate",
            "email": "existing@test.com",
            "phone": "+255700000404",
            "password": "TestPass1!",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_admin_creates_customer_short_password(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/superadmin/customers", json={
            "name": "Short Pass Customer",
            "email": "shortpass@test.com",
            "phone": "+255700000405",
            "password": "short",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestDeleteCustomer:
    def test_admin_deletes_customer(self, client, db, admin_user):
        customer = User(
            name="To Delete",
            email="delete@test.com",
            phone="+255700000500",
            password_hash=hash_password("TestPass1!"),
            role="user",
            is_active=True,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.delete(f"/superadmin/customers/{customer.id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower()

    def test_admin_deletes_nonexistent_customer(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.delete("/superadmin/customers/99999", headers=auth_header(token))
        assert response.status_code == 404


class TestCustomerCRUD:
    def test_customer_list_empty(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/superadmin/customers", headers=auth_header(token))
        assert response.status_code == 200
        assert response.json() == []

    def test_customer_create_and_list(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        create_resp = client.post("/superadmin/customers", json={
            "name": "CRUD Customer",
            "email": "crud@test.com",
            "phone": "+255700000600",
            "password": "TestPass1!",
        }, headers=auth_header(token))
        assert create_resp.status_code == 201

        list_resp = client.get("/superadmin/customers", headers=auth_header(token))
        assert list_resp.status_code == 200
        customers = list_resp.json()
        assert len(customers) >= 1