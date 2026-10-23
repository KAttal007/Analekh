# First password by email, forced change, password rules: design

Date: 2026-10-23. Extends `2026-10-22-auth-roles-locks-design.md` (stage 1, sign-in). Owner:
Kaushal. Marked *(builder's call)* where the decision was made in writing this, not by the owner.

## 1. Intent

Today an admin types a first password into the "Add user" panel and has to pass it on by hand.
Instead, Analekh makes the first password itself, emails it to the new person with their username
(their email address), and makes them choose their own password the first time they sign in. The
first password works like a one-time password. An admin's "reset password" uses the same path.

## 2. Goals

- Adding a user (analyst or admin) needs only email, name and role. No password box.
- The server generates a random first password that meets the password rules (section 5), stores
  only its argon2id hash, and emails it. The welcome email is the only place it ever appears: not
  in a reply, a log, the admin screen or a URL.
- The first password lasts 24 hours. After that an admin sends a new one.
- Signing in with the first password allows one thing only: setting a new password. Then the
  person goes back to the sign-in page and signs in with the new one.
- An admin's password reset sends a new first password the same way (same 24 hours, same forced
  change).
- The account records whether its first sign-in has been completed (the "must change password"
  flag).
- Password rules on every password a person chooses: length (as today) plus character rules.

## 3. Non-goals and anti-goals

- Not: sign-in links, invite tokens, SMS, Microsoft sign-in changes, model locks.
- Anti-goal: the admin ever seeing the generated password.
- Anti-goal: the password or any code in a URL or a log (CLAUDE.md rule 9).
- Anti-goal: an account usable for anything (data, tokens, admin pages) before the forced change.
- Anti-goal: existing accounts disturbed. The 2 accounts in the database today carry on unchanged.

## 4. Flows

**Add user.** Admin enters email, name, role, clicks "Add user". If email (SMTP) is not set up
the request is refused with 503 "Email is not set up. Contact the admin team." and no user is
made. Otherwise the server creates the user with a generated first password, sets the flag and an
expiry 24 hours ahead, writes an audit entry, and sends the welcome email *inline* (not as a
background task) so the reply can say whether it was sent. If sending failed, the user is still
created and the admin sees "The welcome email was not sent." with a "Send again" button.

**Send again / admin reset.** One server action, used by both buttons: generate a new first
password, replace the hash, set the flag, set a new 24-hour expiry, end the user's sessions, clear
any pause or block, audit it, send the email inline, report sent or not. Replaces the current
admin "Reset password" panel where the admin types a new password. Not for Microsoft accounts.

**First sign-in.** Email + first password on the normal sign-in page.
- Right password, flag set, not expired: signed in with a limited session. The web app goes
  straight to a "Choose your password" screen. Every route except the ones in section 6 answers
  403 `password_change_required`.
- Right password, flag set, expired: refused with "This first password has expired. Ask an admin
  to send a new one." Safe to say: only someone holding the right password sees it.
- Wrong password: the normal reply and the normal pause and block counting, unchanged.
- Closing the tab before choosing: the first password keeps working until it is changed or the 24
  hours run out, whichever is first (owner agreed).

**Choose your password.** Enter the first password again and the new one twice. The new password
must meet the rules and must differ from the first password. On success: new hash, flag cleared,
expiry cleared, every session of that user ended, audit entry, and the web app returns to the
sign-in page with "Password set. Sign in with your new password."

