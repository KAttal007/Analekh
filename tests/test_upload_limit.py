"""One admin-set upload limit for every upload (plan task 7)."""

import io
import re
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import select

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.api.uploads import get_max_upload_bytes, read_limited
from analekh.auth.service import create_user
from analekh.config import get_settings
from analekh.db.models import AuditEntry
from analekh.db.session import get_session

GOOD = "correct horse battery"
CSRF = {"X-Analekh-CSRF": "1"}
MB = 1024 * 1024


@pytest.fixture
def raw(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _as(raw, db, role):
    create_user(db, f"{role}@firm.in", role.title(), role, GOOD)
    assert (
        raw.post("/auth/login", json={"email": f"{role}@firm.in", "password": GOOD}).status_code
        == 200
    )
    return raw


@pytest.fixture
def admin(raw, db):
    return _as(raw, db, "admin")


@pytest.fixture
def analyst(raw, db):
    return _as(raw, db, "analyst")


def _upload(file_bytes: bytes):
    return UploadFile(file=io.BytesIO(file_bytes), filename="m.xlsx")


def test_default_comes_from_settings(db):
    assert get_max_upload_bytes(db) == get_settings().max_upload_default_bytes


def test_an_oversized_upload_is_413_with_the_message(db):
    limit = get_max_upload_bytes(db)
    with pytest.raises(HTTPException) as exc:
        read_limited(db, _upload(b"x" * (limit + MB)))
    assert exc.value.status_code == 413
    assert re.fullmatch(
        r"This file is \d+(\.\d+)? MB; the limit is \d+(\.\d+)? MB\. Ask your admin\.",
        exc.value.detail,
    )


def test_a_file_at_the_limit_is_accepted(db):
    limit = get_max_upload_bytes(db)
    assert len(read_limited(db, _upload(b"x" * limit))) == limit


def test_stops_reading_at_the_limit(db):
    """A stream that would yield 1 GB is cut off just past the limit."""
    limit = get_max_upload_bytes(db)
    read = 0

    class Endless:
        def read(self, n=-1):
            nonlocal read
            n = 1024 * 1024 if n is None or n < 0 else n
            read += n
            return b"x" * n

    with pytest.raises(HTTPException):
        read_limited(db, UploadFile(file=Endless(), filename="big.xlsx"))  # type: ignore[arg-type]
    assert read <= limit + 2 * MB


def test_admin_reads_and_changes_the_limit(admin, db):
    now = admin.get("/settings/upload-limit").json()
    assert now["bytes"] == get_settings().max_upload_default_bytes
    assert now["ceiling_bytes"] == get_settings().max_upload_ceiling_bytes
    res = admin.put("/settings/upload-limit", json={"bytes": 40 * MB}, headers=CSRF)
    assert res.status_code == 200 and res.json()["bytes"] == 40 * MB
    assert res.json()["updated_by"]
    assert get_max_upload_bytes(db) == 40 * MB


def test_raising_the_limit_allows_a_new_upload_only(admin, db):
    admin.put("/settings/upload-limit", json={"bytes": 2 * MB}, headers=CSRF)
    with pytest.raises(HTTPException):
        read_limited(db, _upload(b"x" * (3 * MB)))
    admin.put("/settings/upload-limit", json={"bytes": 5 * MB}, headers=CSRF)
    assert len(read_limited(db, _upload(b"x" * (3 * MB)))) == 3 * MB


def test_above_the_ceiling_or_below_one_mb_is_rejected(admin):
    ceiling = get_settings().max_upload_ceiling_bytes
    assert (
        admin.put("/settings/upload-limit", json={"bytes": ceiling + 1}, headers=CSRF).status_code
        == 422
    )
    assert (
        admin.put("/settings/upload-limit", json={"bytes": MB - 1}, headers=CSRF).status_code == 422
    )
    assert (
        admin.put("/settings/upload-limit", json={"bytes": ceiling}, headers=CSRF).status_code
        == 200
    )


def test_the_422_says_what_is_allowed(admin):
    res = admin.put("/settings/upload-limit", json={"bytes": 10_000 * MB}, headers=CSRF)
    assert "100 MB" in res.json()["detail"]


def test_analyst_can_read_but_not_change(analyst):
    assert analyst.get("/settings/upload-limit").status_code == 200
    assert (
        analyst.put("/settings/upload-limit", json={"bytes": 30 * MB}, headers=CSRF).status_code
        == 403
    )


def test_signed_out_cannot_read(raw):
    assert raw.get("/settings/upload-limit").status_code == 401


def test_a_change_is_audited(admin, db):
    admin.put("/settings/upload-limit", json={"bytes": 30 * MB}, headers=CSRF)
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "upload_limit_changed")).one()
    assert entry.detail == {"from": get_settings().max_upload_default_bytes, "to": 30 * MB}


def test_template_upload_obeys_the_limit(admin):
    admin.put("/settings/upload-limit", json={"bytes": MB}, headers=CSRF)
    res = admin.post(
        "/templates",
        files={"workbook": ("t.xlsx", b"PK" + b"x" * (2 * MB))},
        data={"name": "x", "sectors": "NBFC"},
        headers=CSRF,
    )
    assert res.status_code == 413
    assert "Ask your admin" in res.json()["detail"]


def test_no_route_reads_uploads_directly():
    api = Path(__file__).resolve().parents[1] / "analekh" / "api"
    offenders = [
        str(p.relative_to(api))
        for p in api.rglob("*.py")
        if p.name != "uploads.py"
        and re.search(r"\.file\.read\(|await \w+\.read\(", p.read_text("utf8"))
    ]
    assert offenders == []
