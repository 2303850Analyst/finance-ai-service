"""Add ai_usage_events table for request tracking and rate limiting

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_usage_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('request_kind', sa.String(50), nullable=False),
        sa.Column('input_chars', sa.Integer(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_cost_usd', sa.Numeric(10, 6), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index('ix_ai_usage_events_user_id', 'ai_usage_events', ['user_id'])
    op.create_index('ix_ai_usage_events_status', 'ai_usage_events', ['status'])
    op.create_index('ix_ai_usage_events_created_at', 'ai_usage_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_usage_events_created_at', 'ai_usage_events')
    op.drop_index('ix_ai_usage_events_status', 'ai_usage_events')
    op.drop_index('ix_ai_usage_events_user_id', 'ai_usage_events')
    op.drop_table('ai_usage_events')
