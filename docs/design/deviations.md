# Deviations from the Technical Design

The current design is **v0.0.5** ([technical-design.md](technical-design.md); the formatted
copy is `Analekh - Technical Design v0.0.5.docx`, the diagrams `Analekh - Architecture v0.0.5.pdf`).
Record here every place the build departs from it, with the section number, what changed, why
and when, and fold the list into the next version of the document.

Status: ✅ done · 🟡 partly done · 🔲 decided, not built · 💬 proposed, not decided

## Since v0.0.5

| Design says | Now | Why | Date |
|---|---|---|---|
| Headless LibreOffice runs inside the application image (16.5, 22.1) | 🟡 LibreOffice in its own `recalc` container (`deploy/recalc`: a standard-library HTTP server, `python:3.12-slim` + `libreoffice-calc-nogui`, uid 10001, no setuid programs, read-only root file system, `cap_drop: [ALL]`, `no-new-privileges`) on a Docker network with `internal: true` (no internet, no Postgres, no MinIO) and no published port. `recalc_file(bytes) -> bytes` stays the one entry point: with `RECALC_URL` set it POSTs the workbook (token in the `X-Recalc-Token` header only, never in a URL or log), retries once on a refused or reset connection, a read timeout or a busy 503 (not on 401 or 504), then either converts with a local LibreOffice (`RECALC_FALLBACK=local`, dev and CI) or raises `RecalcUnavailable`, which Apply turns into a 503 `recalc_unavailable`: nothing is saved, the lock is released, the change set stays approved and the message points to the Excel bridge. A 200 whose body is not an xlsx is treated as unavailable. Saving a version without recalculating was rejected: stale cached values would feed Checks, `ModelReader` and the report tools. The application image no longer holds LibreOffice (or, if `lxml` imports without them, `libxml2` and `libxslt1.1`). With `RECALC_URL` empty nothing changes (a local `soffice` if installed, else the bytes come back unchanged). The service cannot import `analekh`, so its limits come from environment variables (`RECALC_TIMEOUT_SECONDS`, `RECALC_CONCURRENCY`, `RECALC_MAX_BYTES`, default from `MAX_UPLOAD_CEILING_BYTES`) that compose fills from `.env`, not from `config.py` (rule 9). Rollback: redeploy the previous `IMAGE_TAG` (the last image with LibreOffice) and leave `RECALC_URL` unset. Built and tested; recalculation time in the old image and through the service, and the staging soak, are still to be recorded here.  `.xlsm` keeps its VBA project (macros never run). A workbook with cells LibreOffice cannot compute (a VBA function, an add-in) is refused: 422 `recalc_cannot_compute`, the cells are named, nothing is saved, and the analyst applies from Excel with the bridge.| Container scanning, 2026-10-24: about 400 Debian CVEs come in with LibreOffice and its dependencies; in its own image on an internal network they are scanned separately and cannot be reached from outside. | 2026-10-24 |
| One user, no sign-in; every request acts as `default_user_id` (19.1, 20, 23) | ✅ Sign-in for every route except `/auth/login`, the reset flow and the signed-out Welcome data (`/public/*`). Email and password (argon2id, 15 to 128 characters) in a POST body only; HttpOnly, SameSite=Strict session cookie (Secure outside `ENV=dev`) plus an `X-Analekh-CSRF` header on every change; sessions end after 9 hours idle or 24 hours in all. Wrong password and unknown email get the same reply. Three failures pause the account 15 minutes, five block it until a password reset; failures are also counted per client address. "Sign out everywhere" in Settings ends every session and revokes bridge tokens. `analekh create-admin EMAIL NAME [--adopt-local]` makes the first admin and moves pre-sign-in data to them. `AUTH_ENABLED=false` (dev only) turns it off. | Owner, 2026-10-22: Analekh will hold several analysts' models and firm data; the spec is `docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md` (stage 1). Pause raised from 5 to 15 minutes and the unknown-email hint dropped on the owner's decision of 2026-10-22. | 2026-10-22 |
| No roles (23) | ✅ Two roles, admin and analyst. Only admins manage users, upload, activate or retire templates and change the upload limit; they have their own area (`/admin`: Users, Templates, Settings). Changes are written to `audit_log`. | Owner, 2026-10-22. | 2026-10-22 |
| Uploads have no stated size limit (19.1) | ✅ One limit for every upload, set by an admin (default 25 MB, between 1 MB and a 100 MB ceiling), applied to new uploads only; a body larger than the ceiling is refused with 413 as it arrives. | One shared guard instead of per-route checks; the edge cap stops a large body before it is spooled to disk. | 2026-10-22 |
| Password reset not designed | ✅ A 6-digit code by email (stored hashed, 10 minutes, single use, 5 tries, one mail per 2 minutes); the reply is the same for known and unknown addresses and the mail is sent after it. Needs `SMTP_URL`. | No reset links in mail: a code cannot be clicked from a phishing copy. | 2026-10-22 |
| Admin types a user's first password and resets by typing a new one (2026-10-22 sign-in row above) | ✅ The server generates the first password (20 characters, argon2id hash, 24 hours), emails it with the username and sets a must-change flag; that sign-in can only choose a new password. Admin reset is the same action ("Send first password"), 503 if email is off. Chosen passwords must be 15 to 30 characters with 8 letters, a number, a special, upper and lower case and no spaces (the 30 also caps sign-in); `analekh create-admin` still prompts. Reset codes last 2 minutes, not 10. | Owner, 2026-10-23: no password passes through an admin; spec `docs/superpowers/specs/2026-10-23-first-password-design.md`. The 15 to 128 character range in the row above is replaced by 15 to 30. | 2026-10-23 |
| Anyone may build, update or report on any model at once (15, 16, 17) | ✅ Model locks: one holder per model while an update, build or report runs (`model_locks`, migration 0012); a colleague's start is refused with 423 and the screens go read-only with the holder named. The lock goes back when the work ends or fails, or when the holder closes it; others who watched it get a toast and a soft chime (Web Audio tone, no audio file). An idle reminder after `IDLE_REMINDER_MINUTES` (30) without input, never while one of the user's jobs runs, and a once-per-sign-in reminder of models still held, in the main and admin shells. Admins see every lock (`GET /admin/locks`, Admin > Model locks) and release any, audited with the holder. Departures from the spec: the web asks for lock state every `LOCK_POLL_SECONDS` (20) instead of a push channel; that figure and the idle wait reach the web in the upload-limit settings reply rather than a route of their own; the chime on/off switch is kept in the browser's preferences, since there is no per-user settings store on the server; deciding and applying a change set also hold the lock (as an update), since both write a model version; a decision on a row or item that is no longer pending is refused with 409, so a stale screen cannot overwrite the holder's choice; Update drafts only from the newest results filing and, when that one is blocked, drafts nothing and says so in a pop-up, so the analyst can update by hand; applying a change set whose base is no longer the model's latest version is refused with 409 (`change_set_stale`, never rebased), and the analyst drafts a new update. | Owner, 2026-10-22: several analysts share models; spec `docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md` section 8 (stage 2). | 2026-10-24 |
| Excel bridge calls the API unauthenticated (14) | ✅ Revocable bearer tokens made in Settings (`ANALEKH_TOKEN`), shown once and stored hashed; sent only in the `Authorization` header. | Every route now needs a signed-in user. | 2026-10-22 |
| The feed watcher polls Board Meetings, corporate actions, insider trading, related-party and announcements feeds (3.2, 9.1, 9.6) | Corporate_action.xml is no longer polled. The results calendar reads Board_Meetings and the filings table only; red flags read insider trading, related party and encumbrance. | Owner, 2026-10-22: its items are dividend and other ex-date notices whose link is NSE's corporate-actions web page, not a file. Rule 1 does not allow that page, so every item failed in the fetch queue, and nothing in Analekh read them. Items already stored stay in `feed_items`. | 2026-10-22 |
| Results desk shows net profit and EBITDA margin; lenders get no margin; the company page charts a bank's net interest income (19.1) | ✅ The desk's "EBITDA margin" column becomes "Margin": EBITDA margin for companies outside finance, net interest margin (NIM) for lenders, each value tagged EBITDA or NIM (API: `margin`, `margin_kind`, `margin_yoy`, `margin_consolidated` replace `ebitda_margin` and `ebitda_margin_yoy`). The company page's chart shows NIM instead of net interest income, plus an "Interest ratios" view: cost of borrowing with the spread stacked on it up to the yield. The history table and its Excel export gain NIM, yield, cost of borrowing and spread. `analekh/interest.py`: NIM = (interest earned - interest expense) x 4 / average interest-earning assets; yield = interest earned x 4 / the same average; cost of borrowing = interest expense x 4 / average deposits + borrowings + debt securities + subordinated liabilities (whichever are tagged, banks and NBFCs alike); spread = yield - cost. Interest expense is InterestExpended for banks and FinanceCosts for NBFCs; earning assets are advances or loans, investments and bank and call-money balances (cash, RBI balances and cash equivalents left out). Averages are of opening and closing balances; balance sheets are filed in March and September only, so June and December balances are interpolated between them by days, and a June or December quarter shows a dash until the next half-year's balance sheet is filed. NIM on consolidated figures when they allow it, else standalone; the company page has both. Every bank and NBFC (LSEG group Banking Services, the banking format, plus a few named primary dealers and NBFC-like finance companies) shows NIM; where interest is under 40% of revenue from operations (IRFC, a lessor) or the balance sheets are not both filed, it is a dash. Brokers, wealth managers and asset managers, named by symbol in `interest.FEE_FINANCE` (no field in NSE's or LSEG's data tells them apart from holding companies and exchanges, which are handled as above), show the core pre-provision profit margin instead; exchanges (IEX, MCX) keep EBITDA margin; holding and investment companies (every other company in those sectors) show operating income (revenue from operations less operating expenses, in rupees) on the company page and no margin on the desk; on the company page brokers and asset managers also get operating leverage (revenue growth less operating-expense growth on the same quarter a year earlier, in percentage points): (revenue from operations - operating expenses) / revenue from operations, with operating expenses = total expenses less finance costs and impairment on financial instruments (new `impairment` line); EBITDA stays hidden for every financial sector (owner, 2026-10-26: their costs are people, platforms and marketing; fee yield on AUM and the cost-to-income ratio need data the XBRL does not carry or are not built). A ratio beyond 100% is dropped as a tagging problem. Computed figures, not the lender's reported NIM (which uses daily averages). | Owner, 2026-10-26: lenders are judged on NIM, not EBITDA; one margin column instead of two. | 2026-10-26 |
| 💬 Before hosting | Failed-sign-in counts per address are kept in memory per API process and use the socket address. With several processes or a reverse proxy they need Redis and trusted-proxy handling (`X-Forwarded-For` only from known proxies). | Owner, 2026-10-22: defer until hosting is decided. | 2026-10-22 |

