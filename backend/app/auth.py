import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.database import SessionLocal, get_db
from backend.app.notification_service import build_login_email, build_password_reset_email, create_notification, resolve_subject
from backend.models import User, BusinessUser, LogisticsUser, RefreshToken, TokenBlocklist

# Security Constants
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_TTL_SECONDS = 60 * 30
SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "superadmin@gmail.com").strip().lower()
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "adminkey")

security = HTTPBearer(auto_error=False)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["Auth"])
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _normalize_role(value: str | None) -> str:
    role = (value or "").strip().lower()
    if role == "customer":
        return "user"
    return role


def validate_password_strength(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False

    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(check, expected)
    except ValueError:
        pass

    # Backward compatibility
    if hmac.compare_digest(stored, password):
        return True

    legacy_hashers = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
    normalized = stored.strip().lower()
    algorithm = legacy_hashers.get(len(normalized))
    if algorithm and all(ch in "0123456789abcdef" for ch in normalized):
        legacy_digest = hashlib.new(algorithm, password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_digest, normalized)
    return False


def password_needs_rehash(stored: str | None) -> bool:
    return "$" not in (stored or "")


def verify_and_upgrade_password(password: str, account: User | BusinessUser | LogisticsUser) -> bool:
    if not verify_password(password, account.password_hash):
        return False
    if password_needs_rehash(account.password_hash):
        account.password_hash = hash_password(password)
    return True


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, user_type: str, db: Session) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token = secrets.token_urlsafe(32)
    db_token = RefreshToken(
        user_id=user_id,
        user_type=user_type,
        token=token,
        expires_at=expire
    )
    db.add(db_token)
    db.commit()
    return token


def decode_token(token: str, db: Session | None = None) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if db and jti:
            blacklisted = db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first()
            if blacklisted:
                raise HTTPException(status_code=401, detail="Token has been revoked")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def set_auth_cookies(response: Response, access_token: str, refresh_token: str | None = None):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=os.getenv("NODE_ENV") == "production",
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            expires=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            samesite="lax",
            secure=os.getenv("NODE_ENV") == "production",
        )


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


def _get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


def _build_superadmin_user() -> User:
    return User(
        id=0,
        name="Super Admin",
        email=SUPERADMIN_EMAIL,
        phone=None,
        address=None,
        role="super_admin",
        is_active=True,
        is_verified=True,
    )


def _normalize_identifier(value: str | None) -> str:
    return (value or "").strip()


def _normalize_email(value: str | None) -> str:
    return _normalize_identifier(value).lower()


def _normalize_phone(value: str | None) -> str | None:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return digits or None


def _phone_matches(stored: str | None, provided: str | None) -> bool:
    stored_digits = _normalize_phone(stored)
    provided_digits = _normalize_phone(provided)
    return bool(stored_digits and provided_digits and stored_digits == provided_digits)


def _superadmin_matches(email: str | None, password: str | None) -> bool:
    return _normalize_email(email) == SUPERADMIN_EMAIL and (password or "") == SUPERADMIN_PASSWORD


