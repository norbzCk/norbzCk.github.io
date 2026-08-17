from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models import Sale, Product, Provider, Customer, User

def calculate_inventory_forecast(db: Session, seller_id: int):
    # Calculate days of stock left based on recent sales (burn rate)
    from datetime import date, timedelta
    
    forecasts = []
    products = db.query(Product).filter(Product.seller_id == seller_id, Product.is_active.isnot(False)).all()
    
    thirty_days_ago = date.today() - timedelta(days=30)
    
    for p in products:
        # Get sales for this product in last 30 days
        total_sales = db.query(func.sum(Sale.quantity)).filter(
            Sale.product_id == p.id,
            Sale.date >= thirty_days_ago
        ).scalar() or 0
        
        daily_burn_rate = float(total_sales) / 30.0
        
        days_left = float('inf')
        if daily_burn_rate > 0:
            days_left = float(p.stock or 0) / daily_burn_rate
            
        forecasts.append({
            "product_id": p.id,
            "product_name": p.name,
            "current_stock": p.stock,
            "daily_burn_rate": round(daily_burn_rate, 2),
            "days_left": round(days_left, 1) if days_left != float('inf') else "N/A",
            "weekly_demand": int(round(daily_burn_rate * 7)),
            "recommended_restock": max(int(round(daily_burn_rate * 14)) - int(p.stock or 0), 0),
            "risk_level": (
                "critical"
                if days_left != float('inf') and days_left < 7
                else "watch"
                if days_left != float('inf') and days_left < 21
                else "healthy"
            ),
            "is_critical": days_left < 7 if days_left != float('inf') else False
        })
        
    forecasts.sort(
        key=lambda item: (
            0 if item["risk_level"] == "critical" else 1 if item["risk_level"] == "watch" else 2,
            float(item["days_left"]) if isinstance(item["days_left"], (int, float)) else 9999,
        )
    )
    return forecasts

def dashboard_stats(db: Session):
    total_revenue = db.query(
        func.sum(Sale.quantity * Sale.unit_price)
    ).scalar() or 0

    total_orders = db.query(Sale.id).count()

    total_units = db.query(
        func.sum(Sale.quantity)
    ).scalar() or 0

    top_product = db.query(
        Sale.product,
        func.sum(Sale.quantity * Sale.unit_price).label("revenue")
    ).group_by(Sale.product).order_by(
        func.sum(Sale.quantity * Sale.unit_price).desc()
    ).first()

    return {
        "total_revenue": float(total_revenue),
        "total_orders": total_orders,
        "total_units": int(total_units),
        "top_product": top_product[0] if top_product else None
    }

def revenue_by_product(db: Session):
    rows = db.query(
        Sale.product,
        func.sum(Sale.quantity * Sale.unit_price)
    ).group_by(Sale.product).all()

    return {
        product: float(revenue)
        for product, revenue in rows
    }

def revenue_over_time(db: Session):
    rows = db.query(
        Sale.date,
        func.sum(Sale.quantity * Sale.unit_price)
    ).group_by(Sale.date).order_by(Sale.date).all()

    return {
        str(date): float(revenue)
        for date, revenue in rows
    }


def market_insights(db: Session):
    total_products = db.query(Product).count()
    total_providers = db.query(Provider).count()
    total_customers = db.query(Customer).count()
    
    low_stock = db.query(Product).filter(Product.stock < 5).count()
    out_of_stock = db.query(Product).filter(Product.stock == 0).count()
    
    avg_price = db.query(func.avg(Product.price)).scalar() or 0
    
    top_categories = db.query(
        Product.category,
        func.count(Product.id).label("count"),
        func.avg(Product.price).label("avg_price")
    ).group_by(Product.category).order_by(func.count(Product.id).desc()).limit(5).all()
    
    verified_providers = db.query(Provider).filter(Provider.verified == True).count()
    
    return {
        "total_products": total_products,
        "total_providers": total_providers,
        "total_customers": total_customers,
        "low_stock_count": low_stock,
        "out_of_stock_count": out_of_stock,
        "average_product_price": float(avg_price),
        "verified_providers": verified_providers,
        "top_categories": [
            {
                "category": cat,
                "product_count": count,
                "avg_price": float(avg_price) if avg_price else 0
            }
            for cat, count, avg_price in top_categories
        ]
    }


