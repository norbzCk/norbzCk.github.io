"""add supabase_uid columns for auth integration

Revision ID: a97801d195fa
Revises: 6fab91b2b942
Create Date: 2026-08-17 18:23:25.605616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a97801d195fa'
down_revision: Union[str, Sequence[str], None] = '6fab91b2b942'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).fetchone()
    return row is not None


def upgrade() -> None:
    """Add supabase_uid columns to user tables for Supabase Auth integration.
    Idempotent — safe to re-run on databases where create_all() already
    created the columns."""
    for table in ('users', 'business_users', 'logistics_users'):
        if not _column_exists(table, 'supabase_uid'):
            op.add_column(table, sa.Column('supabase_uid', sa.String(), nullable=True))
        idx_name = f'ix_{table}_supabase_uid'
        # Check if index already exists
        bind = op.get_bind()
        exists = bind.execute(sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :idx"
        ), {"idx": idx_name}).fetchone()
        if not exists:
            op.create_index(idx_name, table, ['supabase_uid'], unique=True)


def downgrade() -> None:
    """Remove supabase_uid columns."""
    for table in ('users', 'business_users', 'logistics_users'):
        idx_name = f'ix_{table}_supabase_uid'
        bind = op.get_bind()
        exists = bind.execute(sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :idx"
        ), {"idx": idx_name}).fetchone()
        if exists:
            op.drop_index(idx_name, table_name=table)
        if _column_exists(table, 'supabase_uid'):
            op.drop_column(table, 'supabase_uid')