def _find_recovery_account(db: Session, identifier: str):
    lookup = _normalize_identifier(identifier)
    if not lookup:
        return None, None

    lowered = lookup.lower()
    normalized_phone = _normalize_phone(lookup)

    if "@" in lookup:
        user = db.query(User).filter(func.lower(User.email) == lowered).first()
        if user and user.is_active:
            user.role = _normalize_role(user.role)
            return "user", user

        business = db.query(BusinessUser).filter(func.lower(BusinessUser.email) == lowered).first()
        if business and business.is_active:
            business.role = _normalize_role(business.role)
            return "business", business

        logistics = db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == lowered).first()
        if logistics and logistics.is_active:
            logistics.role = "logistics"
            return "logistics", logistics

    if normalized_phone:
        users = db.query(User).filter(User.phone.isnot(None)).all()
        for user in users:
            if _phone_matches(user.phone, normalized_phone) and user.is_active:
                user.role = _normalize_role(user.role)
                return "user", user

        businesses = db.query(BusinessUser).filter(BusinessUser.phone.isnot(None)).all()
        for business in businesses:
            if _phone_matches(business.phone, normalized_phone) and business.is_active:
                business.role = _normalize_role(business.role)
                return "business", business

        logistics = db.query(LogisticsUser).filter(LogisticsUser.phone.isnot(None)).all()
        for logistics_user in logistics:
            if _phone_matches(logistics_user.phone, normalized_phone) and logistics_user.is_active:
                logistics_user.role = "logistics"
                return "logistics", logistics_user

    return None, None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | BusinessUser | LogisticsUser:
    user = get_optional_current_user(request, credentials, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _resolve_user_from_payload(
    db: Session,
    payload: dict,
) -> User | BusinessUser | LogisticsUser:
    if payload.get("user_type") == "superadmin" or (
        _normalize_role(payload.get("role")) == "super_admin" and str(payload.get("sub", "")) == "0"
    ):
        return _build_superadmin_user()

    user_type = payload.get("user_type")
    if user_type == "business":
        user_id = payload.get("user_id") or payload.get("sub")
        business = None
        if user_id is not None:
            try:
                business = db.query(BusinessUser).filter(BusinessUser.id == int(user_id)).first()
            except (TypeError, ValueError):
                business = None
        if not business or not business.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        business.role = _normalize_role(business.role)
        return business

    if user_type == "logistics":
        user_id = payload.get("user_id") or payload.get("sub")
        logistics = None
        if user_id is not None:
            try:
                logistics = db.query(LogisticsUser).filter(LogisticsUser.id == int(user_id)).first()
            except (TypeError, ValueError):
                logistics = None
        if not logistics or not logistics.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        logistics.role = "logistics"
        return logistics

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = _get_user_by_id(db, int(user_id))
    user.role = _normalize_role(user.role)
    return user


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | BusinessUser | LogisticsUser | None:
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        return None

    # 1. Try the existing app JWT (signed with APP_SECRET_KEY)
    try:
        payload = decode_token(token, db)
        return _resolve_user_from_payload(db, payload)
    except HTTPException:
        pass
    except Exception:
        pass

    # 2. Fall back to Supabase Auth JWT
    try:
        from backend.app.supabase_auth import verify_supabase_token, _resolve_app_user, _ensure_supabase_uid
        payload = verify_supabase_token(token)
        user = _resolve_app_user(db, payload)
        _ensure_supabase_uid(db, user, str(payload.get("sub", "")))
        return user
    except HTTPException:
        return None
    except Exception:
        return None


def get_user_from_token(
    token: str,
    db: Session | None = None,
) -> User | BusinessUser | LogisticsUser | None:
    """Extract user from JWT token without requiring FastAPI dependencies.

    Tries the app JWT first; falls back to Supabase Auth JWT.
    """
    if db is None:
        from backend.database import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        # 1. Try app JWT
        try:
            payload = decode_token(token, db)
            return _resolve_user_from_payload(db, payload)
        except Exception:
            pass

        # 2. Try Supabase JWT
        from backend.app.supabase_auth import verify_supabase_token, _resolve_app_user, _ensure_supabase_uid
        payload = verify_supabase_token(token)
        user = _resolve_app_user(db, payload)
        _ensure_supabase_uid(db, user, str(payload.get("sub", "")))
        return user
    except Exception:
        return None
    finally:
        if close_db:
            db.close()


def require_roles(*allowed: str):
    allowed_set = {_normalize_role(role) for role in allowed}

    def checker(user: User = Depends(get_current_user)) -> User:
        role = _normalize_role(user.role)
        user.role = role
        if role == "owner" and ("super_admin" in allowed_set or "admin" in allowed_set):
            return user
        if role == "seller" and "admin" in allowed_set:
            return user
        if role == "super_admin" and "admin" in allowed_set:
            return user
        if role not in allowed_set:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return checker


@router.post("/password-recovery/request")
@limiter.limit("3/minute")
def request_password_recovery(
    request: Request,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    identifier = (payload.get("identifier") or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Please enter your email or phone number")

    account_type, account = _find_recovery_account(db, identifier)
    response = {
        "message": "If an account matches the provided details, password recovery instructions are ready."
    }

    if account and account.is_active:
        reset_token = create_access_token(
            data={
                "purpose": "password_recovery",
                "account_type": account_type,
                "user_id": account.id,
                "sub": account.id,
            },
            expires_delta=timedelta(seconds=PASSWORD_RESET_TTL_SECONDS)
        )
        
        recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(account)
        reset_subject, reset_body = build_password_reset_email(recipient_name, reset_token)
        create_notification(
            db,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_email=recipient_email,
            title="Password reset requested",
            message="Password reset instructions are ready for your account.",
            notification_type="security",
            severity="warning",
            action_href="/forgot-password",
            metadata={"purpose": "password_recovery"},
            send_email=bool(recipient_email),
            email_subject=reset_subject,
            email_body=reset_body,
            background_tasks=background_tasks,
        )
        db.commit()

    return response


@router.post("/password-recovery/reset")
@limiter.limit("3/minute")
def reset_password_recovery(request: Request, payload: dict, db: Session = Depends(get_db)):
    token = (payload.get("token") or "").strip()
    new_password = payload.get("new_password") or ""

    if not token:
        raise HTTPException(status_code=400, detail="Reset token is required")
    validate_password_strength(new_password)

    try:
        decoded = decode_token(token, db)
    except HTTPException:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

    if decoded.get("purpose") != "password_recovery":
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

    account_type = decoded.get("account_type")
    account_id = decoded.get("user_id") or decoded.get("sub")

    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

    if account_type == "business":
        account = db.query(BusinessUser).filter(BusinessUser.id == account_id).first()
    elif account_type == "logistics":
        account = db.query(LogisticsUser).filter(LogisticsUser.id == account_id).first()
    else:
        account = db.query(User).filter(User.id == account_id).first()

    if not account or not account.is_active:
        raise HTTPException(status_code=400, detail="We could not reset the password for this account")

    account.password_hash = hash_password(new_password)
    db.add(account)
    # Revoke the reset token
    jti = decoded.get("jti")
    if jti:
        db.add(TokenBlocklist(jti=jti))
    db.commit()
    return {"message": "Password reset successful. You can now sign in with your new password."}


@router.post("/register")
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: dict,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    from backend.app.supabase_auth import extract_supabase_uid_from_request
    supabase_uid = extract_supabase_uid_from_request(request, db)

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    validate_password_strength(password)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    phone = (payload.get("phone") or "").strip() or None
    if phone:
        existing_phone = db.query(User).filter(User.phone == phone).first()
        if existing_phone:
            raise HTTPException(status_code=400, detail="Phone number already registered")

    verification_token = secrets.token_urlsafe(32)
    model = User(
        name=name,
        email=email,
        phone=phone,
        address=(payload.get("address") or "").strip() or None,
        profile_photo=(payload.get("profile_photo") or "").strip() or None,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
        is_verified=False,
        verification_token=verification_token,
        supabase_uid=supabase_uid,
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
        title="Welcome to Soko-Link",
        message="Please verify your email to complete registration.",
        notification_type="system",
        severity="success",
        action_href=f"/verify-email?token={verification_token}",
        send_email=bool(recipient_email),
        email_subject="Verify your Soko-Link account",
        email_body=f"Hello {recipient_name},\n\nWelcome to Soko-Link. Please click the link below to verify your email:\n\n{verification_token}\n\nSoko-Link Team",
        background_tasks=background_tasks,
    )
    db.commit()

    token = create_access_token({"sub": model.id, "role": "user", "email": model.email, "user_type": "user"})
    refresh_token = create_refresh_token(model.id, "user", db)
    set_auth_cookies(response, token, refresh_token)

    return {
        "access_token": token,
        "token_type": "bearer",
        "userType": "user",
        "user": {
            "id": model.id,
            "name": model.name,
            "email": model.email,
            "role": "user",
            "is_verified": model.is_verified,
        },
    }


@router.post("/register-customer")
@limiter.limit("5/minute")
def register_customer(
    request: Request,
    payload: dict,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    from backend.app.supabase_auth import extract_supabase_uid_from_request
    supabase_uid = extract_supabase_uid_from_request(request, db)

    name = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip().lower() or None
    password = payload.get("password") or ""
    location = (payload.get("location") or "").strip() or None
    
    if not name or not phone or not password:
        raise HTTPException(status_code=400, detail="Name, phone and password are required")
    validate_password_strength(password)
    
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    normalized_email = email or f"{phone}@phone.local"
    existing_email = db.query(User).filter(func.lower(User.email) == normalized_email.lower()).first()
    if existing_email:
        normalized_email = f"{phone}+{secrets.token_hex(3)}@phone.local"
    
    verification_token = secrets.token_urlsafe(32)
    model = User(
        name=name,
        email=normalized_email,
        phone=phone,
        address=location,
        profile_photo=(payload.get("profile_photo") or "").strip() or None,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
        is_verified=False,
        verification_token=verification_token,
        supabase_uid=supabase_uid,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    
    token = create_access_token({"sub": model.id, "role": "user", "email": model.email})
    refresh_token = create_refresh_token(model.id, "user", db)
    set_auth_cookies(response, token, refresh_token)
    
    return {
        "access_token": token,
        "user": {
            "id": model.id,
            "name": model.name,
            "email": model.email,
            "phone": model.phone,
            "role": "user",
        }
    }


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: dict,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    email = _normalize_email(payload.get("email"))
    phone = _normalize_phone(payload.get("phone"))
    password = payload.get("password") or ""
    
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    if _superadmin_matches(email, password):
        temp_user = _build_superadmin_user()
        recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(temp_user)
        subject, body = build_login_email(
            recipient_name,
            "super admin",
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )
        create_notification(
            db,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_email=recipient_email,
            title="Superadmin login detected",
            message="A superadmin session was opened successfully.",
            notification_type="security",
            severity="warning",
            action_href="/app/superadmin",
            send_email=bool(recipient_email),
            email_subject=subject,
            email_body=body,
            background_tasks=background_tasks,
        )
        db.commit()
        
        token = create_access_token(
            data={
                "sub": 0,
                "role": "super_admin",
                "email": SUPERADMIN_EMAIL,
                "user_type": "superadmin",
            }
        )
        refresh_token = create_refresh_token(0, "superadmin", db)
        set_auth_cookies(response, token, refresh_token)
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": 0,
                "name": "Super Admin",
                "email": SUPERADMIN_EMAIL,
                "role": "super_admin",
                "is_active": True,
            },
        }
    
    user = None
    user_type = "user"
    if email:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user:
            user = db.query(BusinessUser).filter(func.lower(BusinessUser.email) == email).first()
            user_type = "business"
        if not user:
            user = db.query(LogisticsUser).filter(func.lower(LogisticsUser.email) == email).first()
            user_type = "logistics"
    elif phone:
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            user = db.query(BusinessUser).filter(BusinessUser.phone == phone).first()
            user_type = "business"
        if not user:
            user = db.query(LogisticsUser).filter(LogisticsUser.phone == phone).first()
            user_type = "logistics"

    if not user or not verify_and_upgrade_password(password, user):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if isinstance(user, User) and not user.is_verified:
        raise HTTPException(status_code=401, detail="Please confirm your email before signing in")

    role = getattr(user, "role", None)
    if role is None:
        role = "logistics" if isinstance(user, LogisticsUser) else "user"
    role = _normalize_role(role)
    user.role = role
    
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
    subject, body = build_login_email(
        recipient_name,
        role or "user",
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Login detected",
        message=f"A new login was recorded for your {role} account.",
        notification_type="security",
        severity="info",
        action_href="/app/profile",
        send_email=bool(recipient_email),
        email_subject=subject,
        email_body=body,
        background_tasks=background_tasks,
    )
    db.commit()

    token = create_access_token(
        data={"sub": user.id, "role": role, "email": getattr(user, "email", None), "user_type": user_type}
    )
    refresh_token = create_refresh_token(user.id, user_type, db)
    set_auth_cookies(response, token, refresh_token)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "userType": user_type,
        "user": {
            "id": user.id,
            "name": getattr(user, "name", getattr(user, "business_name", "User")),
            "email": getattr(user, "email", None),
            "phone": user.phone,
            "role": role,
        },
    }


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        
    # Get user to build payload
    user = None
    if db_token.user_type == "business":
        user = db.query(BusinessUser).filter(BusinessUser.id == db_token.user_id).first()
    elif db_token.user_type == "logistics":
        user = db.query(LogisticsUser).filter(LogisticsUser.id == db_token.user_id).first()
    elif db_token.user_type == "superadmin":
        user = _build_superadmin_user()
    else:
        user = db.query(User).filter(User.id == db_token.user_id).first()
        
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account disabled")
        
    role = _normalize_role(user.role)
    new_access_token = create_access_token(
        data={"sub": user.id, "role": role, "email": getattr(user, "email", None), "user_type": db_token.user_type}
    )
    
    set_auth_cookies(response, new_access_token)
    return {"access_token": new_access_token}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        db_token = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
        if db_token:
            db_token.is_revoked = True
            db.commit()
            
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            jti = payload.get("jti")
            if jti:
                db.add(TokenBlocklist(jti=jti))
                db.commit()
        except:
            pass
            
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.post("/verify-email")
def verify_email(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Verification token is required")
        
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        user = db.query(BusinessUser).filter(BusinessUser.verification_token == token).first()
    if not user:
        user = db.query(LogisticsUser).filter(LogisticsUser.verification_token == token).first()
        
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
        
    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email verified successfully"}


@router.get("/me")
def me(current: User = Depends(get_current_user)):
    return {
        "id": current.id,
        "name": getattr(current, "name", getattr(current, "business_name", "User")),
        "email": getattr(current, "email", None),
        "phone": current.phone,
        "address": getattr(current, "address", None),
        "role": current.role,
        "is_verified": current.is_verified,
    }


@router.put("/me")
def update_me(
    payload: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    name = (payload.get("name") or getattr(current, "name", getattr(current, "business_name", ""))).strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")

    if hasattr(current, "name"):
        current.name = name
    elif hasattr(current, "business_name"):
        current.business_name = name
        
    current.phone = (payload.get("phone") or current.phone).strip()
    if hasattr(current, "address"):
        current.address = payload.get("address")
        
    db.add(current)
    db.commit()
    db.refresh(current)
    return {"message": "Profile updated"}


@router.post("/upload-profile-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"profile-{current.id}-{uuid.uuid4().hex}{suffix}"
    destination = uploads_dir / filename

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    destination.write_bytes(content)
    return {"image_url": f"/uploads/{filename}"}


@router.post("/change-password")
@limiter.limit("3/minute")
def change_password(
    request: Request,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.id == 0 and current.role == "super_admin":
        raise HTTPException(status_code=400, detail="Superadmin password managed separately")
        
    current_password = payload.get("current_password") or ""
    new_password = payload.get("new_password") or ""
    
    if not verify_password(current_password, current.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    validate_password_strength(new_password)

    current.password_hash = hash_password(new_password)
    db.add(current)
    
    recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(current)
    create_notification(
        db,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_email=recipient_email,
        title="Password changed",
        message="Your account password was changed successfully.",
        notification_type="security",
        severity="success",
        send_email=bool(recipient_email),
        email_subject="Password changed",
        email_body=f"Hello {recipient_name},\n\nYour password was changed.\n\nSokoLnk Security",
        background_tasks=background_tasks,
    )
    db.commit()
    return {"message": "Password updated"}


@router.post("/users")
def create_user(
    payload: dict,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    role = _normalize_role(payload.get("role") or "user")
    if role not in {"user", "admin", "super_admin", "owner"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if role in {"super_admin", "owner"} and current.role not in {"super_admin", "owner"}:
        raise HTTPException(status_code=403, detail="Only super_admin/owner can create super_admin or owner")
    if not name or not email or len(password) < 8:
        raise HTTPException(status_code=400, detail="Invalid user payload")
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    model = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return {
        "id": model.id,
        "name": model.name,
        "email": model.email,
        "role": model.role,
        "is_active": model.is_active,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    rows = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
        }
        for u in rows
    ]


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "super_admin", "owner")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = str(payload.get("role") or user.role).strip().lower()
    if role not in {"user", "admin", "super_admin", "owner"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    is_active = payload.get("is_active")
    if is_active is not None:
        user.is_active = bool(is_active)

    user.role = role
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.post("/supabase/link")
def link_supabase_account(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Link the currently-authenticated app user to a Supabase Auth account.

    The frontend sends the Supabase access_token (obtained via supabase.auth).
    We verify it, store the supabase_uid, and return the linked user info.
    """
    supabase_token = payload.get("supabase_access_token") or ""
    if not supabase_token:
        raise HTTPException(status_code=400, detail="supabase_access_token is required")

    from backend.app.supabase_auth import verify_supabase_token

    supabase_payload = verify_supabase_token(supabase_token)
    supabase_uid = str(supabase_payload.get("sub", ""))
    supabase_email = (supabase_payload.get("email") or "").strip().lower()

    # Prevent re-linking to a different Supabase account
    if getattr(current, "supabase_uid", None) and current.supabase_uid != supabase_uid:
        raise HTTPException(
            status_code=409,
            detail=f"Already linked to Supabase UID {current.supabase_uid}",
        )

    # Prevent two app users from linking the same Supabase UID
    for model_cls in (User, BusinessUser, LogisticsUser):
        existing = db.query(model_cls).filter(model_cls.supabase_uid == supabase_uid).first()
        if existing and existing.id != current.id:
            raise HTTPException(
                status_code=409,
                detail="This Supabase account is already linked to another user",
            )

    current.supabase_uid = supabase_uid
    # If the app user doesn't have an email yet, take it from Supabase
    if hasattr(current, "email") and not getattr(current, "email", None) and supabase_email:
        current.email = supabase_email
    db.add(current)
    db.commit()

    return {
        "message": "Supabase account linked",
        "supabase_uid": supabase_uid,
        "user": {
            "id": current.id,
            "name": getattr(current, "name", getattr(current, "business_name", "User")),
            "email": getattr(current, "email", None),
            "role": current.role,
        },
    }


@router.get("/supabase/me")
def supabase_me(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Endpoint callable with a Supabase JWT in the Authorization header.

    Returns app user info (creating a minimal record if the Supabase user
    has not yet been linked to an app account).
    """
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from backend.app.supabase_auth import verify_supabase_token, _resolve_or_create_app_user, _ensure_supabase_uid, _resolve_user_type

    payload = verify_supabase_token(token)
    user_type = _resolve_user_type(payload)

    user = _resolve_or_create_app_user(db, payload)

    # If user exists but has no supabase_uid, link it now (auto-link)
    if getattr(user, "supabase_uid", None) is None:
        _ensure_supabase_uid(db, user, str(payload.get("sub", "")))

    return {
        "id": user.id,
        "name": getattr(user, "name", getattr(user, "business_name", "User")),
        "email": getattr(user, "email", None),
        "phone": getattr(user, "phone", None),
        "role": user.role,
        "user_type": user_type,
        "is_verified": getattr(user, "is_verified", True),
        "is_active": user.is_active,
    }
