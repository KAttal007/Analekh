# First Password and Password Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin adds a user without typing a password; Analekh generates a first password, emails it once, and forces the user to choose their own at first sign-in. Password rules (15 to 30 characters, 8 letters, 1 digit, 1 special, 1 upper, 1 lower, no spaces) are enforced on the server and shown live on screen from one source.

**Architecture:** Server owns the rules (`analekh/auth/passwords.py`, numbers from `config.py`) and publishes them with per-rule regexes at `GET /auth/password-rules`. The web app runs the same regexes as the user types and the server runs them on submit. A `must_change_password` flag and a 24-hour `first_password_expires_at` on `users` gate every route except three through one dependency in `api/deps.py`. The first password and admin resets share one server action that emails inline.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic (PostgreSQL 16), argon2-cffi, pytest; React + TypeScript, Vitest, pnpm; Node 24 for the front end.

**Spec:** `docs/superpowers/specs/2026-10-23-first-password-design.md` (and parent `docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md`). Executors read both.

## Global Constraints

- Password length: `password_min_length = 15`, `password_max_length = 30`. Sign-in, choose-password, reset and admin send all refuse 31+ characters. No other maximum anywhere.
- Rules: `password_min_letters = 8`, `password_min_digits = 1`, `password_min_specials = 1`, `password_min_upper = 1`, `password_min_lower = 1`. Letters are ASCII `A-Z a-z`. Specials are printable ASCII that are not letters or digits. No whitespace.
- Rules apply when a password is chosen (choose-password, reset-confirm, `create-admin`, admin add/send). Not at sign-in for an existing password, except the length cap of 30.
- `first_password_hours = 24`; `first_password_length = 20`; generated specials are exactly `!#$%*+-=?@^_`; generated set leaves out `0 O o 1 l I`.
- Passwords are stored only as argon2id hashes. No password, first password or reset code in any reply, log line, audit entry, URL or `localStorage`.
- Every route needs a signed-in user, except `/auth/login`, the reset flow, `/auth/password-rules` and `/public/*` (CLAUDE.md rule 9).
- Money and limits come from `config.py`; no numeric literal for these values in code or tests.
- SQL: no `text(` and no `execute("` under `analekh/auth/` or in `analekh/api/routers/auth.py` / `users.py`.
- Email with SMTP off: adding a user returns 503 `Email is not set up. Contact the admin team.` and creates nothing.
- Reuse: one constant for the length limit (`password_max_length`); one React component for the new-password field with the rule checklist, used by the reset step and the first-sign-in step; the existing `Login.tsx` card is extended, not replaced.

## Review Focus

1. A pasted password containing `'`, `"`, `<script>`, `; DROP TABLE` is stored, verified and signs in exactly, and the tables survive. Expected: works; no error text echoes it.
2. A password of 31 characters with otherwise valid content is refused at every entry point with the same message; 30 is accepted. Expected: consistent refusal, no hashing done first.
3. A user who closes the tab after the first sign-in can still sign in with the first password until it is changed or 24 hours pass. Expected: works until expiry.
4. Admin sends a new first password while the user is signed in: their sessions end, the old first password stops working at once. Expected: immediate.
5. The generated first password passes the rules on every generation (1,000 samples), with the configured length, no ambiguous characters. Expected: always valid.

Each line is tested in the task that owns the code (see Tasks 2, 3, 4, 6 and 7).

---

## File Map

