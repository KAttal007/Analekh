# LibreOffice in Its Own Container Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move headless LibreOffice out of the application image (API, worker, beat) into a small
recalculation service on an internal network, with fallbacks that never save a model version
whose cached values were not recalculated.

**Architecture:** `recalc_file(bytes) -> bytes` in `analekh/workbook/recalc.py` stays the only
entry point. When `RECALC_URL` is set it POSTs the workbook to the `recalc` service. The service
is a standard-library HTTP server in its own image (LibreOffice and Python, no app code, no pip
packages), and it answers only on a Docker network with no outside access. When the service fails,
the client retries once. It then either falls back to a local LibreOffice (dev or CI) or raises
`RecalcUnavailable`, which the apply route turns into a clean 503 that points the analyst to the
Excel bridge.

**Tech Stack:** Python 3.12 (`http.server`, `subprocess`), httpx (already a dependency),
FastAPI, pydantic-settings, Docker Compose, GitLab CI container scanning, React + Vitest.

**Spec:** No separate spec. This plan follows the owner's 2026-10-24 request (security scan
sweep, then "LibreOffice in its own container, with fallback options"). The design doc sections
are 15.1 step 5, 16.5 and 22.1.

## Global Constraints

- Rule 2: the original workbook is never overwritten. A failed recalculation saves **no** new `model_versions` row.
- Rule 9: limits and timings come from `config.py` settings. The service can't import `analekh`, so it reads the same values from env vars that compose fills from `.env`. Record this in `deviations.md`.
- Rule 9: the service token travels only in a header (`X-Recalc-Token`), never in a URL, and is never logged.
- The `recalc` service publishes no host port, and its only network is `internal: true` (no internet, no Postgres, no MinIO).
- The service runs as a non-root user (uid 10001) with no setuid binaries, `read_only: true` root file system, `tmpfs: /tmp`, `cap_drop: [ALL]` and `no-new-privileges`.
- When `RECALC_URL` is empty, behaviour stays exactly as today (local `soffice` if installed, otherwise the bytes come back unchanged). Dev machines and existing tests don't change.
- The xlwings bridge path is untouched.

## Review Focus

1. The service is down or restarting while an analyst clicks Apply. Expected: one retry, then a 503 with a readable message; the lock is released, no version is saved, and the change set stays `approved` so Apply can be clicked again.
2. Two analysts apply at the same moment. Expected: each conversion gets its own LibreOffice profile directory (shared profiles clash); a request beyond `RECALC_CONCURRENCY` waits, then gets 503 "busy" rather than hanging.
3. The service returns 200 with a body that is not an xlsx (empty, HTML error page). Expected: the client treats it as unavailable and never stores it as a model version.
4. A wrong or missing token, for example after a rotated `.env` on one side only. Expected: 401 from the service, no retry, a 503 to the analyst, and an error in the server log that does not contain the token.
5. LibreOffice hangs on one workbook. Expected: the service kills it at `RECALC_TIMEOUT_SECONDS`, frees the slot and returns 504; the client does not retry a 504 (the same file would hang again).

Each line has its test in Task 1 (2, 5), Task 2 (1, 3, 4) or Task 3 (1).

## Fallbacks (decided)

| Order | When | What happens |
|---|---|---|
| 1. Retry | Connection refused, connection reset, read timeout or 503 busy | One retry after `RECALC_RETRY_DELAY_SECONDS` (2 s). Covers a service restart. |
| 2. Local LibreOffice | `RECALC_FALLBACK=local` and `soffice` on PATH | Converts locally, as today. For dev machines and CI. The production image has no LibreOffice, so this mode is off there. |
| 3. Refuse cleanly (production default) | `RECALC_FALLBACK=fail`, or local not available | 503 `recalc_unavailable`. Nothing is saved, the lock is released, and the change set stays approved for a later retry. |
| 4. Excel bridge | The analyst can't wait | Apply from Excel with the bridge (native recalculation). This exists already; the 503 message names it. |
| 5. Deployment rollback | The service is broken after a release | Redeploy the previous `IMAGE_TAG` (the last image with LibreOffice) and leave `RECALC_URL` unset: old behaviour, no code change. |

