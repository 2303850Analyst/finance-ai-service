"""add_expense_support

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-09
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operationtype ADD VALUE IF NOT EXISTS 'expense'")

    op.add_column("operations", sa.Column("expense_group", sa.String(20), nullable=True))
    op.add_column("operations", sa.Column("expense_category", sa.String(50), nullable=True))
    op.add_column("operations", sa.Column("merchant", sa.String(255), nullable=True))
    op.add_column(
        "operations",
        sa.Column("is_refund", sa.Boolean(), nullable=True, server_default=sa.text("false")),
    )
    op.add_column("operations", sa.Column("principal_amount", sa.Numeric(20, 8), nullable=True))
    op.add_column("operations", sa.Column("interest_amount", sa.Numeric(20, 8), nullable=True))
    op.add_column("operations", sa.Column("liability_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("operations", "liability_name")
    op.drop_column("operations", "interest_amount")
    op.drop_column("operations", "principal_amount")
    op.drop_column("operations", "is_refund")
    op.drop_column("operations", "merchant")
    op.drop_column("operations", "expense_category")
    op.drop_column("operations", "expense_group")
