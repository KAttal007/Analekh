"""Q&A threads and their messages

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-02 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "qa_threads",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("title", sa.Text(), server_default="", nullable=False),
        sa.Column("busy_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("busy_job_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_qa_threads_owner", "qa_threads", ["owner_id", "updated_at"])
    op.create_table(
        "qa_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("qa_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('analyst', 'ai')", name="ck_qa_messages_role"),
    )
    op.create_index("ix_qa_messages_thread_id", "qa_messages", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_qa_messages_thread_id", table_name="qa_messages")
    op.drop_table("qa_messages")
    op.drop_index("ix_qa_threads_owner", table_name="qa_threads")
    op.drop_table("qa_threads")