**Rejected:** saving the version without recalculating. Stale cached values would feed Checks,
`ModelReader` and the report tools, which breaks the grounded-numbers rule in spirit.

---

## File Structure

| File | Responsibility |
|---|---|
| Create `deploy/recalc/server.py` | The service: token check, size cap, xlsx check, one LibreOffice run per request in its own profile, concurrency slots, `/healthz`. Standard library only. |
| Create `deploy/recalc/Dockerfile` | `python:3.12-slim` + `apt-get upgrade` + `libreoffice-calc-nogui`, non-root, setuid strip, `CMD python /srv/server.py`. |
| Modify `analekh/workbook/recalc.py` | `recalc_file` dispatch (service, retry, fallback, local) and `RecalcUnavailable`; the local timeout comes from settings. |
| Modify `analekh/config.py` | `recalc_*` settings. |
| Modify `analekh/api/routers/change_sets.py` | Turn `RecalcUnavailable` into a 503 `recalc_unavailable`. |
| Modify `web/src/pages/ChangeSetReview.tsx` | Show the server's message for `recalc_unavailable`, as it does for `change_set_stale`. |
| Modify `Dockerfile` | Remove LibreOffice (and `libxml2`, `libxslt1.1` if lxml imports without them). |
| Modify `docker-compose.yml`, `deploy/compose.staging.yml`, `deploy/compose.production.yml`, `.env.example` | The `recalc` service, the internal network, env vars. |
| Modify `.gitlab-ci.yml` | Build, push and scan the second image. |
| Test `tests/test_recalc_service.py`, `tests/test_recalc_client.py`, `tests/test_locks_api.py`, `web/src/pages/ChangeSetReview.test.tsx` | |
| Modify `docs/design/deviations.md`, `Commit-Info.md`, `CLAUDE.md` (Commands) | |

---

### Task 0: Baseline timing and deviation entry (30 min)

**Files:** Modify `docs/design/deviations.md` (Since v0.0.5 table)

- [ ] **Step 1: Time one real recalculation in today's image.** Run `docker compose build api && docker compose run --rm api python -c "import time,pathlib;from analekh.workbook.recalc import recalc_file;b=pathlib.Path('/app/import/<a model>.xlsx').read_bytes();t=time.perf_counter();recalc_file(b);print(time.perf_counter()-t)"`. Run it 3 times and write down the median, so Task 6 has something to compare against.
- [ ] **Step 2: Add a 🔲 row:** "Headless LibreOffice runs inside the application image (16.5, 22.1)" → "LibreOffice in its own `recalc` container on an internal network; the API calls it over HTTP; fallbacks: retry, local, refuse with 503, Excel bridge. The service reads its limits from env, not `config.py`." Why: container scanning, 2026-10-24; about 400 Debian CVEs come in with LibreOffice.

### Task 1: The recalc service (3 h)

**Files:**
- Create: `deploy/recalc/server.py`, `deploy/recalc/Dockerfile`
- Test: `tests/test_recalc_service.py` (loads `server.py` with `importlib.util.spec_from_file_location`, starts it on port 0 in a thread, swaps in a fake `convert`)

**Interfaces:**
- Produces: `POST /recalc` with an xlsx body and the `X-Recalc-Token` header. It returns 200 with the xlsx, or 401, 413, 415, 503 (`busy`), 504 (`timeout`) or 500 (`convert_failed`), each with a JSON `{"code": ...}` body. `GET /healthz` returns 200 `ok` with no token.
- Env: `RECALC_TOKEN` (required: the service exits at start when it is empty), `RECALC_MAX_BYTES` (default `104857600`), `RECALC_TIMEOUT_SECONDS` (`180`), `RECALC_CONCURRENCY` (`2`), `RECALC_PORT` (`8080`).
- Python: `convert(src: bytes, timeout: float) -> bytes` and `make_handler(token: str, max_bytes: int, timeout: float, slots: threading.BoundedSemaphore, convert: Callable[[bytes, float], bytes]) -> type[BaseHTTPRequestHandler]`, `main() -> None`.

