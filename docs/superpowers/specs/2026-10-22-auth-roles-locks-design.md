# Sign-in, roles, upload limit and model locks: design

Status: draft for the owner's approval. Nothing here is built.
Date: 2026-10-22. Author: Claude, with Kaushal Attal.
Related: technical design section 23 (Security), CLAUDE.md rules 2 and 6, `analekh/api/deps.py`.

## 1. Intent

Analekh is used by one person today. Every request runs as one built-in user
(`get_user()` in `analekh/api/deps.py`), uploads have no size limit, and nothing stops two people
changing the same company's model. Before several analysts use it daily the app needs to know who
is asking, limit what each person can do, bound what can be uploaded, and stop two people working
on one model at once.

## 2. Goals

- Every request is made by a known, signed-in user. No sign-in, no data.
- Two roles: **admin** (Head of Research and the people they pick) and **analyst**.
- Only admins upload, activate or retire templates, manage users, change the upload limit and
  release stuck locks.
- One upload-size rule for every upload in the app, set by an admin in the app, with no release
  needed to change it.
- A model in use by one analyst is read-only for everyone else, with the holder named.
- Username and password sign-in now; Microsoft sign-in later without redoing anything else.
- Several analysts can use the app at the same time without interfering.

## 3. Non-goals and anti-goals

- No automatic release of a lock on a timer. A long report or deck can run well past any
  timeout, and a lock that disappears mid-job is worse than a lock that stays.
- No credentials, session tokens or any secret in a URL, ever (section 5).
- No SQL built from user input anywhere in the sign-in path (section 5).
- No rating or target-price features, no changes to how filings are read or validated.
- Not a full permissions system: two roles only. Per-company access control is out of scope.
- Does not change how the Excel bridge talks to Excel; only how it proves who it is.
- Deleting or re-checking already-stored files when the upload limit changes is out of scope.

## 4. Roles

| Capability | Analyst | Admin |
|---|---|---|
| Results desk, watchlist, comps, company pages | yes | yes |
| Build, update and report on a model (takes the lock) | yes | yes |
| Upload, activate, retire templates | no | yes |
| Add, disable users; reset passwords; set roles | no | yes |
| Change the upload limit | no | yes |
| Release another person's lock | no | yes |
| View another analyst's model, read-only | only while it is locked by someone else | yes, always (view only) |
| See who holds a lock | yes | yes |
| Edit another analyst's model | no | no (admins view and can release locks; they do not edit) |

Disabling a user ends their sessions at once and releases their locks only through an admin.

**Admin area (owner, 2026-10-22).** Admin screens live on their own routes, `/admin/users`,
`/admin/templates` and `/admin/settings`, in their own shell whose navigation shows only Users,
Templates and Settings, plus "Back to Analekh". The research screens (desk, watchlist, models,
reports, comps) are not in it. Admins reach it from an "Admin" link in the main app; analysts
never see the link, and the server refuses `/admin` data to them (403) whatever the page shows.
My calls: template management (upload, activate, retire) moves to `/admin/templates` and leaves
the main navigation; analysts still pick a template when they build a model. Firm-wide settings
(upload limit, alert channels, data status) move to `/admin/settings`; personal settings (theme,
Excel bridge token, sign-out) stay in the main app's Settings for everyone.

## 5. Security requirements (hard rules)

**Nothing sensitive in the URL.**
- Login is `POST /api/auth/login` with a JSON body. Email, password, session tokens, reset
  tokens and lock identifiers that grant anything are never in a path or query string, so they
  never reach browser history, proxy logs, access logs or the `Referer` header.
- The web app keeps its session in a cookie: `HttpOnly`, `Secure`, `SameSite=Strict`, no
  JavaScript access. The Excel bridge and add-in send a token in the `Authorization` header.
- The post-login return address is a relative path only (for example `/companies/TCS`), checked
  against an allow-list of the app's own routes. Anything else goes to `/`. No open redirects.
- The server never logs request bodies or the `Authorization` and `Cookie` headers.
- The sign-in page sets `Cache-Control: no-store` and `Referrer-Policy: no-referrer`.

**No SQL injection.**
- Every database access in the sign-in path uses SQLAlchemy with bound parameters. No string
  concatenation, f-strings or `text()` with interpolated values. A test searches the auth code
  for raw SQL and fails the build if it finds any.
- Inputs are validated before they reach the database: email is a valid address of bounded
  length, password has a maximum length (so very long inputs cannot be used to slow the server),
  and the role is one of the two allowed values.
- Tests send injection strings (`' OR 1=1 --`, stacked statements, comment tricks) as email and
  password and check they are rejected as ordinary wrong credentials, with no database error and
  no change in response time or wording.

**Passwords and sessions.**
- Passwords are hashed with argon2id, never stored or logged in clear. Compare in constant time.
- The error is always "Email or password is incorrect". It never says which was wrong, and an
  unknown email takes the same time as a wrong password.
