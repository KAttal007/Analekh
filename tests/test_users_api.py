"""User administration, admin-only templates and the create-admin command (plan task 6)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from typer.testing import CliRunner

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.auth.service import create_user, login
from analekh.config import get_settings
from analekh.db.models import AuditEntry, Base, Template, User
from analekh.db.session import get_session

GOOD = "correct horse battery"
CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def raw(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _sign_in(raw, email):
    res = raw.post("/auth/login", json={"email": email, "password": GOOD})
    assert res.status_code == 200
    return raw


@pytest.fixture
def admin(db, raw):
    create_user(db, "boss@firm.in", "Boss", "admin", GOOD)
    return _sign_in(raw, "boss@firm.in")


@pytest.fixture
def analyst(db, raw):
    create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    return _sign_in(raw, "ana@firm.in")


def test_analyst_cannot_upload_template_or_list_users(analyst):
    assert analyst.get("/users").status_code == 403
    assert analyst.post("/users", json={}, headers=CSRF).status_code == 403
    up = analyst.post(
        "/templates",
        files={"workbook": ("t.xlsx", b"PK\x03\x04")},
        data={"name": "x", "sectors": "NBFC"},
        headers=CSRF,
    )
    assert up.status_code == 403
    assert analyst.post("/templates/1/mapping", json={}, headers=CSRF).status_code == 403
    assert analyst.post("/templates/1/activate", headers=CSRF).status_code == 403
    assert analyst.get("/templates").status_code == 200  # everyone can read the list


def test_admin_creates_disables_and_changes_role(db, admin, raw):
    made = admin.post(
        "/users",
        json={"email": "New@Firm.in", "name": "New", "role": "analyst", "password": GOOD},
        headers=CSRF,
    )
    assert made.status_code == 201
    uid = made.json()["id"]
    assert GOOD not in made.text and "hash" not in made.text
    assert (
        admin.post(
            "/users",
            json={"email": "new@firm.in", "name": "Dup", "role": "analyst", "password": GOOD},
            headers=CSRF,
        ).status_code
        == 409
    )
    assert admin.get("/users").status_code == 200
    # the new user signs in, is promoted, then disabled: the live session dies
    other = TestClient(app)
    assert (
        other.post("/auth/login", json={"email": "new@firm.in", "password": GOOD}).status_code
        == 200
    )
    assert (
        admin.patch(f"/users/{uid}", json={"role": "admin"}, headers=CSRF).json()["role"] == "admin"
    )
    assert admin.patch(f"/users/{uid}", json={"is_active": False}, headers=CSRF).status_code == 200
    assert other.get("/auth/me").status_code == 401
    actions = set(db.scalars(select(AuditEntry.action)))
    assert {"user.create", "user.role", "user.disable"} <= actions


def test_short_password_is_refused(admin):
    res = admin.post(
        "/users",
        json={"email": "s@firm.in", "name": "S", "role": "analyst", "password": "short"},
        headers=CSRF,
    )
    assert res.status_code == 422


def test_admin_cannot_remove_the_last_active_admin(db, admin):
    me = db.scalar(select(User).where(User.email == "boss@firm.in"))
    for body in ({"is_active": False}, {"role": "analyst"}):
        res = admin.patch(f"/users/{me.id}", json=body, headers=CSRF)
        assert res.status_code == 400


def test_reset_password_and_unblock(db, admin):
    ana = create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    for _ in range(get_settings().login_block_after):
        login(db, "ana@firm.in", "wrong")
        ana.paused_until = None
    db.flush()
    assert ana.blocked
    assert admin.post(f"/users/{ana.id}/unblock", headers=CSRF).status_code == 204
    assert not ana.blocked and ana.failed_count == 0
    new = "another long passphrase"
    res = admin.post(f"/users/{ana.id}/reset-password", json={"new_password": new}, headers=CSRF)
    assert res.status_code == 204
    assert login(db, "ana@firm.in", new).ok
    assert "user.password_reset" in set(db.scalars(select(AuditEntry.action)))


def test_adopt_local_moves_watchlist_and_templates(db, monkeypatch):
    from analekh.cli import adopt_local

    local = get_settings().default_user_id
    t = Template(owner=local, name="n", sectors=[], storage_key="k")
    db.add(t)
    db.flush()
    new = create_user(db, "boss@firm.in", "Boss", "admin", GOOD)
    adopt_local(db, new)
    db.flush()
    db.refresh(t)
    assert t.owner == new.id


def test_no_row_still_keyed_by_local_after_adopt(db):
    from analekh.cli import adopt_local

    local = get_settings().default_user_id
    new = create_user(db, "boss@firm.in", "Boss", "admin", GOOD)
    adopt_local(db, new)
    from sqlalchemy import text

    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if col.name in ("user_id", "owner") and table.name not in ("audit_log",):
                n = db.scalar(
                    text(f'select count(*) from "{table.name}" where "{col.name}" = :v'),
                    {"v": local},
                )
                assert n == 0, (table.name, col.name)


def test_create_admin_command_prompts_for_password(db, monkeypatch):
    from analekh import cli

    monkeypatch.setattr(cli, "_session", lambda: _Scope(db))
    res = CliRunner().invoke(
        cli.app, ["create-admin", "boss@firm.in", "Boss"], input=f"{GOOD}\n{GOOD}\n"
    )
    assert res.exit_code == 0, res.output
    u = db.scalar(select(User).where(User.email == "boss@firm.in"))
    assert u is not None and u.role == "admin"
    assert GOOD not in res.output
    assert login(db, "boss@firm.in", GOOD).ok


class _Scope:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *a):
        return False