def pricing_insights(db: Session):
    min_price = db.query(func.min(Product.price)).scalar() or 0
    max_price = db.query(func.max(Product.price)).scalar() or 0
    avg_price = db.query(func.avg(Product.price)).scalar() or 0
    median_price = db.query(Product).order_by(Product.price).offset(
        db.query(func.count(Product.id)).scalar() // 2
    ).first()
    
    price_ranges = [
        {"range": "Under 1000", "count": db.query(Product).filter(Product.price < 1000).count()},
        {"range": "1000-5000", "count": db.query(Product).filter(Product.price >= 1000, Product.price < 5000).count()},
        {"range": "5000-20000", "count": db.query(Product).filter(Product.price >= 5000, Product.price < 20000).count()},
        {"range": "20000-50000", "count": db.query(Product).filter(Product.price >= 20000, Product.price < 50000).count()},
        {"range": "Over 50000", "count": db.query(Product).filter(Product.price >= 50000).count()},
    ]
    
    return {
        "min_price": float(min_price),
        "max_price": float(max_price),
        "avg_price": float(avg_price),
        "median_price": float(median_price.price) if median_price else 0,
        "price_ranges": price_ranges
    }


def demand_forecast(db: Session):
    rows = db.query(
        func.extract("month", Sale.date).label("month"),
        func.sum(Sale.quantity).label("total_qty"),
        func.sum(Sale.quantity * Sale.unit_price).label("revenue")
    ).filter(Sale.date.isnot(None)).group_by(
        func.extract("month", Sale.date)
    ).order_by("month").all()
    
    monthly_data = []
    for month, qty, revenue in rows:
        monthly_data.append({
            "month": int(month) if month else 0,
            "quantity": int(qty) if qty else 0,
            "revenue": float(revenue) if revenue else 0
        })
    
    return {
        "monthly_sales": monthly_data,
        "trend": "increasing" if (len(monthly_data) > 1 and monthly_data[-1]["revenue"] > monthly_data[0]["revenue"]) else "stable"
    }


def peak_sales_periods(db: Session):
    # Day of week analysis
    dow_rows = db.query(
        func.extract("dow", Sale.created_at).label("dow"),
        func.count(Sale.id).label("count"),
        func.sum(Sale.quantity * Sale.unit_price).label("revenue")
    ).filter(Sale.created_at.isnot(None)).group_by("dow").all()
    
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    dow_data = {days[int(row.dow)]: {"orders": row.count, "revenue": float(row.revenue or 0)} for row in dow_rows}
    
    # Hour of day analysis
    hour_rows = db.query(
        func.extract("hour", Sale.created_at).label("hour"),
        func.count(Sale.id).label("count"),
        func.sum(Sale.quantity * Sale.unit_price).label("revenue")
    ).filter(Sale.created_at.isnot(None)).group_by("hour").order_by("hour").all()
    
    hour_data = {int(row.hour): {"orders": row.count, "revenue": float(row.revenue or 0)} for row in hour_rows}
    
    return {
        "day_of_week": dow_data,
        "hour_of_day": hour_data
    }


def customer_buying_patterns(db: Session):
    from sqlalchemy import Integer, cast
    
    # Top customers by revenue
    top_customers = db.query(
        User.id,
        User.name,
        func.count(Sale.id).label("order_count"),
        func.sum(Sale.quantity * Sale.unit_price).label("total_spent")
    ).join(Sale, cast(Sale.created_by, Integer) == User.id).group_by(User.id, User.name).order_by(func.sum(Sale.quantity * Sale.unit_price).desc()).limit(10).all()
    
    # Repeat purchase rate
    total_customers_with_orders = db.query(func.count(func.distinct(Sale.created_by))).scalar() or 0
    if total_customers_with_orders == 0:
        repeat_rate = 0
    else:
        customers_with_multiple_orders = db.query(Sale.created_by).group_by(Sale.created_by).having(func.count(Sale.id) > 1).count()
        repeat_rate = (customers_with_multiple_orders / total_customers_with_orders) * 100
        
    return {
        "top_customers": [
            {"id": c.id, "name": c.name, "orders": c.order_count, "total_spent": float(c.total_spent or 0)}
            for c in top_customers
        ],
        "repeat_purchase_rate_percent": round(repeat_rate, 2)
    }