- Modify `analekh/config.py` — new settings (`password_max_length`, rule counts, first-password hours and length).
- Modify `analekh/auth/passwords.py` — rules, per-rule regexes, combined regex, generator, length checks. Replaces `MAX_PASSWORD`.
- Create `analekh/auth/first_password.py` — generate, send and expire the first password; the one admin action.
- Modify `analekh/auth/service.py` — `create_user` takes no password; `set_password` clears the flag and expiry; sign-in returns `must_change_password`; expired first password refused.
- Modify `analekh/auth/reset.py` — the forgot-password confirm clears the flag and expiry; the reset mail reads the setting-driven text.
- Modify `analekh/db/models.py` and create migration `analekh/db/migrations/versions/0010_first_password.py` — two columns.
- Modify `analekh/api/deps.py` — `get_current` refuses every route except the allow-list while the flag is set.
- Modify `analekh/api/routers/auth.py` — password-rules route; `MeOut` gets `must_change_password`; `POST /auth/first-password`; max length from settings.
- Modify `analekh/api/routers/users.py` — add user without password; `POST /users/{id}/send-first-password` replaces `reset-password`.
- Modify `analekh/alerts/mail.py` — unchanged sender; used by the welcome text.
- Create `web/src/components/PasswordRules.tsx` — the shared new-password field and live checklist.
- Modify `web/src/pages/Login.tsx` — `first` mode; `confirm` uses the shared field.
- Modify `web/src/pages/admin/Users.tsx` — no password box; "Send first password"; waiting tag.
- Tests: `tests/test_auth_passwords_rules.py` (new), `tests/test_auth_first_password.py` (new), existing `tests/test_auth_*.py` and `tests/test_users_api.py` updated where they assumed a typed password; `web/src/components/PasswordRules.test.tsx` (new), `web/src/pages/Login.test.tsx` and `web/src/pages/admin/Users.test.tsx` updated.

---

### Task 1: Settings and the shared limit

**Files:**
- Modify: `analekh/config.py` (near `password_min_length`, line ~76)
- Test: `tests/test_auth_passwords_rules.py` (create)

**Interfaces:**
- Produces: `Settings.password_max_length: int = 30`, `password_min_letters: int = 8`, `password_min_digits: int = 1`, `password_min_specials: int = 1`, `password_min_upper: int = 1`, `password_min_lower: int = 1`, `first_password_hours: int = 24`, `first_password_length: int = 20`. Also `Settings.check_password_settings()` raising `ValueError` when the rules cannot be met (`min_letters + min_digits + min_specials > password_max_length`, or `first_password_length` outside `[password_min_length, password_max_length]`), called from `get_settings()` construction.

- [ ] **Step 1: Write the failing test**

```python
def test_password_limits_come_from_settings(monkeypatch):
    s = get_settings()
    assert s.password_max_length == 30 and s.password_min_length == 15
    assert s.first_password_hours == 24 and s.first_password_length == 20


def test_impossible_rule_settings_refused(monkeypatch):
    s = Settings(password_max_length=5)
    with pytest.raises(ValueError):
        s.check_password_settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth_passwords_rules.py -v`
Expected: FAIL (attributes missing).

- [ ] **Step 3: Add the fields and `check_password_settings` to `Settings` in `config.py`.**
Defaults exactly as in Global Constraints. The check is a plain method; `get_settings()` calls it once.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_auth_passwords_rules.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add analekh/config.py tests/test_auth_passwords_rules.py
git commit -m "feat(auth): password rule and first-password settings"
```

---

### Task 2: Password rules, per-rule regexes, combined regex, generator

**Files:**
- Modify: `analekh/auth/passwords.py` (replace `MAX_PASSWORD` with a function reading the setting; keep `_EMAIL`, hashing, `verify_password`)
- Test: `tests/test_auth_passwords_rules.py` (extend)

**Interfaces:**
- Produces:
  - `password_rules() -> list[dict[str, str]]` — `[{"id", "label", "pattern"}, ...]` in order `length, letters, digits, specials, upper, lower, no_spaces`; patterns exactly as in the spec table, numbers from settings.
  - `combined_pattern() -> str` — the spec's `all` regex built from settings.
  - `check_password_rules(plain: str) -> list[str]` — returns the labels of unmet rules (empty = ok). Uses the per-rule patterns via `re.search` (anchored as published). Length above the max returns `["length"]` before running any regex.
  - `validate_new_password(plain: str) -> None` — raises `PasswordRuleError(missing: list[str])` whose message is `"Password needs: " + ", ".join(labels)`; `PasswordTooLong` / `PasswordTooShort` kept for existing callers (message from settings).
  - `generate_first_password() -> str` — length `first_password_length`; guaranteed at least 8 letters (2 or more each case), 2 digits, 2 specials; drawn with `secrets`; shuffled with `secrets.SystemRandom`; alphabet excludes `0 O o 1 l I`; specials `!#$%*+-=?@^_`.
  - `MAX_PASSWORD` removed; every caller switches to `get_settings().password_max_length`.

- [ ] **Step 1: Write the failing tests**

