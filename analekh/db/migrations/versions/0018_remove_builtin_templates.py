"""Remove the two built-in templates (owner 'builtin'); refuse if any model or test still uses them

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-31 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM templates WHERE owner = 'builtin'"))]
    if not ids:
        return
    in_use = conn.execute(
        sa.text(
            "SELECT (SELECT count(*) FROM models WHERE template_id = ANY(:ids))"
            " + (SELECT count(*) FROM model_builds WHERE template_id = ANY(:ids))"
            " + (SELECT count(*) FROM template_tests WHERE template_id = ANY(:ids))"
        ),
        {"ids": ids},
    ).scalar()
    if in_use:
        raise RuntimeError("built-in templates are still used by models or tests; unlink them before this migration")
    conn.execute(sa.text("DELETE FROM template_tests WHERE template_id = ANY(:ids)"), {"ids": ids})
    conn.execute(sa.text("DELETE FROM templates WHERE id = ANY(:ids)"), {"ids": ids})


def downgrade() -> None:
    # The rows are not recreated: the app no longer ships built-in templates.
    pass
