"""Backend-side verification of Supabase Auth JWT tokens.

When the frontend authenticates with Supabase Auth (via supabase.auth.signIn*),
it receives a JWT access_token.  That token is sent as a Bearer header to the
FastAPI backend.  This module verifies the token against Supabase's JWKS
endpoint and resolves the Supabase user to an existing app user model.

Env vars required:
    SUPABASE_URL     – e.g. https://xyzabc.supabase.co
    SUPABASE_SERVICE_ROLE_KEY (optional) – for admin-level lookups, not needed
                                            for token verification.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, BusinessUser, LogisticsUser

security = HTTPBearer(auto_error=False)


def _get_supabase_url() -> str:
    url = os.getenv("SUPABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "SUPABASE_URL is not set. Add it to your environment, e.g. "
            "https://your-project-ref.supabase.co"
        )
    return url.rstrip("/")


def _get_jwks_url() -> str:
    # Allow explicit override (some Supabase projects use .jwks.json)
    jwks_url = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if jwks_url:
        return jwks_url
    return f"{_get_supabase_url()}/auth/v1/.well-known/jwks"


@lru_cache(maxsize=1)
def _get_jwk_client() -> PyJWKClient:
    jwks_url = _get_jwks_url()
    return PyJWKClient(jwks_url, cache_keys=True, cache_jwk_set=True)


def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase JWT and return its decoded payload.

    Raises HTTPException(401) if the token is invalid, expired, or the
    signing key cannot be obtained.
    """
    try:
        jwk_client = _get_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Supabase token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Supabase token: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Supabase token verification failed: {exc}")


def _resolve_user_type(payload: dict) -> str:
    """Determine the user_type from the JWT's user_metadata."""
    metadata = payload.get("user_metadata") or {}
    user_type = (metadata.get("user_type") or metadata.get("role") or "").strip().lower()
    if user_type not in ("user", "business", "logistics", "superadmin"):
        user_type = payload.get("app_metadata", {}).get("role", "user")
    if user_type not in ("user", "business", "logistics", "superadmin"):
        user_type = "user"
    return user_type


def _resolve_app_user(db: Session, payload: dict):
    """Look up the app user (User / BusinessUser / LogisticsUser) that corresponds
    to the Supabase user identified by *payload*.

    Matching strategy (in order):
      1. supabase_uid column (if the column exists on the table)
      2. phone number match (digits only)
      3. email match

    For 'superadmin' there is no DB row — build an in-memory User object.
    """
    sub = str(payload.get("sub", ""))
    email = (payload.get("email") or "").strip().lower()
    phone = _normalize_phone(payload.get("phone"))

    user_type = _resolve_user_type(payload)

    if user_type == "superadmin":
        from backend.app.auth import _build_superadmin_user
        return _build_superadmin_user()

    # Try to find by supabase_uid first (column may not exist yet)
    for model_cls in (User, BusinessUser, LogisticsUser):
        if hasattr(model_cls, "supabase_uid"):
            user = db.query(model_cls).filter(getattr(model_cls, "supabase_uid") == sub).first()
            if user:
                return user

    # Fallback: match by email / phone
    if user_type == "business":
        if email:
            user = db.query(BusinessUser).filter(func.lower(BusinessUser.email) == email).first()
            if user:
                return user
        if phone:
            user = db.query(BusinessUser).filter(BusinessUser.phone == phone).first()
            if user:
                return user
        raise HTTPException(status_code=401, detail="No business account linked to this Supabase user")

    if user_type == "logistics":
        if email:
            user = db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == email).first()
            if user:
                return user
        if phone:
            user = db.query(LogisticsUser).filter(LogisticsUser.phone == phone).first()
            if user:
                return user
        raise HTTPException(status_code=401, detail="No logistics account linked to this Supabase user")

    # Default: regular user
    if email:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if user and user.is_active:
            return user
    raise HTTPException(status_code=401, detail="No user account linked to this Supabase user")


