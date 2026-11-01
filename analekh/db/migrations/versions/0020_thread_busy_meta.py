"""Report threads: busy marker for AI jobs, and what each AI turn did

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-01 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("report_threads", sa.Column("busy_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("report_threads", sa.Column("busy_job_id", sa.Text(), nullable=True))
    op.add_column("thread_messages", sa.Column("meta", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("thread_messages", "meta")
    op.drop_column("report_threads", "busy_job_id")
    op.drop_column("report_threads", "busy_since")
