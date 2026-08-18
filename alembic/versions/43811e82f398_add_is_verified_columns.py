"""add is_verified columns

Revision ID: 43811e82f398
Revises: 20260428_01
Create Date: 2026-05-09 06:41:03.482070

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '43811e82f398'
down_revision: Union[str, Sequence[str], None] = '20260428_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).fetchone()
    return row is not None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = :idx"
    ), {"idx": index_name}).fetchone()
    return row is not None


def _create_index_safe(index_name: str, table: str, columns: list[str]):
    if not _index_exists(op.f(index_name)):
        op.create_index(op.f(index_name), table, columns, unique=False)


def upgrade() -> None:
    """Upgrade schema.  Idempotent — safe to re-run on databases where
    create_all() has already created these columns."""
    if not _column_exists('business_users', 'is_verified'):
        op.add_column('business_users', sa.Column('is_verified', sa.Boolean(),
            nullable=False, server_default=sa.text('false')))
    if not _column_exists('business_users', 'verification_token'):
        op.add_column('business_users', sa.Column('verification_token', sa.String(), nullable=True))

    op.alter_column('business_users', 'auto_confirm',
        existing_type=sa.BOOLEAN(), nullable=False,
        existing_server_default=sa.text('false'))

    if not _column_exists('logistics_users', 'is_verified'):
        op.add_column('logistics_users', sa.Column('is_verified', sa.Boolean(),
            nullable=False, server_default=sa.text('false')))
    if not _column_exists('logistics_users', 'verification_token'):
        op.add_column('logistics_users', sa.Column('verification_token', sa.String(), nullable=True))

    op.alter_column('products', 'is_active',
        existing_type=sa.BOOLEAN(), nullable=False,
        existing_server_default=sa.text('true'))
    op.alter_column('products', 'rating_avg',
        existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=False,
        existing_server_default=sa.text('0'))
    op.alter_column('products', 'rating_count',
        existing_type=sa.INTEGER(), nullable=False,
        existing_server_default=sa.text('0'))

    op.alter_column('sales', 'status',
        existing_type=sa.VARCHAR(), nullable=False,
        existing_server_default=sa.text("'Delivered'::character varying"))

    op.execute("""
       ALTER TABLE sales
       ALTER COLUMN created_by
       TYPE INTEGER
       USING created_by::integer
    """)

    _create_index_safe('ix_sales_id', 'sales', ['id'])

    for col in ('issue_resolved_at', 'support_note', 'review_tags',
                'issue_title', 'issue_created_at', 'issue_status',
                'review_text', 'compensation_code', 'issue_updated_at',
                'compensation_discount', 'issue_first_response_at',
                'issue_description'):
        if _column_exists('sales', col):
            op.drop_column('sales', col)

    if not _column_exists('users', 'is_verified'):
        op.add_column('users', sa.Column('is_verified', sa.Boolean(),
            nullable=False, server_default=sa.text('false')))
    if not _column_exists('users', 'verification_token'):
        op.add_column('users', sa.Column('verification_token', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'is_verified')

    for col in ('issue_resolved_at', 'support_note', 'review_tags',
                'issue_title', 'issue_created_at', 'issue_status',
                'review_text', 'compensation_code', 'issue_updated_at',
                'compensation_discount', 'issue_first_response_at',
                'issue_description'):
        if not _column_exists('sales', col):
            pass

    op.add_column('sales', sa.Column('issue_description', sa.VARCHAR(),
        autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('issue_first_response_at',
        postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('compensation_discount',
        sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('issue_updated_at',
        postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('compensation_code',
        sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('review_text',
        sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('issue_status',
        sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('issue_created_at',
        postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('issue_title',
        sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('review_tags',
        sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('support_note',
        sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('issue_resolved_at',
        postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))

    op.drop_index(op.f('ix_sales_id'), table_name='sales')

    op.alter_column('sales', 'created_by',
        existing_type=sa.Integer(), type_=sa.VARCHAR(),
        existing_nullable=True)

    op.alter_column('sales', 'status',
        existing_type=sa.VARCHAR(), nullable=True,
        existing_server_default=sa.text("'Delivered'::character varying"))

    op.alter_column('products', 'rating_count',
        existing_type=sa.INTEGER(), nullable=True,
        existing_server_default=sa.text('0'))
    op.alter_column('products', 'rating_avg',
        existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True,
        existing_server_default=sa.text('0'))
    op.alter_column('products', 'is_active',
        existing_type=sa.BOOLEAN(), nullable=True,
        existing_server_default=sa.text('true'))

    op.drop_column('logistics_users', 'verification_token')
    op.drop_column('logistics_users', 'is_verified')

    op.alter_column('business_users', 'auto_confirm',
        existing_type=sa.BOOLEAN(), nullable=True,
        existing_server_default=sa.text('false'))
    op.drop_column('business_users', 'verification_token')
    op.drop_column('business_users', 'is_verified')