```python
def test_sample_table_matches_spec():
    cases = {
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
    for pw, ok in cases.items():
        assert (check_password_rules(pw) == []) is ok, pw


def test_combined_and_per_rule_agree(samples):
    for pw in samples:  # 2,000 random strings from a mixed alphabet plus the table above
        assert bool(re.match(combined_pattern(), pw)) == (check_password_rules(pw) == []), pw


def test_thirty_ok_thirty_one_refused():
    assert check_password_rules("Abcdefgh12345!x" + "a" * 14) == []  # 30 chars
    assert "length" in check_password_rules("Abcdefgh12345!x" + "a" * 15)  # 31


def test_generated_passwords_always_valid():
    for _ in range(1000):
        pw = generate_first_password()
        assert len(pw) == get_settings().first_password_length
        assert check_password_rules(pw) == []
        assert not set(pw) & set("0O o1lI".replace(" ", ""))


def test_patterns_run_in_javascript(tmp_path):  # cross-check with node on the same samples
    ...  # writes patterns + samples to a JSON file, runs node with -e, asserts equal results
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth_passwords_rules.py -v`
Expected: FAIL (functions missing).

- [ ] **Step 3: Implement** the functions above in `passwords.py`. Use `re.compile` once per call of `password_rules()` cached with `functools.lru_cache` keyed on settings values. Per-rule checks use `re.search(pattern, plain)` on the published patterns (they are anchored at `^`). The `no_spaces` pattern is `^\S*$`, which is `re.search`-safe.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth_passwords_rules.py -v`
Expected: PASS. Then `uv run ruff check analekh && uv run mypy analekh/auth/passwords.py`: clean.

- [ ] **Step 5: Commit**

```bash
git add analekh/auth/passwords.py tests/test_auth_passwords_rules.py
git commit -m "feat(auth): password rules from settings, combined regex, first-password generator"
```

---

### Task 3: Injection and echo safety on the password path

**Files:**
- Modify: `analekh/auth/passwords.py` (refuse over-length before any regex; errors never include input)
- Test: `tests/test_auth_passwords_rules.py` (extend), `tests/test_auth_first_password.py` (create, later tasks extend)

**Interfaces:**
- Consumes: Task 2 functions.
- Produces: unchanged signatures; behaviour tests only.

- [ ] **Step 1: Write the failing tests**

```python
ATTACKS = [
    "Ab1'; DROP TABLE users;--xY",
    'Ab1" OR "1"="1"--xyzQ',
    "<script>alert(1)</script>Aa1",
    "Ab1<img src=x onerror=a>q",
]


@pytest.mark.parametrize("pw", ATTACKS)
def test_attack_strings_store_and_sign_in_exactly(db, pw):
    # each is padded in the test to 15..30 chars and meets the rules first
    assert check_password_rules(pw) == []
    user = create_user(db, "a@firm.in", "A", "analyst", pw)
    assert login(db, "a@firm.in", pw).user is not None
    assert db.scalar(select(func.count()).select_from(User)) >= 1  # tables intact


def test_refusal_never_echoes_input(caplog):
    with pytest.raises(PasswordRuleError) as e:
        validate_new_password("<script>x")
    assert "<script>" not in str(e.value) and "<script>" not in caplog.text


def test_no_raw_sql_in_auth_routes_and_service():  # extends test_auth_code_has_no_raw_sql
    for path in ["analekh/auth", "analekh/api/routers/auth.py", "analekh/api/routers/users.py"]:
        ...  # fails on "text(" or 'execute("'
```

- [ ] **Step 2: Run to verify fail.** `uv run pytest tests/test_auth_passwords_rules.py tests/test_auth_first_password.py -v` → FAIL.

- [ ] **Step 3: Implement.** `validate_new_password` checks length first, returns before regexes on >30. Error messages use only labels from `password_rules()`, never the input. Log lines in the auth code log only exception class names and ids.

- [ ] **Step 4: Run to verify pass;** ruff and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add analekh/auth/passwords.py tests/
git commit -m "test(auth): injection-safe storage and no echo of password input"
```

---

### Task 4: Database columns and the first-password flag

**Files:**
- Modify: `analekh/db/models.py` (`User`, after `blocked` at line ~476)
- Create: `analekh/db/migrations/versions/0010_first_password.py`
- Test: `tests/test_auth_schema.py` (extend)

