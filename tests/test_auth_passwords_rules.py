"""Password settings, rules, regexes and the first-password generator (first-password design 5)."""

import json
import random
import shutil
import string
import subprocess
from pathlib import Path

import pytest

from analekh.auth import passwords
from analekh.auth.passwords import (
    PasswordRuleError,
    PasswordTooLong,
    PasswordTooShort,
    check_password_rules,
    combined_pattern,
    generate_first_password,
    password_rules,
    python_regex,
    validate_new_password,
)
from analekh.config import Settings, get_settings

TABLE = {
    "Abcdefgh12345!x": True,
    "abcdefgh12345!x": False,
    "ABCDEFGH12345!X": False,
    "Abcdefgh12345xy": False,
    "Abcdefgh!!!!!!x": False,
    "Abc1!xxxxxxxx": False,
    "Abcdefgh 12345!x": False,
    "Abcdefg123456!!": False,
    "Kp7#mQz2!wRt9vLa": True,
}
NODE = Path("E:/fnm/node-versions/v24.22.1/installation/node.exe")


def _samples(n: int = 2000) -> list[str]:
    rng = random.Random(7)
    alphabet = string.ascii_letters + string.digits + "!#$%'\"<>;-_ \t" + "\né"
    out = list(TABLE)
    for _ in range(n):
        length = rng.choice([0, 5, 14, 15, 20, 30, 31, 40])
        out.append("".join(rng.choice(alphabet) for _ in range(length)))
    for _ in range(n // 2):
        base = [rng.choice(string.ascii_letters) for _ in range(rng.randint(8, 24))]
        base += [rng.choice(string.digits), rng.choice("!#$%*+-=?@^_")]
        rng.shuffle(base)
        out.append("".join(base))
    return out


def test_password_limits_come_from_settings():
    s = get_settings()
    assert s.password_max_length == 30 and s.password_min_length == 15
    assert s.first_password_hours == 24 and s.first_password_length == 20
    assert (s.password_min_letters, s.password_min_digits, s.password_min_specials) == (8, 1, 1)
    assert (s.password_min_upper, s.password_min_lower) == (1, 1)


def test_impossible_rule_settings_refused():
    with pytest.raises(ValueError):
        Settings(password_max_length=5).check_password_settings()
    with pytest.raises(ValueError):
        Settings(first_password_length=40).check_password_settings()
    with pytest.raises(ValueError):
        Settings(first_password_length=10).check_password_settings()
    Settings().check_password_settings()


def test_get_settings_checks_the_rules(monkeypatch):
    monkeypatch.setenv("PASSWORD_MAX_LENGTH", "5")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError):
            get_settings()
    finally:
        monkeypatch.delenv("PASSWORD_MAX_LENGTH")
        get_settings.cache_clear()


def test_published_rules_match_the_spec_table():
    rules = password_rules()
    assert [r["id"] for r in rules] == [
        "length", "letters", "digits", "specials", "upper", "lower", "no_spaces",
    ]  # fmt: skip
    by_id = {r["id"]: r for r in rules}
    assert by_id["length"]["pattern"] == r"^[\s\S]{15,30}$"
    assert by_id["letters"]["pattern"] == r"^(?:[^A-Za-z]*[A-Za-z]){8}"
    assert by_id["digits"]["pattern"] == r"^(?:[^0-9]*[0-9]){1}"
    assert by_id["specials"]["pattern"] == r"^(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){1}"
    assert by_id["upper"]["pattern"] == r"^(?:[^A-Z]*[A-Z]){1}"
    assert by_id["lower"]["pattern"] == r"^(?:[^a-z]*[a-z]){1}"
    assert by_id["no_spaces"]["pattern"] == r"^\S*$"
    assert by_id["length"]["label"] == "15 to 30 characters"
    assert by_id["digits"]["label"] == "At least 1 number"
    assert combined_pattern() == (
        r"^(?=(?:[^A-Za-z]*[A-Za-z]){8})(?=(?:[^0-9]*[0-9]){1})"
        r"(?=(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){1})(?=(?:[^A-Z]*[A-Z]){1})"
        r"(?=(?:[^a-z]*[a-z]){1})\S{15,30}$"
    )


