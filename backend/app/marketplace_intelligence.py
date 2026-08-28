from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt
from typing import Any, List, Dict

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.utils.geo import coords_for_location, haversine_km, interpolate_coords
from backend.utils.text import clean_text, normalize_lookup_key

from backend.models import (
    BusinessMetrics,
    BusinessUser,
    DeliveryOrder,
    LogisticsUser,
    Product,
    RFQ,
    Sale,
    User,
)


def _clean_text(value: str | None) -> str:
    return clean_text(value)


def build_ai_product_insight(db: Session, payload: Any) -> dict[str, Any]:
    name = clean_text(getattr(payload, "name", None) or "")
    category = clean_text(getattr(payload, "category", None) or "General")
    description_seed = clean_text(getattr(payload, "description", None) or "")
    stock = max(int(getattr(payload, "stock", 0) or 0), 0)
    current_price = getattr(payload, "current_price", None)
    seller_area = clean_text(getattr(payload, "seller_area", None) or "")

    category_prices = (
        db.query(Product.price)
        .filter(Product.category.ilike(category), Product.price.isnot(None), Product.is_active.isnot(False))
        .all()
    )
    matching_name_prices = (
        db.query(Product.price)
        .filter(Product.name.ilike(f"%{name}%"), Product.price.isnot(None), Product.is_active.isnot(False))
        .all()
    )
    recent_cutoff = datetime.utcnow().date() - timedelta(days=45)
    recent_sales_qty = (
        db.query(func.sum(Sale.quantity))
        .filter(
            Sale.date >= recent_cutoff,
            or_(
                Sale.product.ilike(f"%{name}%"),
                Sale.category.ilike(category)
            )
        )
        .scalar()
        or 0
    )

    benchmark_values = [float(row[0]) for row in matching_name_prices if row[0] is not None] or [
        float(row[0]) for row in category_prices if row[0] is not None
    ]
    benchmark_avg = sum(benchmark_values) / len(benchmark_values) if benchmark_values else 15000.0
    lower_bound = round(benchmark_avg * 0.92, 2)
    upper_bound = round(benchmark_avg * 1.1, 2)

    demand_level = "steady"
    confidence = 0.74
    if recent_sales_qty >= 60:
        demand_level = "high"
        confidence = 0.89
    elif recent_sales_qty >= 20:
        demand_level = "rising"
        confidence = 0.83
    elif recent_sales_qty <= 5:
        demand_level = "early"
        confidence = 0.71

    suggested_price = round(benchmark_avg, 2)
    if current_price:
        suggested_price = round((float(current_price) * 0.35) + (benchmark_avg * 0.65), 2)
    if demand_level == "high":
        suggested_price = round(suggested_price * 1.05, 2)
    if stock and stock < 8:
        suggested_price = round(suggested_price * 1.03, 2)

    keywords = [
        name,
        f"{category.lower()} tanzania",
        f"buy {name.lower()} online",
        "fast delivery dar es salaam",
        f"{category.lower()} marketplace",
    ]
    if seller_area:
        keywords.append(f"{name.lower()} {seller_area.lower()}")

    short_seed = description_seed.rstrip(".")
    extra_line = short_seed if short_seed else f"Built for buyers who want reliable {category.lower()} quality and quick fulfillment."
    description = (
        f"{name} is a marketplace-ready {category.lower()} offer crafted for visibility, trust, and repeat purchase. "
        f"{extra_line}. "
        f"Optimized for customers searching for dependable value, fast delivery, and consistent product quality in Tanzania."
    )

    trend_summary = (
        f"{category} listings are averaging TZS {benchmark_avg:,.0f} and {demand_level} demand over the last 45 days."
    )
    if seller_area:
        trend_summary += f" Products positioned around {seller_area} can be bundled for cheaper last-mile delivery."

    return {
        "description": description,
        "suggested_price": suggested_price,
        "seo_keywords": keywords[:6],
        "confidence": confidence,
        "price_range": {
            "low": lower_bound,
            "high": upper_bound,
            "benchmark_average": round(benchmark_avg, 2),
        },
        "trend_summary": trend_summary,
        "demand_level": demand_level,
    }