**Interfaces:**
- Produces on `User`: `must_change_password: Mapped[bool]` (`server_default=false`), `first_password_expires_at: Mapped[datetime | None]`.

- [ ] **Step 1: Write the failing test**

```python
def test_first_password_columns_default_off(db, user):
    assert user.must_change_password is False and user.first_password_expires_at is None
```

- [ ] **Step 2: Run to verify fail.** `uv run pytest tests/test_auth_schema.py -v` → FAIL.

- [ ] **Step 3: Add the columns, then** `uv run alembic revision --autogenerate -m "first password"`; rename to `0010_first_password.py`; review by hand (two `op.add_column`, server defaults, downgrade drops them).

- [ ] **Step 4: Run** `uv run alembic upgrade head && uv run alembic check` → no drift; `uv run pytest tests/test_auth_schema.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add analekh/db/models.py analekh/db/migrations/versions/0010_first_password.py tests/test_auth_schema.py
git commit -m "feat(auth): must-change-password flag and first-password expiry"
```

---

### Task 5: Service: create without password, first-password send, change clears flag

**Files:**
- Create: `analekh/auth/first_password.py`
- Modify: `analekh/auth/service.py` (`create_user` signature; `set_password`; `login`)
- Modify: `analekh/auth/reset.py` (confirm clears flag and expiry)
- Test: `tests/test_auth_first_password.py` (extend)

**Interfaces:**
- `service.create_user(db, email, name, role, auth_kind="password") -> User` — no password argument; for `password` kind it generates via `first_password.issue(...)`; returns the user; the plain password is returned separately: `create_user_with_first_password(db, email, name, role) -> tuple[User, str]`. Only the router and `issue` see the plain text.
- `first_password.issue(db, user, now=None) -> str` — sets `password_hash`, `must_change_password=True`, `first_password_expires_at=now+first_password_hours`, clears `paused_until`, `blocked`, `failed_count`; ends the user's sessions; returns the plain password. Does not commit.
- `first_password.send(user, plain, *, first: bool) -> bool` — builds the plain-text welcome (or "reset") body with the email as username, the password, "works once and lasts 24 hours" (from settings), and calls `alerts.mail.send_mail` inline; returns sent or not. Subject `"Your Analekh account"` or `"Your Analekh password was reset"`.
- `first_password.send_now(db, user, *, first: bool) -> bool` — `issue` + commit + `send`; if send fails the password is still issued (admin sees `mail_sent: false` and can send again).
- `service.set_password(db, user, plain)` — validates with `validate_new_password`, sets hash, clears `must_change_password` and `first_password_expires_at`, ends other sessions.
- `service.login(db, email, password) -> LoginResult` — `LoginResult` gains `must_change_password: bool`; when the flag is set and `first_password_expires_at < now`, returns a refused result with reason `first_password_expired`.

- [ ] **Step 1: Write the failing tests**

```python
def test_add_user_makes_first_password_and_sends_once(db, sent):
    user, plain = create_user_with_first_password(db, "new@firm.in", "New", "analyst")
    assert user.must_change_password and user.first_password_expires_at is not None
    assert verify_password(plain, user.password_hash)
    assert "new@firm.in" in sent.body and plain in sent.body
    assert plain not in repr(user)                       # never on the model object's repr path

def test_first_password_works_until_changed_then_dies(db, user_with_first):
    user, plain = user_with_first
    assert login(db, user.email, plain).must_change_password is True
    set_password(db, user, NEW_VALID)
    assert login(db, user.email, plain).ok is False
    assert login(db, user.email, NEW_VALID).must_change_password is False

def test_expired_first_password_refused(db, user_with_first, clock):
    clock.advance(hours=24, seconds=1)
    assert login(db, user.email, plain).reason == "first_password_expired"

def test_mail_failure_still_issues(db, mail_down):
    user, plain, sent_ok = send_now(db, user, first=True) ... ; assert sent_ok is False and user.must_change_password

def test_send_first_password_ends_sessions_and_clears_block(db, blocked_user_with_session):
    ...  # session token dead; blocked False; old password dead; expiry 24h from now

def test_forgot_password_confirm_clears_flag(db, user_with_first, code):
    ...  # reset.confirm_reset with the emailed code; must_change_password False

def test_welcome_mail_has_no_html_and_no_link(sent):
    assert "<" not in sent.body and "http" not in sent.body
```