- Failed sign-ins are counted per account (and per address), reset by a successful sign-in, and
  logged for admins:
  - **3 failures:** sign-in for that account is paused for **5 minutes**.
  - **5 failures:** the account is blocked from password sign-in until the password is reset (by
    the emailed code below) or, for a Microsoft account, until the admin team clears it. The
    card then shows "Reset your password" (password accounts) or "Contact the admin team"
    (Microsoft accounts). A
    stranger who types 5 wrong passwords cannot get in, and cannot clear the block either,
    because clearing needs the user's email code or an admin. The cost is that the real user has
    to reset; that is the intended trade.
- **Password reset without a link.** Reset links normally carry a secret in the URL, which this
  design forbids. Instead the user asks for a reset on the sign-in page, receives a 6-digit
  one-time code by email (the existing email alert channel), and types it into the page. The
  code is single-use, expires in 10 minutes, is stored hashed, and has its own attempt limit.
  The reply to "request a reset" is the same whether or not the email is known. If email
  delivery is not configured, the page says to contact the admin team and an admin resets the
  password instead. Resetting ends all of that user's other sessions.
- Session tokens are random, long, stored only as a hash on the server, expire after **9 hours
  of inactivity** and are revoked on sign-out and on password change.
- Bridge and add-in tokens are created by the user, shown once, stored hashed, individually
  revocable, and tied to that user's role.
- State-changing requests are protected against cross-site requests (`SameSite=Strict` plus an
  anti-forgery header the web app sends).
- The first admin is created from the command line (`analekh create-admin`), never through a
  default password.
- HTTPS is required outside local development.
- **Development switch.** `AUTH_ENABLED=false` (default on) turns sign-in off so the owner can work
  without signing in each time. It acts as a built-in admin with no password, is honoured only
  when `ENV=dev`, and the API refuses to start with it off in any other environment. The web app
  asks `GET /public/auth-status` and skips the sign-in screen when it is off.

## 6. The sign-in screen (chosen mockup)

Mockup file: `docs/superpowers/specs/assets/login-calendar-mockup.html` (follows the system
light or dark setting).

**Where it sits in the flow.** The Welcome page stays exactly as it is. The existing scroll,
swipe or click animation now brings up this sign-in screen (instead of opening the desk). On a
successful sign-in the same scroll animation plays again and opens the homepage (the results
desk). A visitor who already has a valid session skips the sign-in step: the Welcome animation
opens the desk directly, as today. Motion stays tied to the gesture or click, as the app's rule
requires; reduced-motion users get the screens at once.

**Layout.** Left: the "A" mark, the greeting, the tagline, a short lead, and this week's results
calendar in a frosted panel (same style as the Welcome stat cards). Right: a frosted "Sign in"
card with work email, password, a pill "Sign in" button, a "Sign in with Microsoft" button that
is disabled until the firm connects its account, and a "Forgot your password?" link that
starts the emailed-code reset (section 5). After 5 failed attempts the card shows "Reset your
password" for password accounts, or "Contact the admin team" for Microsoft accounts. Footer:
"End-of-day data from NSE filings. No ratings or target prices."

**States to build.** Empty; focused field; submitting (button disabled, "Signing in"); wrong
credentials ("Email or password is incorrect.");
paused after 3 failures ("Too many attempts. Try again in 5 minutes."); blocked after 5
("Reset your password to continue", or "Contact the admin team" for Microsoft accounts); reset code entry
(request, enter code, set new password, signed in); account disabled (same message as wrong credentials, so
accounts cannot be probed); server unreachable; session expired (return here, then back to where
the user was). On phones the calendar drops below the sign-in card.

**My call: what shows before sign-in.** The Welcome counts and the calendar are public NSE data
with no per-user flags. To show them before sign-in, two small read-only endpoints return only
counts and company names for the week, and nothing user-specific (no watchlist marks). Everything
else requires a session. Say if you would rather show neither until after sign-in.

## 7. Upload limit

- A setting `max_upload_bytes` stored in the database with who changed it and when. Default 25 MB
  until an admin sets it.
- A fixed technical ceiling in server config (default 100 MB) that the setting cannot exceed,
  because a file is read whole before it is saved.
- One check, applied by the API before reading the file, covering every upload route now and in
  future (a shared dependency, not a per-route check). Oversized: HTTP 413 with
  "This file is 31 MB; the limit is 25 MB. Ask your admin." The check uses the declared size and
  also stops reading at the limit, so a wrong declared size cannot bypass it.
- Changing it affects new uploads only. Stored files are never removed or re-checked.
- Each change is written to the audit trail.
- Shown and edited on the Settings page for admins; analysts see the current limit in the
  upload dialogs.

## 8. Model locks

**What is locked.** A company's model (or, when none exists yet, the company's model-to-be). Three
activities take the lock: quarterly update, new build, and report (Word or PowerPoint). Locks are
per model, so different companies never interfere.

**Behaviour.**
- First to start holds the lock. Anyone else opening that model sees "In use by Kaushal since
  10:42" and a read-only view: they can look, but update, build and generate are disabled.
- When the holder closes the model, or the job that held it finishes or fails, the lock is
  released and the other person's view refreshes to the new version with buttons enabled.
