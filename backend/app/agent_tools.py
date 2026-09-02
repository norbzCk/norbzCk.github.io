"""
Real tools the AI agent can call to actually DO things, not just describe
data. Every tool here is a thin wrapper around the EXISTING, already-tested
FastAPI route function for that action (create_product, update_order_status,
etc.) -- called directly as a plain Python function with real arguments,
bypassing only the HTTP/dependency-injection layer. This is deliberate:
duplicating that business logic (ownership checks, payment validation,
status-transition rules) into separate "agent" code would inevitably drift
from the real endpoints over time. Calling the real function means the
agent can never do anything the corresponding API endpoint wouldn't also
allow, and any future bugfix to that endpoint automatically applies here
too.

Two tiers:
  - AUTO-EXECUTE: read-only lookups and clearly reversible actions (rate an
    order, deactivate/reactivate a product). The agent runs these itself,
    no confirmation needed.
  - CONFIRM-FIRST: anything that creates data, changes an order's status,
    or is otherwise consequential. The agent proposes the action; nothing
    happens until the person explicitly confirms it. This mirrors how
    Alibaba's Accio Work scopes its own agent -- financial/destructive
    actions require explicit approval, read/low-risk actions don't.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Callable

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from backend.models import BusinessUser, LogisticsUser, Sale, User


@dataclasses.dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema, minus "type": "object" wrapper details
    handler: Callable[..., dict]
    requires_confirmation: bool
    allowed_roles: set[str]  # role strings this tool is visible to


def _actor_role(user: User | BusinessUser | LogisticsUser | None) -> str:
    if user is None:
        return "guest"
    return str(getattr(user, "role", None) or ("logistics" if isinstance(user, LogisticsUser) else "user"))


# ---------------------------------------------------------------------------
# Read tools (auto-execute for everyone who can see the data)
# ---------------------------------------------------------------------------

def _tool_search_products(db: Session, current, *, query: str = "", category: str | None = None, max_price: float | None = None) -> dict:
    from backend.app.products import search_products as _search_products

    results = _search_products(
        q=query or None,
        category=category,
        min_price=None,
        max_price=max_price,
        in_stock=None,
        sort="featured",
        limit=8,
        offset=0,
        db=db,
    )
    items = results.get("items", results) if isinstance(results, dict) else results
    return {"products": items}


def _tool_get_my_orders(db: Session, current, *, status: str | None = None) -> dict:
    from backend.app.sales import get_orders as _get_orders

    orders = _get_orders(db=db, current=current)
    if status:
        orders = [o for o in orders if str(o.get("status", "")).lower() == status.lower()]
    return {"orders": orders[:10]}


def _tool_get_my_products(db: Session, current, *, include_inactive: bool = True) -> dict:
    from backend.app.products import get_products as _get_products

    products = _get_products(db=db, current=current)
    if not include_inactive:
        products = [p for p in products if p.get("is_active") is not False]
    return {"products": products[:15]}


# ---------------------------------------------------------------------------
# Low-risk write tools (auto-execute, but only on the caller's own data)
# ---------------------------------------------------------------------------

def _tool_rate_order(db: Session, current, *, order_id: int, rating: int) -> dict:
    from backend.app.sales import rate_order as _rate_order

    result = _rate_order(order_id=order_id, payload={"rating": rating}, background_tasks=BackgroundTasks(), db=db, current=current)
    return {"result": result}


def _tool_confirm_order_received(db: Session, current, *, order_id: int) -> dict:
    from backend.app.sales import confirm_received as _confirm_received

    result = _confirm_received(order_id=order_id, background_tasks=BackgroundTasks(), db=db, current=current)
    return {"result": result}


def _tool_deactivate_product(db: Session, current, *, product_id: int) -> dict:
    from backend.app.products import delete_product as _delete_product

    result = _delete_product(product_id=product_id, db=db, current=current)
    return {"result": result}


def _tool_reactivate_product(db: Session, current, *, product_id: int) -> dict:
    from backend.app.products import reactivate_product as _reactivate_product

    result = _reactivate_product(product_id=product_id, db=db, current=current)
    return {"result": result}


# ---------------------------------------------------------------------------
# High-risk write tools (require explicit confirmation before executing)
# ---------------------------------------------------------------------------

def _tool_create_product(db: Session, current, *, name: str, category: str, price: float, stock: int, description: str) -> dict:
    from backend.app.products import create_product as _create_product
    from backend.app.schemas import ProductCreate

    payload = ProductCreate(name=name, category=category, price=price, stock=stock, description=description)
    result = _create_product(product=payload, db=db, current=current)
    return {"result": result}


def _tool_update_order_status(db: Session, current, *, order_id: int, new_status: str) -> dict:
    from backend.app.sales import update_order_status as _update_order_status

    result = _update_order_status(order_id=order_id, payload={"status": new_status}, background_tasks=BackgroundTasks(), db=db, current=current)
    return {"result": result}


TOOLS: dict[str, ToolSpec] = {
    "search_products": ToolSpec(
        name="search_products",
        description="Search the marketplace for products by keyword, category, or max price. Use this whenever the person asks to find, browse, or compare products.",
        parameters={
            "query": {"type": "string", "description": "Search keywords, e.g. product name"},
            "category": {"type": "string", "description": "Optional category filter"},
            "max_price": {"type": "number", "description": "Optional maximum price in TZS"},
        },
        handler=_tool_search_products,
        requires_confirmation=False,
        allowed_roles={"guest", "user", "seller", "logistics", "admin", "super_admin", "owner"},
    ),
    "get_my_orders": ToolSpec(
        name="get_my_orders",
        description="Get the current person's own orders (as a buyer) or sales (as a seller), optionally filtered by status.",
        parameters={"status": {"type": "string", "description": "Optional status filter, e.g. 'Pending', 'Shipped', 'Received'"}},
        handler=_tool_get_my_orders,
        requires_confirmation=False,
        allowed_roles={"user", "seller", "admin", "super_admin", "owner"},
    ),
    "get_my_products": ToolSpec(
        name="get_my_products",
        description="List the seller's own product catalog, including deactivated listings.",
        parameters={"include_inactive": {"type": "boolean", "description": "Whether to include deactivated products"}},
        handler=_tool_get_my_products,
        requires_confirmation=False,
        allowed_roles={"seller", "admin", "super_admin", "owner"},
    ),
    "rate_order": ToolSpec(
        name="rate_order",
        description="Rate a received order 1-5 stars. Only works on the buyer's own orders that are already marked Received.",
        parameters={
            "order_id": {"type": "integer", "description": "The order ID to rate"},
            "rating": {"type": "integer", "description": "Rating from 1 to 5"},
        },
        handler=_tool_rate_order,
        requires_confirmation=False,
        allowed_roles={"user"},
    ),
    "confirm_order_received": ToolSpec(
        name="confirm_order_received",
        description="Confirm the buyer has physically received their order. Only works on the buyer's own orders.",
        parameters={"order_id": {"type": "integer", "description": "The order ID to confirm as received"}},
        handler=_tool_confirm_order_received,
        requires_confirmation=False,
        allowed_roles={"user"},
    ),
    "deactivate_product": ToolSpec(
        name="deactivate_product",
        description="Deactivate (unlist) one of the seller's own products. This is reversible with reactivate_product.",
        parameters={"product_id": {"type": "integer", "description": "The product ID to deactivate"}},
        handler=_tool_deactivate_product,
        requires_confirmation=False,
        allowed_roles={"seller", "admin", "super_admin", "owner"},
    ),
    "reactivate_product": ToolSpec(
        name="reactivate_product",
        description="Restore a previously deactivated product listing owned by the seller.",
        parameters={"product_id": {"type": "integer", "description": "The product ID to reactivate"}},
        handler=_tool_reactivate_product,
        requires_confirmation=False,
        allowed_roles={"seller", "admin", "super_admin", "owner"},
    ),
    "create_product": ToolSpec(
        name="create_product",
        description="List a brand-new product on the seller's storefront. Requires explicit confirmation before it actually goes live.",
        parameters={
            "name": {"type": "string"},
            "category": {"type": "string"},
            "price": {"type": "number", "description": "Price in TZS, must be positive"},
            "stock": {"type": "integer", "description": "Stock quantity, 0 or more"},
            "description": {"type": "string"},
        },
        handler=_tool_create_product,
        requires_confirmation=True,
        allowed_roles={"seller", "admin", "super_admin", "owner"},
    ),
    "update_order_status": ToolSpec(
        name="update_order_status",
        description="Move one of the seller's orders to a new status (e.g. Confirmed, Packed, Ready For Shipping, Cancelled). Requires explicit confirmation. Will fail if the transition isn't valid or payment isn't complete -- same rules as the dashboard.",
        parameters={
            "order_id": {"type": "integer"},
            "new_status": {"type": "string", "description": "One of: Confirmed, Packed, Ready For Shipping, Shipped, Cancelled"},
        },
        handler=_tool_update_order_status,
        requires_confirmation=True,
        allowed_roles={"seller", "admin", "super_admin", "owner"},
    ),
}


def tools_for_role(role: str) -> list[ToolSpec]:
    return [tool for tool in TOOLS.values() if role in tool.allowed_roles]


def get_tool(name: str) -> ToolSpec | None:
    return TOOLS.get(name)


def execute_tool(name: str, db: Session, current_user, **kwargs) -> dict:
    """Run a tool's handler, translating any HTTPException the underlying
    route function raises (ownership checks, invalid transitions, payment
    not complete, etc.) into a plain result dict the model can read and
    explain to the person, instead of an unhandled exception."""
    tool = get_tool(name)
    if not tool:
        return {"error": f"Unknown tool '{name}'"}

    role = _actor_role(current_user)
    if role not in tool.allowed_roles:
        return {"error": f"This action isn't available for your account type."}

    try:
        return tool.handler(db, current_user, **kwargs)
    except HTTPException as exc:
        db.rollback()
        return {"error": str(exc.detail)}
    except TypeError as exc:
        return {"error": f"Invalid arguments for {name}: {exc}"}
