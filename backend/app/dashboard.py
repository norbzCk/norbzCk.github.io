from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import String, cast, func
from backend.models import Sale

def _sales_query_for_user(db, user):
    query = db.query(Sale)
    if user.role == "user":
        # Keep compatibility with legacy databases where created_by is varchar.
        query = query.filter(cast(Sale.created_by, String) == str(user.id))
    elif user.role == "seller":
        business_name = getattr(user, "business_name", None)
        query = query.filter(
            (Sale.seller_id == user.id) |
            ((Sale.seller_id.is_(None)) & (Sale.provider_name == business_name))
        )
    return query


def _load_analysis_modules():
    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
        return pd, np
    except Exception:
        return None, None


def _load_graph_modules():
    try:
        os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt  # type: ignore
        return plt
    except Exception:
        return None


def _graph_output_paths(user, suffix: str) -> tuple[Path, str]:
    user_key = f"{getattr(user, 'role', 'admin')}-{getattr(user, 'id', '0')}"
    directory = Path(__file__).resolve().parents[1] / "uploads" / "graphs"
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"dashboard-{user_key}-{suffix}.svg"
    return directory / filename, f"/uploads/graphs/{filename}"


def _write_revenue_time_graph(points: list[dict[str, Any]], user) -> str | None:
    plt = _load_graph_modules()
    if plt is None:
        return None

    output_path, public_path = _graph_output_paths(user, "revenue-time")
    labels = [str(point["label"]) for point in points] or ["No data"]
    values = [float(point["value"]) for point in points] or [0.0]
    x_positions = list(range(len(values)))

    # Modern Tech Palette
    primary_color = "#3b82f6"  # Brand Blue
    grid_color = "#f1f5f9"    # Slate 100
    text_color = "#64748b"    # Slate 500

    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(x_positions, values, color=primary_color, linewidth=4, marker="o", markersize=6, markerfacecolor="white", markeredgewidth=2)
    ax.fill_between(x_positions, values, color=primary_color, alpha=0.1)
    
    ax.set_title("Operational Revenue Flow", fontsize=14, fontweight="black", loc="left", color="#0f172a", pad=20)
    ax.set_ylabel("Revenue (TZS)", color=text_color, fontsize=10, fontweight="bold")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, color=text_color, fontweight="bold")
    
    ax.grid(axis="y", color=grid_color, linewidth=1, linestyle="--")
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_visible(False)
        
    ax.tick_params(axis="x", rotation=0, labelsize=9, colors=text_color, length=0)
    ax.tick_params(axis="y", labelsize=9, colors=text_color, length=0)
    
    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    return public_path


def _write_revenue_product_graph(points: list[dict[str, Any]], user) -> str | None:
    plt = _load_graph_modules()
    if plt is None:
        return None

    output_path, public_path = _graph_output_paths(user, "revenue-product")
    labels = [str(point["label"]) for point in points] or ["No data"]
    values = [float(point["value"]) for point in points] or [0.0]

    primary_color = "#3b82f6"  # Brand Blue
    secondary_color = "#10b981" # Emerald
    text_color = "#64748b"    # Slate 500

    fig, ax = plt.subplots(figsize=(10.2, 5.4))
    positions = list(range(len(values)))
    
    # Use a subtle blue for the bars
    bars = ax.bar(positions, values, color=primary_color, alpha=0.85, width=0.6)
    
    ax.set_title("Asset Performance Analysis", fontsize=14, fontweight="black", loc="left", color="#0f172a", pad=20)
    ax.set_ylabel("Total Revenue (TZS)", color=text_color, fontsize=10, fontweight="bold")
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=45, ha="right", color=text_color, fontweight="bold")
    
    ax.grid(axis="y", color="#f1f5f9", linewidth=1, linestyle="--")
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_visible(False)
        
    ax.tick_params(axis="x", labelsize=9, colors=text_color, length=0)
    ax.tick_params(axis="y", labelsize=9, colors=text_color, length=0)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + (max(values)*0.02),
                f'{height:,.0f}', ha='center', va='bottom', fontsize=8, fontweight='black', color=primary_color)
                
    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    return public_path


def _sales_records_for_user(db, user):
    rows = _sales_query_for_user(db, user).with_entities(
        Sale.id,
        Sale.date,
        Sale.product,
        Sale.category,
        Sale.quantity,
        Sale.unit_price,
        Sale.status,
    ).order_by(Sale.date.asc(), Sale.id.asc()).all()
    return [
        {
            "id": int(row[0]),
            "date": row[1].isoformat() if row[1] else None,
            "product": row[2] or "Unspecified product",
            "category": row[3] or "Uncategorized",
            "quantity": int(row[4] or 0),
            "unit_price": float(row[5] or 0),
            "status": row[6] or "Pending",
        }
        for row in rows
    ]


