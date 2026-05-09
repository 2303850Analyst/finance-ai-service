"""add_savings_and_interest_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-08 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE requires a separate autocommit transaction in PostgreSQL
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'savings'")

    op.create_table(
        "account_interest_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False, unique=True),
        sa.Column("is_interest_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("annual_rate_percent", sa.Numeric(8, 4), nullable=False),
        sa.Column("interest_start_date", sa.Date(), nullable=False),
        sa.Column("interest_end_date", sa.Date(), nullable=True),
        sa.Column("accrual_type", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("capitalization", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("payout_day", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_account_interest_settings_account_id", "account_interest_settings", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_account_interest_settings_account_id", table_name="account_interest_settings")
    op.drop_table("account_interest_settings")
    # Note: PostgreSQL does not support removing enum values; downgrade leaves 'savings' in the enum