- [ ] **Step 2: Run to verify fail.** `uv run pytest tests/test_auth_first_password.py -v` → FAIL.

- [ ] **Step 3: Implement** the interfaces above. The clock is `service._now(now)` (existing helper) so tests advance time. `first_password.send` uses `alerts.mail.send_mail` directly, not a background task.

- [ ] **Step 4: Run** the file, then `uv run pytest tests/test_auth_service.py tests/test_auth_reset.py -q` → PASS; update any test that passed a password to `create_user` (expected: those now call `create_user_with_first_password` or `create_user` with no password).

- [ ] **Step 5: Commit**

```bash
git add analekh/auth/ tests/test_auth_first_password.py tests/test_auth_service.py tests/test_auth_reset.py
git commit -m "feat(auth): first password issued, emailed, expires in 24 hours, forced change"
```

---

### Task 6: Dependency gate, auth routes, password-rules route

**Files:**
- Modify: `analekh/api/deps.py` (`get_current`)
- Modify: `analekh/api/routers/auth.py` (`MeOut`, `login`, `me`, `first-password`, `password-rules`)
- Test: `tests/test_auth_first_password.py` (extend), `tests/test_auth_api.py` (extend)

**Interfaces:**
- `deps.FIRST_PASSWORD_ALLOWED: frozenset[tuple[str, str]]` = `{("GET","/auth/me"), ("POST","/auth/logout"), ("GET","/auth/password-rules"), ("POST","/auth/first-password")}`. `get_current` raises `HTTPException(403, {"code": "password_change_required"})` when `user.must_change_password` and `(request.method, request.scope["route"].path)` not in the allow-list. `request` is injected.
- `GET /auth/password-rules` → `{"rules": password_rules(), "combined": combined_pattern(), "max_length": int, "min_length": int}`; no sign-in; `no-store`.
- `POST /auth/first-password` body `{current_password: str (max 128 field), new_password: str (max 128 field)}`; 204 on success; 400 `{"detail": "...", "missing": [...]}` on rule failure (checked before hashing); 401 when `current_password` is wrong (counted by the normal failure counter); only for a signed-in user with the flag.
- `MeOut` gains `must_change_password: bool`; login reply the same.

- [ ] **Step 1: Write the failing tests**

```python
def test_flagged_user_is_limited_to_four_routes(client, flagged_session):
    for route in app_get_paths_with_methods():
        if (route.method, route.path) in FIRST_PASSWORD_ALLOWED:
            continue
        r = client.request(route.method, route.resolved, cookies=flagged_session)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "password_change_required"


def test_password_rules_endpoint_public_and_no_store(client):
    r = client.get("/auth/password-rules")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert [x["id"] for x in r.json()["rules"]] == [
        "length",
        "letters",
        "digits",
        "specials",
        "upper",
        "lower",
        "no_spaces",
    ]


def test_first_password_route_rejects_31_chars_and_rule_failures(client, flagged_session): ...


def test_first_password_success_then_normal_access(client, flagged_session): ...


def test_wrong_current_password_counts_as_failure(client, flagged_session): ...
```

- [ ] **Step 2: Run to verify fail.** `uv run pytest tests/test_auth_first_password.py tests/test_auth_api.py -v` → FAIL.

- [ ] **Step 3: Implement** the gate in `get_current`; add the route; the login reply carries the flag; `expired` maps to 401 `{"detail": "This first password has expired. Ask an admin to send a new one."}`.

- [ ] **Step 4: Run** the two files and `uv run pytest tests/test_auth_api.py tests/test_users_api.py -q`; fix any test that assumed the old full access for a flagged account (none expected, since the flag is new). PASS.

- [ ] **Step 5: Commit**

```bash
git add analekh/api/deps.py analekh/api/routers/auth.py tests/test_auth_first_password.py tests/test_auth_api.py
git commit -m "feat(auth): first-password gate on every route, password-rules endpoint"
```

---

### Task 7: Admin user routes

**Files:**
- Modify: `analekh/api/routers/users.py` (`UserIn` drops `password`; `create_user` route; `send-first-password` replaces `reset-password`)
- Test: `tests/test_users_api.py` (extend)

