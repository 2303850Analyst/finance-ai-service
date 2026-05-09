"""add_transfer_and_recurring_income

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add 'transfer' enum value — must run outside a transaction
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operationtype ADD VALUE IF NOT EXISTS 'transfer'")

    # 2. Add to_account_id column to operations (no FK constraint)
    op.add_column(
        "operations",
        sa.Column("to_account_id", UUID(as_uuid=True), nullable=True),
    )

    # 3. Create recurring_income table
    op.create_table(
        "recurring_income",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            server_default=sa.text("'Зарплата'"),
        ),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "income_source",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'salary'"),
        ),
        sa.Column(
            "day_of_month",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_recurring_income_user_id",
        "recurring_income",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recurring_income_user_id", table_name="recurring_income")
    op.drop_table("recurring_income")
    op.drop_column("operations", "to_account_id")
    # NOTE: cannot remove enum value 'transfer' from PostgreSQL — skipping
