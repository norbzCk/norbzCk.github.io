import json
import logging
import os
import uuid
from pathlib import Path
from typing import Literal
from urllib import error, request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.auth import get_optional_current_user
from backend.database import get_db
from backend.models import (
    AssistantConversation,
    AssistantConversationMessage,
    BusinessUser,
    DeliveryOrder,
    LogisticsUser,
    Product,
    Provider,
    RFQ,
    Sale,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

# --- Gemini customer-service provider ---
# Uses a dedicated system prompt + knowledge base (assistant_knowledge/) written
# specifically for customer-facing support, distinct from the general SYSTEM_PROMPT
# below used for the OpenAI path. Tried first for guest/customer chats; falls back
# to OpenAI, then the rule-based fallback, if unavailable.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GEMINIAI_API_KEY", "")).strip()
# Fallback chain, most capable/newest first. Kept short and verified against
# currently-supported models -- gemini-1.5-flash and gemini-2.0-flash are retired
# and will 404, so don't add them back without checking they're still live.
GEMINI_MODEL_FALLBACK = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
_ASSISTANT_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "assistant_knowledge"
_gemini_client = None
_gemini_system_instruction: str | None = None

if GEMINI_API_KEY:
    try:
        from google import genai as _genai
        from google.genai import types as _genai_types
        from google.genai.errors import APIError as _GeminiAPIError, ServerError as _GeminiServerError

        _gemini_client = _genai.Client(api_key=GEMINI_API_KEY)
    except ImportError:
        logger.warning("GEMINI_API_KEY is set but google-genai is not installed; Gemini provider disabled.")
        _gemini_client = None


def _load_gemini_system_instruction() -> str:
    global _gemini_system_instruction
    if _gemini_system_instruction is not None:
        return _gemini_system_instruction

    instructions_path = _ASSISTANT_KNOWLEDGE_DIR / "system_instructions.md"
    knowledge_path = _ASSISTANT_KNOWLEDGE_DIR / "company_information.md"
    instructions = instructions_path.read_text(encoding="utf-8")
    company_info = knowledge_path.read_text(encoding="utf-8")

    _gemini_system_instruction = f"""{instructions}

# COMPANY INFORMATION
The following describes Soko-Link. Use this information when answering
customer questions. Do not invent information that isn't contained here or
in the LIVE PLATFORM CONTEXT provided with each message.

{company_info}
"""
    return _gemini_system_instruction
SYSTEM_PROMPT = """
You are the SokoLink assistant inside a marketplace and operations platform.

Your personality and reply policy:
- Be supportive, calm, practical, and respectful.
- Sound like a reliable teammate, not a robot.
- Prefer clear business English and simple guidance.
- Keep answers concise but useful.
- When the user sounds stuck, reassure them briefly and then give the next best step.
- Adapt to the user's role and current page context.
- Never claim to have completed actions you did not complete.
- Never invent order, payment, delivery, inventory, or account facts.
- If live data is missing, say what is missing and suggest the next action.
- If the request is broad, break it into short steps.
- If asked what to reply or how to reply, provide wording the user can actually use.

Domain guidance:
- Buyer/customer questions should focus on product discovery, orders, payments, and support.
- Seller/business questions should focus on catalog, inventory, order handling, fulfillment, and customer response.
- Logistics questions should focus on assignment, tracking, delivery state, and communication.
- Admin and super admin questions should focus on oversight, users, providers, products, RFQs, and operations.

Formatting:
- Prefer a short paragraph.
- Use a short flat list only if steps are clearer than prose.
- Do not use markdown tables.
""".strip()


class AssistantHistoryItem(BaseModel):
    role: Literal["assistant", "user"]
    text: str = Field(..., min_length=1, max_length=4000)


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    current_path: str = Field("/", max_length=300)
    conversation_id: str | None = Field(default=None, max_length=80)
    history: list[AssistantHistoryItem] = Field(default_factory=list, max_items=12)


class AssistantResponse(BaseModel):
    conversation_id: str
    reply: str
    source: Literal["gemini", "openai", "fallback"]
    model: str


class AssistantHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[AssistantHistoryItem]


def _normalize_role_name(user: User | BusinessUser | LogisticsUser | None) -> str:
    role = (getattr(user, "role", "") or "").strip().lower()
    if role == "user":
        return "customer"
    if role == "super_admin":
        return "super admin"
    return role or "guest"


def _display_name(user: User | BusinessUser | LogisticsUser | None) -> str:
    if not user:
        return "Guest"
    return (
        getattr(user, "name", None)
        or getattr(user, "business_name", None)
        or getattr(user, "owner_name", None)
        or getattr(user, "email", None)
        or "User"
    )


def _describe_area(path: str) -> str:
    current = (path or "/").strip().lower()
    if current == "/":
        return "marketplace home"
    if "/seller" in current:
        return "seller workspace"
    if "/customer" in current:
        return "customer dashboard"
    if "/logistics" in current:
        return "logistics workspace"
    if "/superadmin" in current:
        return "super admin area"
    if "/orders" in current:
        return "orders page"
    if "/products" in current:
        return "products page"
    if "/settings" in current:
        return "settings page"
    if "/profile" in current:
        return "profile page"
    return "current page"


def _build_market_snapshot(db: Session) -> dict:
    top_categories = (
        db.query(Product.category, func.count(Product.id).label("count"))
        .filter(Product.is_active.is_(True))
        .group_by(Product.category)
        .order_by(func.count(Product.id).desc(), Product.category.asc())
        .limit(5)
        .all()
    )
    latest_products = (
        db.query(Product.name, Product.category, Product.price)
        .filter(Product.is_active.is_(True))
        .order_by(Product.id.desc())
        .limit(5)
        .all()
    )
    return {
        "active_products": db.query(func.count(Product.id)).filter(Product.is_active.is_(True)).scalar() or 0,
        "providers": db.query(func.count(Provider.id)).scalar() or 0,
        "rfqs": db.query(func.count(RFQ.id)).scalar() or 0,
        "sales": db.query(func.count(Sale.id)).scalar() or 0,
        "delivery_orders": db.query(func.count(DeliveryOrder.id)).scalar() or 0,
        "top_categories": [
            {"category": category or "Uncategorized", "count": int(count or 0)}
            for category, count in top_categories
        ],
        "latest_products": [
            {
                "name": name,
                "category": category or "General",
                "price": float(price or 0),
            }
            for name, category, price in latest_products
        ],
    }


def _extract_keywords(message: str) -> list[str]:
    words = [token.strip(" ,.!?:;()[]{}").lower() for token in message.split()]
    blocked = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "what",
        "when",
        "where",
        "which",
        "there",
        "their",
        "about",
        "would",
        "could",
        "should",
        "have",
        "need",
        "want",
        "reply",
        "respond",
        "response",
    }
    return [word for word in words if len(word) > 2 and word not in blocked][:6]


