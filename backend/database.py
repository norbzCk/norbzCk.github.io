import os
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_database_url():
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres123")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "sales_db")

    password = quote_plus(db_pass)
    return f"postgresql://{db_user}:{password}@{db_host}:{db_port}/{db_name}"


def resolve_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url[len("postgres://"):]
        database_url = _fix_password_encoding(database_url)
        return _ensure_ssl_mode(database_url)

    render_env = os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL")
    if render_env:
        raise RuntimeError(
            "DATABASE_URL is not set. On Render, connect the web service to a "
            "Render PostgreSQL database or define DATABASE_URL manually."
        )

    return _ensure_ssl_mode(get_database_url())


def _ensure_ssl_mode(url: str) -> str:
    """Append sslmode=require for remote PostgreSQL connections (e.g. Supabase).

    Supabase requires TLS/SSL for all connections.  Local SQLite or
    localhost Postgres instances are left untouched so dev workflows are
    unaffected.
    """
    if "sslmode=" in url:
        return url
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or not host:
        return url
    query = parsed.query + ("&sslmode=require" if parsed.query else "sslmode=require")
    parsed = parsed._replace(query=query)
    return urlunparse(parsed)


def _fix_password_encoding(url: str) -> str:
    """Fix connection strings where the password contains unencoded special
    characters (``#``, ``@``, etc.).

    This often happens with Supabase pooled connection strings where the
    password contains characters that have special meaning in URIs.  For
    example, ``4444#norbie1234567890`` will be split at the ``#`` by
    ``urlparse`` — everything after ``#`` becomes the URL fragment and the
    hostname appears empty.
    """
    parsed = urlparse(url)

    # If urlparse found a real hostname (with @ in netloc), URL is fine
    if "@" in (parsed.netloc or ""):
        return url

    # If the fragment contains @ and a hostname:port, the password had an
    # unencoded # (or @) that caused urlparse to misparse the URL.
    # Re-encode the password by splitting on the last @ in the full URL.
    if parsed.fragment and "@" in parsed.fragment:
        scheme_end = url.find("://")
        if scheme_end == -1:
            return url
        scheme = url[:scheme_end]
        rest = url[scheme_end + 3:]

        at_index = rest.rfind("@")
        if at_index == -1:
            return url

        userinfo = rest[:at_index]
        hostinfo = rest[at_index + 1:]

        colon_index = userinfo.find(":")
        if colon_index == -1:
            return url  # no password, nothing to fix

        user = userinfo[:colon_index]
        password = userinfo[colon_index + 1:]

        encoded_password = quote_plus(password)
        return f"{scheme}://{user}:{encoded_password}@{hostinfo}"

    return url


DATABASE_URL = resolve_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