**Forgot password while the flag is set.** Still allowed. Setting a password with the emailed code
also clears the flag and the expiry *(builder's call)*.

**Microsoft accounts and sign-in off.** Adding a Microsoft account generates and sends nothing
and sets no flag. With sign-in off (`ENV=dev`) the flag is ignored *(builder's call)*.

**`analekh create-admin`.** Unchanged: it prompts for the password (a fresh install may have no
email yet) and sets no flag. The new rules apply to the password it is given.

## 5. Password rules

Applied wherever a person chooses a password: choose-your-password, forgot-password confirm,
`create-admin`. Not applied when checking a password at sign-in (old passwords keep working).

The rules, as the owner set them (2026-10-23), each shown on screen with its own line:

- At least 15 characters (`password_min_length`, unchanged); at most 30
  (`password_max_length = 30`, owner 2026-10-23; was 128). The 30 applies everywhere a password
  is typed: choosing one, and signing in.
- **One constant, reused everywhere.** `password_max_length` in `config.py` is the only number.
  The routers' `Field(max_length=...)`, the "refuse before hashing" guard in `passwords.py`, the
  `GET /auth/password-rules` reply, and every password input's `maxLength` in the web app read
  it (the web gets it from the rules reply, not a typed-in 128). It replaces `MAX_PASSWORD` (128)
  and the four hard-coded `maxLength={128}` in `Login.tsx` and `admin/Users.tsx`.
- **Existing accounts.** Owner confirmed (2026-10-23) that the current account's password is
  under 30 characters, so no account is locked out. Passwords are stored as hashes, so the
  length can't be read back; no pre-check is built.
- At least 8 letters (`password_min_letters = 8`), either case.
- At least 1 number (`password_min_digits = 1`).
- At least 1 special character (`password_min_specials = 1`): any printable ASCII character that
  is not a letter or digit *(builder's call)*.
- At least 1 uppercase letter (`password_min_upper = 1`).
- At least 1 lowercase letter (`password_min_lower = 1`).
- No spaces or other whitespace.

The published regexes, one per rule, in this order (numbers filled from settings; each must match
somewhere in the password, except the last, which must match the whole of it):

| id | label | pattern |
| --- | --- | --- |
| `length` | 15 to 30 characters | `^[\s\S]{15,30}$` |
| `letters` | At least 8 letters | `^(?:[^A-Za-z]*[A-Za-z]){8}` |
| `digits` | At least 1 number | `^(?:[^0-9]*[0-9]){1}` |
| `specials` | At least 1 special character | `^(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){1}` |
| `upper` | At least 1 uppercase letter | `^(?:[^A-Z]*[A-Z]){1}` |
| `lower` | At least 1 lowercase letter | `^(?:[^a-z]*[a-z]){1}` |
| `no_spaces` | No spaces | `^\S*$` |

The whole rule set is also published as one combined regex (`all`), built from the same settings,
for anything that wants a single check:
`^(?=(?:[^A-Za-z]*[A-Za-z]){8})(?=(?:[^0-9]*[0-9]){1})(?=(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){1})(?=(?:[^A-Z]*[A-Z]){1})(?=(?:[^a-z]*[a-z]){1})\S{15,30}$`.
The server checks with the per-rule regexes (so the error can name what is missing) and a test
asserts the combined regex agrees with them on every sample. Letters mean ASCII A-Z and a-z
*(builder's call: keeps Python and JavaScript identical without Unicode flags)*.

**SQL injection and XSS.** A password is never part of a query or a page, so neither can work;
the build keeps it that way and tests it. Symbols such as `'`, `"`, `<`, `>`, `;` stay allowed
in a chosen password: banning them would not add safety, because nothing ever interprets them.
- Stored only as an argon2id hash, so the database never holds the text the person typed. Every
  database write goes through the SQLAlchemy ORM with bound parameters; the existing
  `test_auth_code_has_no_raw_sql` (no `text(` or `execute("` under `analekh/auth/`) is extended
  to the new code and to `api/routers/auth.py` and `users.py`.
- Never echoed: no reply, error message, log line or audit entry contains the password or any
  part of it. Rule errors name the rule ("needs a number"), never the input.
- Web: the password is only ever an input's value and a JSON body field. It is never put into
  HTML, never rendered with `dangerouslySetInnerHTML`, never put in a URL or `localStorage`. The
  rule labels shown on screen are plain text rendered by React (escaped), and the patterns are
  compiled with `new RegExp` and used only for testing. The JSON reply is
  `application/json` with `X-Content-Type-Options: nosniff` (check it is set).
- Welcome email: plain text only (no HTML part), so a generated password cannot be read as markup.
  The generated password's specials leave out `<`, `>`, `'`, `"` and `&`
  *(builder's call: the set is `!#$%*+-=?@^_`)*.
- Tests: these passwords are accepted where they meet the rules, stored, and sign in exactly as
  typed, with the tables intact afterwards: `Ab1'; DROP TABLE users;--xY`,
  `Ab1" OR "1"="1"--xyzQ`, `<script>alert(1)</script>Aa1`, `Ab1<img src=x onerror=a>q`
  (the builder adjusts each to meet the length and letter rules); and the reply bodies and
  captured logs for those requests never contain them.
- Regex safety: every published pattern is linear (no nested repeats that can backtrack
  exponentially), and inputs over 30 characters are refused before any regex runs.
- Length: a 31-character password is refused at sign-in, at choose-password and at reset, with
  the same message; a 30-character one is accepted. An existing account with a longer password is
  refused at sign-in with "Password is longer than 30 characters. Ask an admin to send a new
  first password." (no hint of the stored value).

**One source of the rules.** The server owns them (`passwords.py`, numbers from `config.py`). It
publishes them at `GET /auth/password-rules` (no sign-in needed, because the forgot-password
screen is used signed out; added to rule 9's allowed list), as a list of
`{id, label, pattern}` where `pattern` is the regex for that rule, for example
`{id: "digits", label: "At least 1 number", pattern: "^(?:[^0-9]*[0-9]){1}"}`. The web app fetches the
list once and runs those same regexes as the person types, ticking each line live. It never
sends the password to the server while typing *(builder's call: a request per keystroke would put
the password on the wire dozens of times and hit the per-address limit; the server runs the same
regexes on submit, which is the check that counts)*. The regexes must work identically in Python
`re` and JavaScript (no lookbehind, no named groups, no flags); a test runs every published
pattern through both on the same sample passwords.

The error on submit lists everything still missing in one message, for example "Password needs at
least 8 letters and a special character." Checked before any hashing or attempt is spent, like
today's length check.

**Generated first password** *(builder's call)*: length `first_password_length` (default 20),
drawn with `secrets` from letters, digits and the specials `!#$%*+-=?@^_`, with ambiguous
characters left out (`0 O o 1 l I`), at least 8 letters (2 or more of each case), 2 digits and 2
specials guaranteed, and
the order shuffled with `secrets.SystemRandom`. It always passes the rules above (tested).

## 6. API and data

**Table `users`** (migration 0010): `must_change_password BOOLEAN NOT NULL DEFAULT false`,
`first_password_expires_at TIMESTAMPTZ NULL`. Existing rows get false and null.

**Settings** (`config.py`, rule 9: no literals in code or tests): `password_max_length = 30`
(replaces the code constant `MAX_PASSWORD = 128`), `first_password_hours = 24`,
`first_password_length = 20`, `password_min_letters = 8`, `password_min_digits = 1`,
`password_min_specials = 1`, `password_min_upper = 1`, `password_min_lower = 1`,
`password_max_length = 30`. A startup check refuses settings that cannot be met (for example
minimum letters + digits + specials above the maximum length, or `first_password_length` outside
the min and max).

**Routes**
- `POST /users`: body drops `password`. Reply adds `mail_sent: bool`.
- `POST /users/{id}/send-first-password` (admin): replaces `POST /users/{id}/reset-password`.
  Reply `{mail_sent: bool}`.
- Changed after the live test (2026-10-23, owner's call): the mail server took 2 to 3 seconds
  inside the request, so both routes now reply at once (201 / 202, the `UserOut` row) and send
  the email in a background task. `User.first_password_mail` (migration 0011) holds `sending`,
  `sent` or `failed`; the Users page asks again while a row is `sending` and shows "Email not
  sent" with the same button to send again. `mail_sent` is gone from both replies; the outcome
  is audited as `user.first_password_mail` `{target, sent}`.
- `POST /auth/login`: reply (`MeOut`) adds `must_change_password: bool`. Expired first password:
  401 with the message in section 4.
- `GET /auth/me`: adds `must_change_password`.
- `POST /auth/first-password` (signed in, flag set): body `{current_password, new_password}`. 204
  on success; 400 with the rule message; 401 if `current_password` is wrong (counts as a failed
  sign-in).
- `GET /auth/password-rules` (no sign-in): the rule list in section 5. Holds no secrets.
- Allowed while the flag is set: `/auth/password-rules`, `/auth/me`, `/auth/logout`, `/auth/first-password`. Everything
  else, including bearer-token routes and the token-making route, answers 403
  `password_change_required`. Enforced in `get_current` (`api/deps.py`) so no router can forget it.

**Welcome email** (plain text, no links with anything secret in them): names Analekh, gives the
username (the email), the first password, that it works once and lasts 24 hours, and that they
will be asked to choose their own password. A bare sign-in address is included only if a
`web_app_url` setting is set; empty means no address *(builder's call)*. Subject: "Your Analekh
account". The reset version says "Your Analekh password was reset" and is otherwise the same.

**Audit entries**: user created (with mail sent or not), first password sent (who, mail sent or
not), first password changed by the user.

## 7. Web app

- Admin, Users page: the "Add user" panel loses "First password" and its help text becomes "We
  email them a first password. They choose their own the first time they sign in." After adding,
  show success or the not-sent warning with "Send again". The row's "Reset password" opens a
  confirm: "Send Kaushal a new first password? Their current password stops working." Unsent and
  not-yet-changed accounts show a "Waiting for first sign-in" tag (from the flag).
- Sign-in: when the reply has `must_change_password`, go to "Choose your password". Show the
  expired message from the server as it comes.
- Reuse the existing reset screen. `web/src/pages/Login.tsx` already has the forgot-password
  steps in the sign-in card (`mode` = `signin` / `request` / `confirm`; `confirm` has the code and
  "New password" fields). Add a fourth mode, `first`, in the same card: first password, new
  password, confirm new password, "Set password", and a "Sign out" link. Pull the new-password
  field into one shared component with the live rules checklist under it, used by both `confirm`
  and `first`, so the two screens can never show different rules. Adding a "Confirm new password"
  field to `confirm` too *(builder's call)*. On success, back to `signin` with the message. Motion
  rule as elsewhere: the screen appears at once.
- The checklist: one line per rule from `GET /auth/password-rules`, unticked until met, ticked as
  the person types; "Set password" stays enabled and the server's message is shown if they submit
  early (keeps keyboard and screen-reader use simple) *(builder's call)*.
- There is no change-password form on the Settings page today, so nothing else to update.

## 8. Tests the build must include

- Generator: 1,000 generated passwords all pass the rules, have the configured length, contain no
  ambiguous characters.
- Rules: each missing rule named; 7 letters refused and 8 accepted; whitespace refused; length
  limits unchanged; no hashing when refused; every pattern from `GET /auth/password-rules` gives
  the same answer in Python and in the web test runner on the same samples.
- Web: the checklist ticks each line as typed; `confirm` and `first` show the same component.
- Add user: no password in the body; flag and expiry set; the reply and the logs never contain the
  generated password (capture the mail); 503 with SMTP off and no user created; mail failure
  gives `mail_sent: false` and the user exists.
- Login: flagged account gets a limited session; every other route (iterate `app.routes`) gives
  403 `password_change_required`; expired gives the expiry message; wrong password counts as
  before.
- First-password change: wrong current is 401 and counts; same as first is 400; success clears
  the flag, ends all sessions, and the first password no longer signs in.
- Send first password: ends sessions, clears block, new 24 hours, old first password dead;
  analysts get 403; Microsoft accounts refused.
- Forgot-password confirm clears the flag.
- Existing unflagged accounts sign in as before.

## 9. Records

`Commit-Info.md` entry. If the main design document (design doc section 5 or 20) describes the
old admin-typed password, add a line to `docs/design/deviations.md`. Update the stage 1 plan's
Task 6 note that the first password is now generated.

## 10. Left to the builder

Exact wording of messages beyond those quoted; the web screen's layout within the existing
sign-in styles; whether the rule checker lives in `passwords.py` (expected) or a new module.
