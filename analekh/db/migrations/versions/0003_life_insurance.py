"""allow results_taxonomy 'life_insurance'

Life insurers file IRDAI's life format (policyholders' and shareholders' accounts), with its own
element table in xbrl/elements.py.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14 21:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "results_taxonomy IN ('indas','banking','nbfc','insurance')"
NEW = "results_taxonomy IN ('indas','banking','nbfc','insurance','life_insurance')"


def upgrade() -> None:
    op.drop_constraint("ck_companies_results_taxonomy", "companies", type_="check")
    op.create_check_constraint("ck_companies_results_taxonomy", "companies", NEW)


def downgrade() -> None:
    op.execute("UPDATE companies SET results_taxonomy = 'insurance' WHERE results_taxonomy = 'life_insurance'")
    op.drop_constraint("ck_companies_results_taxonomy", "companies", type_="check")
    op.create_check_constraint("ck_companies_results_taxonomy", "companies", OLD)
