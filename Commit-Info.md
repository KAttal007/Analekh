# Commit Info

Newest first. One entry per major update: what moved, and what it unblocks. Kept out of
[README.md](README.md) so the README stays short.

- **2026-10-23** Sign-in and landing, after the live test. Opening Analekh always lands on the
  welcome page when signed out (a live session opens the Results desk directly; Enter and a mouse drag now open it too), which hands off to
  sign-in. After sign-in the desk's data loads first and a short (~0.35 s) unlock plays, so the
  table no longer fills in mid-animation. Results desk: 10 database queries instead of one per
  company (the blank year-ago notes in one query), and its filters stay on one row instead of
  wrapping and pushing the title down. The auth-switch tests no longer read the developer's .env.
- **2026-10-23** First password by email and password rules. Adding a user needs only email,
  name and role: Analekh makes a random first password (20 characters, hashed, valid 24 hours), emails
  it inline after the reply (the user row shows sending, sent or failed; migration 0011); the first sign-in allows nothing but choosing a new
  password, which ends all sessions. Admin "Send first password" replaces the typed reset (503 when
  email is off). New rules on every chosen password: 15 to 30 characters, 8 letters, a number, a
  special, upper and lower case, no spaces, published at `GET /auth/password-rules` and shown live in
  the web app; the 30 cap also limits sign-in. Migration 0010 adds the two account columns.
  Reset codes now last 2 minutes (was 10), matching the 2-minute wait to resend. Unblocks the live
  test with real mail and onboarding analysts without passing passwords by hand. Sign out now
  goes to the welcome page as soon as the server confirms (it used to wait for another click);
  a failed sign-out stays put and shows the error. The sign-in unlock is now a plain animation on
  the live page: as a view transition it covered the page and swallowed clicks (Sign out right after
  signing in did nothing).
- **2026-10-23** OCR for scanned pages moves from Tesseract to RapidOCR (`rapidocr` + `onnxruntime`,
  models in the package): no system binary, so scans are read on Windows too and the image drops
  the tesseract apt packages. Model routing and limits in `analekh/docs/rapidocr.yaml` (bundled
  PP-OCRv6 small models, 2 threads per task). `requirements.txt` re-exported; tests cover the OCR
  path and the config.
- **2026-10-23** Results watcher hourly in season (was every 2 hours; owner's call, rule 1 and
  design doc 9.6 updated). Off season it still asks once a day at 21:00. Restart beat to apply.
- **2026-10-23** Node 24.22.1 (latest 24.x LTS) pinned exactly in `.node-version`, the CI web
  job and the web Docker image. Node 26 becomes LTS on 2026-10-28; planned for later.
