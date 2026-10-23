"""User administration, admin-only templates and the create-admin command (plan task 6)."""

import logging
import re
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from typer.testing import CliRunner

from analekh.api.deps import get_session_scope, get_store
from analekh.api.main import app
from analekh.auth.service import create_user, login
from analekh.config import get_settings
from analekh.db.models import AuditEntry, Base, Template, User
from analekh.db.session import get_session

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def raw(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    # The mail goes in a background task with its own session: here, the test's session.
    app.dependency_overrides[get_session_scope] = lambda: lambda: nullcontext(db)
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


@pytest.fixture
def sent(monkeypatch):
    """SMTP switched on; every mail captured as (to, subject, body)."""
    box: list[tuple[str, str, str]] = []
    monkeypatch.setenv("SMTP_URL", "smtp://u:p@mail.example:587")
    get_settings.cache_clear()

    def fake(to, subject, body):
        box.append((to, subject, body))
        return True

    monkeypatch.setattr("analekh.alerts.mail.send_mail", fake)
    return box


def _first_password(box):
    found = re.search(r"First password: (\S+)", box[-1][2])
    assert found is not None
    return found.group(1)


def test_admin_creates_disables_and_changes_role(db, admin, raw, sent):
    made = admin.post(
        "/users",
        json={"email": "New@Firm.in", "name": "New", "role": "analyst"},
        headers=CSRF,
    )
    assert made.status_code == 201
    uid = made.json()["id"]
    plain = _first_password(sent)
    assert plain not in made.text and "hash" not in made.text and "password" not in made.json()
    assert (
        admin.post(
            "/users",
            json={"email": "new@firm.in", "name": "Dup", "role": "analyst"},
            headers=CSRF,
        ).status_code
        == 409
    )
    assert admin.get("/users").status_code == 200
    # the new user signs in with the emailed password, is promoted, then disabled
    other = TestClient(app)
    assert (
        other.post("/auth/login", json={"email": "new@firm.in", "password": plain}).status_code
        == 200
    )
    assert (
        admin.patch(f"/users/{uid}", json={"role": "admin"}, headers=CSRF).json()["role"] == "admin"
    )
    assert admin.patch(f"/users/{uid}", json={"is_active": False}, headers=CSRF).status_code == 200
    assert other.get("/auth/me").status_code == 401
    actions = set(db.scalars(select(AuditEntry.action)))
    assert {"user.create", "user.role", "user.disable"} <= actions


def test_add_user_has_no_password_field_and_mails_one(db, admin, sent):
    res = admin.post(
        "/users", json={"email": "x@firm.in", "name": "X", "role": "analyst"}, headers=CSRF
    )
    # the reply says the mail is on its way; it is sent after the reply
    assert res.status_code == 201 and res.json()["first_password_mail"] == "sending"
    assert "password" not in res.json()
    assert len(sent) == 1 and sent[0][0] == "x@firm.in"
    u = db.scalar(select(User).where(User.email == "x@firm.in"))
    assert u.must_change_password and u.first_password_expires_at is not None
    assert u.first_password_mail == "sent"
    assert db.scalar(select(AuditEntry).where(AuditEntry.action == "user.create")) is not None
    entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "user.first_password_mail"))
    assert entry.detail == {"target": u.id, "sent": True}


def test_add_user_mail_failure_keeps_the_user(db, admin, sent, monkeypatch):
    monkeypatch.setattr("analekh.alerts.mail.send_mail", lambda *a: False)
    res = admin.post(
        "/users", json={"email": "x@firm.in", "name": "X", "role": "analyst"}, headers=CSRF
    )
    assert res.status_code == 201
    u = db.scalar(select(User).where(User.email == "x@firm.in"))
    assert u is not None and u.first_password_mail == "failed"
    rows = {r["email"]: r for r in admin.get("/users").json()}
    assert rows["x@firm.in"]["first_password_mail"] == "failed"  # the Users page shows it