- [ ] **Step 1: Write the failing tests**
  - `test_missing_or_wrong_token_is_401`: no header and a wrong header both give 401, and the fake `convert` is never called.
  - `test_body_over_limit_is_413`: `Content-Length` = max + 1 gives 413 before the body is read.
  - `test_non_xlsx_is_415`: a body not starting with `b"PK\x03\x04"` gives 415.
  - `test_success_returns_converted_bytes`: the fake returns `b"PK\x03\x04done"`; the reply is 200 with that body and content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
  - `test_convert_timeout_is_504_and_frees_slot`: the fake raises `subprocess.TimeoutExpired`; the reply is 504, and the next request still gets a slot.
  - `test_busy_is_503`: concurrency 1, the fake blocks on an Event, the second request gets 503 `busy` after the slot wait (`timeout` seconds; the test passes a small value).
  - `test_convert_failure_is_500_without_detail`: the fake raises `CalledProcessError` with stderr `"secret path"`; the reply body does not contain it.
  - `test_healthz_needs_no_token`.
  - `test_convert_uses_own_profile_per_call`: patch `subprocess.run`; two calls pass two different `-env:UserInstallation=file:///...` arguments, both under the call's temp dir.
- [ ] **Step 2: Run `uv run pytest tests/test_recalc_service.py -q`.** Expected: FAIL (the module is missing).
- [ ] **Step 3: Implement `server.py`.** Use `ThreadingHTTPServer`. Compare tokens with `hmac.compare_digest`. `convert` runs `soffice --headless --norestore -env:UserInstallation=file://<tmp>/profile --convert-to xlsx --outdir <tmp>/out <tmp>/in.xlsx` with `HOME=<tmp>` and `timeout`. Log one line per request (status, bytes, milliseconds), never the token. Acquire a slot with `slots.acquire(timeout=timeout)`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Write `deploy/recalc/Dockerfile`.** Use the same apt pattern as the main Dockerfile (HTTPS mirror, retries, `upgrade -y`, `--no-install-recommends libreoffice-calc-nogui`), then `useradd --uid 10001 recalc`, strip setuid bits, `COPY server.py /srv/`, `USER recalc`, `EXPOSE 8080`, and a `HEALTHCHECK` that runs `python -c` with urllib on `/healthz`.
- [ ] **Step 6: Check it.** Run `docker build -t analekh-recalc:dev deploy/recalc`, then `docker run --rm -e RECALC_TOKEN=t -p 8080:8080 analekh-recalc:dev`. A `curl -H "X-Recalc-Token: t" --data-binary @tests/fixtures/<synthetic>.xlsx localhost:8080/recalc -o out.xlsx` returns 200, and `out.xlsx` opens with openpyxl.
- [ ] **Step 7: Run ruff, then commit** (the owner runs it, signed): `git add deploy/recalc tests/test_recalc_service.py && git commit -S -m "Recalc service: LibreOffice in its own image"`

### Task 2: Client, settings and fallbacks (2 h)

**Files:** Modify `analekh/workbook/recalc.py` and `analekh/config.py`. Test: `tests/test_recalc_client.py`.

**Interfaces:**
- Settings: `recalc_url: str = ""`, `recalc_token: str = ""`, `recalc_timeout_seconds: float = 180.0`, `recalc_retries: int = 1`, `recalc_retry_delay_seconds: float = 2.0`, `recalc_fallback: Literal["fail", "local"] = "fail"`.
- Produces: `class RecalcUnavailable(Exception)`; `recalc_file(workbook: bytes) -> bytes` (same signature as now); private `_remote(workbook: bytes, s: Settings) -> bytes` and `_local(workbook: bytes, timeout: float) -> bytes | None` (`None` when `soffice` is not installed).
- The client timeout is `recalc_timeout_seconds + 15`, so the service's 504 arrives before the client gives up.

