import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.database import SessionLocal, engine, Base
from backend.models import User, BusinessUser, LogisticsUser, Product, Provider, Sale, BusinessMetrics


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_user(db_session):
    user = User(
        name="Test User",
        email="test@example.com",
        phone="+255700000001",
        password_hash="hashed_password",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_business(db_session):
    business = BusinessUser(
        business_name="Test Business",
        owner_name="Test Owner",
        phone="+255700000002",
        email="business@example.com",
        password_hash="hashed_password",
        business_type="individual",
        category="Groceries",
        region="Dar es Salaam",
        role="seller",
        is_active=True,
        verification_status="verified",
    )
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    metrics = BusinessMetrics(business_id=business.id)
    db_session.add(metrics)
    db_session.commit()
    return business


@pytest.fixture
def test_logistics(db_session):
    logistics = LogisticsUser(
        name="Test Rider",
        phone="+255700000003",
        email="logistics@example.com",
        password_hash="hashed_password",
        account_type="individual",
        vehicle_type="motorcycle",
        status="online",
        availability="available",
        verification_status="verified",
        is_active=True,
    )
    db_session.add(logistics)
    db_session.commit()
    db_session.refresh(logistics)
    return logistics


@pytest.fixture
def test_provider(db_session):
    provider = Provider(
        name="Test Supplier",
        location="Dar es Salaam",
        email="supplier@example.com",
        phone="+255700000004",
        verified=True,
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture
def test_product(db_session, test_business):
    product = Product(
        name="Test Product",
        category="Groceries",
        price=5000.0,
        stock=100,
        description="A test product",
        seller_id=test_business.id,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_sale(db_session, test_business, test_product):
    sale = Sale(
        date="2026-01-15",
        product="Test Product",
        category="Groceries",
        quantity=2,
        unit_price=5000.0,
        status="Received",
        seller_id=test_business.id,
        product_id=test_product.id,
    )
    db_session.add(sale)
    db_session.commit()
    db_session.refresh(sale)
    return sale