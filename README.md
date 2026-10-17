<h1 align="center">Analekh</h1>

<p align="center">
  <b>NSE results in, analyst-approved Excel models and grounded research drafts out.</b>
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="PostgreSQL 16 + pgvector" src="https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="React 19" src="https://img.shields.io/badge/web-React%2019-61DAFB?logo=react&logoColor=black">
  <img alt="v0.0.3" src="https://img.shields.io/badge/version-v0.0.3-informational">
  <img alt="Phase 1 in progress" src="https://img.shields.io/badge/status-Phase%201%20in%20progress-orange">
</p>

Pick any NSE-listed company. Analekh finds its results filings, extracts and validates the
numbers, builds a model from your own template (or updates the model you already keep), writes
to Excel only after you approve, and drafts the results flash, earnings note, initiation, slides
and comps with every number traced to its source.

> **Design document:** *Analekh Technical Design Document v0.0.3*
> ([docs/design/technical-design.md](docs/design/technical-design.md); formatted copy
> `docs/design/Analekh - Technical Design v0.0.3.docx`, diagrams
> `docs/design/Analekh - Architecture v0.0.3.pdf`). Section numbers in code comments (e.g.
> "design doc 12.3") refer to it; departures since are logged in
> [docs/design/deviations.md](docs/design/deviations.md).
>
> **Versions** follow the build phases: v0.0.x during Phase 0, v0.1.x once Phase 0 is complete,
> v0.2.x once Phase 1 is complete, and so on. The first release for proper testing is
> v1.0.0-pre-release.
>
> **Source control:** GitLab is the source of truth. GitHub is a read-only mirror, updated by CI
> after a green pipeline on `main` (design doc 22.5). Never push to GitHub directly.

## Contents

