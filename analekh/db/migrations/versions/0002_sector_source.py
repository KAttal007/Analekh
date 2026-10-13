"""add companies.sector_source

Records where a company's sector came from (universe/sectors.py): user > excel_stocks >
nse_indices. Existing sectors keep NULL, which the sector code treats like a user value.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 19:32:43.629143
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("sector_source", sa.Text(), nullable=True))
    # Autogenerate does not detect check constraints.
    op.create_check_constraint(
        "ck_companies_sector_source",
        "companies",
        "sector_source IN ('user','excel_stocks','nse_indices')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_companies_sector_source", "companies", type_="check")
    op.drop_column("companies", "sector_source")