def test_rules_follow_settings(monkeypatch):
    monkeypatch.setenv("PASSWORD_MIN_DIGITS", "3")
    get_settings.cache_clear()
    try:
        by_id = {r["id"]: r for r in password_rules()}
        assert by_id["digits"]["pattern"] == r"^(?:[^0-9]*[0-9]){3}"
        assert by_id["digits"]["label"] == "At least 3 numbers"
    finally:
        monkeypatch.delenv("PASSWORD_MIN_DIGITS")
        get_settings.cache_clear()


def test_sample_table_matches_spec():
    for pw, ok in TABLE.items():
        assert (check_password_rules(pw) == []) is ok, pw


def test_combined_and_per_rule_agree():
    for pw in _samples():
        assert bool(python_regex(combined_pattern()).match(pw)) == (check_password_rules(pw) == []), pw


def test_thirty_ok_thirty_one_refused():
    assert check_password_rules("Abcdefgh12345!x" + "a" * 15) == []  # 30 chars
    assert "length" in check_password_rules("Abcdefgh12345!x" + "a" * 16)  # 31


def test_over_length_returns_before_any_regex(monkeypatch):
    monkeypatch.setattr(passwords, "python_regex", lambda *a, **k: pytest.fail("regex ran"))
    assert check_password_rules("x" * 10_000) == ["length"]


def test_validate_names_every_missing_rule_without_the_input():
    with pytest.raises(PasswordRuleError) as e:
        validate_new_password("abcdefgh")
    msg = str(e.value)
    assert msg.startswith("Password needs: ")
    assert "At least 1 number" in msg and "At least 1 uppercase letter" in msg
    assert "abcdefgh" not in msg
    validate_new_password("Kp7#mQz2!wRt9vLa")


def test_length_errors_keep_their_classes():
    with pytest.raises(PasswordTooShort):
        validate_new_password("Ab1#")
    with pytest.raises(PasswordTooLong):
        validate_new_password("Ab1#" * 20)
    assert issubclass(PasswordTooShort, PasswordRuleError)


def test_generated_passwords_always_valid():
    for _ in range(1000):
        pw = generate_first_password()
        assert len(pw) == get_settings().first_password_length
        assert check_password_rules(pw) == []
        assert not set(pw) & set("0Oo1lI")
        assert not set(pw) & set("<>'\"&")
        assert sum(c.isdigit() for c in pw) >= 2
        assert sum(c in "!#$%*+-=?@^_" for c in pw) >= 2
        assert sum(c.isupper() for c in pw) >= 2 and sum(c.islower() for c in pw) >= 2
    assert len({generate_first_password() for _ in range(50)}) == 50


@pytest.mark.skipif(not (NODE.exists() or shutil.which("node")), reason="node not found")
def test_patterns_run_in_javascript(tmp_path):
    node = str(NODE) if NODE.exists() else str(shutil.which("node"))
    samples = [s for s in _samples(600) if len(s) <= get_settings().password_max_length]
    data = tmp_path / "in.json"
    data.write_text(
        json.dumps(
            {
                "rules": [r["pattern"] for r in password_rules()],
                "all": combined_pattern(),
                "samples": samples,
            }
        ),
        encoding="utf-8",
    )
    script = tmp_path / "run.js"
    script.write_text(
        "const d = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));"
        "const out = d.samples.map(s => [d.rules.map(p => new RegExp(p).test(s)),"
        " new RegExp(d.all).test(s)]);"
        "console.log(JSON.stringify(out));",
        encoding="utf-8",
    )
    done = subprocess.run([node, str(script), str(data)], capture_output=True, text=True, check=True, timeout=60)
    got = json.loads(done.stdout)
    for s, (per_rule, combined) in zip(samples, got, strict=True):
        want = [bool(python_regex(r["pattern"]).search(s)) for r in password_rules()]
        assert per_rule == want, s
        assert combined == bool(python_regex(combined_pattern()).match(s)), s


ATTACKS = [
    "Ab1';DROP-TABLE-users;--xY",
    'Ab1"OR"1"="1"--xyzQabc',
    "<script>alert(1)</script>Aa1",
    "Ab1<img/src=x/onerror=a>qq",
]


@pytest.mark.parametrize("pw", ATTACKS)
def test_attack_strings_meet_the_rules(pw):
    assert check_password_rules(pw) == []


def test_refusal_never_echoes_input(caplog):
    with pytest.raises(PasswordRuleError) as e:
        validate_new_password("<script>x")
    assert "<script>" not in str(e.value) and "<script>" not in caplog.text
    with pytest.raises(PasswordTooLong) as e2:
        validate_new_password("<script>" * 10)
    assert "<script>" not in str(e2.value)