def compute_seller_badges(
    db: Session,
    seller: BusinessUser | None,
    metrics: BusinessMetrics | None = None,
) -> list[dict[str, str]]:
    if not seller:
        return []

    metrics = metrics or db.query(BusinessMetrics).filter(BusinessMetrics.business_id == seller.id).first()
    badges: list[dict[str, str]] = []

    rating = float(getattr(metrics, "rating", 0) or 0)
    reviews_count = int(getattr(metrics, "reviews_count", 0) or 0)
    total_sales = int(getattr(metrics, "total_sales", 0) or 0)

    completed_deliveries = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.seller_id == seller.id,
            DeliveryOrder.status == "delivered",
            DeliveryOrder.created_at.isnot(None),
            DeliveryOrder.delivered_at.isnot(None),
        )
        .all()
    )
    avg_delivery_hours = None
    if completed_deliveries:
        durations = [
            max((item.delivered_at - item.created_at).total_seconds() / 3600, 0)
            for item in completed_deliveries
            if item.created_at and item.delivered_at
        ]
        if durations:
            avg_delivery_hours = sum(durations) / len(durations)

    if rating >= 4.5 and max(reviews_count, total_sales) >= 5:
        badges.append({"id": "top_rated", "label": "Top Rated", "icon": "star"})
    if avg_delivery_hours is not None and avg_delivery_hours <= 8 and len(completed_deliveries) >= 3:
        badges.append({"id": "fast_shipper", "label": "Fast Shipper", "icon": "bolt"})
    if seller.verification_status == "verified" and total_sales >= 20:
        badges.append({"id": "trusted_seller", "label": "Trusted Seller", "icon": "verified"})

    return badges


def refresh_business_metrics(db: Session, seller_id: int | None) -> BusinessMetrics | None:
    if not seller_id:
        return None

    metrics = db.query(BusinessMetrics).filter(BusinessMetrics.business_id == seller_id).first()
    if not metrics:
        metrics = BusinessMetrics(business_id=seller_id)
        db.add(metrics)

    revenue, total_sales, avg_rating, reviews_count = (
        db.query(
            func.sum(Sale.quantity * Sale.unit_price),
            func.count(Sale.id),
            func.avg(Sale.rating),
            func.count(Sale.rating),
        )
        .filter(Sale.seller_id == seller_id)
        .first()
    )
    metrics.total_revenue = float(revenue or 0)
    metrics.total_sales = int(total_sales or 0)
    metrics.rating = round(float(avg_rating or 0), 2)
    metrics.reviews_count = int(reviews_count or 0)
    db.add(metrics)
    return metrics


