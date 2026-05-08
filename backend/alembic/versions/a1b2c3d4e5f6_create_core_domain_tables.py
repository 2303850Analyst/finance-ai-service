"""create_core_domain_tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-08 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum type name → values (order matters for CREATE TYPE)
_ENUMS: dict[str, tuple[str, ...]] = {
    "accounttype": ("broker", "bank", "crypto", "cash", "deposit", "other"),
    "assettype": ("stock", "bond", "etf", "currency", "cash", "deposit", "crypto", "real_estate", "other"),
    "operationtype": ("buy", "sell", "deposit", "withdraw", "dividend", "coupon", "fee", "tax", "manual_valuation"),
    "operationstatus": ("pending", "confirmed", "cancelled", "rejected"),
}


def _enum(name: str) -> postgresql.ENUM:
    """Reference an already-created PostgreSQL enum type without re-creating it."""
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    # ── 1. PostgreSQL enum types ──────────────────────────────────────────────
    # CREATE TYPE has no IF NOT EXISTS; use a DO block that silences
    # duplicate_object so the migration is safe to re-run on a dirty DB.
    for type_name, values in _ENUMS.items():
        quoted = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"""
            DO $$ BEGIN
                CREATE TYPE {type_name} AS ENUM ({quoted});
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )

    # ── 2. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── 3. assets (no FK to other domain tables) ──────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", _enum("assettype"), nullable=False),
        sa.Column(
            "currency",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_assets_ticker", "assets", ["ticker"], unique=True)

    # ── 4. accounts ───────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", _enum("accounttype"), nullable=False),
        sa.Column(
            "currency",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    # ── 5. operations ─────────────────────────────────────────────────────────
    op.create_table(
        "operations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assets.id"),
            nullable=True,
        ),
        sa.Column("operation_type", _enum("operationtype"), nullable=False),
        sa.Column(
            "status",
            _enum("operationstatus"),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=True),
        sa.Column("price", sa.Numeric(20, 8), nullable=True),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("operated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_operations_user_id", "operations", ["user_id"])
    op.create_index("ix_operations_account_id", "operations", ["account_id"])

    # ── 6. positions ──────────────────────────────────────────────────────────
    op.create_table(
        "positions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(20, 8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "average_price",
            sa.Numeric(20, 8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("account_id", "asset_id", name="uq_position_account_asset"),
    )
    op.create_index("ix_positions_account_id", "positions", ["account_id"])

    # ── 7. audit_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("positions")
    op.drop_table("operations")
    op.drop_table("accounts")
    op.drop_table("assets")
    op.drop_table("users")

    for type_name in reversed(list(_ENUMS.keys())):
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
