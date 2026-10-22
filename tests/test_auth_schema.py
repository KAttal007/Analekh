"""Tables behind sign-in, roles, tokens, settings and the audit trail (auth design, stage 1)."""

import pytest
from sqlalchemy.exc import IntegrityError

from analekh.db.models import User


def _user(email: str, role: str = "analyst") -> User:
    return User(id=f"id-{email}", email=email, name="Test", role=role, auth_kind="password")


def test_users_email_unique(db):
    db.add(_user("a@firm.in"))
    db.flush()
    db.add(User(id="other", email="a@firm.in", name="Dup", role="analyst", auth_kind="password"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_role_must_be_admin_or_analyst(db):
    db.add(_user("boss@firm.in", role="boss"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_new_user_starts_active_and_unblocked(db):
    u = _user("new@firm.in")
    db.add(u)
    db.flush()
    db.refresh(u)
    assert u.is_active is True and u.blocked is False and u.failed_count == 0
    assert u.paused_until is None and u.password_hash is None
