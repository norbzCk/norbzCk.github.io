import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from backend.app.auth import get_current_user, require_roles
from backend.database import get_db
from backend.app.marketplace_intelligence import (
    build_ai_product_insight,
    build_cart_optimization,
    compute_seller_badges,
    refresh_business_metrics,
)
from backend.models import BusinessUser, Product, Provider, User, BusinessMetrics
from backend.app.schemas import (
    ProductCreate, ProductSearchQuery, 
    AISuggestRequest, AISuggestResponse
)

router = APIRouter(prefix="/products", tags=["Products"])
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@router.post("/ai-suggest", response_model=AISuggestResponse)
def get_ai_product_suggestion(
    payload: AISuggestRequest,
    db: Session = Depends(get_db),
    _: User | BusinessUser = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    return build_ai_product_insight(db, payload)


def _serialize_provider(provider: Provider | None) -> dict | None:
    if not provider:
        return None
    return {
        "id": provider.id,
        "name": provider.name,
        "location": provider.location,
        "email": provider.email,
        "phone": provider.phone,
        "verified": provider.verified,
        "response_time": provider.response_time,
        "min_order_qty": provider.min_order_qty,
    }


def _serialize_seller(db: Session, seller: BusinessUser | None, metrics: BusinessMetrics | None = None) -> dict | None:
    if not seller:
        return None

    return {
        "id": seller.id,
        "business_name": seller.business_name,
        "owner_name": seller.owner_name,
        "phone": seller.phone,
        "email": seller.email,
        "region": seller.region,
        "area": seller.area,
        "street": seller.street,
        "verification_status": seller.verification_status,
        "badges": compute_seller_badges(db, seller, metrics),
    }


def _serialize_product(
    db: Session,
    product: Product,
    provider: Provider | None,
    seller: BusinessUser | None = None,
    metrics: BusinessMetrics | None = None,
) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "price": product.price,
        "stock": product.stock,
        "description": product.description,
        "image_url": product.image_url,
        "seller_id": product.seller_id,
        "is_active": bool(product.is_active) if product.is_active is not None else True,
        "provider_id": product.provider_id,
        "provider": _serialize_provider(provider),
        "seller": _serialize_seller(db, seller, metrics),
        "seller_name": seller.business_name if seller else None,
        "rating_avg": product.rating_avg or 0,
        "rating_count": product.rating_count or 0,
    }


def _serialize_public_product(
    db: Session,
    product: Product,
    provider: Provider | None,
    seller: BusinessUser | None = None,
    metrics: BusinessMetrics | None = None,
) -> dict:
    data = _serialize_product(db, product, provider, seller, metrics)
    data["in_stock"] = bool((product.stock or 0) > 0)
    return data


def _is_seller(current: User | BusinessUser) -> bool:
    return str(getattr(current, "role", "")).strip().lower() == "seller"


def _is_admin(current: User | BusinessUser) -> bool:
    return str(getattr(current, "role", "")).strip().lower() in {"admin", "super_admin", "owner"}


def _ensure_product_owner(product: Product, current: User | BusinessUser):
    if not _is_seller(current):
        return
    if int(product.seller_id or 0) != int(getattr(current, "id", 0)):
        raise HTTPException(status_code=403, detail="Product does not belong to this seller")


@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    _: User | BusinessUser = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    destination = uploads_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    destination.write_bytes(content)
    return {"image_url": f"/uploads/{filename}"}