def build_tracking_payload(
    delivery: DeliveryOrder,
    order: Sale | None = None,
    logistics: LogisticsUser | None = None,
) -> dict[str, Any]:
    pickup = (
        float(delivery.pickup_lat) if delivery.pickup_lat is not None else coords_for_location(delivery.pickup_location)[0],
        float(delivery.pickup_lng) if delivery.pickup_lng is not None else coords_for_location(delivery.pickup_location)[1],
    )
    destination = (
        float(delivery.destination_lat) if delivery.destination_lat is not None else coords_for_location(delivery.delivery_location)[0],
        float(delivery.destination_lng) if delivery.destination_lng is not None else coords_for_location(delivery.delivery_location)[1],
    )
    status = str(delivery.status or "assigned").strip().lower()
    if delivery.current_lat is not None and delivery.current_lng is not None:
        current = (float(delivery.current_lat), float(delivery.current_lng))
    else:
        ratio = 0.05 if status == "assigned" else 0.28 if status == "picked_up" else 0.68 if status == "in_transit" else 1.0
        current = interpolate_coords(pickup, destination, ratio)

    progress_map = {"assigned": 18, "picked_up": 42, "in_transit": 76, "delivered": 100, "cancelled": 0}
    total_distance = haversine_km(pickup, destination)
    progress_percent = progress_map.get(status, 24)
    eta_minutes = 0 if status == "delivered" else max(int((100 - progress_percent) * 0.9), 12)

    checkpoints = [
        {"id": "pickup", "label": "Pickup scheduled", "done": True, "location": delivery.pickup_location, "timestamp": delivery.created_at.isoformat() if delivery.created_at else None},
        {"id": "picked", "label": "Picked up", "done": status in {"picked_up", "in_transit", "delivered"}, "location": delivery.pickup_location, "timestamp": delivery.picked_at.isoformat() if delivery.picked_at else None},
        {"id": "transit", "label": "In transit", "done": status in {"in_transit", "delivered"}, "location": delivery.last_location_name or "On the way", "timestamp": delivery.tracking_updated_at.isoformat() if delivery.tracking_updated_at else None},
        {"id": "delivered", "label": "Delivered", "done": status == "delivered", "location": delivery.delivery_location, "timestamp": delivery.delivered_at.isoformat() if delivery.delivered_at else None},
    ]

    return {
         "order_id": delivery.order_id,
         "delivery_id": delivery.id,
         "status": status,
         "progress_percent": progress_percent,
         "eta_minutes": eta_minutes,
         "distance_km": round(float(delivery.estimated_distance_km or total_distance or 0), 1),
         "last_updated_at": delivery.tracking_updated_at.isoformat() if delivery.tracking_updated_at else None,
         "logistics_partner": {
             "id": logistics.id if logistics else delivery.logistics_id,
             "name": logistics.name if logistics else "Delivery partner",
             "phone": logistics.phone if logistics else None,
             "vehicle_type": logistics.vehicle_type if logistics else None,
         },
         "buyer_id": delivery.buyer_id,
         "map": {
             "pickup": {"label": delivery.pickup_location or "Pickup", "lat": pickup[0], "lng": pickup[1]},
             "current": {
                 "label": delivery.last_location_name or ("Delivered" if status == "delivered" else "Current rider position"),
                 "lat": current[0],
                 "lng": current[1],
             },
             "destination": {"label": delivery.delivery_location or "Destination", "lat": destination[0], "lng": destination[1]},
         },
         "checkpoints": checkpoints,
         "order": {
             "id": order.id if order else delivery.order_id,
             "product": order.product if order else None,
             "status": order.status if order else None,
         },
         "rating": delivery.rating,
         "rated_at": delivery.rated_at.isoformat() if delivery.rated_at else None,
         "rating_comment": delivery.rating_comment,
     }