def test_add_user_refused_without_smtp(db, admin, monkeypatch):
    monkeypatch.setenv("SMTP_URL", "")
    get_settings.cache_clear()
    res = admin.post(
        "/users", json={"email": "x@firm.in", "name": "X", "role": "analyst"}, headers=CSRF
    )
    assert res.status_code == 503 and "Email is not set up" in res.json()["detail"]
    assert db.scalar(select(User).where(User.email == "x@firm.in")) is None


def test_generated_password_never_in_reply_or_log(admin, sent, caplog):
    caplog.set_level(logging.DEBUG)
    res = admin.post(
        "/users", json={"email": "x@firm.in", "name": "X", "role": "analyst"}, headers=CSRF
    )
    plain = _first_password(sent)
    assert plain not in res.text and plain not in caplog.text


def test_typed_password_in_body_is_ignored(db, admin, sent):
    admin.post(
        "/users",
        json={"email": "x@firm.in", "name": "X", "role": "analyst", "password": GOOD},
        headers=CSRF,
    )
    assert login(db, "x@firm.in", GOOD).ok is False


def test_send_first_password_resets_everything(db, admin, sent):
    ana = create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    for _ in range(get_settings().login_block_after):
        login(db, "ana@firm.in", "wrong")
        ana.paused_until = None
    db.flush()
    assert ana.blocked
    res = admin.post(f"/users/{ana.id}/send-first-password", headers=CSRF)
    assert res.status_code == 202 and res.json()["first_password_mail"] == "sending"
    plain = _first_password(sent)
    assert plain not in res.text
    assert not ana.blocked and ana.failed_count == 0 and ana.must_change_password
    assert ana.first_password_mail == "sent"
    assert login(db, "ana@firm.in", GOOD).ok is False  # the old password is dead
    assert login(db, "ana@firm.in", plain).must_change_password is True
    entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "user.password_reset"))
    assert entry.detail["target"] == ana.id
    assert admin.post(f"/users/{ana.id}/reset-password", json={}, headers=CSRF).status_code in (
        404,
        405,
    )


def test_send_again_wording_follows_whether_first_sign_in_is_pending(db, admin, sent):
    body = {"email": "new@firm.in", "name": "New", "role": "analyst"}
    new_id = admin.post("/users", json=body, headers=CSRF).json()["id"]
    admin.post(f"/users/{new_id}/send-first-password", headers=CSRF)  # still pending
    assert sent[-1][1] == "Your Analekh account"
    assert "has been made for you" in sent[-1][2] and "reset" not in sent[-1][2]
    active = create_user(db, "old@firm.in", "Old", "analyst", GOOD)  # has chosen a password
    admin.post(f"/users/{active.id}/send-first-password", headers=CSRF)
    assert sent[-1][1] == "Your Analekh password was reset"
    assert "reset by an admin" in sent[-1][2]


def test_send_first_password_on_microsoft_account_refused(db, admin, sent):
    ms = create_user(db, "ms@firm.in", "Ms", "analyst", auth_kind="microsoft")
    res = admin.post(f"/users/{ms.id}/send-first-password", headers=CSRF)
    assert res.status_code == 400 and sent == []
    assert not ms.must_change_password


def test_analyst_cannot_add_or_send(db, analyst, sent):
    other = create_user(db, "o@firm.in", "O", "analyst", GOOD)
    body = {"email": "x@firm.in", "name": "X", "role": "analyst"}
    assert analyst.post("/users", json=body, headers=CSRF).status_code == 403
    assert analyst.post(f"/users/{other.id}/send-first-password", headers=CSRF).status_code == 403
    assert sent == []


def test_admin_cannot_remove_the_last_active_admin(db, admin):
    me = db.scalar(select(User).where(User.email == "boss@firm.in"))
    for body in ({"is_active": False}, {"role": "analyst"}):
        res = admin.patch(f"/users/{me.id}", json=body, headers=CSRF)
        assert res.status_code == 400


def test_unblock(db, admin):
    ana = create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    for _ in range(get_settings().login_block_after):
        login(db, "ana@firm.in", "wrong")
        ana.paused_until = None
    db.flush()
    assert ana.blocked
    assert admin.post(f"/users/{ana.id}/unblock", headers=CSRF).status_code == 204
    assert not ana.blocked and ana.failed_count == 0


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
