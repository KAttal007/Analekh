# Deviations from the Technical Design

The current design is **v0.0.2** ([technical-design.md](technical-design.md); the formatted
original is `Analekh - Technical Design v0.0.2.docx`). Record here every place the build departs
from it, with the section number, what changed, why and when, and fold the list into the next
version of the document.

Status: ✅ done · 🟡 partly done · 🔲 decided, not built · 💬 proposed, not decided

## Since v0.0.2

| Design says | Now | Why | Date |
|---|---|---|---|
| MinIO from the `minio/minio` image (Appendix D, 22.1) | `docker compose` builds MinIO from source: `deploy/minio/Dockerfile`, pinned to `RELEASE.2025-10-15T17-29-55Z` (image `analekh-minio`, about 165 MB). | MinIO no longer publishes community images; `minio/minio` can't be pulled. Same AGPL-3.0 licence note (G.9). | 2026-10-14 |
| (not specified) | Object storage fails fast: 2 s connect timeout, one attempt; the API answers 503 "object storage not reachable" instead of hanging. One store per API process instead of one per request. | Template, model, change-set and report endpoints hung for 13 s or more while MinIO was down. | 2026-10-14 |

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

### 11. Proposed, not decided

| Area | Proposal |
|---|---|
| Report generation (17) | Today `genai/reports.py` runs one open tool loop per report (all tools, up to 20 turns). Proposal: fixed workflows for the flash; section-by-section runs for the note, IC note and initiation (outline from a report template, core data pre-fetched by code, a short tool loop per section, grounding check per section so one section can be redone); keep the open loop for Q&A and red-flag digging. |
| Python 3.15 | Blocked on Windows wheels for pyyaml, playa-pdf (via camelot-py) and numpy-financial. |
