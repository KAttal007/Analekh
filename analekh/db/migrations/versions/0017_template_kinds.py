"""Template kinds (Excel model, Word report, PowerPoint report) and a macro flag

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-31 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("templates", sa.Column("kind", sa.Text(), nullable=False, server_default="excel_model"))
    op.add_column("templates", sa.Column("has_macros", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("templates", "has_macros")
    op.drop_column("templates", "kind")
