"""add prices.prev_close

The bhavcopy carries each stock's previous close, so the day's change is known from one file
without keeping price history (owner's choice, 2026-10-17).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("prices", sa.Column("prev_close", sa.Numeric(14, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("prices", "prev_close")