- [How it works](#how-it-works)
- [Status](#status)
- [Quick start](#quick-start)
- [Development](#development)
- [CI/CD](#cicd)
- [Data rules](#data-rules)

## How it works

```mermaid
flowchart LR
    NSE["NSE integrated filings,<br/>published feeds and lists"] --> Ingest["Ingest<br/>fetch, link, store"]
    Ingest --> XBRL["XBRL parse<br/>+ validate V1-V10"]
    Ingest --> Docs["PDF read<br/>+ KPI extraction"]
    XBRL --> Facts[("Facts<br/>PostgreSQL")]
    Docs --> Facts
    Facts --> Build["Coverage Builder<br/>(new model)"]
    Facts --> Sync["Model sync<br/>(change sets)"]
    Build --> Approve{"Analyst<br/>approves"}
    Sync --> Approve
    Approve --> Excel["New model version<br/>in Excel"]
    Facts --> GenAI["Grounded drafts<br/>flash, note, initiation"]
    Facts --> Desk["Results desk and<br/>company pages"]
```

- **XBRL wins** over AI-extracted values, and contexts are matched by dates, never by id.
- **The newest filing wins** when a company refiles a quarter; the older numbers are kept as
  history, and the company page tags the quarter Restated or Revised with what changed.
- **Nothing touches a model without approval**, and every write saves a new version; the
  original workbook is never overwritten.
- **Generated text may only contain numbers** from tool results or `calc`; a grounding check
  blocks anything else.

## Status

**v0.0.3, status on 17 October 2026.** The data layer runs on real NSE data:

| | |
|---|---|
| Companies in the universe | 3,186 (2,606 main board + 580 SME) |
| Companies with results stored | **2,537** (backfills still finishing: S to Z, and the companies that gained a sector on 16 October) |
| Results filings / values | **50,319 filings, 9.5 million values**, both bases |
| History | From **March 2023** (NSE's older files are incomplete); 1,407 companies already have 14 or more quarters |
| Blocked by a check | 14 filings (V2; see Next up) |
| September 2026 quarter (Q2 FY27) | 113 companies reported so far, collected every 2 hours |
| Sectors | **NSE's own taxonomy** for 1,430 companies (22 sectors), LSEG groups for 1,587 (mapping to NSE names awaits the owner), none for 169 |
| Storage | About 10 GB (PostgreSQL 5.1 GB, raw XBRL 4.1 GB) |

Results come from NSE's integrated-filing lookup (the results feed stopped on 24 August 2026)
and, for 2023-2024, its financial-results list. Banks, NBFCs, general insurers (reinsurers
included) and life insurers are read in their own formats and tie out. Home is a Results desk;
company pages show the latest quarter with QoQ and YoY changes; refiled quarters use the newest
filing and are tagged. The engines for later phases have working cores with synthetic tests;
gaps are marked `PHASE n` and `# verify` in the code.

### What stops the next phases

The full picture is in design doc 26.1. In short:

| Phase | Waiting on |
|---|---|
| 0 → v0.1.0 | Hand-check of about 10 values per filing against the results PDF for a golden set covering every results format; `analekh golden-test` |
| 1 → v0.2.0 | Backfills finishing (history S-Z; results for the 559 companies that gained an NSE sector, then their history); the 290 companies with nothing on NSE (about 250 file only with BSE, whose API refuses automated requests); the 169 without any sector; the scheduler on a server (the results watcher runs from a Windows scheduled task on the laptop for now; the feed watcher not at all) |
| 2 | Real model templates and existing models from an analyst; balance sheet and cash flow history; desktop Excel for the bridge; a price source |
| 3 | A valid Anthropic API key; a source for presentations and transcripts; the embeddings provider |
| 5 | A price source for comps; hosting in an Indian region with a login |

### Next up

1. **Finish the backfills:** history for S-Z (running), results for the newly sectored
   companies (running), then history for the newly sectored companies before "S".
2. **Hosting on Oracle Cloud** (Always Free Arm VM, Mumbai): account, VM, then one honest NSE
   request from it to see whether NSE serves cloud addresses; then the stack, the data (dump, not
   re-download), HTTPS and a login, auto-deploy from GitLab, and the scheduler moved off the laptop.
3. **The 14 blocked filings** (V2: L&T, KIMS, MT Educare, four SME companies): likely one P&L line
   V2 doesn't include yet (share of associates or joint ventures), as with GIC Re's transfer to
   reserves.
4. **Golden set and hand-check** across the results formats, then `analekh golden-test`:
   completes Phase 0 (v0.1.0).
5. **Balance sheet and cash flow** from the half-year and year-end filings; V4 for Ind-AS.
6. **Results history table** on the company page with an Excel export.
7. **Results calendar** from the Board Meetings feed; **peer view** of growth and margins.
8. **Sector editing screen** (owner's values outrank NSE's), including NSE basic industries read
   off the quote page for covered companies.

Decisions waiting on the owner: the LSEG-to-NSE sector mapping (28 clear groups, 25 to decide);
bank presentation and calculations (owner's walkthrough); hosting details (domain, login);
investor presentations through NSE's announcements list; the 250 BSE-only filers (manual import
or a tooltip); the price source; the Anthropic API key.

### Tracker

✅ verified on real data &nbsp;·&nbsp; 🟡 built, synthetic tests only &nbsp;·&nbsp; 🔲 to do &nbsp;·&nbsp; ⛔ blocked (reason given)

Keep these tables current in the same merge request as the change, and add a line to the
[dev log](#dev-log).

#### Phase 0 · Spike

| Item | Status | Notes / still needed |
|---|:---:|---|
| NSE published archives reachable | ✅ | From the local development machine |
| `scripts/phase0_spike.py` (lists, two feeds, XBRL parse + validate, element census) | ✅ | First run 2026-10-13; the results feed held only one company |
| Ind-AS element names in `xbrl/elements.py` | ✅ | Seen in real files (one company, 2020-03-31 taxonomy); fallbacks `TotalIncome`, `TotalExpenses` unconfirmed |
| Filing metadata element names (symbol, period, nature, audited) | ✅ | All nine seen |
| SME equity list path and columns | ✅ | 580 companies; two-digit-year dates now parsed |
| Bank, NBFC and insurance element tables | ✅ | Banks (HDFC Bank, SBI), general insurers (ICICI Lombard) and life insurers (Canara HSBC Life: net premium as the top line, solvency, persistency, expense ratio) mapped from real filings and tying out; NBFCs use the Ind-AS names. Insurers' balance sheet (V4) not mapped |
| Feed `pubDate` format | 🟡 | `DD-Mon-YYYY HH:MM:SS`, no offset (IST); parsed since 2026-10-14, so V8 runs. Not yet seen through the live watcher |
| Contexts with the same dates but different values | 🔲 | Seen in a real filing (`OneD` vs `FourD`); parser keeps the first value; decide how to flag |
| Hand-check of spike values against the results PDF | 🔲 | 10 values per file |
| V2 exceptional-items sign convention | ✅ | Tagged with their sign (a charge is negative) and added: Tata Elxsi Q3 FY26 labour-code charge |
| Daily prices | 🔲 | Kite Connect removed (paid). Candidate: NSE/BSE daily bhavcopy; needs rule 1 amended |

#### Phase 1 · Data layer

| Item | Status | Notes / still needed |
|---|:---:|---|
| Universe loader | ✅ | 3,186 companies (2,606 main board + 580 SME); renames and delistings not yet seen on real data |
| Company search (API and CLI) | ✅ | Type-ahead: one letter matches the start, two or more match anywhere in ticker or name; paged |
| Web design system and app shell (sidebar, tokens, dark mode, shared components) | ✅ | Used with real data; phone widths checked (390, 1,366, 2,000 px) |
| Web type-ahead search box | ✅ | Used against the live API |
| Results desk on Home (`GET /desk`) | ✅ | Reporters ten per page, YoY revenue, profit and EBITDA margin, movers, sector progress; filters in the URL |
| Company page: basis switch, Latest quarter column (`GET /companies/{symbol}/glance`), lakh amounts | ✅ | QoQ and YoY with margins in bps; notes and tags open on hover or tap; dash with a reason when a comparison quarter was never filed |
| Revised results: newest filed value wins; Restated / Revised / Superseded tags | ✅ | `analekh recompute-latest` switched 108 values; NSE's revision flag stored on new filings |
| Watchlist and coverage levels | 🟡 | |
| Feed watcher, polite fetcher, linking, storage | 🟡 | Polled once on 2026-10-14 (118 items, dated, 97 linked); not yet running on a schedule. The results feed is frozen since 24 August; results now come as integrated filings |
| Integrated filing lookup (`ingest/integrated.py`, `analekh refresh`) | ✅ | Rule 1 amended 2026-10-14. 2,537 companies stored; integrated filings start with the March 2025 quarter; SME companies through `index=sme` |
| Results history (`analekh results-backfill --history [--sector …]`, NSE's financial-results list; rule 1 amended 2026-10-15) | ✅ | From March 2023: NSE's older `_WEB` files lack the main contexts and are skipped (`pipeline.IncompleteXbrl`; owner's call, no rebuilding by id). Full run S-Z still going; Banking Services stored for the owner's walkthrough |
| Results watcher (`analekh results-watch`, beat `watch-results` every 2 hours) | ✅ | ONE request to the latest-results list every 2 hours (owner, 2026-10-16). Windows scheduled task "Analekh results watch" until the scheduler is hosted; log `out/results-watch.log` |
| Broken and missing XBRL files | ✅ | A 404, or a file cut off partway (fetched once more), is skipped and noted; the company's other filings are kept (Laurus Labs) |
| XBRL parser, validation V1-V9 | ✅ | Integrated filings (`in-capmkt` taxonomy) parse: all 18 Ind-AS names match; typed dimensions read. Tata Elxsi's 7 filings pass V1-V9 (V4 skips without a balance sheet) |
| Sectors: NSE's taxonomy (`analekh universe sectors`) | ✅ | Owner's choice 2026-10-16. 11 NSE Indices lists (found among all 116) cover every indexed company: 1,430 with NSE's exact sector (22 current names; stale pre-2022 labels ignored). Precedence user > NSE > LSEG |
| Sectors: LSEG groups from an Excel Stocks workbook (`--stocks-file`) | ✅ | Kept in `companies.sector_lseg` (migration 0004); shown for the 1,587 companies in no index until the LSEG-to-NSE mapping is approved. Runbook: [docs/sectors-from-excel-stocks.md](docs/sectors-from-excel-stocks.md) |
| NSE basic industries (58 industries, 200 basic industries) | ⛔ | Only in NSE's quote data, which refuses automated requests (403, honest or browser headers); needs NSE's permission or a licence, or the owner's own entries |
| Results backfill (`analekh results-backfill [--start-at] [--sector]`) | ✅ | First full run finished 2026-10-15 (0 errors); 290 companies have nothing on NSE (`out/bulk/no-filings.csv`, ~250 BSE-only filers). NSE's limit varies (590 to 4,195 requests, then a 10-minute pause); the watchdog resumes at the stalled company |

#### Phase 2 · Builder and sync

| Item | Status | Notes / still needed |
|---|:---:|---|
| Workbook understanding engine | 🟡 | Real templates and models |
| Template onboarding + test build | 🟡 | Real templates |
| Built-in NBFC and consumer templates | 🟡 | P&L and KPIs only; balance sheet and cash flow 🔲 |
| Coverage Builder (fill, propose assumptions, finalize) | 🟡 | |
| Discovery and tags, change sets, headless apply | 🟡 | |
| Excel bridge (xlwings) | 🟡 | First run on an analyst's machine |
| Web review screens (change sets, assumptions, models, templates) | 🟡 | |

#### Phase 3 · Document AI

| Item | Status | Notes / still needed |
|---|:---:|---|
| PDF read, page classifier, KPI extraction with quote check, chunking, transcripts | 🟡 | API key, golden set, classifier tuning |
| V10 (XBRL wins over KPI values) in `docs/pipeline.py` | 🔲 | Map KPI names to XBRL names |
| Embeddings | ⛔ | Provider undecided (open question 28.7) |

#### Phase 4 · GenAI outputs

| Item | Status | Notes / still needed |
|---|:---:|---|
| Tools (incl. model reader), calc, grounding check | 🟡 | |
| Report loop (flash, note, initiation), Q&A, Word/PowerPoint writers | 🟡 | Prompt tuning on 10 companies |
| Reports as Celery jobs, files in object storage | 🔲 | Run inline in the API today |
| Web Reports and Q&A screens | 🔲 | Placeholders |

#### Phase 5 · Discovery, IB, polish

| Item | Status | Notes / still needed |
|---|:---:|---|
| Comps | 🟡 | EBITDA, debt, cash, book value not sourced |
| Profile slide, pitch refresh | 🟡 | Branded templates |
| Alerts, Office.js task pane, Streamlit admin | 🟡 | |
| Web Comps and Settings screens | 🔲 | Placeholders |
| Demo | 🔲 | |

#### Platform and CI/CD

| Item | Status | Notes / still needed |
|---|:---:|---|
| GitLab pipeline (lint, tests, web, security scans, image) | ✅ | Green on `main` |
| Staging and production deploys, DAST | ⛔ | Runner tagged `india`, `STAGING_URL`, `PRODUCTION_URL` |
| Hosting (Oracle Cloud Always Free, Mumbai) | 🔲 | Walkthrough started 2026-10-16; first test: does NSE serve the VM's address? Arm VM, so images build on the server |
| Python 3.12 everywhere (`.python-version`, CI, Dockerfile) | ✅ | |
| Local stack: Docker Desktop (WSL2), PostgreSQL 16 + pgvector, migrations | ✅ | Migrations at `0004`; 114 Python and 13 web tests run locally, none skipped. A laptop sleeping mid-run can skew Docker's clock briefly (MinIO rejects uploads until it catches up) |
| Design documents | ✅ | v0.0.3 Markdown, Word copy and architecture PDF; `scripts/design_docx.py` and `scripts/diagram_panels.py` rebuild them |
| Front-end toolchain: Node 24 (fnm), pnpm workspace for `web/` and `office-addin/` | ✅ | Lint, tests, both builds and the web Docker image pass |
| Excel add-in manifest version | 🔲 | Below 1.0, which Microsoft's validator rejects; bump before publishing |
| Dependency audit (OSV-Scanner, Free tier) | ✅ | Runs on every pipeline, warns on findings |
| Known vulnerabilities: `adm-zip`, `node-forge` (add-in dev tooling only) | 🔲 | Not in the built add-in; wait for Microsoft's tooling to update |
| Upgrade to Python 3.15 | ⛔ | Windows wheels for pyyaml, playa-pdf (via camelot-py), numpy-financial; zope-interface left with Kite |

### Dev log

Newest first. One line per notable change: what moved, and what it unblocks.

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

## Quick start

### Everything in Docker

```bash
cp .env.example .env            # fill in ANTHROPIC_API_KEY, USER_AGENT and storage keys
docker compose up -d            # postgres, redis, minio, api, worker, beat, web
docker compose exec api alembic upgrade head
docker compose exec api analekh universe load      # published NSE equity lists (Indian network)
docker compose exec api analekh watch MUTHOOTFIN   # deep coverage for one company
docker compose exec api analekh build MUTHOOTFIN --out muthoot.xlsx
```

| | URL |
|---|---|
| API docs | http://localhost:8000/docs |
| Web app | http://localhost:5173 |

Without NSE access, load the universe from a file downloaded by hand:
`analekh universe load --file EQUITY_L.csv`.

### Python on the host, services in Docker

```bash
docker compose up -d postgres minio      # add redis for jobs; MinIO is built from source on first run
uv sync
uv run alembic upgrade head
uv run analekh universe load
uv run analekh search "tata mo"          # --limit N for more rows
uv run analekh refresh TATAELXSI         # one company's results from NSE's integrated filings
uv run analekh results-watch             # new results (ONE request to NSE; scheduled every 2 hours)
uv run analekh results-backfill --history --sector "Oil Gas & Consumable Fuels"   # 2023-2024 history
uv run analekh universe sectors          # NSE sectors from NSE Indices' published lists
```

> **`.env` hosts:** `.env.example` uses the container names (`postgres`, `redis`, `minio`),
> which only resolve inside Docker. When Python runs on the host, set `DATABASE_URL`,
> `REDIS_URL` and `MINIO_ENDPOINT` to `localhost`.

### Excel bridge (on the analyst's machine)

```bash
uv sync --group bridge
# .env: WATCH_FOLDERS=C:/Models;D:/Coverage  ANALEKH_API=http://<server>:8000
uv run python -m analekh.excel_bridge scan                   # find and identify models
uv run python -m analekh.excel_bridge link Muthoot.xlsx MUTHOOTFIN   # confirm a link
uv run python -m analekh.excel_bridge watch                  # keep models in step
uv run python -m analekh.excel_bridge apply 42 Muthoot.xlsx  # apply an approved change set
```

The bridge talks to the API at `ANALEKH_API`. It never runs macros and never overwrites the
original workbook; `SAVE_MODE=versioned` (the default) writes a new file per apply.

### Excel task pane (optional)

See [`office-addin/README.md`](office-addin/README.md).

## Development

### Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | latest | Python 3.12 (pinned in `.python-version`), dependencies, running everything |
| Docker Desktop | latest, WSL2 backend on Windows | PostgreSQL 16 + pgvector, Redis, MinIO |
| Node.js | 24 LTS (via [fnm](https://github.com/Schniz/fnm), pinned in `.node-version`) | `web/` and `office-addin/` |
| [pnpm](https://pnpm.io/) | pinned in `package.json` (`npm install -g pnpm`) | Front-end workspace and lockfile |
| Excel | desktop | Excel bridge (xlwings), optional |

LibreOffice and Tesseract are only needed when running the API outside Docker; the Docker
image installs both.

### Everyday commands

```bash
uv sync                  # dev group installs by default
uv run pytest -q         # DB tests need PostgreSQL + pgvector (docker compose up -d postgres)
uv run ruff check . && uv run ruff format --check . && uv run mypy analekh
uv run alembic upgrade head
pnpm install && pnpm dev                 # web app; proxies /api to :8000
pnpm lint && pnpm test && pnpm build     # front-end checks CI runs
pre-commit install       # ruff, gitleaks, no exchange files or workbooks
```

Run ruff, mypy and pytest before every commit. Pinned dependencies live in `uv.lock`, with
`requirements*.txt` exported from it (design doc Appendix G). Front-end types are generated from
the API: `pnpm api-types` (the API must be running). Commit `pnpm-lock.yaml` with any
`package.json` change.

## CI/CD

`.gitlab-ci.yml` runs lint, tests (PostgreSQL + Redis services), the web build, GitLab SAST,
secret detection and container scanning, audits `uv.lock` and `pnpm-lock.yaml` for known
vulnerabilities with OSV-Scanner (`dependency_audit`; GitLab's own dependency scanning needs the
Ultimate tier), and builds the image. Jobs that need
infrastructure run only once it is configured (CI/CD variables, all masked and protected):

| Job | Needs |
|---|---|
| `deploy_staging`, `dast` | `STAGING_URL`, a runner tagged `india` |
| `deploy_production` | `PRODUCTION_URL`, a release tag, manual approval |
| `mirror_to_github` | `GITHUB_MIRROR_TOKEN`, `GITHUB_MIRROR_USER`, `GITHUB_MIRROR_REPO` |

## Data rules

From design doc 23. These are not optional.

- Only NSE's **published RSS feeds**, the **published equity list CSVs** and the files they
  link to, NSE Indices' **published index constituent lists** (for sectors), NSE's
  **integrated-filing lookup** (approved by the owner on 2026-10-14) and its **financial-results
  list** (approved 2026-10-15): per company, plus ONE request every 2 hours without a ticker for
  the latest results. No other NSE page or internal endpoint, never crawling, and requests always
  identify as Analekh. `analekh/ingest/http.py` enforces a host and path allow-list (`/`,
  `/api/integrated-filing-results` and `/api/corporates-financial-results` on `www.nseindia.com`,
  `/IndexConstituent/` on `niftyindices.com`); widening it needs the owner's approval.
- Raw exchange files, user models and keys are **never committed** (`.gitignore` and the
  pre-commit hooks cover `data/`, `import/`, `out/`, `*.xlsx`, `.env`).
- Get written confirmation from NSE, or license a feed, before any public or commercial use.
- No buy/sell/hold ratings or target prices in anything shared.
