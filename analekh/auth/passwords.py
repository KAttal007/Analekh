"""Password hashing and email normalisation (auth design, section 5).

Passwords are hashed with argon2id and never stored or logged in clear. Over-long passwords are
refused before any hashing, so a huge input cannot be used to burn server time.
"""

import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MAX_PASSWORD = 128
MAX_EMAIL = 254
_EMAIL = re.compile(r"^[^@\s'\";,<>()\[\]\\]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

_hasher = PasswordHasher()
# Checked against when the account does not exist, so an unknown email costs the same as a wrong
# password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))  # random per process, never a real password


class PasswordTooLong(ValueError):
    """The password is longer than MAX_PASSWORD characters."""


class PasswordTooShort(ValueError):
    pass


def hash_password(plain: str) -> str:
    from analekh.config import get_settings

    if len(plain) < get_settings().password_min_length:
        raise PasswordTooShort(
            f"password must be at least {get_settings().password_min_length} characters"
        )
    if len(plain) > MAX_PASSWORD:
        raise PasswordTooLong(f"password is longer than {MAX_PASSWORD} characters")
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    """True when `plain` matches `hashed`. A missing hash still does the work of a check."""
    if len(plain) > MAX_PASSWORD:
        return False
    try:
        _hasher.verify(hashed or _DUMMY_HASH, plain)
    except (VerificationError, InvalidHashError):
        return False
    return hashed is not None


def normalize_email(raw: str) -> str:
    """Trim and lowercase an email, or raise ValueError. A conservative shape check, no DNS."""
    email = raw.strip().lower()
    if not email or len(email) > MAX_EMAIL or not _EMAIL.match(email):
        raise ValueError("not a valid email address")
    return email
