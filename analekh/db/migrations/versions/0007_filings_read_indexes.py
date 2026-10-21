"""indexes for the results desk and glance reads

filings is wide (the validation report sits in meta), so scans for the desk's period list, the
newest filed_at and V11's suspect filings each took 20-40 ms. Partial indexes keep them small.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-21 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_filings_results_quarter",
        "filings",
        ["period_end", "company_id"],
        postgresql_where=sa.text("kind = 'results_xbrl' AND period_type = 'Q'"),
    )
    op.create_index("ix_filings_filed_at", "filings", ["filed_at"])
    op.create_index(
        "ix_filings_scale_suspect",
        "filings",
        ["company_id"],
        postgresql_where=sa.text("(meta -> 'scale') ->> 'status' = 'suspect'"),
    )


def downgrade() -> None:
    op.drop_index("ix_filings_scale_suspect", table_name="filings")
    op.drop_index("ix_filings_filed_at", table_name="filings")
    op.drop_index("ix_filings_results_quarter", table_name="filings")
