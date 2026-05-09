"""Asset extended fields: estimated_value, note, acquisition_date, credit link, include_in_capital

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa

revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('estimated_value', sa.Numeric(20, 2), nullable=True))
    op.add_column('assets', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('assets', sa.Column('acquisition_date', sa.Date(), nullable=True))
    op.add_column('assets', sa.Column(
        'is_credit_linked', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('assets', sa.Column('credit_kind', sa.String(50), nullable=True))
    op.add_column('assets', sa.Column('credit_note', sa.Text(), nullable=True))
    op.add_column('assets', sa.Column(
        'include_in_capital', sa.Boolean(), nullable=False, server_default='true'
    ))


def downgrade() -> None:
    op.drop_column('assets', 'include_in_capital')
    op.drop_column('assets', 'credit_note')
    op.drop_column('assets', 'credit_kind')
    op.drop_column('assets', 'is_credit_linked')
    op.drop_column('assets', 'acquisition_date')
    op.drop_column('assets', 'note')
    op.drop_column('assets', 'estimated_value')
