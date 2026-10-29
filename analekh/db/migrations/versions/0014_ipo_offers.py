"""IPO offer tables: issues, offer documents, restated figures, chunks, drafts

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-29 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ipo_issues",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("stem", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "ipo_documents",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("issue_id", sa.BigInteger(), sa.ForeignKey("ipo_issues.id"), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("sebi_id", sa.String(32), nullable=False, unique=True),
        sa.Column("entry_url", sa.Text(), nullable=False),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filed_on", sa.Date(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("stage IN ('rhp', 'prospectus')", name="ck_ipo_documents_stage"),
        sa.CheckConstraint(
            "status IN ('new', 'read', 'extracted', 'flagged', 'failed')",
            name="ck_ipo_documents_status",
        ),
    )
    op.create_index("ix_ipo_documents_issue_id", "ipo_documents", ["issue_id"])
    op.create_table(
        "ipo_financials",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("ipo_documents.id"), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_label", sa.Text(), nullable=False),
        sa.Column("is_stub", sa.Boolean(), nullable=False),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(24, 4), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("flagged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.UniqueConstraint("document_id", "basis", "period_end", "line", name="uq_ipo_financials_figure"),
        sa.CheckConstraint("basis IN ('consolidated', 'standalone')", name="ck_ipo_financials_basis"),
        sa.CheckConstraint("unit IN ('INR', 'INR/share')", name="ck_ipo_financials_unit"),
    )
    op.create_index("ix_ipo_financials_document_id", "ipo_financials", ["document_id"])
    op.create_table(
        "ipo_chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("ipo_documents.id"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
        ),
    )
    op.create_index("ix_ipo_chunks_document_id", "ipo_chunks", ["document_id"])
    op.create_index("ix_ipo_chunks_tsv", "ipo_chunks", ["tsv"], postgresql_using="gin")
    op.create_table(
        "ipo_drafts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("issue_id", sa.BigInteger(), sa.ForeignKey("ipo_issues.id"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("ipo_documents.id"), nullable=False),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ipo_drafts_issue_id", "ipo_drafts", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_ipo_drafts_issue_id", table_name="ipo_drafts")
    op.drop_table("ipo_drafts")
    op.drop_index("ix_ipo_chunks_tsv", table_name="ipo_chunks")
    op.drop_index("ix_ipo_chunks_document_id", table_name="ipo_chunks")
    op.drop_table("ipo_chunks")
    op.drop_index("ix_ipo_financials_document_id", table_name="ipo_financials")
    op.drop_table("ipo_financials")
    op.drop_index("ix_ipo_documents_issue_id", table_name="ipo_documents")
    op.drop_table("ipo_documents")
    op.drop_table("ipo_issues")
