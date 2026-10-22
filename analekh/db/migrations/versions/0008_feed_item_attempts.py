"""feed items record failed attempts

One feed item whose file failed (gone, broken, unreadable) stayed first in the queue and failed
every run, so newer items were never processed. Failures are now counted per item, with the last
error kept; after a few the item is given up on instead of blocking the queue.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feed_items", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("feed_items", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("feed_items", "error")
    op.drop_column("feed_items", "attempts")
