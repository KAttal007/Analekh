"""reset failures across codes

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-29 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("password_resets", sa.Column("failures", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("password_resets", "failures")
