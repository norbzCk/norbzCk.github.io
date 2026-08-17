import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models import User, BusinessUser, Product, Provider, Sale, BusinessMetrics, Order, OrderItem
from backend.app.auth import hash_password, create_access_token
from backend.app.notification_service import create_notification, resolve_subject


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
def buyer_user(db):
    buyer = User(
        name="Buyer User",
        email="buyer@test.com",
        phone="+255700000300",
        password_hash=hash_password("TestPass1!"),
        role="user",
        is_active=True,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


@pytest.fixture
def provider(db):
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
    return provider


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


class TestProductCreate:
    def test_seller_create_product(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/products/", json={
            "name": "New Product",
            "category": "Groceries",
            "price": 3000.0,
            "stock": 50,
            "description": "A new product",
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Product created"
        assert data["product"]["name"] == "New Product"

    def test_seller_create_product_with_provider(self, client, db, seller_user, provider):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/products/", json={
            "name": "Provider Product",
            "category": "Groceries",
            "price": 7000.0,
            "stock": 30,
            "description": "Product from provider",
            "provider_id": provider.id,
        }, headers=auth_header(token))
        assert response.status_code == 201
        data = response.json()
        assert data["product"]["provider_id"] == provider.id

    def test_seller_create_product_missing_name(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/products/", json={
            "name": "",
            "category": "Groceries",
            "price": 3000.0,
            "stock": 50,
        }, headers=auth_header(token))
        assert response.status_code == 422

    def test_seller_create_product_negative_price(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/products/", json={
            "name": "Bad Price Product",
            "category": "Groceries",
            "price": -100.0,
            "stock": 50,
        }, headers=auth_header(token))
        assert response.status_code == 422

    def test_non_seller_cannot_create_product(self, client, db, buyer_user):
        login = login_as(client, "buyer@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/products/", json={
            "name": "Unauthorized Product",
            "category": "Groceries",
            "price": 3000.0,
            "stock": 50,
        }, headers=auth_header(token))
        assert response.status_code == 403