def _empty_dashboard_analytics():
    return {
        "cards": [
            {"id": "total_revenue", "label": "Total revenue", "display": "TZS 0", "value": 0, "kind": "money", "subtitle": "All recorded revenue"},
            {"id": "total_orders", "label": "Total orders", "display": "0", "value": 0, "kind": "count", "subtitle": "Orders processed"},
            {"id": "total_units", "label": "Units sold", "display": "0", "value": 0, "kind": "count", "subtitle": "Total pieces sold"},
            {"id": "average_order_value", "label": "Average order value", "display": "TZS 0", "value": 0, "kind": "money", "subtitle": "Average basket size"},
            {"id": "top_product", "label": "Top product", "display": "-", "value": 0, "kind": "text", "subtitle": "Highest revenue product"},
            {"id": "top_product_units", "label": "Top product units", "display": "0", "value": 0, "kind": "count", "subtitle": "Units from best seller"},
            {"id": "active_categories", "label": "Active categories", "display": "0", "value": 0, "kind": "count", "subtitle": "Categories with sales"},
            {"id": "best_day_revenue", "label": "Best day revenue", "display": "TZS 0", "value": 0, "kind": "money", "subtitle": "Highest single-day revenue"},
            {"id": "recent_revenue", "label": "Last 7 days revenue", "display": "TZS 0", "value": 0, "kind": "money", "subtitle": "Fresh sales momentum"},
            {"id": "avg_units_per_order", "label": "Avg units per order", "display": "0", "value": 0, "kind": "count", "subtitle": "Typical units per sale"},
        ],
        "revenueByProduct": [],
        "revenueOverTime": [],
        "recentSales": [],
        "graphs": {
            "revenueByProduct": None,
            "revenueOverTime": None,
        },
        "orderStatusBreakdown": {
            "Pending": 0,
            "Completed": 0,
            "Cancelled": 0,
        },
    }


