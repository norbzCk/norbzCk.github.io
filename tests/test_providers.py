import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, Provider
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


class TestListProviders:
    def test_admin_lists_providers(self, client, db, admin_user):
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

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/providers/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_providers_empty(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/providers/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestGetProviderProfile:
    def test_get_provider_exists(self, client, db, admin_user):
        provider = Provider(
            name="Profile Provider",
            location="Dar es Salaam",
            email="profile@test.com",
            phone="+255700000401",
            verified=True,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get(f"/providers/{provider.id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Profile Provider"

    def test_get_nonexistent_provider(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.get("/providers/99999", headers=auth_header(token))
        assert response.status_code == 404


class TestCreateProvider:
    def test_admin_creates_provider(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/providers/", json={
            "name": "New Provider",
            "location": "Dar es Salaam",
            "email": "newprovider@test.com",
            "phone": "+255700000402",
            "verified": True,
            "response_time": "< 6 hrs",
            "min_order_qty": "100 pcs",
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Provider"

    def test_admin_creates_provider_short_name(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/providers/", json={
            "name": "A",
            "location": "Dar es Salaam",
            "email": "shortname@test.com",
            "phone": "+255700000403",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_admin_creates_provider_no_name(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post("/providers/", json={
            "name": "",
            "location": "Dar es Salaam",
            "email": "noname@test.com",
            "phone": "+255700000404",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestUpdateProvider:
    def test_admin_updates_provider(self, client, db, admin_user):
        provider = Provider(
            name="Original Name",
            location="Dar es Salaam",
            email="original@test.com",
            phone="+255700000405",
            verified=False,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.put(f"/providers/{provider.id}", json={
            "name": "Updated Name",
            "location": "Urgently",
            "email": "updated@test.com",
            "phone": "+255700000406",
            "verified": True,
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_admin_updates_nonexistent_provider(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.put("/providers/99999", json={
            "name": "Nonexistent",
        }, headers=auth_header(token))
        assert response.status_code == 404


class TestDeleteProvider:
    def test_admin_deletes_provider(self, client, db, admin_user):
        provider = Provider(
            name="To Delete",
            location="Dar es Salaam",
            email="delete@test.com",
            phone="+255700000407",
            verified=True,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.delete(f"/providers/{provider.id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower()

    def test_admin_deletes_nonexistent_provider(self, client, db, admin_user):
        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.delete("/providers/99999", headers=auth_header(token))
        assert response.status_code == 404


class TestPublicProviders:
    def test_public_providers_list(self, client, db):
        provider = Provider(
            name="Public Provider",
            location="Dar es Salaam",
            email="public@test.com",
            phone="+255700000408",
            verified=True,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        response = client.get("/providers/public")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)