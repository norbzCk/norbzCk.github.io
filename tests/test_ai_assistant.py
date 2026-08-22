import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, AssistantConversation, AssistantConversationMessage
from backend.app.ai_assistant import AssistantHistoryItem
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


class TestGeminiProvider:
    def test_gemini_tried_first_and_falls_back_cleanly_on_failure(self, client, db, monkeypatch):
        """With Gemini 'configured' but failing (bad key/unreachable), the
        request should still succeed via fallback -- never a 500/502 to the
        end user just because one provider is down."""
        from backend.app import ai_assistant as m

        monkeypatch.setattr(m, "_gemini_client", object())  # truthy, so the Gemini path is attempted

        def fake_call_gemini(*args, **kwargs):
            raise __import__("fastapi").HTTPException(status_code=502, detail="Gemini provider unavailable: mocked failure")

        monkeypatch.setattr(m, "_call_gemini", fake_call_gemini)

        response = client.post("/ai/assistant", json={
            "message": "hi there",
            "current_path": "/",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "fallback"
        assert data["reply"]

    def test_gemini_success_path_is_used_and_stored(self, client, db, monkeypatch):
        from backend.app import ai_assistant as m

        monkeypatch.setattr(m, "_gemini_client", object())

        def fake_call_gemini(message, history, area, user_context, market_context, tool_context):
            return "Hello! I'm the Soko-Link customer service assistant. How can I help?", "gemini-3.7-flash"

        monkeypatch.setattr(m, "_call_gemini", fake_call_gemini)

        response = client.post("/ai/assistant", json={
            "message": "hi",
            "current_path": "/",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "gemini"
        assert data["model"] == "gemini-3.7-flash"
        assert "Soko-Link" in data["reply"]

        # Confirm it persisted correctly and history round-trips.
        history_response = client.get(f"/ai/assistant/history/{data['conversation_id']}")
        assert history_response.status_code == 200
        messages = history_response.json()["messages"]
        assert messages[-1]["text"] == data["reply"]


class TestAssistantReply:
    def test_assistant_reply_creates_conversation(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/ai/assistant", json={
            "message": "Hello, I need help with my order",
            "current_path": "/app/orders",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "conversation_id" in data
        assert data["source"] in ("openai", "fallback")

    def test_assistant_reply_greeting(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/ai/assistant", json={
            "message": "Hello there",
            "current_path": "/",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    def test_assistant_reply_product_query(self, client, db, buyer_user, product):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/ai/assistant", json={
            "message": "I want to buy Test Product",
            "current_path": "/products",
        }, headers=auth_header(token))
        assert response.status_code == 200

    def test_assistant_reply_settings_query(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/ai/assistant", json={
            "message": "How do I change my password",
            "current_path": "/app/settings",
        }, headers=auth_header(token))
        assert response.status_code == 200

    def test_assistant_reply_with_history(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/ai/assistant", json={
            "message": "What should I reply to the seller?",
            "current_path": "/app/orders",
            "history": [
                {"role": "user", "text": "Hello"},
                {"role": "assistant", "text": "Hi there"},
            ],
        }, headers=auth_header(token))
        assert response.status_code == 200


class TestAssistantHistory:
    def test_get_conversation_history(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        create_resp = client.post("/ai/assistant", json={
            "message": "Test message",
            "current_path": "/",
        }, headers=auth_header(token))
        conversation_id = create_resp.json()["conversation_id"]

        response = client.get(f"/ai/assistant/history/{conversation_id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert data["conversation_id"] == conversation_id

    def test_get_nonexistent_conversation(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/ai/assistant/history/nonexistent-conv", headers=auth_header(token))
        assert response.status_code == 404


class TestAssistantConversationOwnership:
    def test_user_cannot_access_other_conversation(self, client, db, buyer_user):
        other_user = User(
            name="Other User",
            email="other@test.com",
            phone="+255700000999",
            password_hash=hash_password("TestPass1!"),
            role="user",
            is_active=True,
            is_verified=True,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        conv = AssistantConversation(
            id="other-conv-123",
            subject_type="user",
            subject_id=other_user.id,
            title="Other conversation",
        )
        db.add(conv)
        db.commit()

        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/ai/assistant/history/other-conv-123", headers=auth_header(token))
        assert response.status_code == 403


def test_prompt_history_ignores_welcome_and_route_noise():
    from backend.app import ai_assistant as m

    history = [
        AssistantHistoryItem(role="assistant", text="I’m your SokoLink assistant. I’m available throughout the app to help with products, orders, account tasks, and the next step whenever you need support."),
        AssistantHistoryItem(role="assistant", text="You’re now in the products page. I’ll keep my help focused on what matters here."),
        AssistantHistoryItem(role="user", text="Where is my order?"),
        AssistantHistoryItem(role="assistant", text="Your most recent order is in transit."),
    ]

    filtered = m._filter_prompt_history(history)

    assert filtered == [
        AssistantHistoryItem(role="user", text="Where is my order?"),
        AssistantHistoryItem(role="assistant", text="Your most recent order is in transit."),
    ]