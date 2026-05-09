"""add physical asset types and linked_asset_id

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new asset type enum values (must run outside a transaction)
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'vehicle'")
        op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'other_physical'")

    # Add linked_asset_id to operations (nullable FK → assets, SET NULL on asset delete)
    op.add_column(
        "operations",
        sa.Column("linked_asset_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_operations_linked_asset_id",
        "operations",
        "assets",
        ["linked_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_operations_linked_asset_id", "operations", type_="foreignkey")
    op.drop_column("operations", "linked_asset_id")