def build_cart_optimization(
    db: Session,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    if not items:
        return {"recommendations": [], "summary": {"separate_delivery_fee": 0, "optimized_delivery_fee": 0, "estimated_savings": 0}}

    product_ids = [int(item.get("product_id")) for item in items if item.get("product_id")]
    products = db.query(Product).filter(Product.id.in_(product_ids)).all() if product_ids else []
    product_map = {item.id: item for item in products}
    seller_ids = [int(item.seller_id) for item in products if item.seller_id]
    sellers = db.query(BusinessUser).filter(BusinessUser.id.in_(seller_ids)).all() if seller_ids else []
    seller_map = {item.id: item for item in sellers}

    groups: dict[str, dict[str, Any]] = {}
    for entry in items:
        product = product_map.get(int(entry.get("product_id") or 0))
        if not product:
            continue
        seller = seller_map.get(int(product.seller_id or 0))
        region = _clean_text(getattr(seller, "region", None) or "Dar es Salaam")
        area = _clean_text(getattr(seller, "area", None) or region)
        key = f"{region}::{area}"
        bucket = groups.setdefault(
            key,
            {
                "region": region,
                "area": area,
                "items": [],
                "seller_names": set(),
                "separate_fee": 0.0,
            },
        )
        quantity = max(int(entry.get("quantity") or 1), 1)
        bucket["items"].append(
            {
                "product_id": product.id,
                "name": product.name,
                "quantity": quantity,
                "seller_name": seller.business_name if seller else "Marketplace seller",
            }
        )
        bucket["seller_names"].add(seller.business_name if seller else "Marketplace seller")
        bucket["separate_fee"] += 2800

    recommendations: list[dict[str, Any]] = []
    separate_total = 0.0
    optimized_total = 0.0
    for index, group in enumerate(sorted(groups.values(), key=lambda item: len(item["items"]), reverse=True), start=1):
        item_count = len(group["items"])
        separate_fee = float(group["separate_fee"])
        optimized_fee = 2200 + (max(item_count - 1, 0) * 650)
        savings = max(separate_fee - optimized_fee, 0)
        separate_total += separate_fee
        optimized_total += optimized_fee
        recommendations.append(
            {
                "id": f"group-{index}",
                "title": f"Bundle {item_count} item{'s' if item_count != 1 else ''} around {group['area']}",
                "seller_area": group["area"],
                "seller_region": group["region"],
                "item_count": item_count,
                "seller_names": sorted(group["seller_names"]),
                "items": group["items"],
                "estimated_delivery_fee": round(optimized_fee, 2),
                "separate_delivery_fee": round(separate_fee, 2),
                "estimated_savings": round(savings, 2),
                "message": (
                    f"These items come from the same area, so one shared drop-off route can reduce delivery cost by about "
                    f"TZS {savings:,.0f}."
                ),
            }
        )

    return {
        "recommendations": recommendations,
        "summary": {
            "separate_delivery_fee": round(separate_total, 2),
            "optimized_delivery_fee": round(optimized_total, 2),
            "estimated_savings": round(max(separate_total - optimized_total, 0), 2),
        },
    }




def build_marketplace_trends(db: Session) -> dict[str, Any]:
    now = datetime.utcnow()
    recent_cutoff = now.date() - timedelta(days=45)
    previous_cutoff = recent_cutoff - timedelta(days=45)
    recent_rfq_cutoff = now - timedelta(days=45)
    previous_rfq_cutoff = recent_rfq_cutoff - timedelta(days=45)

    active_categories = (
        db.query(
            func.trim(Product.category).label("category"),
            func.count(Product.id).label("product_count"),
            func.coalesce(func.sum(Product.stock), 0).label("stock"),
            func.count(func.distinct(Product.seller_id)).label("seller_count"),
            func.avg(Product.price).label("avg_price"),
        )
        .filter(Product.category.isnot(None), Product.is_active.isnot(False))
        .group_by(func.trim(Product.category))
        .all()
    )

    recent_sales = (
        db.query(
            func.trim(Sale.category).label("category"),
            func.coalesce(func.sum(Sale.quantity), 0).label("recent_qty"),
            func.count(Sale.id).label("recent_orders"),
            func.coalesce(func.sum(Sale.quantity * Sale.unit_price), 0).label("recent_revenue"),
        )
        .filter(Sale.category.isnot(None), Sale.date >= recent_cutoff)
        .group_by(func.trim(Sale.category))
        .all()
    )

    previous_sales = (
        db.query(
            func.trim(Sale.category).label("category"),
            func.coalesce(func.sum(Sale.quantity), 0).label("previous_qty"),
        )
        .filter(Sale.category.isnot(None), Sale.date >= previous_cutoff, Sale.date < recent_cutoff)
        .group_by(func.trim(Sale.category))
        .all()
    )

    recent_rfqs = (
        db.query(
            func.trim(RFQ.product_interest).label("category"),
            func.count(RFQ.id).label("rfq_count"),
            func.coalesce(func.sum(RFQ.quantity), 0).label("rfq_qty"),
        )
        .filter(RFQ.product_interest.isnot(None), RFQ.created_at >= recent_rfq_cutoff)
        .group_by(func.trim(RFQ.product_interest))
        .all()
    )

    previous_rfqs = (
        db.query(
            func.trim(RFQ.product_interest).label("category"),
            func.count(RFQ.id).label("previous_rfq_count"),
            func.coalesce(func.sum(RFQ.quantity), 0).label("previous_rfq_qty"),
        )
        .filter(RFQ.product_interest.isnot(None), RFQ.created_at >= previous_rfq_cutoff, RFQ.created_at < recent_rfq_cutoff)
        .group_by(func.trim(RFQ.product_interest))
        .all()
    )

    category_metrics: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "product_count": 0,
            "stock": 0,
            "seller_count": 0,
            "avg_price": 0,
            "recent_qty": 0,
            "recent_orders": 0,
            "recent_revenue": 0,
            "previous_qty": 0,
            "rfq_count": 0,
            "rfq_qty": 0,
            "previous_rfq_count": 0,
            "previous_rfq_qty": 0,
        }
    )

    for row in active_categories:
        key = str(row.category or "").strip().lower()
        if not key:
            continue
        category_metrics[key]["product_count"] = int(row.product_count or 0)
        category_metrics[key]["stock"] = int(row.stock or 0)
        category_metrics[key]["seller_count"] = int(row.seller_count or 0)
        category_metrics[key]["avg_price"] = float(row.avg_price or 0)

    for row in recent_sales:
        key = str(row.category or "").strip().lower()
        if not key:
            continue
        category_metrics[key]["recent_qty"] = int(row.recent_qty or 0)
        category_metrics[key]["recent_orders"] = int(row.recent_orders or 0)
        category_metrics[key]["recent_revenue"] = float(row.recent_revenue or 0)

    for row in previous_sales:
        key = str(row.category or "").strip().lower()
        if not key:
            continue
        category_metrics[key]["previous_qty"] = int(row.previous_qty or 0)

    for row in recent_rfqs:
        key = str(row.category or "").strip().lower()
        if not key:
            continue
        category_metrics[key]["rfq_count"] = int(row.rfq_count or 0)
        category_metrics[key]["rfq_qty"] = int(row.rfq_qty or 0)

    for row in previous_rfqs:
        key = str(row.category or "").strip().lower()
        if not key:
            continue
        category_metrics[key]["previous_rfq_count"] = int(row.previous_rfq_count or 0)
        category_metrics[key]["previous_rfq_qty"] = int(row.previous_rfq_qty or 0)

    def format_trend(current: float, previous: float) -> str:
        if previous <= 0:
            return "New" if current > 0 else "0.0%"
        return f"{((current - previous) / previous) * 100:+.1f}%"

    def trend_status(metrics: dict[str, float | int]) -> str:
        product_count = int(metrics["product_count"])
        stock = int(metrics["stock"])
        recent_qty = int(metrics["recent_qty"])
        recent_orders = int(metrics["recent_orders"])
        rfq_qty = int(metrics["rfq_qty"])
        rfq_count = int(metrics["rfq_count"])
        previous_qty = int(metrics["previous_qty"])
        previous_rfq_qty = int(metrics["previous_rfq_qty"])

        demand_growth = recent_qty - previous_qty
        request_growth = rfq_qty - previous_rfq_qty
        stock_pressure = product_count > 0 and stock <= max(1, product_count * 2)

        if stock_pressure and recent_qty >= 8:
            return "Supply Tight"
        if rfq_qty >= max(10, recent_qty * 0.5) or request_growth > 0:
            return "Sourcing Now"
        if demand_growth > 0 and recent_orders >= 3:
            return "Rising"
        if recent_qty >= 15:
            return "High Demand"
        if recent_qty > 0 or rfq_count > 0:
            return "Active"
        return "Quiet"

    def trend_score(metrics: dict[str, float | int]) -> float:
        product_count = int(metrics["product_count"]) or 1
        demand_density = int(metrics["recent_qty"]) / product_count
        return (
            int(metrics["recent_qty"]) * 2
            + int(metrics["recent_orders"]) * 8
            + int(metrics["rfq_qty"]) * 1.5
            + int(metrics["rfq_count"]) * 6
            + demand_density * 12
        )

    trend_items = [
        {
            "label": str(category_key or "").strip(),
            "trend": format_trend(float(row["recent_qty"]) + float(row["rfq_qty"]), float(row["previous_qty"]) + float(row["previous_rfq_qty"])),
            "status": trend_status(row),
            "_score": trend_score(row),
        }
        for category_key, row in category_metrics.items()
        if row.get("recent_qty") or row.get("recent_orders") or row.get("rfq_count") or row.get("rfq_qty")
    ]
    trend_items.sort(key=lambda item: float(item["_score"]), reverse=True)

    total_sellers = db.query(BusinessUser).filter(BusinessUser.role == "seller", BusinessUser.is_active.isnot(False)).count()
    verified_sellers = db.query(BusinessUser).filter(
        BusinessUser.role == "seller",
        BusinessUser.is_active.isnot(False),
        BusinessUser.verification_status == "verified",
    ).count()
    active_deliveries = db.query(DeliveryOrder).filter(
        DeliveryOrder.status.in_(["assigned", "picked_up", "in_transit"])
    ).count()
    available_logistics = db.query(LogisticsUser).filter(
        LogisticsUser.is_active.isnot(False),
        LogisticsUser.status == "online",
        LogisticsUser.availability == "available",
    ).count()

    operational_items: list[dict[str, str]] = []
    if total_sellers:
        ratio = round((verified_sellers / total_sellers) * 100, 1)
        operational_items.append({
            "label": "Verified Sellers",
            "trend": f"{ratio:.1f}%",
            "status": "Verified" if ratio >= 80 else "Building Trust",
        })
    if active_deliveries:
        operational_items.append({
            "label": "Live Deliveries",
            "trend": str(active_deliveries),
            "status": "In Transit",
        })
    if available_logistics:
        operational_items.append({
            "label": "Available Logistics",
            "trend": str(available_logistics),
            "status": "Ready",
        })

    items = [
        {
            "label": item["label"],
            "trend": item["trend"],
            "status": item["status"],
        }
        for item in [*trend_items, *operational_items]
        if item.get("label")
    ][:8]

    return {
        "items": items,
        "generated_at": now.isoformat() + "Z",
    }


