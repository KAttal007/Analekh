"""Password hashing and email normalisation (auth design, section 5)."""

import pytest

from analekh.auth import passwords
from analekh.auth.passwords import (
    PasswordTooLong,
    hash_password,
    normalize_email,
    verify_password,
)
from analekh.config import get_settings


def test_verify_roundtrip():
    h = hash_password("Correct-Horse-Battery-9")
    assert h.startswith("$argon2id$")
    assert verify_password("Correct-Horse-Battery-9", h) is True
    assert verify_password("wrong", h) is False


def test_too_long_password_refused_before_hashing(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("argon2 must not run for an over-long password")

    monkeypatch.setattr(passwords, "_hasher", type("H", (), {"hash": boom, "verify": boom})())
    with pytest.raises(PasswordTooLong):
        hash_password("x" * 10_000)
    assert (
        verify_password("x" * (get_settings().password_max_length + 1), "$argon2id$whatever")
        is False
    )


def test_none_hash_still_does_work(monkeypatch):
    calls = []
    real = passwords._hasher

    class Counting:
        def verify(self, h, p):
            calls.append(1)
            return real.verify(h, p)

    monkeypatch.setattr(passwords, "_hasher", Counting())
    assert verify_password("anything", None) is False
    assert calls == [1]


def test_normalize_email_strips_and_lowercases():
    assert normalize_email(" Kaushal@Firm.IN ") == "kaushal@firm.in"


@pytest.mark.parametrize(
    "raw",
    ["' OR 1=1 --", "x'; DROP TABLE users;--", "", "a@b", "a b@firm.in", "a" * 250 + "@firm.in"],
)
def test_injection_strings_and_junk_are_invalid_emails(raw):
    with pytest.raises(ValueError):
        normalize_email(raw)