- **2026-10-21** v0.0.5: design document, deviations log and architecture diagrams brought up to
  date (V11, scheduler and feeds in Docker, results calendar, results history, Reports, the
  owner's amendment on ratings). Code version 0.0.5.
- **2026-10-21** Reports screen: set up a quarterly update or an initiating coverage note
  (Word and a dense IB-style PowerPoint) for a company, basis (standalone by default,
  consolidated or both) and quarter, all in the URL; see which inputs are ready and what each
  output will contain. Drafting comes next. Rule 8 amended by the owner: a report may carry the
  recommendation from the analyst's own model; Analekh never makes one up.
- **2026-10-21** Company page: the filings box is folded into the results history. Each quarter's
  heading links its filing on NSE (iXBRL, the newest after a refiling), opens its details and
  shows one status mark; other filings fold out under the table. Raw XBRL is no longer linked.
  The top search bar gives way to the page's own company picker on Reports and Comps.
- **2026-10-21** Scheduler in Docker (Celery beat, worker, Redis); the feed watcher runs, and the
  Board Meetings feed now drives a results calendar on the desk and watchlist. V11 unit check
  (28 filings corrected, 44 suspects), results history with Excel export, desk-style watchlist,
  Analyse that says when the queue is down, and a faster first company view (about 0.25 s).
- **2026-10-18** Results watcher by season: every 2 hours from 09:00 to 23:00 IST in SEBI's
  results windows, once a day at 21:00 otherwise, about 60% fewer requests. No filing is blocked
  any more: the last 14 tagged exceptional items as `ExceptionalItems` (one also had an
  extraordinary line), which V2 now reads; 517 companies revalidated, nothing newly blocked.
- **2026-10-18** v0.0.4: design document and architecture brought up to date, with a diagram for
  every workflow, built or planned (results, prices, sectors, reading results, model update,
  start coverage, templates, documents and drafts, events and alerts), the job schedule and the
  hosting plan. The Word copy puts each diagram on its own landscape page. Code version 0.0.4.
- **2026-10-18** Daily prices keep only the latest close: each bhavcopy replaces the previous day
  (owner's rule, for storage). A check of NSE's two lookups for 24 companies: NSE shows a filing
  about a second after it is filed, and every first filing since 2023 fell inside SEBI's windows,
  which supports polling by season.
- **2026-10-17** Prices on screen: share price and market cap on the company page, a market-cap
  column and sort on the desk, `GET /companies/{symbol}/price`; previous close stored (migration
  0005). A welcome screen opens each session; tabs and switches glide; data stays fresh for five
  minutes instead of reloading on every tab. Filings box scrolls inside its card.
- **2026-10-17** Results for the 559 companies that gained an NSE sector (539 SME, through NSE's
  SME index) are being fetched; they were outside the first backfill. The results watcher runs
  every 2 hours from a Windows scheduled task; 113 companies have reported the September quarter.
- **2026-10-16** Sectors switched to **NSE's own taxonomy** (owner's choice): all 116 NSE Indices
  lists were found and read; 11 of them cover every indexed company, giving 1,430 companies NSE's
  exact sector (539 SME via SME Emerge). Precedence is now user > NSE > LSEG; LSEG groups are kept
  in `sector_lseg` (migration 0004). Wrong list names no longer fail silently (the site answers
  with a 200 page). NSE's company-level classification (basic industries) sits behind its quote
  data, which refuses automated requests.
- **2026-10-16** Results watcher every 2 hours (was once a day; owner's call, rule 1 updated).
- **2026-10-16** History overnight: about 15,000 filings from 2023-2024 added; NSE stalled twice
  (after 4,195 requests each time) and the watchdog resumed. 72% of companies covered by then had
  14 or more clean quarters.
- **2026-10-15** Results history from NSE's financial-results list (rule 1 amended by the owner):
  XBRL back to 2018 is listed, but files before 2023 lack their main contexts, so history starts in
  March 2023 (owner's decision; such files are rejected, never half-stored). `--sector` runs a
  sector at a time; `--history` fetches history for every company in scope.
- **2026-10-15** GIC Re: every filing was blocked because V2 didn't deduct a reinsurer's transfer
  to reserves; fixed, 0 blocked. Laurus Labs lost all its filings to one broken file; broken files
  are now fetched once more, then skipped. NSE's "no XBRL" links (`.../xbrl/-`) are no longer
  requested.
- **2026-10-15** The first full results backfill finished: 2,168 of 2,458 companies with a sector,
  23,853 filings, 0 errors. 290 have nothing on NSE: 250 joined NSE in batches in 2026 and file
  with BSE (BSE's API refuses automated requests), 14 are non-compliant (BZ), 23 were NSE server
  errors (since fetched).

- **2026-10-15** v0.0.3: design document, deviations log and architecture diagrams brought up to
  date (integrated filings, NSE's request limit, results formats, revisions, Results desk,
  status and blockers per phase); Word copy and PDF regenerated from the Markdown and
  `architecture.html`. Code version set to 0.0.3 (it said 0.1.0).
- **2026-10-15** Revised results: the value in use for each line is now the one from the most
  recently filed filing (it was the last downloaded; 88 values were wrong). `analekh
  recompute-latest` fixed stored data (108 values switched) and labelled 1,242 refilings; new
  filings keep NSE's Original/Revision flag. Company page: Restated, Revised and Superseded tags
  with a popup listing old to new for each changed line.
- **2026-10-15** Backfill: NSE stops answering after about 590 requests whatever the pace, so
  the pace stays at 2 s; `--start-at` resumes at the company a run stopped on, and companies
  already known to have no filings are skipped (`--recheck-no-filings` to re-check). The
  estimate fell from about 51 hours to about 16.
- **2026-10-15** Results desk: ten companies per page with Prev and Next; Movers and By sector
  scroll inside fixed-height boxes. A missing YoY now says why (Canara Robeco AMC's first results
  after listing covered a half-year only; recent listings have no year-ago quarter).
- **2026-10-14** Life insurers: new `life_insurance` format (migration 0003) with net premium as
  the top line, solvency, persistency and expenses of management; V1 through the policyholders'
  account, V2 through the shareholders'. Canara HSBC Life's empty row and page now show numbers.
- **2026-10-14** Small companies in lakhs (under Rs 10 crore of revenue: Agri-Tech read "Rs 0
  cr"); notes behind an information icon; margins in basis points with full figures in the
  Latest quarter column.

- **2026-10-14** Home is now the Results desk (`GET /desk`): who reported the quarter, newest
  first, with revenue, profit and EBITDA margin against a year ago; movers (₹50 cr revenue
  floor, profit base at least 2% of revenue, sign changes listed apart); progress and medians by
  sector. Filters (quarter, sector, period, watchlist) live in the URL; rows become cards on
  phones and columns give way to the table's own width. EBITDA is left out for lenders and
  holding companies, here and on the company page. New daily `analekh results-watch`: one
  request to NSE's latest-results list, then the new filings.
- **2026-10-14** Company page: a full-height "Latest quarter" column on wide screens
  (`GET /companies/{symbol}/glance`: the quarter's P&L in the company's format, with QoQ and
  YoY change, derived EBITDA, net interest income and margins) and a Call highlights card that
  stays empty until call notes exist. Phones: icon-only navigation, two figure tiles per row,
  the quarter right after the tiles, low-value table columns hidden; checked at 390, 820,
  1,366 and 2,000 px with no sideways scrolling.
- **2026-10-14** Earnings-call audio to text: `analekh transcribe-audio <SYMBOL>` runs Whisper
  large-v3 on the GPU (faster-whisper; optional `audio` group, no PyTorch) over recordings in
  `import/<SYMBOL>/`, writing timestamped text to `out/audio/`. Recordings are online within
  24 hours of a call, days before the written transcript.
- **2026-10-14** Standalone and consolidated side by side: the bulk fetch now takes both bases
  for every quarter (`--one-basis` to opt out), and the company page has a Consolidated /
  Standalone switch (kept in the URL as `?basis=`) that drives the figures, chart and filings
  table. Companies with nothing to store are listed with the reason in
  `out/bulk/no-filings.csv`, kept across runs.
- **2026-10-14** Banks and insurers understood: element tables filled from real filings, the
  results format now detected from the line items (integrated filings share one schema), V1/V2
  take each format's extra terms (bank provisions; an insurer's investment income and
  shareholders' account), and company pages chart interest earned or premium earned.
  `analekh revalidate` re-runs the checks on stored files. Bulk fetch started for the 2,458
  companies with a sector (`analekh results-backfill --interval 5`, about a day).
- **2026-10-14** First real company end to end: Tata Elxsi's last seven quarters fetched,
  validated and shown on its company page. NSE's results feed has been frozen since 24 August
  (results moved to SEBI's integrated filings), so rule 1 was amended to allow NSE's
  integrated-filing lookup (`/api/integrated-filing-results` only) and `analekh refresh` uses
  it. Found and fixed on real files: NSE's CDN stalls any User-Agent holding an email or URL
  (contact now goes in `From:`); typed XBRL dimensions were read as empty; V2 subtracted
  exceptional items that filings tag as negative; the company page showed nothing for
  standalone-only filers and would have mixed year-to-date figures into the quarterly chart.
- **2026-10-14** V8 (late filing) follows SEBI's results deadlines (LODR 33(3)): 45 days after
  a quarter, 60 after the financial year end, plus a day for the XBRL to follow the PDF. It was
  180 days, which only caught stale filings.
- **2026-10-14** Feed dates: NSE writes `pubDate` as `24-Aug-2026 17:39:16` (IST, no offset),
  which feedparser can't read, so every feed item had no date and V8 (late filing) always
  skipped. `parse_rss` now falls back to NSE's format and stores the time in UTC.
- **2026-10-14** Object storage: MinIO no longer publishes community images, so compose builds it
  from source (`deploy/minio/Dockerfile`, pinned release). When storage is down the API now
  answers 503 within seconds instead of hanging, and the Models and Templates pages show the
  error instead of loading forever.
- **2026-10-13** Kite Connect removed (paid, and its pinned `autobahn` carried two known
  vulnerabilities): `market/kite.py`, the `KITE_*` settings, the spike's `--price` step and
  the `kiteconnect` dependency with Twisted and autobahn. The `prices` table stays for a
  free source.
- **2026-10-13** UI motion and polish: Inter variable font (bundled), light / dark / system theme
  switch, collapsible sidebar, screens fade in section by section, animated search dropdown,
  shimmering loading placeholders, cards that lift on hover, company initials badge, figure tiles
  with icons and green/red changes, gradient revenue chart. Motion is switched off when the
  system asks for reduced motion.
- **2026-10-13** Instant company search: the web app loads every company once
  (`GET /companies/index`, about 80 KB gzipped, ETag-revalidated) and ranks matches in the
  browser on each keystroke, in under 3 ms, with results identical to the API on real data. The
  API's fuzzy search is only asked when nothing matches locally (typos). API responses over
  1 KB are now gzipped.
- **2026-10-13** Sectors for 2,458 companies from a BSE securities list converted with Excel's
  Stocks data type (LSEG industry groups), imported by ISIN. New `companies.sector_source`
  (migration 0002) ranks sources: user > excel_stocks > nse_indices. Stocks sectors never set
  the results taxonomy, since LSEG's "Banking Services" also holds NBFCs.
- **2026-10-13** Sectors: niftyindices.com allowed, limited to its `/IndexConstituent/` lists.
  `analekh universe sectors` applies curated overrides, then the Nifty 500 and Microcap 250
  lists; bank index membership marks banks. The results taxonomy is now only set from strong
  signals, so the first filing's schema reference decides the rest. Not yet run: both NSE hosts
  stopped answering this machine on 2026-10-13.
- **2026-10-13** Web UI design pass: left sidebar with grouped navigation, sticky search bar
  (`/` to focus), shared colour and spacing tokens with automatic dark mode, and common pieces
  (page headers, cards, figure tiles, badges, alerts, empty states) used on every screen. The
  watchlist grid and the revenue chart follow the same theme.
- **2026-10-13** GitLab Free has no dependency scanning, so CI now runs OSV-Scanner on both
  lockfiles (`dependency_audit`, warning only). First run: 27 known vulnerabilities in 5 packages:
  `autobahn` (pinned by `kiteconnect`) and the Excel add-in's dev tooling (see the tracker). Fixed `mirror_to_github`:
  the `alpine/git` image's entrypoint swallowed the job's shell.
- **2026-10-13** Front ends moved to a pnpm workspace (`web/`, `office-addin/`, one lockfile),
  Node 24 pinned in `.node-version`. CI now also builds the Excel task pane. Dependency install
  scripts are denied by default; the three the add-in tooling wanted are listed in
  `pnpm-workspace.yaml`. Added `.dockerignore` so `.env`, exchange data and models never enter a
  Docker build context.
- **2026-10-13** Company search rebuilt as a type-ahead: one letter matches the start of a
  ticker or name, two or more match anywhere, words match in any order ("tata pass"), results
  page with `offset` and the web box loads more on scroll. Look-alike (fuzzy) matches now only
  appear when nothing else matches, so "tata motors" no longer returns Force Motors.
- **2026-10-13** Universe loaded from NSE's published lists: 3,186 companies. Fixed SME listing
  dates (the SME list uses two-digit years).
- **2026-10-13** Local stack up: Docker Desktop on WSL2, PostgreSQL 16 with pgvector and
  pg_trgm, migrations at `0001`. All tests now run locally, none skipped.
- **2026-10-13** First Phase 0 spike run. Universe and SME lists confirmed; the results feed held
  only Asian Hotels (West), two Q4 FY21 Ind-AS files. Validation V1-V4, V6, V7, V9 pass. Ind-AS
  and metadata element names confirmed, `# verify` markers removed. Found: the feed `pubDate`
  format is not parsed (V8 skips), and a filing reuses the quarter's dates for full-year values.
- **2026-10-13** First local development instance. NSE's published archives respond from it,
  so the Phase 0 spike can run. Pinned Python 3.12 in `.python-version` to match CI and the
  Dockerfile. Python 3.15 waits for Windows wheels of four dependencies (see the tracker); to
  upgrade, change `.python-version`, the Dockerfile and `.gitlab-ci.yml` together.
- **2026-10-12** Skeleton of all phases committed; GitLab CI added, first green pipeline on `main`.
