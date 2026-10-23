"""first password mail status

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-23 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_password_mail", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "first_password_mail")
