"""Sync data between the local PostgreSQL database and Supabase.

Usage:
    python -m backend.supabase_sync push   # local  -> Supabase
    python -m backend.supabase_sync pull   # Supabase -> local
    python -m backend.supabase_sync push --dry-run

The local DB URL is resolved via backend.database.resolve_database_url().
The Supabase DB URL comes from the SUPABASE_DATABASE_URL env var.
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.database import resolve_database_url, _ensure_ssl_mode, _fix_password_encoding
from backend.models import Base


def _resolve_supabase_url() -> str:
    url = os.getenv("SUPABASE_DATABASE_URL", "").strip()
    if not url:
        print(
            "ERROR: SUPABASE_DATABASE_URL is not set.\n"
            "  Get it from Supabase Dashboard → Settings → Database → "
            "Connection string → URI.\n"
            "  Export SUPABASE_DATABASE_URL=postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres",
            file=sys.stderr,
        )
        sys.exit(1)
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    url = _fix_password_encoding(url)
    return _ensure_ssl_mode(url)


def _sync_direction(direction: str):
    if direction == "push":
        source_url = resolve_database_url()
        dest_url = _resolve_supabase_url()
        print(f"  source (local):   {source_url}")
        print(f"  destination:      {dest_url}  (Supabase)")
    else:
        dest_url = resolve_database_url()
        source_url = _resolve_supabase_url()
        print(f"  source (Supabase): {source_url}")
        print(f"  destination:       {dest_url}  (local)")
    return source_url, dest_url


def sync(direction: str, dry_run: bool = False) -> None:
    source_url, dest_url = _sync_direction(direction)

    source_engine = create_engine(source_url, pool_pre_ping=True)
    dest_engine = create_engine(dest_url, pool_pre_ping=True)

    # Gather tables in dependency-safe order: drop FK check, truncate, insert
    inspector = inspect(dest_engine)
    existing_tables = set(inspector.get_table_names())
    metadata_tables = list(Base.metadata.tables.values())

    # Create tables in destination that don't exist yet
    for table in metadata_tables:
        if table.name not in existing_tables:
            print(f"  Creating table: {table.name}")
            if not dry_run:
                table.create(dest_engine)

    # Truncate destination tables (in reverse order to respect FK constraints)
    table_names = [t.name for t in metadata_tables]
    print(f"  Truncating {len(table_names)} tables in destination...")
    if not dry_run:
        with dest_engine.begin() as conn:
            conn.execute(text("SET session_replication_role = 'replica';"))
            for name in reversed(table_names):
                conn.execute(text(f"TRUNCATE TABLE {name} RESTART IDENTITY CASCADE;"))
            conn.execute(text("SET session_replication_role = 'origin';"))

    # Copy data table by table
    SourceSession = sessionmaker(bind=source_engine)
    DestSession = sessionmaker(bind=dest_engine)

    for table in metadata_tables:
        columns = [c.name for c in table.columns]
        col_list = ", ".join(columns)
        placeholders = ", ".join([f":{c}" for c in columns])
        insert_sql = f'INSERT INTO {table.name} ({col_list}) VALUES ({placeholders})'

        with source_engine.connect() as src_conn:
            rows = src_conn.execute(text(f'SELECT {col_list} FROM {table.name}')).fetchall()

        print(f"  Syncing {table.name}: {len(rows)} rows")
        if not dry_run and rows:
            with dest_engine.begin() as dest_conn:
                dest_conn.execute(text(insert_sql), [dict(zip(columns, row)) for row in rows])

    source_engine.dispose()
    dest_engine.dispose()
    print(f"\n  Done! {'(dry run)' if dry_run else ''} {direction} complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Sync data between local PostgreSQL and Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
  push  — copy local data  -> Supabase
  pull  — copy Supabase data -> local

  Env vars:
    DATABASE_URL           (local DB, auto-resolved from backend.database)
    SUPABASE_DATABASE_URL  (Supabase Postgres connection string)
""",
    )
    parser.add_argument("direction", choices=["push", "pull"], help="Sync direction")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    args = parser.parse_args()

    sync(args.direction, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