class TestProductList:
    def test_list_products_authenticated(self, client, db, seller_user, product):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/products/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_products_public(self, client, db, product):
        response = client.get("/products/public")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestProductGet:
    def test_get_product_exists(self, client, db, product):
        response = client.get(f"/products/{product.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Product"

    def test_get_product_not_found(self, client, db):
        response = client.get("/products/99999")
        assert response.status_code == 404


class TestProductUpdate:
    def test_seller_update_own_product(self, client, db, seller_user, product):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put(f"/products/{product.id}", json={
            "name": "Updated Product",
            "category": "Groceries",
            "price": 6000.0,
            "stock": 80,
            "description": "Updated description",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["product"]["name"] == "Updated Product"
        assert data["product"]["price"] == 6000.0

    def test_seller_update_other_sellers_product(self, client, db, seller_user, product):
        other_seller = BusinessUser(
            business_name="Other Seller",
            owner_name="Other Owner",
            phone="+255700000500",
            email="other@test.com",
            password_hash=hash_password("TestPass1!"),
            business_type="individual",
            category="Groceries",
            region="Dar es Salaam",
            role="seller",
            is_active=True,
            verification_status="verified",
        )
        db.add(other_seller)
        db.commit()
        db.refresh(other_seller)

        login = login_as(client, "other@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put(f"/products/{product.id}", json={
            "name": "Hacked Product",
            "category": "Groceries",
            "price": 1.0,
            "stock": 1,
            "description": "Hacked description",
        }, headers=auth_header(token))
        assert response.status_code == 403


class TestProductDelete:
    def test_seller_deactivate_own_product(self, client, db, seller_user, product):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.delete(f"/products/{product.id}", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Product deactivated"

        db.expire_all()
        updated = db.query(Product).filter(Product.id == product.id).first()
        assert updated.is_active is False


class TestProductSearch:
    def test_search_products_by_name(self, client, db, product):
        response = client.get("/products/public/search", params={"q": "Test"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_search_products_by_category(self, client, db, product):
        response = client.get("/products/public/search", params={"category": "Groceries"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_search_products_price_range(self, client, db, product):
        response = client.get("/products/public/search", params={
            "min_price": 1000.0,
            "max_price": 10000.0,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_search_products_sort_price_low(self, client, db, product):
        response = client.get("/products/public/search", params={"sort": "price_low"})
        assert response.status_code == 200


class TestProductCategories:
    def test_get_public_categories(self, client, db, product):
        response = client.get("/products/public/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "Groceries" in data["categories"]


class TestProductImageUpload:
    def test_upload_product_image(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(
            "/products/upload-image",
            files={"file": ("test.jpg", b"fake image content", "image/jpeg")},
            headers=auth_header(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_url" in data

    def test_upload_invalid_format(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(
            "/products/upload-image",
            files={"file": ("test.txt", b"not an image", "text/plain")},
            headers=auth_header(token),
        )
        assert response.status_code == 400

    def test_upload_empty_file(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post(
            "/products/upload-image",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
            headers=auth_header(token),
        )
        assert response.status_code == 400


class TestCartOptimization:
    def test_cart_optimization_empty(self, client, db):
        response = client.post("/products/cart-optimization", json={"items": []})
        assert response.status_code == 200
        data = response.json()
        assert data["recommendations"] == []

    def test_cart_optimization_with_items(self, client, db, product):
        response = client.post("/products/cart-optimization", json={
            "items": [
                {"product_id": product.id, "quantity": 2},
            ]
        })
        assert response.status_code == 200


class TestInventoryStats:
    def test_inventory_stats_authenticated(self, client, db, seller_user, product):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/products/inventory/stats", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["total_products"] >= 1
        assert "low_stock_count" in data
        assert "out_of_stock_count" in data


class TestAISuggest:
    def test_ai_suggest_authenticated(self, client, db, seller_user):
        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.post("/products/ai-suggest", json={
            "name": "Organic Rice",
            "category": "Groceries",
            "current_price": 5000.0,
            "stock": 100,
            "description": "Premium organic rice",
            "seller_area": "Kariakoo",
        }, headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert "description" in data
        assert "suggested_price" in data
        assert "seo_keywords" in data


class TestProductOwnerCheck:
    def test_seller_cannot_update_other_sellers_product(self, client, db, seller_user, product):
        other_seller = BusinessUser(
            business_name="Other Seller",
            owner_name="Other Owner",
            phone="+255700000600",
            email="other@test.com",
            password_hash=hash_password("TestPass1!"),
            business_type="individual",
            category="Groceries",
            region="Dar es Salaam",
            role="seller",
            is_active=True,
            verification_status="verified",
        )
        db.add(other_seller)
        db.commit()
        db.refresh(other_seller)

        login = login_as(client, "other@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.put(f"/products/{product.id}", json={
            "name": "Hacked",
            "category": "Groceries",
            "price": 1.0,
            "stock": 1,
            "description": "Hacked description",
        }, headers=auth_header(token))
        assert response.status_code == 403


class TestProductSellerFiltering:
    def test_seller_only_sees_own_products(self, client, db, seller_user, product):
        other_seller = BusinessUser(
            business_name="Other Seller",
            owner_name="Other Owner",
            phone="+255700000700",
            email="other2@test.com",
            password_hash=hash_password("TestPass1!"),
            business_type="individual",
            category="Electronics",
            region="Dar es Salaam",
            role="seller",
            is_active=True,
            verification_status="verified",
        )
        db.add(other_seller)
        other_product = Product(
            name="Other Product",
            category="Electronics",
            price=10000.0,
            stock=10,
            description="Other sellers product",
            seller_id=other_seller.id,
            is_active=True,
        )
        db.add(other_product)
        db.commit()

        login = login_as(client, "seller@test.com", "TestPass1!")
        token = login.json()["access_token"]

        response = client.get("/products/", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        product_names = [p["name"] for p in data]
        assert "Test Product" in product_names
        assert "Other Product" not in product_names