def _resolve_or_create_app_user(db: Session, payload: dict):
    """Like _resolve_app_user, but auto-provisions an app user record from the
    Supabase JWT metadata when no existing row is found.

    Used by the /auth/supabase/me endpoint so that any user who has a valid
    Supabase account can obtain an app session on first login.
    """
    sub = str(payload.get("sub", ""))
    email = (payload.get("email") or "").strip().lower()
    phone = _normalize_phone(payload.get("phone"))
    metadata = payload.get("user_metadata") or {}
    user_type = _resolve_user_type(payload)

    if user_type == "superadmin":
        from backend.app.auth import _build_superadmin_user
        return _build_superadmin_user()

    # Try to find by supabase_uid
    for model_cls in (User, BusinessUser, LogisticsUser):
        if hasattr(model_cls, "supabase_uid"):
            user = db.query(model_cls).filter(getattr(model_cls, "supabase_uid") == sub).first()
            if user:
                return user

    # Try email / phone match
    if user_type == "business":
        if email:
            user = db.query(BusinessUser).filter(func.lower(BusinessUser.email) == email).first()
            if user:
                return user
        if phone:
            user = db.query(BusinessUser).filter(BusinessUser.phone == phone).first()
            if user:
                return user
    elif user_type == "logistics":
        if email:
            user = db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == email).first()
            if user:
                return user
        if phone:
            user = db.query(LogisticsUser).filter(LogisticsUser.phone == phone).first()
            if user:
                return user
    else:
        if email:
            user = db.query(User).filter(func.lower(User.email) == email).first()
            if user and user.is_active:
                return user
        if phone:
            user = db.query(User).filter(User.phone == phone).first()
            if user and user.is_active:
                return user

    # --- Auto-provision a new app user from the JWT metadata ---
    name = metadata.get("name", "") or payload.get("email", "").split("@")[0]

    if user_type == "business":
        user = BusinessUser(
            business_name=name or metadata.get("business_name", "Unnamed Business"),
            owner_name=name or "Owner",
            phone=phone,
            email=email or None,
            password_hash=f"supabase:{sub}",
            role="seller",
            is_active=True,
            supabase_uid=sub,
        )
    elif user_type == "logistics":
        user = LogisticsUser(
            name=name,
            phone=phone,
            email=email or None,
            password_hash=f"supabase:{sub}",
            role="logistics",
            is_active=True,
            supabase_uid=sub,
        )
    else:
        existing_email = None
        if email:
            existing_email = (
                db.query(User).filter(func.lower(User.email) == email).first()
                or db.query(BusinessUser).filter(func.lower(BusinessUser.email) == email).first()
                or db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == email).first()
            )
        if existing_email:
            # Email already belongs to another account type — link it
            existing_email.supabase_uid = sub
            db.add(existing_email)
            db.commit()
            return existing_email

        user = User(
            name=name,
            email=email or f"{sub}@supabase.user",
            phone=phone,
            password_hash=f"supabase:{sub}",
            role="user",
            is_active=True,
            supabase_uid=sub,
        )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def get_supabase_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """FastAPI dependency: verify the Supabase Bearer token and return the
    mapped app user.  Falls back to the existing app JWT if the token is not
    a Supabase token (so both auth systems coexist during migration).
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials

    # Try Supabase first — look for Supabase-specific claims
    try:
        # Quick check: Supabase tokens have a 'sub' that's a UUID and
        # 'app_metadata' with a 'provider' field
        unverified_header = jwt.get_unverified_header(token)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})

        is_supabase = "app_metadata" in unverified_payload or (
            unverified_payload.get("aud") == "authenticated"
            and "user_metadata" in unverified_payload
        )

        if is_supabase:
            payload = verify_supabase_token(token)
            user = _resolve_app_user(db, payload)
            _ensure_supabase_uid(db, user, str(payload.get("sub", "")))
            return user
    except HTTPException:
        raise
    except Exception:
        pass

    # Fall back to the existing app JWT
    from backend.app.auth import decode_token, _resolve_user_from_payload

    try:
        payload = decode_token(token, db)
        return _resolve_user_from_payload(db, payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def _ensure_supabase_uid(db: Session, user, supabase_uid: str) -> None:
    """Store the Supabase UID on the user model if the column exists and isn't set."""
    if not supabase_uid:
        return
    if hasattr(user, "supabase_uid") and not getattr(user, "supabase_uid", None):
        try:
            user.supabase_uid = supabase_uid
            db.add(user)
            db.commit()
        except Exception:
            db.rollback()


def extract_supabase_uid_from_request(request: Request, db: Session) -> str | None:
    """Extract and verify a Supabase JWT from the Authorization header.

    Returns the Supabase user UID (``sub``) if a valid Supabase token is
    present, or ``None`` if no token / non-Supabase token / verification fails.
    Used by registration endpoints to link new app users to their Supabase account.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        if "app_metadata" not in unverified:
            return None
        payload = verify_supabase_token(token)
        return str(payload.get("sub", ""))
    except HTTPException:
        return None
    except Exception:
        return None
