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


def upgrade() -> None:
    """Add supabase_uid columns to user tables for Supabase Auth integration."""
    op.add_column('users', sa.Column('supabase_uid', sa.String(), nullable=True))
    op.add_column('business_users', sa.Column('supabase_uid', sa.String(), nullable=True))
    op.add_column('logistics_users', sa.Column('supabase_uid', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_supabase_uid'), 'users', ['supabase_uid'], unique=True)
    op.create_index(op.f('ix_business_users_supabase_uid'), 'business_users', ['supabase_uid'], unique=True)
    op.create_index(op.f('ix_logistics_users_supabase_uid'), 'logistics_users', ['supabase_uid'], unique=True)


def downgrade() -> None:
    """Remove supabase_uid columns."""
    op.drop_index(op.f('ix_users_supabase_uid'), table_name='users')
    op.drop_index(op.f('ix_business_users_supabase_uid'), table_name='business_users')
    op.drop_index(op.f('ix_logistics_users_supabase_uid'), table_name='logistics_users')
    op.drop_column('users', 'supabase_uid')
    op.drop_column('business_users', 'supabase_uid')
    op.drop_column('logistics_users', 'supabase_uid')