def _tool_product_matches(db: Session, message: str) -> list[dict]:
    keywords = _extract_keywords(message)
    if not keywords:
        return []

    filters = []
    for keyword in keywords:
        pattern = f"%{keyword}%"
        filters.append(Product.name.ilike(pattern))
        filters.append(Product.category.ilike(pattern))
        filters.append(Product.description.ilike(pattern))

    items = (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .filter(or_(*filters))
        .order_by(Product.rating_avg.desc(), Product.id.desc())
        .limit(5)
        .all()
    )

    return [
        {
            "id": item.id,
            "name": item.name,
            "category": item.category or "General",
            "price": float(item.price or 0),
            "rating_avg": float(item.rating_avg or 0),
            "rating_count": int(item.rating_count or 0),
        }
        for item in items
    ]


def _tool_role_specific_data(
    db: Session,
    user: User | BusinessUser | LogisticsUser | None,
) -> dict:
    if not user:
        return {}

    role = _normalize_role_name(user)

    if role == "customer":
        recent_sales = (
            db.query(Sale)
            .filter(Sale.created_by == user.id)
            .order_by(Sale.created_at.desc())
            .limit(5)
            .all()
        )
        return {
            "recent_orders": [
                {
                    "id": sale.id,
                    "product": sale.product or "Order",
                    "status": sale.status or "Pending",
                    "delivery_method": sale.delivery_method or "Standard",
                }
                for sale in recent_sales
            ]
        }

    if role == "seller":
        seller_sales = (
            db.query(Sale)
            .filter(Sale.seller_id == user.id)
            .order_by(Sale.created_at.desc())
            .limit(5)
            .all()
        )
        low_stock = (
            db.query(Product)
            .filter(Product.seller_id == user.id, Product.is_active.is_(True), Product.stock <= 5)
            .order_by(Product.stock.asc(), Product.id.desc())
            .limit(5)
            .all()
        )
        return {
            "recent_orders": [
                {
                    "id": sale.id,
                    "product": sale.product or "Order",
                    "status": sale.status or "Pending",
                }
                for sale in seller_sales
            ],
            "low_stock_products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "stock": int(product.stock or 0),
                }
                for product in low_stock
            ],
        }

    if role == "logistics":
        deliveries = (
            db.query(DeliveryOrder)
            .filter(DeliveryOrder.logistics_id == user.id)
            .order_by(DeliveryOrder.created_at.desc())
            .limit(5)
            .all()
        )
        return {
            "recent_deliveries": [
                {
                    "id": item.id,
                    "status": item.status or "pending",
                    "pickup_location": item.pickup_location,
                    "delivery_location": item.delivery_location,
                }
                for item in deliveries
            ]
        }

    if role in {"admin", "super admin", "owner"}:
        latest_rfqs = db.query(RFQ).order_by(RFQ.created_at.desc()).limit(5).all()
        latest_sales = db.query(Sale).order_by(Sale.created_at.desc()).limit(5).all()
        return {
            "latest_rfqs": [
                {
                    "id": rfq.id,
                    "product_interest": rfq.product_interest,
                    "status": rfq.status,
                }
                for rfq in latest_rfqs
            ],
            "latest_sales": [
                {
                    "id": sale.id,
                    "product": sale.product or "Order",
                    "status": sale.status or "Pending",
                }
                for sale in latest_sales
            ],
        }

    return {}


def _tool_provider_matches(db: Session, message: str) -> list[dict]:
    keywords = _extract_keywords(message)
    if not keywords:
        return []

    filters = []
    for keyword in keywords:
        pattern = f"%{keyword}%"
        filters.append(Provider.name.ilike(pattern))
        filters.append(Provider.location.ilike(pattern))

    providers = db.query(Provider).filter(or_(*filters)).order_by(Provider.id.desc()).limit(5).all()
    return [
        {
            "id": provider.id,
            "name": provider.name,
            "location": provider.location,
            "verified": bool(provider.verified),
            "response_time": provider.response_time,
        }
        for provider in providers
    ]


def _build_tool_context(
    db: Session,
    message: str,
    user: User | BusinessUser | LogisticsUser | None,
) -> dict:
    return {
        "matched_products": _tool_product_matches(db, message),
        "matched_providers": _tool_provider_matches(db, message),
        "role_specific": _tool_role_specific_data(db, user),
    }


def _build_user_snapshot(db: Session, user: User | BusinessUser | LogisticsUser | None) -> dict:
    if not user:
        return {"role": "guest"}

    role = _normalize_role_name(user)
    snapshot: dict[str, object] = {
        "role": role,
        "name": _display_name(user),
    }

    if role == "customer" and getattr(user, "id", None):
        snapshot["recent_orders"] = (
            db.query(func.count(Sale.id)).filter(Sale.created_by == user.id).scalar() or 0
        )
    elif role == "seller" and getattr(user, "id", None):
        snapshot["active_products"] = (
            db.query(func.count(Product.id))
            .filter(Product.seller_id == user.id, Product.is_active.is_(True))
            .scalar()
            or 0
        )
        snapshot["seller_orders"] = db.query(func.count(Sale.id)).filter(Sale.seller_id == user.id).scalar() or 0
    elif role == "logistics" and getattr(user, "id", None):
        snapshot["delivery_orders"] = (
            db.query(func.count(DeliveryOrder.id)).filter(DeliveryOrder.logistics_id == user.id).scalar() or 0
        )
        snapshot["status"] = getattr(user, "status", None) or "offline"
        snapshot["availability"] = getattr(user, "availability", None) or "available"

    return snapshot


def _build_openai_input(
    message: str,
    history: list[AssistantHistoryItem],
    area: str,
    user_context: dict,
    market_context: dict,
    tool_context: dict,
) -> list[dict]:
    items: list[dict] = [
        {
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": SYSTEM_PROMPT,
                }
            ],
        },
        {
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": json.dumps(
                        {
                            "current_area": area,
                            "user_context": user_context,
                            "market_context": market_context,
                            "tool_context": tool_context,
                        },
                        ensure_ascii=True,
                    ),
                }
            ],
        },
    ]

    for item in history[-10:]:
        items.append(
            {
                "role": item.role,
                "content": [{"type": "input_text", "text": item.text}],
            }
        )

    items.append(
        {
            "role": "user",
            "content": [{"type": "input_text", "text": message}],
        }
    )
    return items


def _extract_response_text(data: dict) -> str:
    output = data.get("output") or []
    for item in output:
        for content in item.get("content") or []:
            text = content.get("text")
            if text:
                return text.strip()
    return ""


def _call_openai(
    message: str,
    history: list[AssistantHistoryItem],
    area: str,
    user_context: dict,
    market_context: dict,
    tool_context: dict,
) -> str:
    body = {
        "model": DEFAULT_OPENAI_MODEL,
        "input": _build_openai_input(message, history, area, user_context, market_context, tool_context),
    }
    req = request.Request(
        f"{OPENAI_BASE_URL}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"AI provider error: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail="AI provider is unreachable") from exc

    text = _extract_response_text(data)
    if not text:
        raise HTTPException(status_code=502, detail="AI provider returned an empty response")
    return text


def _call_gemini(
    message: str,
    history: list[AssistantHistoryItem],
    area: str,
    user_context: dict,
    market_context: dict,
    tool_context: dict,
) -> tuple[str, str]:
    """Stateless call to Gemini: unlike a REPL session, each HTTP request here
    is independent, so we rebuild the conversation from stored history each
    time rather than keeping a live `client.chats.create()` session in memory
    (that pattern doesn't survive across requests/workers)."""
    if not _gemini_client:
        raise HTTPException(status_code=503, detail="Gemini provider is not configured")

    system_instruction = _load_gemini_system_instruction() + (
        "\n\n# LIVE PLATFORM CONTEXT\n"
        "The knowledge base above tells you to 'use tools' for product and order "
        "lookups. There is no separate tool-calling step in this integration -- "
        "the JSON below IS that tool output, already retrieved for you for this "
        "exact message. Treat it as the live, authoritative platform data the "
        "knowledge base refers to. If a field you need isn't present here (e.g. "
        "no matching product, no recent orders), that means the lookup genuinely "
        "found nothing -- say so plainly rather than guessing or claiming to "
        "check again.\n"
    ) + json.dumps(
        {
            "current_area": area,
            "user_context": user_context,
            "market_context": market_context,
            "tool_context": tool_context,
        },
        ensure_ascii=True,
    )

    contents = [
        _genai_types.Content(
            role="user" if item.role == "user" else "model",
            parts=[_genai_types.Part(text=item.text)],
        )
        for item in history[-10:]
    ]
    contents.append(_genai_types.Content(role="user", parts=[_genai_types.Part(text=message)]))

    last_error: Exception | None = None
    for model_name in GEMINI_MODEL_FALLBACK:
        try:
            response = _gemini_client.models.generate_content(
                model=model_name,
                contents=contents,
                config=_genai_types.GenerateContentConfig(system_instruction=system_instruction),
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Gemini returned an empty response")
            return text, model_name
        except (_GeminiServerError, _GeminiAPIError, ValueError) as exc:
            logger.warning("Gemini model %s unavailable: %s", model_name, exc)
            last_error = exc
            continue

    raise HTTPException(status_code=502, detail=f"Gemini provider unavailable: {last_error}")


def get_ai_reply(message: str, user_context: dict, market_context: dict, tool_context: dict, area: str = "marketplace home") -> str:
    """Rule-based fallback reply, used when neither Gemini nor OpenAI is
    configured or reachable.

    IMPORTANT: this must answer the person's actual question directly. It
    previously always responded in a "here's how you should reply to the
    customer" coaching voice -- reasonable for a staff member explicitly
    asking for reply wording, completely wrong for a customer who just
    asked "where's my order" and got told how someone else should answer
    them. That mismatch is what made fallback replies look broken/
    nonsensical. Grounded in the same knowledge base doc used by the
    Gemini path plus live db-derived context -- never invents platform
    facts."""
    query = message.strip().lower()
    role = str(user_context.get("role") or "guest")
    name = str(user_context.get("name") or "there")
    is_staff = role in {"seller", "logistics", "admin", "super_admin", "owner"}

    # Only staff explicitly asking for reply wording get the coaching voice --
    # this was previously the behavior for every single message.
    if is_staff and any(phrase in query for phrase in ["what to reply", "how to reply", "how should i respond", "draft a reply"]):
        return (
            f"Here's a reply you can use: \"I've checked this and the next step is to confirm the key details first so I can help you correctly.\" "
            "Tell me the exact message or situation and I'll tailor the wording."
        )

    # Check for a real product match FIRST, before any keyword gate: someone
    # asking "do you have solar lamps?" or just naming a product by name
    # won't hit a generic keyword list like ["product", "catalog", "find"],
    # but the live db search behind tool_context already found (or didn't
    # find) a real match for this exact message -- trust that over guessing
    # from a handful of keywords.
    matched_products = tool_context.get("matched_products") or []
    if matched_products and not any(word in query for word in ["hello", "hi", "hey", "mambo", "habari"]):
        preview = ", ".join(f"{item['name']} (TZS {item['price']:,.0f})" for item in matched_products[:3])
        return f"Here's what I found: {preview}. Want more detail on any of these, or a different category?"

    if any(word in query for word in ["hello", "hi", "hey", "mambo", "habari"]):
        return f"Hi {name}! I'm the Soko-Link assistant. Ask me about products, your orders, deliveries, payments, or your account, and I'll help directly."

    if any(word in query for word in ["product", "catalog", "find", "search", "recommend"]):
        top_categories = market_context.get("top_categories") or []
        category_text = ", ".join(item["category"] for item in top_categories[:3])
        if category_text:
            return f"I don't have an exact match for that yet, but our most active categories right now are {category_text}. What are you looking for specifically?"
        return "I don't have a specific match for that search yet. Could you tell me the product name or category you're after?"

    if any(word in query for word in ["order", "delivery", "shipment", "dispatch", "track", "where is my"]):
        role_specific = tool_context.get("role_specific") or {}
        if role == "customer" and role_specific.get("recent_orders"):
            latest = role_specific["recent_orders"][0]
            return f"Your most recent order ({latest['product']}) is currently: {latest['status']}. You can see full tracking details and confirm receipt from your Orders page."
        if role == "logistics" and role_specific.get("recent_deliveries"):
            latest = role_specific["recent_deliveries"][0]
            return f"Your most recent delivery is currently: {latest['status']}. Check your Deliveries tab for pickup/drop-off details and the verification code."
        if role == "customer":
            return "I don't see any recent orders on your account yet. Once you place an order, you'll be able to track its status here and on your Orders page."
        if role == "guest":
            return "To check an order's status, you'll need to sign in first -- I can only look up orders tied to your account. Once you're signed in, ask me again and I'll pull up the details."
        return (
            f"For {role} order/delivery questions in the {area}: check the order's current status and what's confirmed vs. pending on the "
            "relevant dashboard page, since that always reflects the live, authoritative state."
        )

    if any(word in query for word in ["payment", "pay", "mpesa", "m-pesa", "airtel", "tigo", "bank transfer", "refund"]):
        return (
            "Soko-Link supports M-Pesa, Airtel Money, Tigo Pesa, bank transfer, and cash on delivery, depending on what the seller "
            "has enabled for that order. For a specific payment or refund question tied to an order, I'd need to check that order's "
            "live payment status rather than guess -- what's the order or issue?"
        )

    if any(word in query for word in ["settings", "profile", "account", "password", "theme"]):
        return "You can update your profile, password, and preferences from Settings. What specifically are you trying to change?"

    if any(word in query for word in ["seller", "sell", "become a seller", "register a business"]):
        return (
            "Sellers on Soko-Link can list and manage products, handle orders and fulfillment, and track sales performance. "
            "If you want to become a seller, you can register a business account from the sign-up page. What would you like to know?"
        )

    if any(word in query for word in ["human", "agent", "support", "help", "complaint", "dispute"]):
        return (
            "I can help with most product, order, payment, and account questions directly. If this needs a human, "
            "let me know the specifics and I'll point you to the right support channel or flag it for escalation."
        )

    return (
        f"I'm the Soko-Link assistant for the {area}. I can help with product discovery, order status, payments, deliveries, "
        "or account questions -- what do you need?"
    )


def _subject_identity(user: User | BusinessUser | LogisticsUser | None) -> tuple[str, int | None]:
    if user is None:
        return "guest", None
    role = _normalize_role_name(user)
    return role, getattr(user, "id", None)


def _ensure_conversation(
    db: Session,
    conversation_id: str | None,
    current_path: str,
    user: User | BusinessUser | LogisticsUser | None,
) -> AssistantConversation:
    subject_type, subject_id = _subject_identity(user)
    normalized_id = (conversation_id or "").strip() or f"conv_{uuid.uuid4().hex}"

    conversation = db.query(AssistantConversation).filter(AssistantConversation.id == normalized_id).first()
    if conversation is None:
        conversation = AssistantConversation(
            id=normalized_id,
            subject_type=subject_type,
            subject_id=subject_id,
            current_path=current_path,
            title="SokoLink Assistant",
        )
        db.add(conversation)
        db.flush()
        return conversation

    if conversation.subject_type != subject_type or conversation.subject_id != subject_id:
        raise HTTPException(status_code=403, detail="Conversation does not belong to the current subject")

    conversation.current_path = current_path
    return conversation


def _get_existing_conversation(
    db: Session,
    conversation_id: str,
    user: User | BusinessUser | LogisticsUser | None,
) -> AssistantConversation:
    subject_type, subject_id = _subject_identity(user)
    conversation = db.query(AssistantConversation).filter(AssistantConversation.id == conversation_id).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.subject_type != subject_type or conversation.subject_id != subject_id:
        raise HTTPException(status_code=403, detail="Conversation does not belong to the current subject")
    return conversation


def _store_message(
    db: Session,
    conversation_id: str,
    role: str,
    text: str,
    source: str | None = None,
    model: str | None = None,
) -> None:
    db.add(
        AssistantConversationMessage(
            conversation_id=conversation_id,
            role=role,
            text=text,
            source=source,
            model=model,
        )
    )


def _is_noise_assistant_message(text: str) -> bool:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return False
    welcome_markers = (
        "I’m your SokoLink assistant",
        "I'm your SokoLink assistant",
        "I’m here with you",
        "I'm here with you",
    )
    route_markers = (
        "You’re now in the",
        "You're now in the",
        "I’ll keep my help focused on what matters here",
        "I'll keep my help focused on what matters here",
    )
    return any(marker in cleaned for marker in welcome_markers) or any(marker in cleaned for marker in route_markers)


def _filter_prompt_history(history: list[AssistantHistoryItem]) -> list[AssistantHistoryItem]:
    return [item for item in history if not _is_noise_assistant_message(item.text)]


def _conversation_history(
    db: Session,
    conversation_id: str,
) -> list[AssistantHistoryItem]:
    items = (
        db.query(AssistantConversationMessage)
        .filter(AssistantConversationMessage.conversation_id == conversation_id)
        .order_by(AssistantConversationMessage.created_at.asc(), AssistantConversationMessage.id.asc())
        .all()
    )
    return _filter_prompt_history([AssistantHistoryItem(role=item.role, text=item.text) for item in items])


@router.post("/assistant", response_model=AssistantResponse)
def assistant_reply(
    payload: AssistantRequest,
    db: Session = Depends(get_db),
    current_user: User | BusinessUser | LogisticsUser | None = Depends(get_optional_current_user),
):
    conversation = _ensure_conversation(db, payload.conversation_id, payload.current_path, current_user)
    area = _describe_area(payload.current_path)
    user_context = _build_user_snapshot(db, current_user)
    market_context = _build_market_snapshot(db)
    tool_context = _build_tool_context(db, payload.message, current_user)

    _store_message(db, conversation.id, "user", payload.message)
    db.flush()
    stored_history = _filter_prompt_history(_conversation_history(db, conversation.id))

    if _gemini_client:
        try:
            reply, model_used = _call_gemini(
                payload.message, stored_history[:-1], area, user_context, market_context, tool_context
            )
            _store_message(db, conversation.id, "assistant", reply, source="gemini", model=model_used)
            db.commit()
            return AssistantResponse(
                conversation_id=conversation.id,
                reply=reply,
                source="gemini",
                model=model_used,
            )
        except HTTPException as exc:
            logger.warning("Gemini provider failed, falling back: %s", exc.detail)
            db.rollback()
            conversation = _ensure_conversation(db, conversation.id, payload.current_path, current_user)
            _store_message(db, conversation.id, "user", payload.message)
            db.flush()

    if OPENAI_API_KEY:
        try:
            reply = _call_openai(payload.message, stored_history[:-1], area, user_context, market_context, tool_context)
            _store_message(db, conversation.id, "assistant", reply, source="openai", model=DEFAULT_OPENAI_MODEL)
            db.commit()
            return AssistantResponse(
                conversation_id=conversation.id,
                reply=reply,
                source="openai",
                model=DEFAULT_OPENAI_MODEL,
            )
        except HTTPException:
            db.rollback()
            conversation = _ensure_conversation(db, conversation.id, payload.current_path, current_user)
            _store_message(db, conversation.id, "user", payload.message)
            db.flush()
            pass

    reply = get_ai_reply(payload.message, user_context, market_context, tool_context, area)
    _store_message(db, conversation.id, "assistant", reply, source="fallback", model="support-policy-fallback")
    db.commit()
    return AssistantResponse(
        conversation_id=conversation.id,
        reply=reply,
        source="fallback",
        model="support-policy-fallback",
    )


@router.get("/assistant/history/{conversation_id}", response_model=AssistantHistoryResponse)
def assistant_history(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User | BusinessUser | LogisticsUser | None = Depends(get_optional_current_user),
):
    conversation = _get_existing_conversation(db, conversation_id, current_user)
    return AssistantHistoryResponse(
        conversation_id=conversation.id,
        messages=_conversation_history(db, conversation.id),
    )
