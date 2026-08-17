from backend.models import User, BusinessUser, LogisticsUser, Product, Provider, Sale, Order, OrderItem, PaymentTransaction, DeliveryOrder, Dispute, RFQ, Notification, BusinessMetrics, LogisticsMetrics, InventoryReservation, ConversationThread, ConversationMessage
from backend.app.auth import hash_password
from datetime import date, datetime


class UserFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+255700000100",
            "password_hash": hash_password("TestPass1!"),
            "role": "user",
            "is_active": True,
        }
        defaults.update(kwargs)
        user = User(**defaults)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


class BusinessUserFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "business_name": "Test Business",
            "owner_name": "Business Owner",
            "phone": "+255700000200",
            "email": "business@test.com",
            "password_hash": hash_password("TestPass1!"),
            "business_type": "individual",
            "category": "Groceries",
            "region": "Dar es Salaam",
            "role": "seller",
            "is_active": True,
            "verification_status": "verified",
        }
        defaults.update(kwargs)
        business = BusinessUser(**defaults)
        db.add(business)
        db.commit()
        db.refresh(business)
        metrics = BusinessMetrics(business_id=business.id)
        db.add(metrics)
        db.commit()
        return business


class LogisticsUserFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "name": "Test Rider",
            "phone": "+255700000400",
            "email": "logistics@test.com",
            "password_hash": hash_password("TestPass1!"),
            "account_type": "individual",
            "vehicle_type": "motorcycle",
            "status": "online",
            "availability": "available",
            "verification_status": "verified",
            "is_active": True,
        }
        defaults.update(kwargs)
        logistics = LogisticsUser(**defaults)
        db.add(logistics)
        db.commit()
        db.refresh(logistics)
        metrics = LogisticsMetrics(logistics_id=logistics.id)
        db.add(metrics)
        db.commit()
        return logistics


class ProductFactory:
    @staticmethod
    def create(db, seller_id=None, **kwargs):
        defaults = {
            "name": "Test Product",
            "category": "Groceries",
            "price": 5000.0,
            "stock": 100,
            "description": "A test product",
            "seller_id": seller_id,
            "is_active": True,
        }
        defaults.update(kwargs)
        product = Product(**defaults)
        db.add(product)
        db.commit()
        db.refresh(product)
        return product


class ProviderFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "name": "Test Provider",
            "location": "Dar es Salaam",
            "email": "provider@test.com",
            "phone": "+255700000400",
            "verified": True,
        }
        defaults.update(kwargs)
        provider = Provider(**defaults)
        db.add(provider)
        db.commit()
        db.refresh(provider)
        return provider


class SaleFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "date": date.today(),
            "product": "Test Sale",
            "category": "Groceries",
            "quantity": 2,
            "unit_price": 5000.0,
            "status": "Received",
        }
        defaults.update(kwargs)
        sale = Sale(**defaults)
        db.add(sale)
        db.commit()
        db.refresh(sale)
        return sale


class DisputeFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "sale_id": 1,
            "buyer_id": 1,
            "seller_id": 1,
            "status": "open",
            "resolution_details": "Test dispute",
        }
        defaults.update(kwargs)
        dispute = Dispute(**defaults)
        db.add(dispute)
        db.commit()
        db.refresh(dispute)
        return dispute


class RFQFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "email": "rfq@test.com",
            "phone": "+255700000100",
            "product_interest": "Bulk Rice",
            "quantity": 100,
            "status": "New",
        }
        defaults.update(kwargs)
        rfq = RFQ(**defaults)
        db.add(rfq)
        db.commit()
        db.refresh(rfq)
        return rfq


class NotificationFactory:
    @staticmethod
    def create(db, **kwargs):
        defaults = {
            "recipient_type": "user",
            "recipient_id": 1,
            "recipient_email": "test@example.com",
            "title": "Test Notification",
            "message": "Test message",
            "notification_type": "system",
            "severity": "info",
        }
        defaults.update(kwargs)
        notification = Notification(**defaults)
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification