"""add companies.sector_lseg

NSE's own sector taxonomy is now shown first (owner's choice, 2026-10-16); the LSEG industry group
from an Excel Stocks workbook is kept in its own column instead of being overwritten.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("sector_lseg", sa.Text(), nullable=True))
    op.execute("UPDATE companies SET sector_lseg = sector WHERE sector_source = 'excel_stocks'")


def downgrade() -> None:
    op.drop_column("companies", "sector_lseg")
