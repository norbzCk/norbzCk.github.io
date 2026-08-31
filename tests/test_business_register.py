import io

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base, BusinessUser
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


VALID_PAYLOAD = {
    "business_name": "Kilimo Fresh Produce",
    "owner_name": "Amina Hassan",
    "phone": "0712345678",
    "email": "amina@example.com",
    "password": "SecurePass1!",
    "region": "Dar es Salaam",
}


class TestBusinessRegister:
    def test_register_success_returns_working_seller_session(self, client, db):
        """The core bug this file guards against: registering as a seller
        must issue a token whose role claim actually says 'seller', not a
        leftover customer token from an earlier broken two-step flow."""
        response = client.post("/business/register", data=VALID_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["userType"] == "business"
        assert data["user"]["role"] == "seller"

        # The returned token must actually authorize seller-only actions --
        # not just claim role="seller" in the response body while the JWT
        # itself encodes something else.
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me = client.get("/business/me", headers=headers)
        assert me.status_code == 200

        # And must NOT have created a stray plain-customer User row as a
        # side effect (the old two-step flow's first step did exactly this).
        from backend.models import User
        stray_customer = db.query(User).filter(User.phone == "+255712345678").first()
        assert stray_customer is None

    def test_register_with_logo_upload(self, client, db, monkeypatch):
        # save_uploaded_image now uploads to Supabase Storage, which needs
        # real SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY credentials and a
        # network call -- neither belongs in this test. Mock the function
        # itself so this test verifies OUR code (does register_business
        # correctly wire a provided file through to shop_logo_url) rather
        # than re-testing Supabase's own upload API.
        async def fake_save_uploaded_image(file):
            return "https://fake-supabase-url.test/storage/v1/object/public/product-images/logo.png"

        monkeypatch.setattr("backend.app.business.save_uploaded_image", fake_save_uploaded_image)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
        files = {"logo": ("logo.png", io.BytesIO(fake_png), "image/png")}
        data = {**VALID_PAYLOAD, "phone": "0712345679", "email": "logo@example.com"}
        response = client.post("/business/register", data=data, files=files)
        assert response.status_code == 200
        assert response.json()["user"]["shop_logo_url"] == "https://fake-supabase-url.test/storage/v1/object/public/product-images/logo.png"

    def test_register_rejects_non_image_logo(self, client, db):
        files = {"logo": ("not-an-image.txt", io.BytesIO(b"hello"), "text/plain")}
        data = {**VALID_PAYLOAD, "phone": "0712345680", "email": "badfile@example.com"}
        response = client.post("/business/register", data=data, files=files)
        assert response.status_code == 400

    def test_register_weak_password_rejected(self, client, db):
        data = {**VALID_PAYLOAD, "phone": "0712345681", "email": "weak@example.com", "password": "weak"}
        response = client.post("/business/register", data=data)
        assert response.status_code == 400

    def test_register_invalid_phone_rejected(self, client, db):
        data = {**VALID_PAYLOAD, "phone": "123", "email": "badphone@example.com"}
        response = client.post("/business/register", data=data)
        assert response.status_code == 400

    def test_register_duplicate_phone_rejected(self, client, db):
        client.post("/business/register", data=VALID_PAYLOAD)
        response = client.post("/business/register", data={**VALID_PAYLOAD, "email": "different@example.com"})
        assert response.status_code == 400

    def test_register_duplicate_email_rejected(self, client, db):
        client.post("/business/register", data=VALID_PAYLOAD)
        response = client.post("/business/register", data={**VALID_PAYLOAD, "phone": "0712345682"})
        assert response.status_code == 400

    def test_register_ignores_client_supplied_role(self, client, db):
        """Security regression test: the old schema had role: str = "seller"
        as a client-controllable field with no server-side restriction on a
        public, unauthenticated endpoint -- anyone could have POSTed
        role="super_admin" and gotten a working super_admin session."""
        data = {**VALID_PAYLOAD, "phone": "0712345683", "email": "escalation@example.com", "role": "super_admin"}
        response = client.post("/business/register", data=data)
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "seller"

    def test_register_short_business_name_rejected(self, client, db):
        data = {**VALID_PAYLOAD, "phone": "0712345684", "email": "shortname@example.com", "business_name": "A"}
        response = client.post("/business/register", data=data)
        assert response.status_code == 400

    def test_register_without_email_still_works(self, client, db):
        """Unlike customer registration, email is optional for sellers."""
        data = {k: v for k, v in VALID_PAYLOAD.items() if k != "email"}
        data["phone"] = "0712345685"
        response = client.post("/business/register", data=data)
        assert response.status_code == 200
        assert response.json()["user"]["email"] is None
