from pathlib import Path
import os
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.app.auth import hash_password, require_roles, router as auth_router, limiter
from backend.app.ai_assistant import router as ai_assistant_router
from backend.app.notification_service import create_notification, resolve_subject
from backend.database import engine, get_db, SessionLocal
from backend.app.products import router as products_router
from backend.app.customers import router as customers_router
from backend.app.sales import router as sales_router
from backend.app.rfq import router as rfq_router
from backend.app.providers import router as providers_router
from backend.app.payments import router as payments_router
from backend.app.business import router as business_router
from backend.app.logistics import router as logistics_router
from backend.app.notifications import router as notifications_router
from backend.app.disputes import router as disputes_router
from backend.models import Base, User, BusinessMetrics, BusinessUser, LogisticsMetrics, LogisticsUser, Product, Provider, Sale
from datetime import date
from fastapi.staticfiles import StaticFiles
from backend.app.marketplace_intelligence import build_marketplace_trends, build_superadmin_overview


from backend.app.dashboard import dashboard_analytics, dashboard_stats, get_recent_sales, revenue_by_product, revenue_over_time
from fastapi.middleware.cors import CORSMiddleware

frontend_dist_dir = Path(__file__).parent.parent.parent / "frontend-react" / "dist"

def _ensure_schema_columns():
    from sqlalchemy import text, inspect
    from backend.database import engine
    
    is_sqlite = 'sqlite' in str(engine.url)
    
    with engine.connect() as conn:
        def table_exists(table_name):
            if is_sqlite:
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")).fetchall()
                return len(result) > 0
            else:
                result = conn.execute(text(f"""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = '{table_name}'
                """)).fetchall()
                return len(result) > 0

        def column_exists(table_name, column_name):
            if not table_exists(table_name):
                return False
            if is_sqlite:
                result = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
                return any(row[1] == column_name for row in result)
            else:
                result = conn.execute(text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = '{table_name}' AND column_name = '{column_name}'
                """)).fetchall()
                return len(result) > 0
        
        def add_column_if_not_exists(table_name, column_name, column_def):
            if not column_exists(table_name, column_name):
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
                conn.commit()
        
        # Lightweight schema patching for existing databases (no Alembic yet).
        add_column_if_not_exists("sales", "created_by", "created_by INTEGER")

        # Supabase Auth integration columns
        add_column_if_not_exists("users", "supabase_uid", "supabase_uid VARCHAR")
        add_column_if_not_exists("business_users", "supabase_uid", "supabase_uid VARCHAR")
        add_column_if_not_exists("logistics_users", "supabase_uid", "supabase_uid VARCHAR")

        # Product catalog: allow storing picture URL per item.
        add_column_if_not_exists("products", "image_url", "image_url VARCHAR")
        add_column_if_not_exists("products", "rating_avg", "rating_avg DOUBLE PRECISION DEFAULT 0")
        add_column_if_not_exists("products", "rating_count", "rating_count INTEGER DEFAULT 0")
        add_column_if_not_exists("products", "provider_id", "provider_id INTEGER")

        add_column_if_not_exists("sales", "product_id", "product_id INTEGER")
        add_column_if_not_exists("sales", "status", "status VARCHAR DEFAULT 'Received'")
        add_column_if_not_exists("sales", "rating", "rating INTEGER")
        add_column_if_not_exists("sales", "rated_at", "rated_at TIMESTAMPTZ")

        add_column_if_not_exists("sales", "provider_id", "provider_id INTEGER")
        add_column_if_not_exists("sales", "provider_name", "provider_name VARCHAR")
        add_column_if_not_exists("sales", "delivery_address", "delivery_address VARCHAR")
        add_column_if_not_exists("sales", "delivery_phone", "delivery_phone VARCHAR")
        add_column_if_not_exists("sales", "delivery_notes", "delivery_notes VARCHAR")
        add_column_if_not_exists("sales", "delivery_method", "delivery_method VARCHAR DEFAULT 'Standard'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — create all tables first, then patch any missing columns
    # For remote databases (e.g. Supabase), skip create_all — it's slow over
    # the network and Alembic migrations manage the schema.  The
    # _ensure_schema_columns() safety-net still runs to patch any drift.
    is_remote = engine.url.drivername == "postgresql" and engine.url.host not in (
        "localhost", "127.0.0.1", "0.0.0.0", "::1"
    )
    if not is_remote:
        Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()
    # Seed demo data and ensure there are sample sales for analytics
    db = SessionLocal()
    try:
        seed_marketplace_demo_data(db)
        if db.query(Sale).count() == 0:
            demo_products = db.query(Product).filter(Product.seller_id.isnot(None)).limit(5).all()
            sample_sales = []
            for product in demo_products:
                sample_sales.append(
                    Sale(
                        date=date.today(),
                        product=product.name,
                        category=product.category,
                        product_id=product.id,
                        seller_id=product.seller_id,
                        quantity=2,
                        unit_price=product.price,
                        status="Received",
                        rating=5,
                    )
                )
            db.add_all(sample_sales)
            db.commit()
    finally:
        db.close()
    yield
    # Shutdown - add any cleanup here if needed


app = FastAPI(lifespan=lifespan)



def _parse_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        origins = [origin.replace("+origin", "") for origin in [os.environ.get("FRONTEND_URL", "")] if origin]
    return origins


_cors_origins = _parse_cors_origins()
_has_wildcard = "*" in _cors_origins or not _cors_origins
_allow_origins = [o for o in _cors_origins if o != "*"] if not _has_wildcard else ["*"]
_allow_origin_regex = r"https?://.*" if _has_wildcard else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_origin_regex=_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Mount static files for uploads
uploads_dir = Path(__file__).parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


def seed_marketplace_demo_data(db: Session) -> None:
    if db.query(Product).filter(Product.is_active.isnot(False)).count() > 0:
        return

    demo_sellers = [
        {
            "business_name": "Kariakoo Fresh Hub",
            "owner_name": "Amina Salim",
            "phone": "+255700100001",
            "email": "seller1@sokolink.local",
            "region": "Dar es Salaam",
            "area": "Kariakoo",
            "street": "Msimbazi Street",
            "category": "Fresh Produce",
        },
        {
            "business_name": "Coastal Home Supplies",
            "owner_name": "Juma Mushi",
            "phone": "+255700100002",
            "email": "seller2@sokolink.local",
            "region": "Dar es Salaam",
            "area": "Ilala",
            "street": "Uhuru Street",
            "category": "Household",
        },
    ]
    sellers: list[BusinessUser] = []
    for entry in demo_sellers:
        existing = db.query(BusinessUser).filter(BusinessUser.phone == entry["phone"]).first()
        if existing:
            sellers.append(existing)
            continue
        model = BusinessUser(
            business_name=entry["business_name"],
            owner_name=entry["owner_name"],
            phone=entry["phone"],
            email=entry["email"],
            password_hash=hash_password("demo12345"),
            business_type="individual",
            category=entry["category"],
            region=entry["region"],
            area=entry["area"],
            street=entry["street"],
            role="seller",
            is_active=True,
            verification_status="verified",
        )
        db.add(model)
        db.flush()
        db.add(BusinessMetrics(business_id=model.id))
        sellers.append(model)

    provider = db.query(Provider).filter(Provider.name == "SokoLink Demo Supplier").first()
    if not provider:
        provider = Provider(
            name="SokoLink Demo Supplier",
            location="Dar es Salaam",
            email="supplier@sokolink.local",
            phone="+255700100010",
            verified=True,
            response_time="< 3 hrs",
            min_order_qty="20 units",
        )
        db.add(provider)
        db.flush()

    # Category-based placeholder images
    CATEGORY_PLACEHOLDERS = {
        "Groceries": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=600&q=80",
        "Electronics": "https://images.unsplash.com/photo-1550009158-9ebf69173e03?auto=format&fit=crop&w=600&q=80",
        "Household": "https://images.unsplash.com/photo-1493809842364-78817add7ffb?auto=format&fit=crop&w=600&q=80",
        "Fashion": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=600&q=80",
        "Accessory": "https://images.unsplash.com/photo-1463171379579-3fdfb86d6285?auto=format&fit=crop&w=600&q=80",
        "Footwear": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=600&q=80",
        "Bags": "https://images.unsplash.com/photo-1590874103328-27cf28d6c78a?auto=format&fit=crop&w=600&q=80",
        "Shoes": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=600&q=80",
        "Office": "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=600&q=80",
        "Official Clothes": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=600&q=80",
        "Furniture": "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=600&q=80",
        "stationery": "https://images.unsplash.com/photo-1533613790285-ccb864783284?auto=format&fit=crop&w=600&q=80",
        "Electronic": "https://images.unsplash.com/photo-1550009158-9ebf69173e03?auto=format&fit=crop&w=600&q=80",
        "cloth": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=600&q=80",
        "women bag": "https://images.unsplash.com/photo-1590874103328-27cf28d6c78a?auto=format&fit=crop&w=600&q=80",
    }
    
    demo_products = [
        {
            "name": "Premium Rice 25kg",
            "category": "Groceries",
            "price": 69000,
            "stock": 44,
            "description": "Long grain rice sourced for retail and wholesale orders.",
            "seller_idx": 0,
        },
        {
            "name": "Sunflower Cooking Oil 5L",
            "category": "Groceries",
            "price": 26500,
            "stock": 62,
            "description": "Refined cooking oil for households and restaurants.",
            "seller_idx": 1,
        },
        {
            "name": "Laundry Soap Bar Pack",
            "category": "Household",
            "price": 12000,
            "stock": 90,
            "description": "Durable multipurpose soap bars in bulk-friendly packs.",
            "seller_idx": 1,
        },
    ]
    for entry in demo_products:
        if db.query(Product).filter(Product.name == entry["name"]).first():
            continue
        seller = sellers[entry["seller_idx"]] if sellers else None
        db.add(
            Product(
                name=entry["name"],
                category=entry["category"],
                price=entry["price"],
                stock=entry["stock"],
                description=entry["description"],
                seller_id=seller.id if seller else None,
                provider_id=provider.id if provider else None,
                is_active=True,
            )
        )
    
    # Add products with images for categories that have uploaded images
    image_products = [
        ("Handbag", "Accessory", 1, "/uploads/74eeeddc54eb48cb931252a116bc5148.jpeg"),
        ("Sandals", "footwear", 6, "/uploads/d6f7031c161848f4b68a03f5bb834759.png"),
        ("Backpack", "Bags", 1, "/uploads/542a938ed44c4e6481cccb41b0db31dd.png"),
        ("Dress Shoes", "Shoes", 1, "/uploads/17865ee571754740a1c4065da623cd0c.jpeg"),
        ("Belt", "Accessory", 1, "/uploads/848c262a4baf46e7909db12a425e2946.jpeg"),
        ("Sandals", "footwear", 6, "/uploads/cc6b73616aa3477383baf7ba3968cf54.jpeg"),
        ("Hand bag", "women bag", 6, "/uploads/68fdc12706da4850ba89669b2e04dd67.jpeg"),
        ("Briefcase", "Office", 1, "/uploads/d5a6aef2ece94f3d891836030027f8d1.jpeg"),
        ("Monochrome Men's Outfit", "Fashion", 2, "/uploads/7221f94f97284faa8dc914f91d7a012c.jpeg"),
        ("Laptopbag", "bags", 1, "/uploads/3aefe98958804f51ac8a9c807b1172db.jpeg"),
        ("Men Suit", "Official Clothes", 2, "/uploads/b4622c6199f548d2b50dfd15c7ff7acc.jpeg"),
        ("Men's Fashion", "Fashion", 2, "/uploads/1a93f907d5ca4f21bb5bbef8d4534722.jpeg"),
    ]
    for name, category, seller_idx, image_url in image_products:
        if db.query(Product).filter(Product.name == name).first():
            continue
        seller = sellers[seller_idx] if seller_idx < len(sellers) else None
        db.add(
            Product(
                name=name,
                category=category,
                price=25000,
                stock=10,
                description=f"High quality {category} product.",
                image_url=image_url,
                seller_id=seller.id if seller else None,
                is_active=True,
            )
        )

    db.commit()

    # Ensure all products have sellers assigned
    ensure_product_seller_assignments(db)

    # Seed sample sales if none exist (for dashboard graphs)
    if db.query(Sale).count() == 0:
        sample_sales = []
        # Get a few products with sellers
        demo_products = db.query(Product).filter(Product.seller_id.isnot(None)).limit(5).all()
        for product in demo_products:
            sample_sales.append(
                Sale(
                    date=date.today(),
                    product=product.name,
                    category=product.category,
                    product_id=product.id,
                    seller_id=product.seller_id,
                    quantity=2,
                    unit_price=product.price,
                    status="Received",
                    rating=5,
                )
            )
        db.add_all(sample_sales)
        db.commit()


def ensure_product_seller_assignments(db: Session) -> None:
    """
    Ensure all active products have a seller_id assigned. Products without a seller
    are assigned to the first available seller in their category, or deactivated
    if no suitable seller exists.
    """
    # Find active products without seller_id
    products_without_seller = db.query(Product).filter(
        Product.is_active.isnot(False),
        Product.seller_id.is_(None)
    ).all()
    
    if not products_without_seller:
        return
    
    # Get all active sellers
    sellers = db.query(BusinessUser).filter(
        BusinessUser.is_active == True,
        BusinessUser.role == "seller"
    ).all()
    
    # Build category -> seller mapping
    category_to_sellers = {}
    for seller in sellers:
        cat = seller.category or ""
        if cat not in category_to_sellers:
            category_to_sellers[cat] = []
        category_to_sellers[cat].append(seller)
    
    # Also build category mapping from products that already have sellers
    product_category_to_seller = {}
    assigned_products = db.query(Product).filter(
        Product.is_active.isnot(False),
        Product.seller_id.isnot(None)
    ).all()
    for p in assigned_products:
        cat = p.category or ""
        if cat and cat not in product_category_to_seller and p.seller_id:
            seller = db.query(BusinessUser).filter(BusinessUser.id == p.seller_id).first()
            if seller:
                
                product_category_to_seller[cat] = seller
    
    for product in products_without_seller:
        cat = product.category or ""
        seller = None
        
        # Try category-based assignment
        if cat and cat in product_category_to_seller:
            seller = product_category_to_seller[cat]
        elif cat and cat in category_to_sellers and category_to_sellers[cat]:
            seller = category_to_sellers[cat][0]
        # Try any available seller
        elif sellers:
            seller = sellers[0]
        
        if seller:
            product.seller_id = seller.id
            db.add(product)
            print(f"  Assigned product '{product.name}' (category: {cat}) to seller '{seller.business_name}'")
        else:
            # No seller available - deactivate product
            product.is_active = False
            db.add(product)
            print(f"  Deactivated product '{product.name}' - no seller available")
    
    db.commit()
    print(f"  Completed: {len(products_without_seller)} products processed")








app.include_router(products_router)
app.include_router(customers_router)
app.include_router(sales_router)
app.include_router(rfq_router)
app.include_router(providers_router)
app.include_router(payments_router)
app.include_router(business_router)
app.include_router(logistics_router)
app.include_router(notifications_router)
app.include_router(auth_router)
app.include_router(ai_assistant_router)
app.include_router(disputes_router)


@app.get("/marketplace/trends")
def marketplace_trends(db: Session = Depends(get_db)):
    return build_marketplace_trends(db)


@app.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection check failed: {str(e)}"
        )


@app.get("/superadmin/stats")
def superadmin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    return build_superadmin_overview(db)


@app.get("/superadmin/me")
def superadmin_me(
    current: User = Depends(require_roles("super_admin", "owner")),
):
    return {
        "id": current.id,
        "name": current.name,
        "email": current.email,
        "role": current.role,
        "is_active": current.is_active,
    }


@app.get("/superadmin/businessmen")
def superadmin_businessmen(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    items = db.query(BusinessUser).order_by(BusinessUser.created_at.desc(), BusinessUser.id.desc()).all()
    return [
        {
            "id": item.id,
            "business_name": item.business_name,
            "owner_name": item.owner_name,
            "email": item.email,
            "phone": item.phone,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


@app.post("/superadmin/businessmen", status_code=201)
def create_superadmin_businessman(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    business_name = (payload.get("business_name") or "").strip()
    owner_name = (payload.get("owner_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip().lower() or None
    password = payload.get("password") or ""

    if len(business_name) < 2 or len(owner_name) < 2:
        raise HTTPException(status_code=400, detail="Business name and owner name are required")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    if email and "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing_phone = db.query(BusinessUser).filter(BusinessUser.phone == phone).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    if email:
        existing_email = db.query(BusinessUser).filter(text("lower(email) = :email")).params(email=email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")

    model = BusinessUser(
        business_name=business_name,
        owner_name=owner_name,
        phone=phone,
        email=email,
        password_hash=hash_password(password),
        business_type=(payload.get("business_type") or "individual").strip() or "individual",
        category=(payload.get("category") or "").strip() or None,
        description=(payload.get("description") or "").strip() or None,
        region=(payload.get("region") or "Dar es Salaam").strip() or "Dar es Salaam",
        area=(payload.get("area") or "").strip() or None,
        street=(payload.get("street") or "").strip() or None,
        shop_number=(payload.get("shop_number") or "").strip() or None,
        operating_hours=(payload.get("operating_hours") or "").strip() or None,
        shop_logo_url=(payload.get("shop_logo_url") or "").strip() or None,
        shop_images=(payload.get("shop_images") or "").strip() or None,
        profile_photo=(payload.get("profile_photo") or "").strip() or None,
        website_url=(payload.get("website_url") or "").strip() or None,
        social_facebook=(payload.get("social_facebook") or "").strip() or None,
        social_instagram=(payload.get("social_instagram") or "").strip() or None,
        social_whatsapp=(payload.get("social_whatsapp") or "").strip() or None,
        social_x=(payload.get("social_x") or "").strip() or None,
        role="seller",
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    db.add(BusinessMetrics(business_id=model.id))
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(model)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="A business account was created for you",
        message="Your SokoLnk seller account has been created by an administrator. You can now sign in and manage your storefront.",
        notification_type="system",
        severity="success",
        action_href="/login",
        send_email=bool(recipient_email),
        email_subject="Your SokoLnk seller account is ready",
        email_body=f"Hello {recipient_name},\n\nAn administrator created your seller account. You can sign in and start using SokoLnk.\n\nSokoLnk Team",
        background_tasks=background_tasks,
    )
    db.commit()

    return {
        "id": model.id,
        "business_name": model.business_name,
        "owner_name": model.owner_name,
        "email": model.email,
        "phone": model.phone,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


@app.get("/superadmin/customers")
def superadmin_customers(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    items = (
        db.query(User)
        .filter(User.role == "user")
        .order_by(User.created_at.desc(), User.id.desc())
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "email": item.email,
            "phone": item.phone,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


@app.post("/superadmin/customers", status_code=201)
def create_superadmin_customer(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    phone = (payload.get("phone") or "").strip() or None
    password = payload.get("password") or ""

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name is required")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    model = User(
        name=name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(model)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="A customer account was created for you",
        message="Your SokoLnk buyer account has been created by an administrator.",
        notification_type="system",
        severity="success",
        action_href="/login",
        send_email=bool(recipient_email),
        email_subject="Your SokoLnk buyer account is ready",
        email_body=f"Hello {recipient_name},\n\nAn administrator created your buyer account.\n\nSokoLnk Team",
        background_tasks=background_tasks,
    )
    db.commit()

    return {
        "id": model.id,
        "name": model.name,
        "email": model.email,
        "phone": model.phone,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


@app.get("/superadmin/logistics")
def superadmin_logistics(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    items = db.query(LogisticsUser).order_by(LogisticsUser.created_at.desc(), LogisticsUser.id.desc()).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "email": item.email,
            "phone": item.phone,
            "account_type": item.account_type,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


@app.get("/superadmin/verifications")
def superadmin_verifications(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    sellers = (
        db.query(BusinessUser)
        .order_by(BusinessUser.verification_status.asc(), BusinessUser.created_at.desc(), BusinessUser.id.desc())
        .all()
    )
    logistics_items = (
        db.query(LogisticsUser)
        .order_by(LogisticsUser.verification_status.asc(), LogisticsUser.created_at.desc(), LogisticsUser.id.desc())
        .all()
    )
    return {
        "businessmen": [
            {
                "id": item.id,
                "business_name": item.business_name,
                "owner_name": item.owner_name,
                "phone": item.phone,
                "email": item.email,
                "category": item.category,
                "region": item.region,
                "area": item.area,
                "verification_status": item.verification_status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in sellers
        ],
        "logistics": [
            {
                "id": item.id,
                "name": item.name,
                "phone": item.phone,
                "email": item.email,
                "vehicle_type": item.vehicle_type,
                "base_area": item.base_area,
                "coverage_areas": item.coverage_areas,
                "verification_status": item.verification_status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in logistics_items
        ],
    }


@app.patch("/superadmin/businessmen/{business_id}/verification")
def update_superadmin_business_verification(
    business_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    item = db.query(BusinessUser).filter(BusinessUser.id == business_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Business account not found")

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"verified", "pending", "rejected", "unverified"}:
        raise HTTPException(status_code=400, detail="Invalid verification status")

    item.verification_status = status
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "message": "Business verification updated",
        "id": item.id,
        "verification_status": item.verification_status,
    }


@app.patch("/superadmin/logistics/{logistics_id}/verification")
def update_superadmin_logistics_verification(
    logistics_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    item = db.query(LogisticsUser).filter(LogisticsUser.id == logistics_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Logistics account not found")

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"verified", "pending", "rejected", "unverified"}:
        raise HTTPException(status_code=400, detail="Invalid verification status")

    item.verification_status = status
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "message": "Logistics verification updated",
        "id": item.id,
        "verification_status": item.verification_status,
    }


@app.post("/superadmin/logistics", status_code=201)
def create_superadmin_logistics(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower() or None
    phone = (payload.get("phone") or "").strip()
    password = payload.get("password") or ""

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name is required")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    if email and "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing_phone = db.query(LogisticsUser).filter(LogisticsUser.phone == phone).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    if email:
        existing_email = db.query(LogisticsUser).filter(text("lower(email) = :email")).params(email=email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")

    model = LogisticsUser(
        name=name,
        phone=phone,
        email=email,
        password_hash=hash_password(password),
        account_type=(payload.get("account_type") or "individual").strip() or "individual",
        vehicle_type=(payload.get("vehicle_type") or "").strip() or None,
        plate_number=(payload.get("plate_number") or "").strip() or None,
        license_number=(payload.get("license_number") or "").strip() or None,
        base_area=(payload.get("base_area") or "").strip() or None,
        coverage_areas=(payload.get("coverage_areas") or "").strip() or None,
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    db.add(LogisticsMetrics(logistics_id=model.id))
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(model)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="A logistics account was created for you",
        message="Your SokoLnk delivery account has been created by an administrator.",
        notification_type="system",
        severity="success",
        action_href="/login",
        send_email=bool(recipient_email),
        email_subject="Your SokoLnk delivery account is ready",
        email_body=f"Hello {recipient_name},\n\nAn administrator created your delivery account.\n\nSokoLnk Team",
        background_tasks=background_tasks,
    )
    db.commit()

    return {
        "id": model.id,
        "name": model.name,
        "email": model.email,
        "phone": model.phone,
        "account_type": model.account_type,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


@app.delete("/superadmin/businessmen/{business_id}")
def delete_superadmin_businessman(
    business_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    item = db.query(BusinessUser).filter(BusinessUser.id == business_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Business account not found")
    db.delete(item)
    db.commit()
    return {"message": "Business account deleted"}


@app.delete("/superadmin/customers/{customer_id}")
def delete_superadmin_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    item = db.query(User).filter(User.id == customer_id, User.role == "user").first()
    if not item:
        raise HTTPException(status_code=404, detail="Customer account not found")
    db.delete(item)
    db.commit()
    return {"message": "Customer account deleted"}


@app.delete("/superadmin/logistics/{logistics_id}")
def delete_superadmin_logistics(
    logistics_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin", "owner")),
):
    item = db.query(LogisticsUser).filter(LogisticsUser.id == logistics_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Logistics account not found")
    db.delete(item)
    db.commit()
    return {"message": "Logistics account deleted"}



@app.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    return dashboard_stats(db, current)

@app.get("/dashboard/revenue-product")
def get_revenue_product(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    return revenue_by_product(db, current)

@app.get("/dashboard/revenue-time")
def get_revenue_time(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    return revenue_over_time(db, current)

@app.get("/dashboard/recent-sales")
def recent_sales(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    return get_recent_sales(db, current)

@app.get("/dashboard/analytics")
def get_dashboard_analytics(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    return dashboard_analytics(db, current)

@app.get("/dashboard/market-insights")
def get_market_insights(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    from backend.analysis.sales_analysis import market_insights, pricing_insights, demand_forecast, peak_sales_periods, customer_buying_patterns
    return {
        "market": market_insights(db),
        "pricing": pricing_insights(db),
        "demand": demand_forecast(db),
        "peak_periods": peak_sales_periods(db),
        "customer_patterns": customer_buying_patterns(db)
    }

@app.get("/dashboard/export-sales")
def export_sales_report(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from backend.models import Sale

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Date", "Product", "Category", "Quantity", "Unit Price", "Total", "Status"])

    sales = db.query(Sale).order_by(Sale.date.desc()).all()
    for s in sales:
        writer.writerow([
            s.id,
            s.date.isoformat() if s.date else "",
            s.product,
            s.category,
            s.quantity,
            s.unit_price,
            (s.quantity or 0) * (s.unit_price or 0),
            s.status
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_report.csv"}
    )


@app.get("/", include_in_schema=False)
def serve_frontend_root():
    if frontend_dist_dir.exists():
        return FileResponse(frontend_dist_dir / "index.html")
    raise HTTPException(status_code=404, detail="Frontend build not found")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_app(full_path: str):
    if not frontend_dist_dir.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")

    requested_path = (frontend_dist_dir / full_path).resolve()
    try:
        requested_path.relative_to(frontend_dist_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Not Found")

    if requested_path.is_file():
        return FileResponse(requested_path)

    return FileResponse(frontend_dist_dir / "index.html")
