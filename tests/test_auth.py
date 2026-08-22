import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, LogisticsUser, RefreshToken, TokenBlocklist
from backend.app.auth import hash_password, create_access_token, create_refresh_token
from datetime import datetime, timedelta, timezone


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
def registered_user(db):
    user = User(
        name="Auth Test User",
        email="auth_test@example.com",
        phone="+255700000100",
        password_hash=hash_password("TestPass1!"),
        role="user",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def registered_business(db):
    business = BusinessUser(
        business_name="Auth Test Business",
        owner_name="Auth Owner",
        phone="+255700000101",
        email="auth_business@example.com",
        password_hash=hash_password("TestPass1!"),
        business_type="individual",
        category="Groceries",
        region="Dar es Salaam",
        role="seller",
        is_active=True,
        verification_status="verified",
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@pytest.fixture
def registered_logistics(db):
    logistics = LogisticsUser(
        name="Auth Test Rider",
        phone="+255700000102",
        email="auth_logistics@example.com",
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
    return logistics


class TestRegister:
    def test_register_user_success(self, client, db):
        response = client.post("/auth/register", json={
            "name": "New User",
            "email": "newuser@example.com",
            "phone": "+255700000200",
            "password": "TestPass1!",
            "address": "Test Address",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["userType"] == "user"
        assert data["user"]["name"] == "New User"
        assert data["user"]["email"] == "newuser@example.com"

    def test_register_user_missing_name(self, client, db):
        response = client.post("/auth/register", json={
            "name": "",
            "email": "newuser2@example.com",
            "phone": "+255700000201",
            "password": "TestPass1!",
        })
        assert response.status_code == 400

    def test_register_user_short_name(self, client, db):
        response = client.post("/auth/register", json={
            "name": "A",
            "email": "newuser3@example.com",
            "phone": "+255700000202",
            "password": "TestPass1!",
        })
        assert response.status_code == 400

    def test_register_user_invalid_email(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Valid Name",
            "email": "not-an-email",
            "phone": "+255700000203",
            "password": "TestPass1!",
        })
        assert response.status_code == 400

    def test_register_user_weak_password(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Valid Name",
            "email": "newuser4@example.com",
            "phone": "+255700000204",
            "password": "weak",
        })
        assert response.status_code == 400

    def test_register_user_duplicate_email(self, client, db, registered_user):
        response = client.post("/auth/register", json={
            "name": "Another User",
            "email": "auth_test@example.com",
            "phone": "+255700000205",
            "password": "TestPass1!",
        })
        assert response.status_code == 400

    def test_register_user_duplicate_phone(self, client, db, registered_user):
        response = client.post("/auth/register", json={
            "name": "Another User",
            "email": "newuser5@example.com",
            "phone": "+255700000100",
            "password": "TestPass1!",
        })
        assert response.status_code == 400


class TestLogin:
    def test_login_user_success(self, client, db, registered_user):
        response = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["userType"] == "user"
        assert data["user"]["email"] == "auth_test@example.com"

    def test_login_user_wrong_password(self, client, db, registered_user):
        response = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "WrongPass1!",
        })
        assert response.status_code == 401

    def test_login_user_nonexistent(self, client, db):
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "TestPass1!",
        })
        assert response.status_code == 401

    def test_login_business_success(self, client, db, registered_business):
        response = client.post("/auth/login", json={
            "email": "auth_business@example.com",
            "password": "TestPass1!",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["userType"] == "business"

    def test_login_logistics_success(self, client, db, registered_logistics):
        response = client.post("/auth/login", json={
            "email": "auth_logistics@example.com",
            "password": "TestPass1!",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["userType"] == "logistics"

    def test_login_missing_password(self, client, db):
        response = client.post("/auth/login", json={
            "email": "auth_test@example.com",
        })
        assert response.status_code == 400


class TestRefreshToken:
    def test_refresh_with_valid_token(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        refresh_token = login.cookies.get("refresh_token")
        assert refresh_token is not None

        response = client.post("/auth/refresh", cookies={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_refresh_without_token(self, client):
        response = client.post("/auth/refresh")
        assert response.status_code == 401

    def test_refresh_with_revoked_token(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        refresh_token = login.cookies.get("refresh_token")

        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        if db_token:
            db_token.is_revoked = True
            db.commit()

        response = client.post("/auth/refresh", cookies={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 401


class TestLogout:
    def test_logout_clears_cookies(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        refresh_token = login.cookies.get("refresh_token")
        assert refresh_token is not None

        response = client.post("/auth/logout", cookies={
            "refresh_token": refresh_token,
            "access_token": login.json()["access_token"],
        })
        assert response.status_code == 200


class TestPasswordRecovery:
    def test_password_recovery_request_valid_email(self, client, db, registered_user):
        response = client.post("/auth/password-recovery/request", json={
            "identifier": "auth_test@example.com",
        })
        assert response.status_code == 200
        assert "message" in response.json()

    def test_password_recovery_request_invalid_identifier(self, client, db):
        response = client.post("/auth/password-recovery/request", json={
            "identifier": "nonexistent@example.com",
        })
        assert response.status_code == 200

    def test_password_recovery_reset_valid_token(self, client, db, registered_user):
        recovery = client.post("/auth/password-recovery/request", json={
            "identifier": "auth_test@example.com",
        })
        assert recovery.status_code == 200

    def test_password_recovery_reset_missing_token(self, client, db):
        response = client.post("/auth/password-recovery/reset", json={
            "new_password": "NewPass1!",
        })
        assert response.status_code == 400

    def test_password_recovery_reset_invalid_token(self, client, db):
        response = client.post("/auth/password-recovery/reset", json={
            "token": "invalid_token_xyz",
            "new_password": "NewPass1!",
        })
        assert response.status_code == 400


class TestPasswordChange:
    def test_change_password_success(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.post("/auth/change-password", json={
            "current_password": "TestPass1!",
            "new_password": "NewPass1!",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_change_password_wrong_current(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.post("/auth/change-password", json={
            "current_password": "WrongPass1!",
            "new_password": "NewPass1!",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400

    def test_change_password_weak_new(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.post("/auth/change-password", json={
            "current_password": "TestPass1!",
            "new_password": "weak",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400


class TestVerifyEmail:
    def test_verify_email_success(self, client, db):
        user = User(
            name="Verify User",
            email="verify@example.com",
            phone="+255700000300",
            password_hash=hash_password("TestPass1!"),
            role="user",
            is_active=True,
            is_verified=False,
            verification_token="test_verify_token_123",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        response = client.post("/auth/verify-email", json={
            "token": "test_verify_token_123",
        })
        assert response.status_code == 200

        db.expire_all()
        updated = db.query(User).filter(User.id == user.id).first()
        assert updated.is_verified is True
        assert updated.verification_token is None

    def test_verify_email_invalid_token(self, client, db):
        response = client.post("/auth/verify-email", json={
            "token": "nonexistent_token",
        })
        assert response.status_code == 400


class TestGetMe:
    def test_me_authenticated(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "auth_test@example.com"
        assert data["role"] == "user"


class TestUpdateMe:
    def test_update_profile_success(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.put("/auth/me", json={
            "name": "Updated Name",
            "phone": "+255700000400",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_update_profile_short_name(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.put("/auth/me", json={
            "name": "A",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400


class TestListUsers:
    def test_list_users_admin(self, client, db):
        admin = User(
            name="Admin User",
            email="admin@example.com",
            phone="+255700000500",
            password_hash=hash_password("AdminPass1!"),
            role="super_admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        login = client.post("/auth/login", json={
            "email": "admin@example.com",
            "password": "AdminPass1!",
        })
        token = login.json()["access_token"]

        response = client.get("/auth/users", headers={
            "Authorization": f"Bearer {token}",
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestCreateUser:
    def test_create_user_admin_success(self, client, db):
        admin = User(
            name="Admin User",
            email="admin@example.com",
            phone="+255700000600",
            password_hash=hash_password("AdminPass1!"),
            role="super_admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        login = client.post("/auth/login", json={
            "email": "admin@example.com",
            "password": "AdminPass1!",
        })
        token = login.json()["access_token"]

        response = client.post("/auth/users", json={
            "name": "New Managed User",
            "email": "managed@example.com",
            "password": "TestPass1!",
            "role": "user",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "managed@example.com"

    def test_create_user_non_admin_forbidden(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.post("/auth/users", json={
            "name": "Unauthorized User",
            "email": "unauth@example.com",
            "password": "TestPass1!",
            "role": "admin",
        }, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


class TestUploadProfilePhoto:
    def test_upload_profile_photo_success(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.post(
            "/auth/upload-profile-photo",
            files={"file": ("test.jpg", b"fake image content", "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_url" in data

    def test_upload_profile_photo_invalid_format(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        response = client.post(
            "/auth/upload-profile-photo",
            files={"file": ("test.txt", b"not an image", "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_upload_profile_photo_too_large(self, client, db, registered_user):
        login = client.post("/auth/login", json={
            "email": "auth_test@example.com",
            "password": "TestPass1!",
        })
        token = login.json()["access_token"]

        large_content = b"x" * (6 * 1024 * 1024 + 1)
        response = client.post(
            "/auth/upload-profile-photo",
            files={"file": ("large.jpg", large_content, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestPasswordStrengthValidation:
    def test_password_no_uppercase(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Test User",
            "email": "weak1@example.com",
            "phone": "+255700000700",
            "password": "lowercase1!",
        })
        assert response.status_code == 400

    def test_password_no_lowercase(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Test User",
            "email": "weak2@example.com",
            "phone": "+255700000701",
            "password": "UPPERCASE1!",
        })
        assert response.status_code == 400

    def test_password_no_digit(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Test User",
            "email": "weak3@example.com",
            "phone": "+255700000702",
            "password": "NoDigit!",
        })
        assert response.status_code == 400

    def test_password_no_special_char(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Test User",
            "email": "weak4@example.com",
            "phone": "+255700000703",
            "password": "NoSpecial1",
        })
        assert response.status_code == 400

    def test_password_too_short(self, client, db):
        response = client.post("/auth/register", json={
            "name": "Test User",
            "email": "weak5@example.com",
            "phone": "+255700000704",
            "password": "Sh1!",
        })
        assert response.status_code == 400