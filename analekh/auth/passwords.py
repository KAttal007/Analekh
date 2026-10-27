"""Password hashing and email normalisation (auth design, section 5).

argon2id; never stored or logged in clear. Over-long passwords refused before hashing, so huge
input cannot burn server time.
"""

import re
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from analekh.config import get_settings

MAX_EMAIL = 254
_EMAIL = re.compile(r"^[^@\s'\";,<>()\[\]\\]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

_hasher = PasswordHasher()
# Checked against when the account does not exist, so an unknown email costs the same as a wrong
# password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))  # random per process, never a real password

_LETTERS = "abcdefghijkmnpqrstuvwxyz"  # no l, o
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, O
_DIGITS = "23456789"  # no 0, 1
_SPECIALS = "!#$%*+-=?@^_"


class PasswordRuleError(ValueError):
    """A chosen password misses rules. `missing` holds the labels, never the input."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Password needs: " + ", ".join(missing))


class PasswordTooLong(PasswordRuleError):
    """The password is longer than the maximum in settings."""


class PasswordTooShort(PasswordRuleError):
    """The password is shorter than the minimum in settings."""


def _plural(n: int, one: str, many: str) -> str:
    return f"At least {n} {one if n == 1 else many}"


@lru_cache
def _rules(
    lo: int, hi: int, letters: int, digits: int, specials: int, upper: int, lower: int
) -> tuple[tuple[str, str, str], ...]:
    return (
        ("length", f"{lo} to {hi} characters", rf"^[\s\S]{{{lo},{hi}}}$"),
        (
            "letters",
            _plural(letters, "letter", "letters"),
            rf"^(?:[^A-Za-z]*[A-Za-z]){{{letters}}}",
        ),
        ("digits", _plural(digits, "number", "numbers"), rf"^(?:[^0-9]*[0-9]){{{digits}}}"),
        (
            "specials",
            _plural(specials, "special character", "special characters"),
            rf"^(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){{{specials}}}",
        ),
        (
            "upper",
            _plural(upper, "uppercase letter", "uppercase letters"),
            rf"^(?:[^A-Z]*[A-Z]){{{upper}}}",
        ),
        (
            "lower",
            _plural(lower, "lowercase letter", "lowercase letters"),
            rf"^(?:[^a-z]*[a-z]){{{lower}}}",
        ),
        ("no_spaces", "No spaces", r"^\S*$"),
    )


def _current_rules() -> tuple[tuple[str, str, str], ...]:
    c = get_settings()
    return _rules(
        c.password_min_length,
        c.password_max_length,
        c.password_min_letters,
        c.password_min_digits,
        c.password_min_specials,
        c.password_min_upper,
        c.password_min_lower,
    )


def password_rules() -> list[dict[str, str]]:
    """The rules as published: id, label and the regex for each (numbers from settings)."""
    return [{"id": i, "label": label, "pattern": p} for i, label, p in _current_rules()]


def combined_pattern() -> str:
    """The whole rule set as one regex, built from the same settings."""
    c = get_settings()
    return (
        rf"^(?=(?:[^A-Za-z]*[A-Za-z]){{{c.password_min_letters}}})"
        rf"(?=(?:[^0-9]*[0-9]){{{c.password_min_digits}}})"
        rf"(?=(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){{{c.password_min_specials}}})"
        rf"(?=(?:[^A-Z]*[A-Z]){{{c.password_min_upper}}})"
        rf"(?=(?:[^a-z]*[a-z]){{{c.password_min_lower}}})"
        rf"\S{{{c.password_min_length},{c.password_max_length}}}$"
    )


def python_regex(pattern: str) -> re.Pattern[str]:
    """Compile a published pattern for Python. JavaScript's `$` only matches at the very end;
    Python's also matches before a final newline, so a trailing `$` becomes an end anchor."""
    return re.compile(pattern[:-1] + r"\Z" if pattern.endswith("$") else pattern)


def check_password_rules(plain: str) -> list[str]:
    """Ids of the rules `plain` does not meet (empty means it is fine). Over-long input is
    refused before any regex runs."""
    if len(plain) > get_settings().password_max_length:
        return ["length"]
    return [i for i, _label, p in _current_rules() if not python_regex(p).search(plain)]


def validate_new_password(plain: str) -> None:
    """For a password being chosen (not for sign-in): raise PasswordRuleError naming what is
    missing, by label, never quoting the input. Length errors have their own subclasses."""
    missing = check_password_rules(plain)
    if not missing:
        return
    labels = {i: label for i, label, _p in _current_rules()}
    exc_class = PasswordRuleError
    if "length" in missing:
        exc_class = (
            PasswordTooLong if len(plain) > get_settings().password_max_length else PasswordTooShort
        )
    raise exc_class([labels[i] for i in missing])


def check_password_length(plain: str) -> None:
    """Raise PasswordTooShort or PasswordTooLong; cheap, so callers check before spending
    anything (a reset code attempt, a hash)."""
    cfg = get_settings()
    if len(plain) < cfg.password_min_length:
        raise PasswordTooShort(
            [f"{cfg.password_min_length} to {cfg.password_max_length} characters"]
        )
    if len(plain) > cfg.password_max_length:
        raise PasswordTooLong(
            [f"{cfg.password_min_length} to {cfg.password_max_length} characters"]
        )


def generate_first_password() -> str:
    """A random password that always meets the rules: letters of both cases, digits and
    specials, without look-alike characters or markup characters."""
    cfg = get_settings()
    chars = [secrets.choice(_UPPER) for _ in range(2)]
    chars += [secrets.choice(_LETTERS) for _ in range(2)]
    chars += [secrets.choice(_DIGITS) for _ in range(2)]
    chars += [secrets.choice(_SPECIALS) for _ in range(2)]
    # the rest: mostly letters, so the letter count always clears the minimum
    rest = cfg.first_password_length - len(chars)
    pool = _LETTERS + _UPPER
    chars += [secrets.choice(pool) for _ in range(max(rest, 0))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def hash_password(plain: str) -> str:
    """Hash a password being chosen; the rules apply here and nowhere on the sign-in path."""
    validate_new_password(plain)
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    """True when `plain` matches `hashed`. A missing hash still does the work of a check."""
    if len(plain) > get_settings().password_max_length:
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