def build_superadmin_overview(db: Session) -> dict[str, Any]:
    total_businessmen = db.query(BusinessUser).count()
    active_businessmen = db.query(BusinessUser).filter(BusinessUser.is_active.is_(True)).count()
    total_customers = db.query(User).filter(User.role == "user").count()
    active_customers = db.query(User).filter(User.role == "user", User.is_active.is_(True)).count()
    total_logistics = db.query(LogisticsUser).count()
    active_logistics = db.query(LogisticsUser).filter(LogisticsUser.status == "online").count()
    total_products = db.query(Product).filter(Product.is_active.isnot(False)).count()
    active_products = total_products

    completed_statuses = ["Received", "Delivered"]
    pending_statuses = ["Pending", "Confirmed", "Packed", "Ready For Shipping", "Shipped"]
    total_orders = db.query(Sale).count()
    completed_orders = db.query(Sale).filter(Sale.status.in_(completed_statuses)).count()
    pending_orders = db.query(Sale).filter(Sale.status.in_(pending_statuses)).count()
    in_transit_orders = db.query(DeliveryOrder).filter(DeliveryOrder.status.in_(["assigned", "picked_up", "in_transit"])).count()
    revenue_total = db.query(func.sum(Sale.quantity * Sale.unit_price)).filter(Sale.status.in_(completed_statuses)).scalar() or 0
    avg_order_value = float(revenue_total or 0) / completed_orders if completed_orders else 0.0
    low_stock_products = db.query(Product).filter(Product.is_active.isnot(False), Product.stock < 5).count()
    pending_business_verifications = db.query(BusinessUser).filter(BusinessUser.verification_status == "pending").count()
    pending_logistics_verifications = db.query(LogisticsUser).filter(LogisticsUser.verification_status == "pending").count()
    pending_user_verifications = db.query(User).filter(User.is_verified == False).count()

    seller_rows = (
        db.query(BusinessUser)
        .order_by(BusinessUser.created_at.desc(), BusinessUser.id.desc())
        .all()
    )
    seller_leaderboard = []
    for seller in seller_rows[:8]:
        metrics = refresh_business_metrics(db, seller.id)
        seller_leaderboard.append(
            {
                "id": seller.id,
                "business_name": seller.business_name,
                "region": seller.region,
                "area": seller.area,
                "rating": float(getattr(metrics, "rating", 0) or 0),
                "total_sales": int(getattr(metrics, "total_sales", 0) or 0),
                "total_revenue": float(getattr(metrics, "total_revenue", 0) or 0),
                "badges": compute_seller_badges(db, seller, metrics),
            }
        )
    seller_leaderboard.sort(key=lambda item: (item["total_revenue"], item["rating"], item["total_sales"]), reverse=True)

    category_rows = (
        db.query(
            Sale.category,
            func.sum(Sale.quantity).label("units"),
            func.sum(Sale.quantity * Sale.unit_price).label("revenue"),
        )
        .group_by(Sale.category)
        .order_by(func.sum(Sale.quantity * Sale.unit_price).desc())
        .limit(6)
        .all()
    )
    category_performance = [
        {
            "category": row[0] or "Uncategorized",
            "units": int(row[1] or 0),
            "revenue": float(row[2] or 0),
        }
        for row in category_rows
    ]

    recent_orders = (
        db.query(Sale)
        .order_by(Sale.id.desc())
        .limit(8)
        .all()
    )
    inventory_watch = (
        db.query(Product, BusinessUser)
        .outerjoin(BusinessUser, BusinessUser.id == Product.seller_id)
        .filter(Product.is_active.isnot(False), Product.stock < 5)
        .order_by(Product.stock.asc(), Product.id.desc())
        .limit(8)
        .all()
    )

    # Full order-status breakdown (not just the completed/pending/in_transit
    # buckets above) -- gives the dashboard enough to draw a real pipeline/
    # funnel view of where orders actually are right now.
    all_statuses = ["Pending", "Confirmed", "Packed", "Ready For Shipping", "Shipped", "Received", "Cancelled"]
    status_counts_rows = db.query(Sale.status, func.count(Sale.id)).group_by(Sale.status).all()
    status_counts_map = {row[0]: row[1] for row in status_counts_rows}
    status_breakdown = [
        {"status": status, "count": status_counts_map.get(status, 0)}
        for status in all_statuses
    ]

    # Daily revenue + order count for the last 14 days, for a real trend
    # line instead of the old static matplotlib image.
    trend_start = datetime.utcnow().date() - timedelta(days=13)
    daily_rows = (
        db.query(
            Sale.date,
            func.count(Sale.id).label("orders"),
            func.sum(Sale.quantity * Sale.unit_price).label("revenue"),
        )
        .filter(Sale.date >= trend_start, Sale.status.in_(completed_statuses))
        .group_by(Sale.date)
        .all()
    )
    daily_map = {row[0]: {"orders": int(row[1] or 0), "revenue": float(row[2] or 0)} for row in daily_rows}
    revenue_trend = []
    for offset in range(14):
        day = trend_start + timedelta(days=offset)
        entry = daily_map.get(day, {"orders": 0, "revenue": 0.0})
        revenue_trend.append({
            "date": day.isoformat(),
            "orders": entry["orders"],
            "revenue": entry["revenue"],
        })

    return {
        "total_businessmen": total_businessmen,
        "active_businessmen": active_businessmen,
        "total_customers": total_customers,
        "active_customers": active_customers,
        "total_logistics": total_logistics,
        "active_logistics": active_logistics,
        "total_products": total_products,
        "active_products": active_products,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "in_transit_orders": in_transit_orders,
        "total_revenue": float(revenue_total or 0),
        "average_order_value": round(avg_order_value, 2),
        "low_stock_products": low_stock_products,
        "pending_business_verifications": pending_business_verifications,
        "pending_logistics_verifications": pending_logistics_verifications,
        "pending_user_verifications": pending_user_verifications,
        "seller_leaderboard": seller_leaderboard[:6],
        "category_performance": category_performance,
        "recent_orders": [
            {
                "id": item.id,
                "product": item.product,
                "category": item.category,
                "seller_id": item.seller_id,
                "provider_name": item.provider_name,
                "status": item.status,
                "quantity": item.quantity,
                "revenue": float((item.quantity or 0) * (item.unit_price or 0)),
                "date": item.date.isoformat() if item.date else None,
            }
            for item in recent_orders
        ],
        "inventory_watch": [
            {
                "product_id": product.id,
                "product_name": product.name,
                "stock": int(product.stock or 0),
                "seller_name": seller.business_name if seller else "Marketplace seller",
                "seller_area": seller.area if seller else None,
            }
            for product, seller in inventory_watch
        ],
        "status_breakdown": status_breakdown,
        "revenue_trend": revenue_trend,
        "insights": [
            {
                "id": "seller-density",
                "title": "Platform oversight",
                "message": f"{active_businessmen} of {total_businessmen} sellers are active across the marketplace.",
            },
            {
                "id": "inventory-risk",
                "title": "Inventory pressure",
                "message": f"{low_stock_products} active products are nearing stock-out and may need replenishment planning.",
            },
            {
                "id": "delivery-load",
                "title": "Delivery load",
                "message": f"{in_transit_orders} deliveries are currently live across the platform.",
            },
        ],
    }