def dashboard_analytics(db, user) -> dict[str, Any]:
    records = _sales_records_for_user(db, user)
    if not records:
        return _empty_dashboard_analytics()

    pd, np = _load_analysis_modules()
    if pd is not None and np is not None:
        frame = pd.DataFrame.from_records(records)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0)
        frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce").fillna(0.0)
        frame["revenue"] = np.round(frame["quantity"] * frame["unit_price"], 2)
        frame["category"] = frame["category"].fillna("Uncategorized")
        frame["product"] = frame["product"].fillna("Unspecified product")
        frame["status"] = frame["status"].fillna("Pending")

        revenue_by_product = (
            frame.groupby("product", dropna=False)["revenue"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        revenue_over_time = (
            frame.dropna(subset=["date"])
            .groupby(frame.dropna(subset=["date"])["date"].dt.strftime("%Y-%m-%d"))["revenue"]
            .sum()
            .sort_index()
            .reset_index()
        )
        recent_sales_frame = (
            frame.sort_values(["date", "id"], ascending=[False, False])
            .head(6)
            .copy()
        )
        top_product_row = (
            frame.groupby("product", dropna=False)
            .agg(revenue=("revenue", "sum"), units=("quantity", "sum"))
            .sort_values(["revenue", "units"], ascending=False)
            .reset_index()
            .iloc[0]
        )
        daily_revenue = (
            frame.dropna(subset=["date"])
            .groupby(frame.dropna(subset=["date"])["date"].dt.strftime("%Y-%m-%d"))["revenue"]
            .sum()
            .sort_index()
        )
        recent_revenue = float(daily_revenue.tail(7).sum()) if len(daily_revenue) else 0.0
        best_day_revenue = float(daily_revenue.max()) if len(daily_revenue) else 0.0
        total_revenue = float(frame["revenue"].sum())
        total_orders = int(len(frame))
        total_units = int(frame["quantity"].sum())
        average_order_value = float(total_revenue / total_orders) if total_orders else 0.0
        avg_units_per_order = float(total_units / total_orders) if total_orders else 0.0
        active_categories = int(frame["category"].nunique())
        status_counts = {"Pending": 0, "Completed": 0, "Cancelled": 0}
        for raw_status in frame["status"].astype(str).tolist():
            normalized = raw_status.strip().lower()
            if normalized in {"received", "delivered"}:
                status_counts["Completed"] += 1
            elif normalized in {"cancelled", "canceled"}:
                status_counts["Cancelled"] += 1
            else:
                status_counts["Pending"] += 1

        cards = [
            {"id": "total_revenue", "label": "Total revenue", "display": f"TZS {total_revenue:,.0f}", "value": total_revenue, "kind": "money", "subtitle": "All recorded revenue"},
            {"id": "total_orders", "label": "Total orders", "display": f"{total_orders:,}", "value": total_orders, "kind": "count", "subtitle": "Orders processed"},
            {"id": "total_units", "label": "Units sold", "display": f"{total_units:,}", "value": total_units, "kind": "count", "subtitle": "Total pieces sold"},
            {"id": "average_order_value", "label": "Average order value", "display": f"TZS {average_order_value:,.0f}", "value": average_order_value, "kind": "money", "subtitle": "Average basket size"},
            {"id": "top_product", "label": "Top product", "display": str(top_product_row['product']), "value": float(top_product_row["revenue"]), "kind": "text", "subtitle": "Highest revenue product"},
            {"id": "top_product_units", "label": "Top product units", "display": f"{int(top_product_row['units']):,}", "value": int(top_product_row["units"]), "kind": "count", "subtitle": "Units from best seller"},
            {"id": "active_categories", "label": "Active categories", "display": f"{active_categories:,}", "value": active_categories, "kind": "count", "subtitle": "Categories with sales"},
            {"id": "best_day_revenue", "label": "Best day revenue", "display": f"TZS {best_day_revenue:,.0f}", "value": best_day_revenue, "kind": "money", "subtitle": "Highest single-day revenue"},
            {"id": "recent_revenue", "label": "Last 7 days revenue", "display": f"TZS {recent_revenue:,.0f}", "value": recent_revenue, "kind": "money", "subtitle": "Fresh sales momentum"},
            {"id": "avg_units_per_order", "label": "Avg units per order", "display": f"{avg_units_per_order:,.1f}", "value": avg_units_per_order, "kind": "count", "subtitle": "Typical units per sale"},
        ]

        revenue_by_product_points = [
            {"label": str(row["product"]), "value": float(row["revenue"])}
            for _, row in revenue_by_product.iterrows()
        ]
        revenue_over_time_points = [
            {"label": str(row["date"]), "value": float(row["revenue"])}
            for _, row in revenue_over_time.iterrows()
        ]
        
        from backend.analysis.sales_analysis import peak_sales_periods, customer_buying_patterns
        return {
            "cards": cards,
            "revenueByProduct": revenue_by_product_points,
            "revenueOverTime": revenue_over_time_points,
            "recentSales": [
                {
                    "id": int(row["id"]),
                    "date": row["date"].date().isoformat() if getattr(row["date"], "date", None) else None,
                    "product": str(row["product"]),
                    "category": str(row["category"]),
                    "quantity": int(row["quantity"]),
                    "revenue": float(row["revenue"]),
                }
                for _, row in recent_sales_frame.iterrows()
            ],
            "graphs": {
                "revenueByProduct": _write_revenue_product_graph(revenue_by_product_points, user),
                "revenueOverTime": _write_revenue_time_graph(revenue_over_time_points, user),
            },
            "orderStatusBreakdown": status_counts,
            "peakPeriods": peak_sales_periods(db),
            "customerPatterns": customer_buying_patterns(db),
        }

    rows = []
    for record in records:
        revenue = float(record["quantity"] * record["unit_price"])
        rows.append({**record, "revenue": revenue})

    by_product: dict[str, float] = {}
    by_date: dict[str, float] = {}
    by_product_units: dict[str, int] = {}
    categories: set[str] = set()
    for row in rows:
        product = row["product"]
        date = row["date"] or ""
        categories.add(row["category"])
        by_product[product] = by_product.get(product, 0.0) + row["revenue"]
        by_product_units[product] = by_product_units.get(product, 0) + int(row["quantity"])
        if date:
            by_date[date] = by_date.get(date, 0.0) + row["revenue"]

    revenue_by_product = sorted(by_product.items(), key=lambda item: item[1], reverse=True)[:8]
    revenue_over_time = sorted(by_date.items(), key=lambda item: item[0])
    recent_sales = sorted(rows, key=lambda row: (row["date"] or "", row["id"]), reverse=True)[:6]
    top_product = revenue_by_product[0][0] if revenue_by_product else "-"
    top_product_units = by_product_units.get(top_product, 0)
    total_revenue = sum(row["revenue"] for row in rows)
    total_orders = len(rows)
    total_units = sum(int(row["quantity"]) for row in rows)
    average_order_value = total_revenue / total_orders if total_orders else 0.0
    avg_units_per_order = total_units / total_orders if total_orders else 0.0
    best_day_revenue = max(by_date.values()) if by_date else 0.0
    recent_revenue = sum(value for _, value in revenue_over_time[-7:])
    status_counts = {"Pending": 0, "Completed": 0, "Cancelled": 0}
    for row in rows:
        normalized = str(row.get("status") or "Pending").strip().lower()
        if normalized in {"received", "delivered"}:
            status_counts["Completed"] += 1
        elif normalized in {"cancelled", "canceled"}:
            status_counts["Cancelled"] += 1
        else:
            status_counts["Pending"] += 1

    revenue_by_product_points = [{"label": label, "value": value} for label, value in revenue_by_product]
    revenue_over_time_points = [{"label": label, "value": value} for label, value in revenue_over_time]
    return {
        "cards": [
            {"id": "total_revenue", "label": "Total revenue", "display": f"TZS {total_revenue:,.0f}", "value": total_revenue, "kind": "money", "subtitle": "All recorded revenue"},
            {"id": "total_orders", "label": "Total orders", "display": f"{total_orders:,}", "value": total_orders, "kind": "count", "subtitle": "Orders processed"},
            {"id": "total_units", "label": "Units sold", "display": f"{total_units:,}", "value": total_units, "kind": "count", "subtitle": "Total pieces sold"},
            {"id": "average_order_value", "label": "Average order value", "display": f"TZS {average_order_value:,.0f}", "value": average_order_value, "kind": "money", "subtitle": "Average basket size"},
            {"id": "top_product", "label": "Top product", "display": top_product, "value": by_product.get(top_product, 0.0), "kind": "text", "subtitle": "Highest revenue product"},
            {"id": "top_product_units", "label": "Top product units", "display": f"{top_product_units:,}", "value": top_product_units, "kind": "count", "subtitle": "Units from best seller"},
            {"id": "active_categories", "label": "Active categories", "display": f"{len(categories):,}", "value": len(categories), "kind": "count", "subtitle": "Categories with sales"},
            {"id": "best_day_revenue", "label": "Best day revenue", "display": f"TZS {best_day_revenue:,.0f}", "value": best_day_revenue, "kind": "money", "subtitle": "Highest single-day revenue"},
            {"id": "recent_revenue", "label": "Last 7 days revenue", "display": f"TZS {recent_revenue:,.0f}", "value": recent_revenue, "kind": "money", "subtitle": "Fresh sales momentum"},
            {"id": "avg_units_per_order", "label": "Avg units per order", "display": f"{avg_units_per_order:,.1f}", "value": avg_units_per_order, "kind": "count", "subtitle": "Typical units per sale"},
        ],
        "revenueByProduct": revenue_by_product_points,
        "revenueOverTime": revenue_over_time_points,
        "recentSales": recent_sales,
        "graphs": {
            "revenueByProduct": _write_revenue_product_graph(revenue_by_product_points, user),
            "revenueOverTime": _write_revenue_time_graph(revenue_over_time_points, user),
        },
        "orderStatusBreakdown": status_counts,
    }


def dashboard_stats(db, user):
    query = _sales_query_for_user(db, user)
    total_revenue = query.with_entities(func.sum(Sale.quantity * Sale.unit_price)).scalar() or 0
    total_orders = query.with_entities(func.count(Sale.id)).scalar() or 0
    total_units = query.with_entities(func.sum(Sale.quantity)).scalar() or 0
    top_product_row = query.with_entities(
        Sale.product,
        func.sum(Sale.quantity * Sale.unit_price).label("revenue"),
    ).group_by(Sale.product).order_by(func.sum(Sale.quantity * Sale.unit_price).desc()).first()
    top_product = top_product_row[0] if top_product_row else "-"
    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "total_units": total_units,
        "top_product": top_product
    }

def revenue_by_product(db, user):
    rows = _sales_query_for_user(db, user).with_entities(
        Sale.product,
        func.sum(Sale.quantity * Sale.unit_price),
    ).group_by(Sale.product).all()
    return {r[0]: r[1] for r in rows}

def revenue_over_time(db, user):
    rows = _sales_query_for_user(db, user).with_entities(
        Sale.date,
        func.sum(Sale.quantity * Sale.unit_price),
    ).group_by(Sale.date).order_by(Sale.date).all()
    return {r[0].isoformat(): r[1] for r in rows}


def get_recent_sales(db, user):
    sales = _sales_query_for_user(db, user).order_by(Sale.date.desc()).limit(5).all()
    return [
        {
            "date": s.date.isoformat(),
            "product": s.product,
            "category": s.category,
            "quantity": s.quantity,
            "revenue": s.quantity * s.unit_price
        }
        for s in sales
    ]
