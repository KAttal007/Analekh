"""Reported ratios (NIM, cost of funds, ...) from investor decks, and the ledger of decks read

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-31 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investor_decks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("broadcast_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("ratios", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('read', 'no_ratios', 'skipped', 'failed')", name="ck_investor_decks_status"),
    )
    op.create_index("ix_investor_decks_company_id", "investor_decks", ["company_id"])
    op.create_table(
        "reported_ratios",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(6, 2), nullable=False),
        sa.Column("deck_id", sa.BigInteger(), sa.ForeignKey("investor_decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("company_id", "period_end", "metric", "basis", name="uq_reported_ratios_key"),
        sa.CheckConstraint("metric IN ('nim','cof','cod','yield_adv','yield_assets','yield_funds')", name="ck_reported_ratios_metric"),
        sa.CheckConstraint("basis IN ('all','consolidated','standalone')", name="ck_reported_ratios_basis"),
    )
    op.create_index("ix_reported_ratios_company_id", "reported_ratios", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_reported_ratios_company_id", table_name="reported_ratios")
    op.drop_table("reported_ratios")
    op.drop_index("ix_investor_decks_company_id", table_name="investor_decks")
    op.drop_table("investor_decks")