## Folded into v0.0.5 (21 October 2026)

Everything below was a departure from v0.0.4 and is now part of v0.0.5, along with V11 and the
nightly backfill's removal (10a below), the scheduler in Docker, the results calendar, the
company page's results history, the Reports screen and the owner's amendment on ratings.
Section numbers are v0.0.4's.

| Design says | Now | Why | Date |
|---|---|---|---|
| Windows scheduled tasks stand in for Celery beat (9.6, 22.1) | Redis, the worker and beat run in Docker (`docker compose up -d redis worker beat`); beat writes its schedule to `/tmp` (the container user cannot write `/app`). The feed watcher runs with it. Containers get the service names from `docker-compose.yml`; `.env` holds 127.0.0.1 for runs on the host. | One scheduler on the laptop until hosting; `localhost` on Windows tried IPv6 first and stalled after a Docker restart. | 2026-10-21 |
| Company page: a filings box linking each period to iXBRL, PDF and XBRL (19.1) | No filings box. Each results-history column heading links the newest filing of that quarter (iXBRL), opens its details (filed on, PDF, what changed, earlier filings) and shows one status mark; filings without a column fold out under the table. Raw XBRL is not linked. | Owner, 2026-10-21: the history table already lists the quarters, so two boxes doubled the reading; raw XBRL means nothing to a reader. | 2026-10-21 |
| Shared outputs carry no ratings or target prices (23; CLAUDE.md rule 8) | A report may carry the recommendation and target price from the analyst's own Excel model, or leave them for the analyst; Analekh never generates one. | Owner's amendment, 2026-10-21. | 2026-10-21 |
| Reports: flash, digest, notes, initiation drafts (17, 19.1) | Two reports, a quarterly update and an initiating coverage note, each as a Word note and an IB-style PowerPoint, set up on a Reports screen (basis: standalone by default, consolidated or both). Drafts must carry no em-dashes or other marks of generated text. Set-up built; drafting not yet. | Owner, 2026-10-21. | 2026-10-21 |
| Raw Filing Store: immutable object storage keyed by hash (6, 9.3) | Results XBRL is stored gzipped (`ingest/storage.py`: `pack` on write, `unpack` on read, S3 `Content-Encoding: gzip`); reads return the original bytes, so keys and `file_sha256` still match. PDFs and Excel files are stored as-is. Files stored before the change were rewritten once by `scripts/compress_raw_files.py`, which checks each against its key's hash before and after. | The 53,600 files took 4.5 GB; a sample compressed 12 times. Only re-parsing (`revalidate`) reads them, and unpacking adds about 0.1 ms per file. | 2026-10-18 |
| Tesseract for scanned pages (9.1, 21, Appendix G) | RapidOCR 3 (`rapidocr` + `onnxruntime`) in `docs/pdf.py`: the page is rendered at 200 dpi and read by bundled ONNX models. `pytesseract` and the apt packages `tesseract-ocr`, `tesseract-ocr-eng` are gone from the image. Settings live in `analekh/docs/rapidocr.yaml` (RapidOCR's YAML model routing; a full copy of its defaults, since it replaces rather than merges): the bundled PP-OCRv6 small models (no download at run time), ONNX threads capped at 2 per task, warnings-only logging. A missing file is an error, not a silent fallback. | Owner's call on 2026-10-23: no system binary, works the same on Windows and in Docker (Tesseract was never installed on the dev machine, so scans gave no text there). On a test scan RapidOCR read every digit with correct spacing, about 6 s a page on CPU. Not yet compared on real scanned filings. | 2026-10-23 |
| Results watcher hourly in season (9.6; rule 1) | In a season every run from 09:00 to 23:00 IST asks NSE, now hourly (`RESULTS_WATCH_CRON=0 9-23 * * *`, `RUN_HOURS` 9 to 23); the 21:00 off-season run is unchanged. About 3,000 requests a year (was about 1,650). | Owner's call on 2026-10-23: new results show sooner during the season. Well under NSE's request cap per run. | 2026-10-23 |
| Results watcher by season, proposed (9.6) | Built: `analekh/seasons.py` decides each run. In a season (day 5 after a quarter end to two days past SEBI's deadline) every run from 09:00 to 23:00 IST asks NSE; outside one only the 21:00 run does. Cron `0 9-23/2 * * *`; the Windows task runs 09:00 to 23:00 every 2 hours. `analekh results-watch --force` asks regardless. | Owner asked for it on 2026-10-18; about 60% fewer requests, and on the evidence in 3.1 nothing missed. | 2026-10-18 |
| Ind-AS exceptional items are `ExceptionalItemsBeforeTax` (10.1, 10.2, Appendix A) | Either `ExceptionalItemsBeforeTax` or `ExceptionalItems` (about 2,400 Ind-AS filings use the second). V2 also adds extraordinary items (`ExtraordinaryItems`, between exceptional items and PBT) for Ind-AS filers only; banks' extraordinary items are net of tax and stay out. | All 14 V2-blocked filings (L&T, KIMS, MT Educare, Chandan, Alletec, Fidel, Felix) were off by exactly that line. After revalidating the 517 affected companies, no filing is blocked; the company page now also shows those companies' exceptional items and derives EBITDA with them. | 2026-10-18 |

## Folded into v0.0.4 (18 October 2026)

Everything below was a departure from v0.0.3 and is now part of v0.0.4, along with the NSE sector
taxonomy, the welcome screen, prices on screen and the motion rule. Section numbers are v0.0.3's.

| Design says | Now | Why | Date |
|---|---|---|---|
| NSE access on www.nseindia.com: the home page and the integrated-filing lookup only (3.2, 23; rule 1) | Also `/api/corporates-financial-results` (NSE's corporate financial-results list), queried per company with the usual honest headers. It lists results back to 2005, with XBRL from 2018 (TCS: 26 quarters, Sep 2018 to Dec 2024; ICICI Bank: 28), ending where integrated filings start. | Approved by the owner on 2026-10-15: 28 quarters and 7 years of annuals are needed to build a model; integrated filings only go back to March 2025. | 2026-10-15 |
| Price source undecided (3.3): Stocks data type now, bhavcopy later | NSE's daily bhavcopy (nsearchives `/content/cm/`), ONE file per trading day after the close (`analekh prices`, beat `fetch-prices` 19:00-23:00 IST on weekdays, skipped once stored). Close, open, high, low and volume in `prices`, matched by ISIN; market cap = close x shares in issue (paid-up equity capital / face value from the latest results filing), plus the previous close for the day's change. Only the latest day is kept: each file replaces the previous day's prices. No live prices. | Owner's decision 2026-10-17: free, end of day only; no money for a live feed. Overwriting daily: owner's rule 2026-10-18 (storage). | 2026-10-17, 2026-10-18 |
| Daily results watcher: ONE request a day without a ticker (9.3; rule 1) | ONE request every 2 hours (`RESULTS_WATCH_CRON=0 */2 * * *`). Locally a Windows scheduled task runs `analekh results-watch` every 2 hours until the scheduler (Redis, worker, beat) is deployed. | Owner's choice on 2026-10-16, for the September-quarter results season. | 2026-10-16 |
| History back to 2018 (the financial-results list links XBRL from 2018) | History from **March 2023** only. NSE's older files (the `_WEB.xml` publications up to December 2022, and some early-2023 bank files) leave out the quarter, year-to-date and balance-sheet contexts that most values point to, so the basis and the main figures can't be placed. Such files are rejected and noted (`pipeline.IncompleteXbrl`), never half-stored; `_WEB` links in the list are not fetched. Rebuilding the missing contexts from the files' declared dates was offered and declined: it would bend rule 5 (contexts by dates, never by id). With integrated filings: about 15 quarters and 4 years of annuals (FY23-FY26). | Owner's decision, 2026-10-15 ("2023 is fine"). TCS and ICICI Bank had 69 + 4 half-read filings, removed. | 2026-10-15 |
| (not specified) | A broken XBRL file (XML cut off partway) is fetched once more, then skipped and noted like a 404, instead of losing the company's other filings. | Laurus Labs lost all 14 filings to one broken file. | 2026-10-15 |
| V2 for general insurers (10.2) | Also deducts the transfer to reserves (`TransferToReserves`) before PBT. | GIC Re, a reinsurer: every filing blocked, off by exactly that line. | 2026-10-15 |

## Folded into v0.0.3 (15 October 2026)

Everything below was a departure from v0.0.2 and is now part of v0.0.3. Section numbers are
v0.0.2's.

| Design says | Now | Why | Date |
|---|---|---|---|
| MinIO from the `minio/minio` image (Appendix D, 22.1) | `docker compose` builds MinIO from source: `deploy/minio/Dockerfile`, pinned to `RELEASE.2025-10-15T17-29-55Z` (image `analekh-minio`, about 165 MB). | MinIO no longer publishes community images; `minio/minio` can't be pulled. Same AGPL-3.0 licence note (G.9). | 2026-10-14 |
| (not specified) | Object storage fails fast: 2 s connect timeout, one attempt; the API answers 503 "object storage not reachable" instead of hanging. One store per API process instead of one per request. | Template, model, change-set and report endpoints hung for 13 s or more while MinIO was down. | 2026-10-14 |
| Results XBRL arrives through NSE's results RSS feed (3.2, 9.2) | The results feed has been frozen since 24 August 2026 (four Asian Hotels items). SEBI moved quarterly results into integrated filings; the announcements feed links their PDFs, not XBRL. `ingest/integrated.py` reads NSE's integrated-filing list per company and downloads the XBRL from nsearchives; `analekh refresh <SYMBOL>` runs it after pending feed items. | The feed no longer carries filings. | 2026-10-14 |
| NSE access limited to RSS feeds, equity lists and the files they link to (3, 23; rule 1) | `www.nseindia.com` allowed, limited by `ALLOWED_PATHS` to `/` (home page only) and `/api/integrated-filing-results`. Requests stay honest (`Analekh/0.1`, contact in `From:`, `Accept`, `Referer`); never disguised as a browser. The home page answers 403 to that User-Agent; the lookup answers without its cookies. | Approved by the owner on 2026-10-14. | 2026-10-14 |
| Descriptive User-Agent with a contact (9.3, 22.3) | The contact goes in the HTTP `From` header (`CONTACT_EMAIL`); any email or URL in `USER_AGENT` is moved there. | NSE's CDN stalls, without refusing, requests whose User-Agent holds an email address or a URL. | 2026-10-14 |
| Results in the `in-bse-fin` Ind-AS taxonomy (10.1) | Integrated filings use `in-capmkt` (`in-capmkt-ent-2026-01-31.xsd`); the Ind-AS element names are the same. Typed dimensions (breakdowns such as `OtherCurrentFinancialAssetsDomain1..3`) are now read from their child element. | Seen on Tata Elxsi's filings. | 2026-10-14 |
| V2: total income - total expenses - exceptional items = PBT (10.2) | Exceptional items are added as tagged: filings give a charge as a negative number. | Tata Elxsi Q3 FY26: -956,888,000 labour-code charge; subtracting it blocked a correct filing. | 2026-10-14 |
| Company figures are consolidated (19.1, 20) | `GET /companies/{symbol}/facts` returns consolidated figures when the company files them, else standalone; the company page charts quarter-length periods only and labels the basis. Comps (18) take TTM figures on one basis per company: consolidated when it gives four quarters, else standalone (noted); `POST /comps` can fix the basis, and the export has a Basis column. | Many companies (Tata Elxsi among them) file standalone results only. | 2026-10-14 |
| Company screen shows one set of figures (19.1) | A Consolidated / Standalone switch (`?basis=` in the URL) when the company files both; figures, chart and filings follow it. Both bases are fetched and stored for every quarter. | Many companies file both, and analysts need either. | 2026-10-14 |
| Company screen (19.1): header, figures, chart, filings | Adds a "Latest quarter" column (sticky, full window height on screens 1,280 px and wider; after the figure tiles on narrow ones) from `GET /companies/{symbol}/glance`, and a Call highlights card (empty until call notes are generated). Derived lines say how they are computed; EPS is as filed, not adjusted for bonuses or splits. | Space on wide screens; the analyst's first question is how the quarter went. | 2026-10-14 |
| Home: search and watchlist entry point (19.1) | Results desk: the quarter's reporters newest first (revenue, profit, EBITDA margin vs a year ago), movers with size and base floors, sector progress; filters in the URL. The intro stays below it for now (owner to decide). | The landing page showed none of the collected data. | 2026-10-14 |
| New results arrive through the feed watcher (9.2) | Also a daily results watcher (`watch_results`, 23:00 IST): ONE request to the integrated-filing lookup without a ticker (page of 500), then the XBRL for filings not yet stored. Logs a warning, rather than making a second request, if every row on the page is new. | The results feed is frozen; the owner set the limit at one request a day. | 2026-10-14 |
| EBITDA for every Ind-AS filer | Not shown for Banking Services (which includes NBFCs), Insurance, Investment Banking & Investment Services, Holding Companies. | Finance costs are a lender's cost of business; an NBFC's "EBITDA margin" came out near 90%. | 2026-10-14 |
| Transcripts from the filed transcript PDF (9.3) | Also from the call recording: `docs/audio.py` (Whisper large-v3 via faster-whisper, GPU when present; optional dependency group `audio`, exported to `requirements-audio.txt`). Generated notes will come from this text first and be regenerated when the official transcript is filed. | Recordings are online within 24 hours; transcripts take up to 5 working days. | 2026-10-14, 🟡 |
| Results taxonomy from the schema reference, confirmed per company (4.2, 9.1) | Detected from the elements a filing tags: banks (InterestEarned and InterestExpended, no RevenueFromOperations), insurers (premium elements, no RevenueFromOperations); NBFCs stay Ind-AS (they tag InterestEarned inside revenue). A filing's line items correct an earlier guess. | Integrated filings use one schema (`in-capmkt-ent`) for every filer. | 2026-10-14 |
| V1-V3 identities in Ind-AS terms (10.2) | Per-format terms, added when tagged: banks deduct provisions in V2; general insurers add investment income in V1 and run V2 through the shareholders' account. Insurers' V4 skips (IRDAI balance sheet not mapped). `GET /companies/{symbol}/facts?logical=revenue` resolves names for the company's format. | Bank and insurer filings had every identity skipped. | 2026-10-14 |
| V8 labels a filing late when filed more than 180 days after period end (10.2) | Tied to SEBI LODR regulation 33(3): late after 45 days for a quarter (or an SME half-year), 60 days when the filing closes the financial year (period ends 31 March, or a full-year duration ends on the period end), plus one day's grace because XBRL may follow the PDF results by up to 24 hours. Still a label, never a block. The filing date is taken in IST. | 180 days only caught stale filings, not late ones. | 2026-10-14 |
| Taxonomies indas, banking, nbfc, insurance (Appendix A) | `life_insurance` added (migration 0003): IRDAI's life format, detected from premium income or persistency elements. Net premium income is the top line; PBT is checked through the shareholders' account (V2), total income through the policyholders' account (V1). | Life insurers file a different revenue account from general insurers; read as either, every check skipped and every line came out empty (Canara HSBC Life). | 2026-10-14 |
| Restatements: new facts inserted, old ones lose is_latest (8.3, V9) | The value in use for each line is the one from the most recently FILED filing (filing time, then id), re-decided per company after every ingest (`ingest.pipeline.refresh_latest`), whatever order the files were downloaded in. NSE's Original or Revision flag is stored in `filings.meta.revision`; older rows were labelled by filing order (`analekh recompute-latest`, which switched 108 values). | 88 values in use came from an older filing than one already stored: "latest" meant last downloaded. | 2026-10-15 |
| Difference shown for a refiled period (6.4) | Company page: Restated (headline numbers changed), Revised (refiled, nothing headline changed, or the quarter added after half-year results) and Superseded tags in the filings table and the Latest quarter column, with a popup listing old to new for each changed line. `GET /companies/{symbol}/filings` and `/glance` carry the revision status. No separate restatement report (the owner saw no use for one). | 1,108 quarters at 564 companies were filed more than once. | 2026-10-15 |
| Backfill: on demand and Nifty 500 first (4.1, 9.4) | `analekh results-backfill` covers every company with a sector, both bases, at one request every 2 s. `--start-at` resumes at the company a run stopped on; companies in `out/bulk/no-filings.csv` are skipped unless `--recheck-no-filings`. A local watchdog (gitignored) resumes after each NSE stop and backs off if NSE stalls quickly. | NSE stalls after about 590 requests whatever the pace, then answers after about 10 minutes; restarting from the first company spent each batch re-checking companies with nothing to fetch. | 2026-10-15 |
| (not specified) | A link ending in `null`, `undefined` or `none` is no link (NSE writes `.../corporate/null` for a missing attachment); an XBRL file NSE lists but answers 404 or 410 for is skipped and noted, not fatal for the company. | About one PDF link in three; Adani Enterprises had 4 missing files. | 2026-10-14 |
| Company figures in crore (10.1 display transforms) | Lakhs when the company's largest quarterly revenue is under Rs 10 crore (1,000 lakh), crore otherwise; one unit per view. | Agri-Tech's Rs 4.6 lakh of revenue read "Rs 0 cr" and its chart was empty. | 2026-10-14 |
| (not specified) | A missing QoQ or YoY shows a dash with the reason: the comparison quarter was filed only inside a half-year (Canara Robeco AMC's first results after listing), or there are no results on record for it. | Analysts asked why a company with a year-ago filing had no YoY. | 2026-10-15 |
| (not specified) | Margins and ratios change in basis points; notes (how EBITDA is derived, EPS as filed) sit behind an information icon that opens on hover, tap or focus; very large changes from a tiny base are capped on the desk ("n.m.", ">+999%") with the exact figure in a tooltip. | Space in the Latest quarter column; analysts read margins in bps. | 2026-10-14 |
| Results desk paging (19.1) | Ten companies per page with Prev and Next (page in the URL); Movers and By sector keep a fixed height and scroll inside, sharing the table's height on wide screens. | The side column ran far below the window. | 2026-10-15 |
| Code version 0.1.0 (pyproject, package.json) | 0.0.3, matching the design document and the versioning rule (v0.0.x until Phase 0 is complete). | The skeleton started at 0.1.0. | 2026-10-15 |

## Folded into v0.0.2 (14 October 2026)

Everything below was a departure from v0.0.1 and is now part of v0.0.2. Section numbers are
v0.0.1's. Reviewed against the code at commit c3bedcd.

### Summary

| Area | Change | Sections | Status |
|---|---|---|---|
| Prices | Kite Connect removed; no price source yet | 3.2, 5.1, 7.2, 21, 22.2, 22.3, 25, 26, G.1, G.9 | ✅ removed, 🔲 replacement |
| Sectors | NSE Indices constituent lists and the Excel Stocks data type as sources, with a precedence order | 3.2, 4.2, 9.1, 23, 28 | 🟡 |
| Schema | `companies.sector_source`; `peer_lists` table; `feed_items.pub_date` index | 8.2, A | ✅ |
| Search | Tiered type-ahead ranking; whole universe searched in the browser | 8.3, 19.1, 20 | ✅ |
| API | Endpoints added beyond the section 20 list | 20 | ✅ |
| Source control and CI | GitLab Free, not Ultimate; OSV-Scanner replaces dependency scanning; direct commits to `main` | 0.0.1 changes, 21, 22.5, 23, F | ✅ |
| Front end tooling | pnpm workspace instead of npm; Node 24 pinned; Inter font | 21, G, G.5 | ✅ |
| Environment variables | `KITE_*` removed; nine variables added | 22.3 | ✅ |
| Repository layout | Extra top-level folders; `templates_builtin/` inside the package | E | ✅ |
| Phase 0 | Price pull dropped from the exit criteria; findings recorded | 26, 28 | 🟡 |
| Reports | Section-by-section report runner | 17 | 💬 |

### 1. Prices and market data

| Design says | Now | Why | Date |
|---|---|---|---|
| Prices and market cap from Kite Connect (3.2, 5.1 Price Fetcher, 7.2); `kiteconnect` in requirements (G.1); `KITE_*` variables (22.3); INR 2,000 a month (25); "one price pull" in Phase 0 (26) | No price source. `analekh/market/`, the `KITE_*` settings, the spike's `--price` step and the `kiteconnect` dependency are gone (11 fewer locked packages, including Twisted and autobahn). The `prices` table stays. | Kite is paid. Its pinned `autobahn` 19.11.2 carried two known vulnerabilities, and `zope-interface` (via Twisted) was one of the blockers for Python 3.15. | 2026-10-13 |
| Bhavcopy listed only as a manual alternative (3.2) | Price source undecided (v0.0.2 section 3.3): the Stocks data type in the analyst's workbook now, NSE's daily bhavcopy later. Analekh uses one static reference price at a time: the day's close after the close, the day's open during market hours. Bhavcopy is end of day only and needs CLAUDE.md rule 1 amended and NSE archives reachable. | Free routes; no live feed needed | 2026-10-14, 💬 |
| Market data licence note for Kite (G.9) | Not applicable while there's no price source. Bhavcopy redistribution terms need checking before any public release. | | 2026-10-13 |

Knock-on effects: comps (18) need market cap for EV and the multiples; the profile slide's
price chart (18) and `get_prices` (17.1) have nothing to return until a source exists.

### 2. Sector classification

| Design says | Now | Why | Date |
|---|---|---|---|
| Options: index constituent files, company disclosures, or a curated Nifty 500 map (4.2); open question "which source beyond a curated Nifty 500 list?" (28) | Three sources, in order of precedence: **user** override > **Excel Stocks** (LSEG industry group via Microsoft 365) > **NSE Indices** constituent lists. `companies.sector_source` records which one set each sector; a lower source never overwrites a higher one. | Neither the equity list nor the XBRL filings carry sector. BSE's List of Securities has no industry column, and scraping BSE security pages or Screener was ruled out. | 2026-10-13 |
| NSE access limited to RSS feeds and the files they link to (3, 23) | `niftyindices.com` added to `ALLOWED_HOSTS`, limited to `/IndexConstituent/` by a new `ALLOWED_PATHS` check. CLAUDE.md rule 1 amended to match. | Published CSVs, same footing as the equity list. | 2026-10-13 |
| — | `analekh universe sectors` fetches Nifty 500 and Microcap 250 constituents (industry) plus the bank indices. File names and columns are marked `# verify`: niftyindices.com wasn't answering when this was written, so it has not run yet. | | 🟡 |
| — | `analekh universe sectors --stocks-file` imports a workbook made with Excel's Stocks data type (`XBOM:<BSE code>` IDs, `FIELDVALUE(…,"Industry")`). 2,458 main-board companies have a sector; 728 remain (148 main board, 580 SME). Process: [../sectors-from-excel-stocks.md](../sectors-from-excel-stocks.md); helper: `scripts/stocks_workbook.py`. | Only route found that covers most of the universe for free. Needs Microsoft 365 (Office 2024 lacks the Stocks data type). | 2026-10-13, 🟡 |
| Results taxonomy set by the universe loader and confirmed from the first filing (4.2, 9.1) | Set from strong signals only: bank index membership, or "NBFC"/"insurance" in an NSE sector name. Excel Stocks sectors never set it (LSEG's "Banking Services" includes NBFCs). Otherwise the first parsed filing decides. | Avoid filing banks' and NBFCs' results under the wrong element table. | 2026-10-13 |
| User override per company (27) | Supported by the precedence rules (`source="user"`), but there's no screen to edit a sector yet. | | 🔲 |

Data rights (23): sectors from the Stocks data type come from LSEG through Microsoft 365. They
live only in the local database, never in git. Microsoft's terms for that data need checking
before any public or commercial release, as with NSE's.

### 3. Data model (section 8, Appendix A)

| Change | Why | Date |
|---|---|---|
| `companies.sector_source TEXT` with `CHECK (sector_source IN ('user','excel_stocks','nse_indices'))` (migration `0002_sector_source`) | Sector precedence, section 2 above | 2026-10-13 |
| `peer_lists (id, name UNIQUE, symbols TEXT[])` | Saved peer lists for comps (18 mentions them; Appendix A has no table) | in the initial skeleton |
| Index `ix_feed_items_pub_date` | Time-ordered feed queries | in the initial skeleton |

Everything else in Appendix A matches the ORM in `analekh/db/models.py`.

### 4. Company search

| Design says | Now | Why | Date |
|---|---|---|---|
| Autocomplete by symbol or name (F2); trigram index on name (8.3) | Tiered type-ahead, highest first: exact ticker or ISIN (100), ticker prefix (80), name prefix (60), every query word starts a word in the name (40), ticker contains (30), name contains (20); the last three need 2+ characters. Trigram similarity is only a fallback when nothing matches. Results page with `offset`. | Typing "T", "TC", "TCS" should narrow the list as you type; pure trigram ranking put unrelated names (Force Motors for "tata motors") in the results. | 2026-10-13 |
| Search runs on the server (20) | The web app downloads the whole universe once (`GET /companies/index`, about 80 KB gzipped, ETag and 304) and ranks locally with the same tiers (`web/src/lib/companySearch.ts` mirrors `universe/search.py`). The server is asked only before the index loads or for the typo fallback. Responses over 1 KB are gzipped. | The API answered in 17–55 ms; the delay was the debounce plus a round trip per keystroke. | 2026-10-13 |

### 5. API (section 20)

Added beyond the section 20 list:

| Endpoint | Purpose |
|---|---|
| `GET /companies/index` | Whole universe for in-browser search (section 4 above) |
| `GET /watchlist` | Watchlist screen |
| `GET /models`, `GET /models/{id}/builds`, `GET /models/{id}/versions/{version}` | Models screen and version downloads |
| `POST /models/link` | Link a model that isn't registered yet (section 20 has only `/models/{id}/link`) |
| `POST /models/{id}/finalize` | Coverage Builder: write the model after assumptions are decided (15.1) |
| `GET /templates`, `POST /templates/{id}/activate` | Templates screen; activation after a passing test build (14.3) |
| `GET /reports/{id}` | Fetch a generated report |

No section 20 endpoint is missing.

### 6. Source control, CI/CD and security scanning

| Design says | Now | Why | Date |
|---|---|---|---|
| GitLab Ultimate (0.0.1 changes, 21, 22.5) | GitLab Free | Plan in use | 2026-10-13 |
| Dependency scanning template (22.5, F) | Removed. A `dependency_audit` job runs OSV-Scanner v2.7.0 on `uv.lock` and `pnpm-lock.yaml`, `allow_failure: true`. 25 findings left, all in the add-in's dev tooling; fixes deferred until more code is built. | GitLab's dependency scanning needs Ultimate | 2026-10-13 |
| DAST against staging; MR approval and scan execution policies (22.5, 23) | The DAST job runs only when `STAGING_URL` is set; there's no staging yet, and DAST and security policies need Ultimate. Not in effect. | Plan and no staging | 2026-10-13 |
| — | Container scanning, SAST and secret detection still run (they work on Free). | | |
| Protected `main`, merge requests only, squash on merge (22.5) | Commits go straight to `main`. | Solo developer at this stage | 2026-10-13 |
| Mirror job (F) | Same design (fast-forward only, after a green pipeline), plus `entrypoint: [""]` for `alpine/git` and a rule that skips the job when `GITHUB_MIRROR_TOKEN` isn't set. GitHub (`KAttal007/Analekh`) has only `main`. | The image's entrypoint is `git`, so the runner's shell failed | 2026-10-13 |
| — | Added jobs: `web` (pnpm lint, test, build) and `dependency_audit`. Deploy and DAST jobs are gated on their URL variables; a `workflow:` block avoids duplicate branch and MR pipelines. | | |
| Self-hosted runner tagged `india` (22.5) | Not set up; deploy jobs can't run. | | 🔲 |

### 7. Front end and tooling

| Design says | Now | Why | Date |
|---|---|---|---|
| npm (`package-lock.json` in G) | pnpm 12.11.2 workspace (`web/`, `office-addin/`), one `pnpm-lock.yaml`. Install scripts denied by default (`allowBuilds`); `minimumReleaseAgeExclude` for supply-chain exceptions. | Faster, stricter, smaller installs | 2026-10-13 |
| Node 24 LTS (G.8) | Same, pinned in `.node-version`; root `package.json` requires `>=24`. Installed locally with fnm. | | 2026-10-13 |
| G.5 dependency list | Matches, plus `@fontsource-variable/inter`. | Self-hosted font; no Google Fonts call | 2026-10-13 |
| Screens (19.1) | All screens restyled: left sidebar (collapsible), light/dark/system theme, design tokens, skeleton loading, page transitions that respect reduced motion. Reports, Q&A, Comps and Settings are still placeholders. | Not specified in the design | 2026-10-13 |

Policy (2026-10-13): keep the app lightweight, pragmatically. New additions take the lighter
option; existing choices (AG Grid, ECharts, Inter, the roadmap's Python libraries) stay.

### 8. Environment variables (22.3)

- Removed: `KITE_API_KEY`, `KITE_API_SECRET` (and `KITE_ACCESS_TOKEN`, which the code had).
- Added: `MINIO_BUCKET`, `CLAUDE_MODEL`, `CLAUDE_SMALL_MODEL`, `EVENT_FEED_POLL_SECONDS`,
  `IMPORT_DIR`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_URL`, `ALERT_EMAIL_TO`.
- `.env.example` uses `you@example.com` for the `USER_AGENT` contact; the real address lives
  only in `.env`.

### 9. Repository layout (Appendix E)

| Design says | Now |
|---|---|
| `templates_builtin/` at the top level | `analekh/templates_builtin/` (inside the package, so it ships with it) |
| — | `scripts/` (Phase 0 spike, Stocks workbook helper), `mappings/` (example mapping YAML), `docs/` (runbooks, this folder) |
| — | `analekh/coverage.py`, `discovery.py`, `facts.py`, `golden.py`, `admin/` (Streamlit), `alerts/` as their own modules |
| — | Root `package.json`, `pnpm-workspace.yaml`, `.node-version`, `.python-version`, `.dockerignore` |
| `market/` was not listed | Was added in the skeleton for Kite; removed 2026-10-13 |

### 10. Phase 0 findings (26, 28)

The spike ran on 2026-10-13 (`out/phase0/20261013-115051`, not in git).

| Finding | Effect |
|---|---|
| The results feed held only two filings (Asian Hotels (West), Q4 FY21, Ind-AS): no bank or NBFC files yet | Bank, NBFC and insurance element tables stay empty; rerun during the October results season (open question 28.1 still open) |
| Ind-AS element names confirmed against real files | `# verify` markers removed in `xbrl/elements.py`, except `TotalIncome` and `TotalExpenses` |
| Feed `pubDate` is `DD-Mon-YYYY HH:MM:SS` | Not parsed yet, so V8 (late filing) skips |
| One filing gives different values for the same dates in two contexts (`OneD` vs `FourD`) | Parser keeps the first; flagging still to decide |
| The SME list uses `DD-Mon-YY` dates | Loader accepts both formats |
| NSE archives and niftyindices.com stopped answering this machine for hours while other sites worked | Not the geo-block 3.1 describes; retry with single requests, never work around it |
| "One price pull" exit criterion | Dropped with Kite (section 1 above) |

Still open from Phase 0: a hand-check of 10 values per file against the results PDF.

### 10a. Values stored as corrected, not as filed (V11, 21 October 2026; folded into v0.0.5)

| Design doc says | Done instead | Why |
|---|---|---|
| Values stay in full INR as filed (8.1, parser) | When V11's two signals agree that a filing's rupee amounts are in the wrong unit, the corrected amounts are stored; the factor and reason are on the filing (meta `scale`), and the stored XBRL file keeps the values as filed | Metro Brands' consolidated September 2025 XBRL tagged every amount 100 times too small (revenue Rs 6.51 crore for Rs 651.14 crore), which put ">+999%" growth at the top of the Results desk. Correcting only on two agreeing signals, with an exact power of ten, keeps rule 5 (XBRL wins) honest: the figure is the filer's own, in the right unit. A suspect with one signal is never changed, only blocked and kept out of growth figures. The full sweep (2,750 companies) found filings where both bases slipped together (Eveready, MTNL: each off its own history by the same power, so the two histories are the two signals) and real jumps level with an in-line other basis (Mahindra Lifespace: passed, not held). After it: 28 filings corrected, 44 suspects left for a check against the PDF, mostly companies with under Rs 10 crore a quarter |
| Background backfill (9, 26) | The nightly Celery beat entry `background-backfill` (01:30, Nifty 500 companies without history) was removed from the schedule on 2026-10-21; the task `background_backfill` stays in `jobs/tasks.py` | The owner says the history backfill is done, and `universe/data/nifty500.csv` is still empty, so the job would find nothing. Re-add the entry when the Nifty 500 list is filled and new constituents need history |

### 11. Proposed, not decided

| Area | Proposal |
|---|---|
| Report generation (17) | Today `genai/reports.py` runs one open tool loop per report (all tools, up to 20 turns). Proposal: fixed workflows for the flash; section-by-section runs for the note, IC note and initiation (outline from a report template, core data pre-fetched by code, a short tool loop per section, grounding check per section so one section can be redone); keep the open loop for Q&A and red-flag digging. |
| Python 3.15 | Blocked on Windows wheels for pyyaml, playa-pdf (via camelot-py) and numpy-financial. |
| Investor presentations (3.2, 11) | Link each quarter's deck from NSE's corporate announcements list (subject "Investor Presentation"): one request a day, plus a backfill by date range or per company; store only the link. Needs the owner's approval to widen `ALLOWED_PATHS`; stashed by the owner on 2026-10-14. |
