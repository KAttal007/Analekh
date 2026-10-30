"""Session limit: remembered devices, a device per session, and the held sign-in choice

Every open session is ended (each now needs a device): everyone signs in once more.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-30 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_devices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column("name", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "device_id", name="uq_user_devices_user_device"),
    )
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
    op.execute("DELETE FROM auth_sessions")
    op.add_column("auth_sessions", sa.Column("device_pk", sa.BigInteger(), nullable=False))
    op.create_foreign_key("auth_sessions_device_pk_fkey", "auth_sessions", "user_devices", ["device_pk"], ["id"], ondelete="CASCADE")
    op.create_index("ix_auth_sessions_device_pk", "auth_sessions", ["device_pk"])
    op.create_table(
        "sign_in_choices",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sign_in_choices_user_id", "sign_in_choices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sign_in_choices_user_id", table_name="sign_in_choices")
    op.drop_table("sign_in_choices")
    op.drop_index("ix_auth_sessions_device_pk", table_name="auth_sessions")
    op.drop_constraint("auth_sessions_device_pk_fkey", "auth_sessions", type_="foreignkey")
    op.drop_column("auth_sessions", "device_pk")
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_table("user_devices")
