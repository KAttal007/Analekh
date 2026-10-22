"""Which browser origins may call the API, and the loopback address the defaults use."""

import pytest
from fastapi.testclient import TestClient

from analekh.api.main import app
from analekh.config import Settings, get_settings


def _preflight(origin: str):
    return TestClient(app).options(
        "/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-analekh-csrf",
        },
    )


def test_defaults_name_127_0_0_1_not_localhost(monkeypatch):
    """On Windows `localhost` tries IPv6 first and stalls; the defaults use the IPv4 address.
    The environment is cleared first: CI sets DATABASE_URL etc. to its service hostnames, and
    those override the defaults this test is about."""
    names = ("database_url", "redis_url", "minio_endpoint", "analekh_api", "cors_origins")
    for name in names:
        monkeypatch.delenv(name.upper(), raising=False)
    cfg = Settings(_env_file=None)
    for value in (cfg.database_url, cfg.redis_url, cfg.minio_endpoint, cfg.analekh_api):
        assert "localhost" not in value
        assert "127.0.0.1" in value
    assert all("localhost" not in origin for origin in cfg.cors_origin_list)


def test_the_web_app_origin_is_allowed_with_credentials():
    origin = get_settings().cors_origin_list[0]
    res = _preflight(origin)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == origin
    assert res.headers["access-control-allow-credentials"] == "true"


def test_a_foreign_origin_is_not_allowed():
    res = _preflight("http://evil.example")
    assert "access-control-allow-origin" not in res.headers


def test_localhost_is_no_longer_allowed_by_default():
    res = _preflight("http://localhost:5173")
    assert "access-control-allow-origin" not in res.headers


def test_origins_come_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://127.0.0.1:3000; http://127.0.0.1:5173 ;")
    get_settings.cache_clear()
    assert get_settings().cors_origin_list == ["https://127.0.0.1:3000", "http://127.0.0.1:5173"]
