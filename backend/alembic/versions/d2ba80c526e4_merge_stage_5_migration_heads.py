"""merge stage 5 migration heads

Revision ID: d2ba80c526e4
Revises: a7b8c9d0e1f2, g7h8i9j0k1l2
Create Date: 2026-05-09 15:09:16.024449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2ba80c526e4'
down_revision: Union[str, None] = ('a7b8c9d0e1f2', 'g7h8i9j0k1l2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
