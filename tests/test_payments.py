import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, Order, OrderItem, PaymentTransaction, PaymentAttempt, DeliveryOrder
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


class TestInitiatePayment:
    def test_buyer_initiates_payment(self, client, db, buyer_user, product, seller_user):
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
            order_id=None,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/payments/initiate", json={
            "order_id": sale.id,
            "amount": 10000.0,
            "payment_method": "mpesa",
            "phone_number": "+255700000300",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "transaction_id" in data
        assert data["status"] == "pending"

    def test_payment_wrong_amount(self, client, db, buyer_user, product, seller_user):
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

        response = client.post("/payments/initiate", json={
            "order_id": sale.id,
            "amount": 99999.0,
            "payment_method": "mpesa",
            "phone_number": "+255700000300",
        }, headers=auth_header(token))
        assert response.status_code == 400

    def test_payment_nonexistent_order(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/payments/initiate", json={
            "order_id": 99999,
            "amount": 100.0,
            "payment_method": "mpesa",
            "phone_number": "+255700000300",
        }, headers=auth_header(token))
        assert response.status_code == 404

    def test_user_cannot_pay_for_other_users_order(self, client, db, buyer_user, product, seller_user):
        other_buyer = User(
            name="Other Buyer",
            email="other_buyer@test.com",
            phone="+255700000900",
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

        response = client.post("/payments/initiate", json={
            "order_id": sale.id,
            "amount": 10000.0,
            "payment_method": "mpesa",
            "phone_number": "+255700000300",
        }, headers=auth_header(token))
        assert response.status_code == 403

    def test_cannot_pay_cancelled_order(self, client, db, buyer_user, product, seller_user):
        sale = Sale(
            date=date.today(),
            product=product.name,
            category=product.category,
            product_id=product.id,
            seller_id=seller_user.id,
            quantity=2,
            unit_price=product.price,
            status="Cancelled",
            created_by=buyer_user.id,
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/payments/initiate", json={
            "order_id": sale.id,
            "amount": 10000.0,
            "payment_method": "mpesa",
            "phone_number": "+255700000300",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestSTKPushPayment:
    def test_stk_push_without_provider_credentials_fails_safely(self, client, db, buyer_user, product, seller_user):
        """With no real M-Pesa credentials configured (the default in tests/dev),
        the push must fail loudly rather than pretend the customer paid."""
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

        response = client.post("/payments/mobile-money/stk-push", params={
            "phone_number": "+255700000300",
            "amount": 10000.0,
            "order_id": sale.id,
        }, headers=auth_header(token))
        assert response.status_code == 502

        # The transaction row should exist and be marked failed, not silently dropped.
        txn = db.query(PaymentTransaction).filter(PaymentTransaction.order_id == sale.id).first()
        assert txn is not None
        assert txn.status == "failed"

    def test_stk_push_then_webhook_completes_payment(self, client, db, buyer_user, product, seller_user, monkeypatch):
        """End-to-end: push succeeds (mocked provider) -> stays 'processing' ->
        webhook confirms -> transaction and order both flip to completed/Confirmed."""
        from backend.app.payment_providers import base as provider_base
        from backend.app.payment_providers import mpesa_service

        def fake_push_payment(self, *, phone_number, amount, reference, description):
            return provider_base.PushResult(accepted=True, provider_reference=reference, raw_response={"ok": True})

        def fake_parse_webhook(self, headers, body):
            import json
            payload = json.loads(body)
            return provider_base.WebhookResult(
                provider_reference=payload["input_TransactionReference"],
                our_transaction_id=None,
                status="completed",
                provider_receipt="MPESA-RECEIPT-1",
                message="Payment confirmed",
                raw_payload=payload,
            )

        monkeypatch.setattr(mpesa_service.MpesaProvider, "push_payment", fake_push_payment)
        monkeypatch.setattr(mpesa_service.MpesaProvider, "parse_webhook", fake_parse_webhook)

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

        push_response = client.post("/payments/mobile-money/stk-push", params={
            "phone_number": "+255700000300",
            "amount": 10000.0,
            "order_id": sale.id,
        }, headers=auth_header(token))
        assert push_response.status_code == 200
        push_data = push_response.json()
        assert push_data["status"] == "processing"
        transaction_id = push_data["transaction_id"]

        webhook_response = client.post(
            "/payments/webhook/mpesa",
            content=__import__("json").dumps({
                "input_TransactionReference": transaction_id,
                "output_ResponseCode": "INS-0",
            }),
        )
        assert webhook_response.status_code == 200
        assert webhook_response.json()["ack"] == "received"
        assert webhook_response.json()["result"]["transaction_status"] == "completed"

        db.expire_all()
        txn = db.query(PaymentTransaction).filter(PaymentTransaction.transaction_id == transaction_id).first()
        assert txn.status == "completed"
        sale_after = db.query(Sale).filter(Sale.id == sale.id).first()
        assert sale_after.status == "Confirmed"

    def test_stk_push_invalid_provider(self, client, db, buyer_user, product, seller_user):
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

        response = client.post("/payments/mobile-money/stk-push", params={
            "phone_number": "+255700000300",
            "amount": 10000.0,
            "order_id": sale.id,
            "provider": "invalid_provider",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestConfirmTransaction:
    def test_admin_confirms_payment(self, client, db, buyer_user, product, seller_user):
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

        txn = PaymentTransaction(
            transaction_id="TXN-TEST123",
            order_id=sale.id,
            payer_type="user",
            payer_id=buyer_user.id,
            amount=10000.0,
            payment_method="mpesa",
            provider="mpesa",
            phone_number="+255700000300",
            status="pending",
            message="Payment initiated",
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/payments/transaction/{txn.transaction_id}/confirm", json={
            "status": "completed",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_confirm_invalid_status(self, client, db, buyer_user, product, seller_user):
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

        txn = PaymentTransaction(
            transaction_id="TXN-TEST456",
            order_id=sale.id,
            payer_type="user",
            payer_id=buyer_user.id,
            amount=10000.0,
            payment_method="mpesa",
            provider="mpesa",
            phone_number="+255700000300",
            status="pending",
            message="Payment initiated",
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

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

        login = login_as(client, "admin@test.com", "AdminPass1!")
        token = login.json()["access_token"]

        response = client.post(f"/payments/transaction/{txn.transaction_id}/confirm", json={
            "status": "invalid_status",
        }, headers=auth_header(token))
        assert response.status_code == 400


class TestGetTransaction:
    def test_get_transaction_status(self, client, db, buyer_user, product, seller_user):
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

        txn = PaymentTransaction(
            transaction_id="TXN-STATUS-TEST",
            order_id=sale.id,
            payer_type="user",
            payer_id=buyer_user.id,
            amount=10000.0,
            payment_method="mpesa",
            provider="mpesa",
            phone_number="+255700000300",
            status="completed",
            message="Payment completed",
            confirmed_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get(f"/payments/transaction/{txn.transaction_id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == txn.transaction_id
        assert data["status"] == "completed"


class TestPaymentHistory:
    def test_payment_history_authenticated(self, client, db, buyer_user, product, seller_user):
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

        txn = PaymentTransaction(
            transaction_id="TXN-HISTORY-TEST",
            order_id=sale.id,
            payer_type="user",
            payer_id=buyer_user.id,
            amount=10000.0,
            payment_method="mpesa",
            provider="mpesa",
            phone_number="+255700000300",
            status="completed",
            message="Payment completed",
            confirmed_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/payments/history", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data


class TestMpesaWebhook:
    def test_mpesa_webhook_with_unknown_reference_is_acked_but_ignored(self, client, db):
        """Providers retry aggressively on non-2xx, so an unrecognized callback
        (e.g. a stale/duplicate one) should still get a 200 -- just marked ignored
        rather than mistakenly applied to some transaction."""
        response = client.post("/payments/webhook/mpesa")
        assert response.status_code == 200
        body = response.json()
        assert body["ack"] == "received"
        assert body["result"]["status"] == "ignored"


class TestPaymentMethods:
    def test_get_payment_methods(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/payments/methods", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "payment_methods" in data
        assert len(data["payment_methods"]) > 0

    def test_get_public_payment_methods(self, client, db):
        response = client.get("/payments/methods/public")
        assert response.status_code == 200
        data = response.json()
        assert "payment_methods" in data
        for method in data["payment_methods"]:
            assert method.get("enabled", True) is True