"""rename_accrual_type_to_payout_frequency

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-08 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("account_interest_settings", "accrual_type", new_column_name="payout_frequency")


def downgrade() -> None:
    op.alter_column("account_interest_settings", "payout_frequency", new_column_name="accrual_type")
