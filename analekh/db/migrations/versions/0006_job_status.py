"""add job_status

When the results watcher and the daily prices job last ran, and last did their work, for the data
status on the Settings screen.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-18 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_status",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_status", sa.Text(), nullable=False),
        sa.Column(
            "last_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_status")