- **Waiting colleague is told.** A person who opened the model read-only while it was locked gets
  a toast and a soft chime when it is released: "Tata Elxsi's model is free. You can open it for
  editing." Clicking it takes the colleague to the model with the buttons enabled. Only people
  who opened it while locked are notified, not everyone. The chime can be turned off in
  Settings and is skipped under reduced-sound settings; the toast alone still appears.
- Admins can open any model view-only at any time and always see who holds a lock.
- Starting any of the three activities while the lock is held by someone else is refused by the
  server, not only hidden in the page.
- The original workbook is still never overwritten; every write is a new `model_versions` row,
  and the existing approval step still decides what is written. The lock decides who may start.

**Forgotten and crashed sessions.**
- No timer releases a lock.
- After a period of no clicks or keys (default 30 minutes) with nothing of the user's still
  running, the app shows a pop-up and plays a soft chime: "You still have Tata Elxsi's model
  open. Close it if you are done." Choices: Keep open, Close. Respects the system's reduced-sound
  and reduced-motion settings; the chime can be turned off in Settings.
- A running update, build or report never triggers the reminder.
- On sign-in, a user who still holds locks sees "You still have 1 model open" with a Close button
  (this covers a crashed browser or a closed laptop).
- An admin can release any lock, with the holder named in the audit trail. A colleague who finds
  a stuck lock sees the holder's name and the time it was taken, so they know whom to ask.

## 9. Delivery order

Each stage works on its own.
1. **Users, sign-in, roles, template permissions, upload limit.** Everything in sections 4 to 7
   except Microsoft sign-in.
2. **Model locks.** Section 8, including the idle reminder and the read-only view.
3. **Microsoft sign-in.** A second button on the same screen; matched to a user by email; once
   live, an admin can switch password sign-in off for everyone except a named break-glass admin.
   Needs the firm's Microsoft tenant to register Analekh once (client ID, secret, redirect
   address); until then the button stays disabled.

## 9a. Email and alert channel setup (part of stage 1)

Today `analekh/alerts/notify.py` sends alerts by Telegram or by email to one fixed address
(`alert_email_to`) through the SMTP server named in `SMTP_URL`. Reset codes need mail to reach
each user's own address, so stage 1 includes:
- A mail function that sends to any recipient through the same SMTP server (the existing alert
  sender stays as it is). Its first user is the reset code; it never logs the message body.
- Setting up the real SMTP account and Telegram bot for the firm, with the values kept in
  environment variables only (`SMTP_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), never in the
  repo or logs. The owner supplies the credentials; the builder does not invent or store them.
- The Settings page "test" buttons (already built) are used to prove delivery before reset
  codes are switched on. Until mail is verified, "Forgot your password?" tells the user to
  contact the admin team.
- A sender address that is not a personal mailbox, and a plain message that names the app and
  the code's 10-minute life but no links.

## 10. Other screens still to be mocked

User management (admin), the upload-limit setting, the "in use by Kaushal" read-only view, the
idle reminder with chime, and "you still have models open". Their mockups come before stage 1's
plan is final.

## 11. Constraints and facts from the codebase

- `get_user()` currently returns `get_settings().default_user_id`; every router already takes a
  `User` dependency, so the change is made in one place. Existing rows carry that single user's id.
- Template upload today reads the whole file with `workbook.file.read()` and checks only the
  `PK` header (`analekh/api/routers/templates.py`).
- Models run migrations through Alembic; new tables (users, sessions, bridge tokens, settings,
  model locks, audit entries) need a migration (`alembic check` runs in CI).
- Front ends use pnpm; types are generated from the OpenAPI schema.
- Motion rule: screens appear at once; motion only answers a click. The idle pop-up and chime
  are the only unprompted attention, by design.
- Secrets stay in environment variables, never in the repo or logs.

## 12. Left to the builder

Library choices (argon2 package, cookie and token helpers), exact table and column names, the
anti-forgery mechanism, the reminder pop-up's styling within the app's existing components, and
test layout. The builder must not weaken any rule in section 5 to make a test pass.

## 13. Open decisions for the owner

Decided by the owner on 2026-10-22:
1. The Welcome counts and the calendar show before sign-in. The Welcome page is unchanged; its
   scroll animation brings up sign-in, and a successful sign-in plays it again to open the desk.
2. Sessions expire after 9 hours of inactivity. Failed sign-ins: a 5-minute pause after 3; after
   5, a forced password reset (password accounts) or "contact the admin team" (Microsoft
   accounts). There is no separate offer after 2 failures.
3. Admins can view any model read-only at any time and see who holds each lock.

Also decided by the owner on 2026-10-22: a 5-minute pause after 3 failed attempts; after 5
failed attempts a forced password reset (or contacting the admin team for Microsoft accounts);
the idle reminder after 30 minutes; the 25 MB upload default.

Still open (my calls, change if you disagree):
- Reset by emailed 6-digit code; if mail cannot be sent, an admin resets.

Also decided by the owner on 2026-10-22: the technical ceiling is **100 MB**, and the email and
alert channel setup is part of stage 1 (section 9a).
