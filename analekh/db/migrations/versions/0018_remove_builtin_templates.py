"""Retire the two built-in templates (owner 'builtin')

Rows nothing uses are deleted with their test records. Rows a model or build still points at are
disabled instead, never deleted, so the migration cannot fail on them or break a link.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-31 16:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IN_USE = "EXISTS (SELECT 1 FROM models WHERE template_id = templates.id) OR EXISTS (SELECT 1 FROM model_builds WHERE template_id = templates.id)"


def upgrade() -> None:
    op.execute(f"UPDATE templates SET status = 'disabled', is_default = false WHERE owner = 'builtin' AND ({_IN_USE})")
    op.execute(f"DELETE FROM template_tests WHERE template_id IN (SELECT id FROM templates WHERE owner = 'builtin' AND NOT ({_IN_USE}))")
    op.execute(f"DELETE FROM templates WHERE owner = 'builtin' AND NOT ({_IN_USE})")


def downgrade() -> None:
    # Deleted rows are not recreated: the app no longer ships built-in templates.
    pass
