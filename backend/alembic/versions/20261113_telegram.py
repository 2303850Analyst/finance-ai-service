"""Persistent Telegram pairing and confirmation drafts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision = "20261113_telegram"
down_revision = "31fd7637628a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("telegram_links",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True))
    op.create_table("telegram_pairings",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("operation_drafts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_key", sa.String(120), nullable=False, unique=True),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operation_id", pg.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_operation_drafts_user_id", "operation_drafts", ["user_id"])


def downgrade():
    op.drop_table("operation_drafts")
    op.drop_table("telegram_pairings")
    op.drop_table("telegram_links")