**Interfaces:**
- `POST /users` body `{email, name, role}` → 201 `UserOut` plus `mail_sent: bool`; 503 `Email is not set up. Contact the admin team.` when `smtp_url` empty (nothing created). Writes `AuditEntry` `user_created` with `mail_sent`.
- `POST /users/{id}/send-first-password` (admin, not Microsoft) → 200 `{mail_sent: bool}`; ends sessions, clears block/pause, new 24h, audit `first_password_sent`. Old `reset-password` route removed.

- [ ] **Step 1: Write the failing tests**

```python
def test_add_user_has_no_password_field_and_mails_one(admin_client, sent):
    r = admin_client.post("/users", json={"email": "x@firm.in", "name": "X", "role": "analyst"})
    assert r.status_code == 201 and r.json()["mail_sent"] is True
    assert "password" not in r.json()


def test_add_user_refused_without_smtp(admin_client, no_smtp):
    r = admin_client.post("/users", json={...})
    assert r.status_code == 503 and "Email is not set up" in r.json()["detail"]
    # and no user row was created


def test_generated_password_never_in_reply_or_log(
    admin_client, sent, caplog
): ...  # the plain password taken from the captured mail is absent from r.text and caplog.text


def test_analyst_cannot_add_or_send(analyst_client): ...  # 403


def test_send_first_password_on_microsoft_account_refused(admin_client, ms_user): ...  # 400
```

- [ ] **Step 2: Run to verify fail.** `uv run pytest tests/test_users_api.py -v` → FAIL.

- [ ] **Step 3: Implement.** The 503 check happens before any write. Admin routes use `AdminUser`. The send call runs `first_password.send_now` and then one commit for the audit row.

- [ ] **Step 4: Run** `uv run pytest tests/test_users_api.py tests/test_auth_first_password.py -q` → PASS; `uv run pytest -q` (full suite) → note any failures and fix only those that assume the removed password field.

- [ ] **Step 5: Commit**

```bash
git add analekh/api/routers/users.py tests/test_users_api.py
git commit -m "feat(admin): add user without a typed password; send first password action"
```

---

### Task 8: Shared password field with live rules (web)

**Files:**
- Create: `web/src/components/PasswordRules.tsx`
- Create: `web/src/components/PasswordRules.test.tsx`
- Modify: `web/src/api/client.ts` (or the existing api module; add `api.passwordRules()`, `api.firstPassword(current, next)`, `api.sendFirstPassword(id)`, `api.addUser` without password)

**Interfaces:**
- `usePasswordRules(): {rules: {id,label,pattern}[]; maxLength: number; ready: boolean}` — fetched once from `GET /auth/password-rules`; falls back to nothing shown and disables submit until loaded.
- `<NewPasswordField value onChange label? name? />` — renders the input with `maxLength={maxLength}` from the rules reply, `autoComplete="new-password"`, `type="password"`, and under it one `<li>` per rule: unticked until `new RegExp(pattern).test(value)`; `aria-live="polite"` on the list.
- Labels are plain text (React escapes). The value is never placed in HTML or storage.

- [ ] **Step 1: Write the failing tests**

```tsx
it("ticks each rule as typed", () => { /* type 'Abcdefgh12345!x' -> all 7 ticked */ });
it("never puts the value in the DOM as markup", () => { /* type '<script>' -> textContent has no script element */ });
it("maxLength comes from the rules reply", () => { /* mock reply max_length 30 -> input.maxLength === 30 */ });
it("patterns agree with the server table", () => { /* the 9 samples from the spec give the same ticks as the Python results */ });
```

- [ ] **Step 2: Run** `pnpm --filter web test -- PasswordRules` → FAIL.

- [ ] **Step 3: Implement.** Compile each pattern with `new RegExp(pattern)`; no flags. Keep the component under 120 lines.