- [ ] **Step 1: Write the failing tests.** Inject replies with `httpx.MockTransport` through a module-level `_transport: httpx.BaseTransport | None = None` that tests set. Never sleep for real: patch `time.sleep`.
  - `test_no_url_uses_local_and_passes_through_without_soffice`: with `shutil.which` returning `None`, the bytes come back unchanged.
  - `test_service_success_returns_body`.
  - `test_token_sent_in_header_not_url`: the request URL has no query string, and the header equals the setting.
  - `test_connect_error_then_success_retries_once`.
  - `test_busy_503_retried_then_fail_raises`.
  - `test_504_not_retried`: one request only, then `RecalcUnavailable`.
  - `test_401_not_retried_and_token_not_in_message`.
  - `test_non_xlsx_200_raises`.
  - `test_fallback_local_used_when_service_down`: `_local` is patched to return `b"PK\x03\x04L"`.
  - `test_fallback_local_without_soffice_raises`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Retry only on `httpx.TransportError`, `httpx.TimeoutException` and 503. Log the reason at WARNING without the token. The local path takes its timeout from `recalc_timeout_seconds`, which replaces the literal `180`.
- [ ] **Step 4: Run `uv run pytest tests/test_recalc_client.py tests/test_locks_api.py -q`, then `uv run mypy analekh`.** Expected: PASS.
- [ ] **Step 5: Add the `RECALC_*` lines to `.env.example`** (empty URL and token, with a comment), **then commit.**

### Task 3: Apply route and web message (1.5 h)

**Files:** Modify `analekh/api/routers/change_sets.py`, `web/src/pages/ChangeSetReview.tsx`. Test: `tests/test_locks_api.py`, `web/src/pages/ChangeSetReview.test.tsx`.

**Interfaces:**
- Consumes `RecalcUnavailable` (Task 2).
- Produces a 503 with detail `{"code": "recalc_unavailable", "message": "Recalculation is unavailable right now. Try Apply again in a few minutes, or apply from Excel with the Analekh bridge."}`.

- [ ] **Step 1: Write the failing tests.** `test_apply_recalc_unavailable_is_503_and_saves_nothing`: monkeypatch `cs_router.recalc_file` to raise. Check the reply is 503 with the code above, there is no new `ModelVersion`, the change set status is still `approved`, there is no `model_locks` row for the model, and `store.put` was never called. Web: `shows the recalc_unavailable message`, mirroring the stale test at `ChangeSetReview.test.tsx:157`, which also asserts that the raw code is not shown.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Wrap `recalc_file(written)` in `_apply`, and raise `HTTPException(503, {...})` from `RecalcUnavailable`. In the web page, generalise the stale-message helper to a set of known codes: `{"change_set_stale", "recalc_unavailable"}`.
- [ ] **Step 4: Run `uv run pytest -q` and `pnpm lint && pnpm test`.** Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 4: Slim the app image and wire up compose (2 h)

**Files:** Modify `Dockerfile`, `docker-compose.yml`, `deploy/compose.staging.yml`, `deploy/compose.production.yml`.

