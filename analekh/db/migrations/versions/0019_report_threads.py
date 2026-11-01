"""Report threads, chat messages, versions, published files, lessons and upgrade checks

Adds the record described in docs/superpowers/specs/2026-11-01-report-chat-design.md. Purely
additive: no existing table changes.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-01 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_threads",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("model_id", sa.BigInteger(), sa.ForeignKey("models.id"), nullable=True),
        sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("quarter_end", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default="drafting", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('drafting', 'approved', 'published')", name="ck_report_threads_status"),
        sa.CheckConstraint("format IN ('word', 'ppt')", name="ck_report_threads_format"),
    )
    op.create_index("ix_report_threads_owner", "report_threads", ["owner_id", "updated_at"])

    op.create_table(
        "thread_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("report_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("selection", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("trace_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('analyst', 'ai')", name="ck_thread_messages_role"),
    )
    op.create_index("ix_thread_messages_thread_id", "thread_messages", ["thread_id"])

    op.create_table(
        "report_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("report_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("parent_no", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("by_user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("full", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("thread_id", "version_no", name="uq_report_versions_no"),
        sa.CheckConstraint(
            "trigger IN ('first_draft', 'ai_reply', 'analyst_edit', 'approved')",
            name="ck_report_versions_trigger",
        ),
    )
    op.create_index("ix_report_versions_thread_id", "report_versions", ["thread_id"])

    op.create_table(
        "published_files",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("report_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("extension", sa.Text(), nullable=False),
        sa.Column("has_macros", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("uploaded_by_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_published_files_thread_id", "published_files", ["thread_id"])

    op.create_table(
        "lessons",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope", sa.Text(), server_default="analyst", nullable=False),
        sa.Column("owner_id", sa.Text(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("test_kind", sa.Text(), nullable=False),
        sa.Column("test_spec", postgresql.JSONB(), nullable=False),
        sa.Column("strength", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "source_thread_id",
            sa.BigInteger(),
            sa.ForeignKey("report_threads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('analyst', 'firm')", name="ck_lessons_scope"),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_lessons_status"),
        sa.CheckConstraint("test_kind IN ('phrase', 'structure', 'judged')", name="ck_lessons_test_kind"),
        sa.CheckConstraint("(scope = 'firm') OR (owner_id IS NOT NULL)", name="ck_lessons_owner"),
    )

    op.create_table(
        "lesson_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("current_model", sa.Text(), nullable=False),
        sa.Column("candidate_model", sa.Text(), nullable=False),
        sa.Column("threads_used", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lesson_checks")
    op.drop_table("lessons")
    op.drop_index("ix_published_files_thread_id", table_name="published_files")
    op.drop_table("published_files")
    op.drop_index("ix_report_versions_thread_id", table_name="report_versions")
    op.drop_table("report_versions")
    op.drop_index("ix_thread_messages_thread_id", table_name="thread_messages")
    op.drop_table("thread_messages")
    op.drop_index("ix_report_threads_owner", table_name="report_threads")
    op.drop_table("report_threads")