- [ ] **Step 4: Run** the test → PASS; `pnpm lint` clean.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PasswordRules.tsx web/src/components/PasswordRules.test.tsx web/src/api
git commit -m "feat(web): shared new-password field with live rules from the server"
```

---

### Task 9: Sign-in screen: first-password step, reset screen reuse

**Files:**
- Modify: `web/src/pages/Login.tsx` (mode `first`; `confirm` uses `NewPasswordField`; login handles `must_change_password` and `first_password_expired`)
- Modify: `web/src/pages/Login.test.tsx`

**Interfaces:**
- Consumes: Task 8 component and api functions; Task 6 reply shapes.
- Produces: mode `first` in the existing card: "First password", "New password" (shared field), "Confirm new password", "Set password", "Sign out" link. On success, `setMode("signin")` with message "Password set. Sign in with your new password."
- `confirm` gets the "Confirm new password" field too. Submit uses the same mismatch check: "The two passwords do not match." (client check only; server remains authoritative.)

- [ ] **Step 1: Write the failing tests**

```tsx
it("routes a flagged sign-in to the first-password step", ...);
it("shows the server's expired message as given", ...);
it("reset step uses the shared rules field", ...);
it("refuses 31 characters with maxLength in the DOM", ...);
```

- [ ] **Step 2: Run** `pnpm --filter web test -- Login` → FAIL.

- [ ] **Step 3: Implement** the `first` mode and reuse. Do not duplicate the rules list in Login.tsx.

- [ ] **Step 4: Run** `pnpm --filter web test` and `pnpm build` → PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Login.tsx web/src/pages/Login.test.tsx
git commit -m "feat(web): first-password step in sign-in; reset screen reuses the rules field"
```

---

### Task 10: Admin Users page

**Files:**
- Modify: `web/src/pages/admin/Users.tsx` (add panel: no password box; reset becomes "Send first password"; "Waiting for first sign-in" tag from `must_change_password`; mail warning with "Send again")
- Modify: `web/src/pages/admin/Users.test.tsx`
- Modify: `web/src/api/schema.d.ts` via `pnpm api-types` (API must be running)

**Interfaces:**
- Consumes: Task 7 routes; Task 8 field not used here (no password typed).
- Add panel help text: "We email them a first password. They choose their own the first time they sign in."
- After add: if `mail_sent` false → "The welcome email was not sent." and a "Send again" button calling `send-first-password`.

- [ ] **Step 1: Write the failing tests**

```tsx
it("has no password box in Add user", ...);
it("shows the not-sent warning and Send again", ...);
it("confirm text reads 'Send <name> a new first password?'", ...);
```

- [ ] **Step 2: Run** `pnpm --filter web test -- Users` → FAIL.

- [ ] **Step 3: Implement** and run `pnpm api-types` against a running API (`uv run uvicorn analekh.api.main:app` with local DATABASE_URL), then `pnpm lint && pnpm test && pnpm build`.

- [ ] **Step 4:** all three pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/admin/ web/src/api/schema.d.ts
git commit -m "feat(web): admin adds users by email; sends first passwords"
```

---

### Task 11: Records and end-to-end check

**Files:**
- Modify: `Commit-Info.md` (new entry at top)
- Modify: `docs/design/deviations.md` (admin-typed password departure, dated 2026-10-23)
- Modify: `docs/superpowers/plans/2026-10-22-auth-stage-1.md` (Task 6 note: first password is generated)

- [ ] **Step 1: Run the whole suite**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy analekh && uv run pytest -q` and `pnpm lint && pnpm test && pnpm build`
Expected: all green.

- [ ] **Step 2: Manual end-to-end (with SMTP working).** Add an analyst; check the welcome mail arrives; sign in with the first password; choose a new password (try a 31-character one and one missing an uppercase: both refused with the rule named); sign in again with the new one; "Send first password" from the admin page and check the second mail; confirm the old first password no longer works.

- [ ] **Step 3: Commit**

```bash
git add Commit-Info.md docs/design/deviations.md docs/superpowers/plans/2026-10-22-auth-stage-1.md
git commit -m "docs: first password and password rules; deviation record"
```

---

## Self-Review notes

- Spec coverage: §2 goals → Tasks 5, 6, 7, 9, 10; §4 flows → Tasks 5–7, 9; §5 rules → Tasks 1–3; §6 API/data → Tasks 4, 6, 7; §7 web → Tasks 8–10; §8 tests → each task; §9 records → Task 11.
- Review Focus items 1–5 map to Task 3 (1), Task 2/3 and Task 6 (2), Task 5 (3, 4 via `send_now`/`issue` ending sessions), Task 2 (5).
- Type names used consistently: `check_password_rules`, `validate_new_password`, `generate_first_password`, `first_password.issue/send/send_now`, `LoginResult.must_change_password`.