- [ ] **Step 1: Slim the Dockerfile.** Remove `libreoffice-calc-nogui` from the apt line. Try removing `libxml2 libxslt1.1` too, and add a build check `RUN python -c "import lxml.etree, lxml.objectify"`; keep the two packages only if that check fails. Update the header comment ("runtime: Python only; LibreOffice lives in deploy/recalc").
- [ ] **Step 2: Add the compose service.** In `docker-compose.yml`, add `recalc` (build `deploy/recalc`, image `analekh-recalc:dev`, `networks: [recalc]`, `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, env `RECALC_TOKEN`, `RECALC_TIMEOUT_SECONDS`, `RECALC_CONCURRENCY`, and `RECALC_MAX_BYTES: ${MAX_UPLOAD_CEILING_BYTES:-104857600}`). Add `networks: { default: {}, recalc: { internal: true } }`. Put `api` and `worker` on `[default, recalc]` and add `RECALC_URL: http://recalc:8080` to the `x-container-network` anchor. Make `api` depend on `recalc: { condition: service_started }`, not healthy: the API must start even when recalc is down.
- [ ] **Step 3: Do the same in the staging and production compose files,** with image `${CI_REGISTRY_IMAGE}/recalc:${IMAGE_TAG}`, `restart: unless-stopped` and `env_file` pointing to the environment's file.
- [ ] **Step 4: Verify.** Run `docker compose build && docker compose up -d`. Then:
  - (a) `docker compose exec api sh -c "command -v soffice || echo none"` prints `none`.
  - (b) Applying an approved change set in the web app saves a new version, and the version opens with fresh values.
  - (c) `docker compose exec recalc python -c "import urllib.request;urllib.request.urlopen('https://deb.debian.org',timeout=5)"` fails (no internet).
  - (d) After `docker compose stop recalc`, Apply shows the 503 message and the lock frees.
  - (e) `docker image ls` shows the app image size before and after; note both.
- [ ] **Step 5: Commit.**

### Task 5: CI build and scan of both images (1 h, plus one pipeline run)

**Files:** Modify `.gitlab-ci.yml`.

- [ ] **Step 1: Build both images in `build_image`.** Add `docker build -t "$CI_REGISTRY_IMAGE/recalc:$CI_COMMIT_SHA" deploy/recalc` and its push, plus the tag push for releases.
- [ ] **Step 2: Scan the second image.** Add a `container_scanning_recalc:` job with `extends: container_scanning`, `needs: [build_image]` and `variables: { CS_IMAGE: $CI_REGISTRY_IMAGE/recalc:$CI_COMMIT_SHA }`.
- [ ] **Step 3: Push a branch.** Check that the pipeline is green and that the app image's container-scanning report has dropped the LibreOffice-related CVEs (libxml2, poppler, tiff, openjpeg, harfbuzz, krb5 and curl from LibreOffice's dependencies). The new job carries them.
- [ ] **Step 4: Commit.**

### Task 6: Measure, document and roll out (1 h, plus a staging soak)

- [ ] **Step 1: Re-run the Task 0 timing through the service** (the same model, 3 runs, the median). Expected: within about 0.2 s of the baseline. Record both figures in the deviation row.
- [ ] **Step 2: Update the docs.** Mark the deviation row ✅ with both figures. Add a `Commit-Info.md` entry. In `CLAUDE.md` Commands, add `docker compose up -d recalc` (headless recalculation for Apply). Run `graphify update .`.
- [ ] **Step 3: Run the full check:** `uv run ruff check . && uv run ruff format . && uv run mypy analekh && uv run pytest -q && pnpm lint && pnpm test && pnpm build`.
- [ ] **Step 4: Roll out to staging.** Set `RECALC_URL`, `RECALC_TOKEN` (a new random value, at least 32 bytes) and `RECALC_FALLBACK=fail` in `/etc/analekh/staging.env`. Merge so that `deploy_staging` runs, then apply one real change set on staging. Rollback: redeploy the previous `IMAGE_TAG` and remove `RECALC_URL`.
- [ ] **Step 5: Production.** Use the same env in `production.env` and the manual `deploy_production` job on a tag.

---

## Time estimate

| Task | Hands-on |
|---|---|
| 0 Baseline + deviation | 0.5 h |
| 1 Service | 3 h |
| 2 Client + fallbacks | 2 h |
| 3 Apply route + web | 1.5 h |
| 4 Image + compose | 2 h |
| 5 CI | 1 h |
| 6 Measure, docs, rollout | 1 h |
| **Total** | **about 11 h of work: 1.5 working days; 2 to 3 calendar days with pipeline runs and a staging soak** |