@router.get("/")
def get_products(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Seller/admin management view -- unlike /marketplace and /public, this
    intentionally does NOT hide inactive (soft-deleted) products: a seller
    managing their own catalog needs to see deactivated items to reactivate
    them, not have them disappear. Only customer-facing endpoints filter by
    is_active."""
    query = db.query(Product)
    if _is_seller(current):
        query = query.filter(Product.seller_id == current.id)
    elif not _is_admin(current):
        # A plain customer role hitting this management endpoint (shouldn't
        # normally happen from the frontend, but don't leak inactive
        # products to them if it does).
        query = query.filter(Product.is_active.isnot(False))
    products = query.order_by(Product.id.desc()).all()
    providers = {p.id: p for p in db.query(Provider).all()}
    sellers = {s.id: s for s in db.query(BusinessUser).all()}
    metrics = {m.business_id: m for m in db.query(BusinessMetrics).all()}
    return [_serialize_product(db, p, providers.get(p.provider_id), sellers.get(p.seller_id), metrics.get(p.seller_id)) for p in products]


@router.get("/public")
def get_public_products(
    db: Session = Depends(get_db),
):
    items = (
        db.query(Product)
        .filter(Product.is_active.isnot(False))
        .order_by(Product.id.desc())
        .limit(200)
        .all()
    )
    providers = {p.id: p for p in db.query(Provider).all()}
    sellers = {s.id: s for s in db.query(BusinessUser).all()}
    metrics = {m.business_id: m for m in db.query(BusinessMetrics).all()}
    return [
        _serialize_public_product(db, p, providers.get(p.provider_id), sellers.get(p.seller_id), metrics.get(p.seller_id))
        for p in items
    ]


@router.get("/public/categories")
def get_public_categories(
    db: Session = Depends(get_db),
):
    rows = (
        db.query(func.trim(Product.category))
        .filter(Product.category.isnot(None))
        .distinct()
        .order_by(func.trim(Product.category).asc())
        .all()
    )
    categories = [row[0] for row in rows if (row[0] or "").strip()]
    return {"categories": categories}


@router.get("/categories")
def get_product_categories(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    query = db.query(func.trim(Product.category)).filter(Product.category.isnot(None), Product.is_active.isnot(False))
    if _is_seller(current):
        query = query.filter(Product.seller_id == current.id)
    rows = query.distinct().order_by(func.trim(Product.category).asc()).all()
    categories = [row[0] for row in rows if (row[0] or "").strip()]
    return {"categories": categories}


@router.get("/public/search")
def search_products(
    q: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock: bool | None = None,
    sort: str = "featured",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.is_active.isnot(False))
    
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            (Product.name.ilike(search_term)) | 
            (Product.category.ilike(search_term)) |
            (Product.description.ilike(search_term))
        )
    
    if category:
        query = query.filter(func.trim(Product.category) == category)
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    if in_stock is True:
        query = query.filter(Product.stock > 0)
    
    total = query.count()
    
    if sort == "price_low":
        query = query.order_by(Product.price.asc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc())
    elif sort == "rating":
        query = query.order_by(Product.rating_avg.desc())
    elif sort == "newest":
        query = query.order_by(Product.id.desc())
    else:
        query = query.order_by(Product.id.desc())
    
    items = query.offset(offset).limit(limit).all()
    providers = {p.id: p for p in db.query(Provider).all()}
    sellers = {s.id: s for s in db.query(BusinessUser).all()}
    metrics = {m.business_id: m for m in db.query(BusinessMetrics).all()}
    
    rows = (
        db.query(func.trim(Product.category))
        .filter(Product.category.isnot(None))
        .distinct()
        .order_by(func.trim(Product.category).asc())
        .all()
    )
    categories = [row[0] for row in rows if (row[0] or "").strip()]
    
    return {
        "items": [_serialize_public_product(db, p, providers.get(p.provider_id), sellers.get(p.seller_id), metrics.get(p.seller_id)) for p in items],
        "total": total,
        "categories": categories
    }


@router.get("/marketplace")
def get_marketplace_products(
    q: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock: bool | None = None,
    sort: str = "featured",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return search_products(
        q=q, category=category, min_price=min_price,
        max_price=max_price, in_stock=in_stock,
        sort=sort, limit=limit, offset=offset, db=db
    )


@router.get("/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    provider = None
    if product.provider_id:
        provider = db.query(Provider).filter(Provider.id == product.provider_id).first()
    seller = None
    if product.seller_id:
        seller = db.query(BusinessUser).filter(BusinessUser.id == product.seller_id).first()
    metrics = db.query(BusinessMetrics).filter(BusinessMetrics.business_id == product.seller_id).first() if product.seller_id else None
    return _serialize_public_product(db, product, provider, seller, metrics)



@router.post("/", status_code=201)   
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    provider = None
    if product.provider_id:
        provider = db.query(Provider).filter(Provider.id == product.provider_id).first()
        if not provider:
            raise HTTPException(status_code=400, detail="Provider not found")
            
    # Determine seller_id
    seller_id = None
    if _is_seller(current):
        seller_id = current.id
    elif product.seller_id:
        # Admin/Super Admin can assign to a seller
        seller_id = product.seller_id
        
    new_product = Product(
        name=product.name,
        category=product.category,
        price=product.price,
        stock=product.stock,
        description=product.description,
        image_url=product.image_url,
        seller_id=seller_id,
        is_active=True,
        provider_id=provider.id if provider else None,
)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    seller = None
    if new_product.seller_id:
        seller = db.query(BusinessUser).filter(BusinessUser.id == new_product.seller_id).first()
        refresh_business_metrics(db, new_product.seller_id)
        db.commit()

    return {
        "message": "Product created",
        "product": _serialize_product(db, new_product, provider, seller)
    }

@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    _ensure_product_owner(product, current)
    product.is_active = False
    db.add(product)
    db.commit()
    return {"message": "Product deactivated", "product_id": product_id}


@router.post("/{product_id}/reactivate")
def reactivate_product(
    product_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    """Undo a soft-delete. Without this, a seller who deletes a product by
    mistake (or wants to re-list something seasonally) has no way back --
    ProductCreate/update_product never touch is_active, so this was a dead
    end before."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    _ensure_product_owner(product, current)
    product.is_active = True
    db.add(product)
    db.commit()
    db.refresh(product)

    provider = db.query(Provider).filter(Provider.id == product.provider_id).first() if product.provider_id else None
    seller = db.query(BusinessUser).filter(BusinessUser.id == product.seller_id).first() if product.seller_id else None
    return {
        "message": "Product reactivated",
        "product": _serialize_product(db, product, provider, seller),
    }

@router.put("/{product_id}")
def update_product(
    product_id: int,
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("seller", "admin", "super_admin", "owner")),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    _ensure_product_owner(product, current)
    
    product.name = product_data.name
    product.category = product_data.category
    product.price = product_data.price
    product.stock = product_data.stock
    product.description = product_data.description
    product.image_url = product_data.image_url
    
    if product_data.seller_id and not _is_seller(current):
        # Admin can update the seller
        product.seller_id = product_data.seller_id
        
    if product_data.provider_id:
        provider = db.query(Provider).filter(Provider.id == product_data.provider_id).first()
        if provider:
            product.provider_id = provider.id
    elif _is_seller(current):
        # Sellers may remove provider association from their own items.
        product.provider_id = None

    db.commit()
    db.refresh(product)
    
    provider = None
    if product.provider_id:
        provider = db.query(Provider).filter(Provider.id == product.provider_id).first()
    seller = None
    if product.seller_id:
        seller = db.query(BusinessUser).filter(BusinessUser.id == product.seller_id).first()
        refresh_business_metrics(db, product.seller_id)
        db.commit()

    return {
        "message": "Product updated",
        "product": _serialize_product(db, product, provider, seller)
    }


@router.get("/inventory/stats")
def get_inventory_stats(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    query = db.query(Product).filter(Product.is_active.isnot(False))
    if _is_seller(current):
        query = query.filter(Product.seller_id == current.id)
    products = query.all()
    providers = {p.id: p for p in db.query(Provider).all()}
    
    total_products = len(products)
    low_stock_count = 0
    out_of_stock_count = 0
    total_value = 0.0
    alerts = []
    
    for product in products:
        stock = product.stock or 0
        price = product.price or 0
        total_value += stock * price
        
        if stock == 0:
            out_of_stock_count += 1
        elif stock < 5:
            low_stock_count += 1
            provider = providers.get(product.provider_id) if product.provider_id else None
            alerts.append({
                "product_id": product.id,
                "product_name": product.name,
                "current_stock": stock,
                "low_stock_threshold": 5,
                "provider_id": product.provider_id,
                "provider_name": provider.name if provider else None
            })
    
    return {
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_value": total_value,
        "alerts": alerts[:10]
    }


@router.post("/cart-optimization")
def get_cart_optimization(
    payload: dict,
    db: Session = Depends(get_db),
):
    items = payload.get("items") or []
    return build_cart_optimization(db, items if isinstance(items, list) else [])
