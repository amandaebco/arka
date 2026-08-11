"""add batch_number to activity_spare_parts

Revision ID: 2a82d91bc802
Revises: 13c51d61060c
Create Date: 2026-08-11 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "2a82d91bc802"
down_revision: str | None = "13c51d61060c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("activity_spare_parts", sa.Column("batch_number", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("activity_spare_parts", "batch_number")
