# Analekh

Pick any NSE-listed company. Analekh finds its results filings, extracts and validates the
numbers, builds a model from your own template (or updates the model you already keep),
writes to Excel only after you approve, and drafts the results flash, earnings note,
initiation, slides and comps with every number traced to its source.

Design: *Analekh Technical Design Document v1.0.1*. Section numbers in code comments refer to it.

Source control: GitLab is the source of truth; GitHub is a read-only mirror updated by CI
after a green pipeline on `main` (design doc 22.5).

## Status

This is a **skeleton of all phases**. Every engine has a working core and tests (green in CI),
but nothing has been run against real NSE data yet: the build sandbox could not reach NSE.
NSE's published archives are now reachable from a development machine, so Phase 0 is
unblocked. Search for `PHASE n` and `# verify` markers in the code for the exact gaps.

### Tracker

✅ verified on real data · 🟡 built, synthetic tests only · 🔲 to do · ⛔ blocked (reason given)

Keep this table current in the same merge request as the change, and add a line to the
dev log below.

**Next up**

1. Run the Phase 0 spike (`--limit 10`, then named symbols across sectors) and hand-check values.
2. Fill `xbrl/elements.py` from `elements.csv`, including the bank, NBFC and insurance tables.
3. Turn spike files into golden fixtures (`tests/fixtures/golden/`, gitignored) and run
   `analekh golden-test`.
4. Run the workbook reader and template onboarding on real templates and models.

| Phase (design doc 26) | Item | Status | Still needed |
|---|---|---|---|
| 0 Spike | NSE published archives reachable | ✅ | |
| | `scripts/phase0_spike.py` (lists, two feeds, XBRL parse + validate, element census) | 🟡 | First real run |
| | XBRL element names (`# verify` in `xbrl/elements.py`) | 🔲 | Confirm from `elements.csv` |
| | Bank, NBFC and insurance element tables | 🔲 | Empty; fill from `elements.csv` |
| | SME list path, feed `pubDate` format | 🔲 | Confirm from spike output |
| | V2 exceptional-items sign convention | 🔲 | Confirm on real filings |
| | Kite price pull | ⛔ | `KITE_*` keys |
| 1 Data layer | Universe loader (renames, delistings), search (pg_trgm) | 🟡 | Load the real equity list |
| | Watchlist and coverage levels | 🟡 | |
| | Feed watcher, polite fetcher, linking, storage | 🟡 | Run against live feeds |
| | XBRL parser, validation V1-V9 | 🟡 | Real fixtures |
| | Sector map (`data/sector_map.csv`), Nifty 500 list | 🔲 | Empty; open question 28.4 |
| | Backfill | 🟡 | First run |
| 2 Builder and sync | Workbook understanding engine | 🟡 | Real templates and models |
| | Template onboarding + test build | 🟡 | Real templates |
| | Built-in NBFC and consumer templates | 🟡 | P&L and KPIs only; balance sheet and cash flow 🔲 |
| | Coverage Builder (fill, propose assumptions, finalize) | 🟡 | |
| | Discovery and tags, change sets, headless apply | 🟡 | |
| | Excel bridge (xlwings) | 🟡 | First run on an analyst's machine |
| | Web review screens (change sets, assumptions, models, templates) | 🟡 | |
| 3 Document AI | PDF read, page classifier, KPI extraction with quote check, chunking, transcripts | 🟡 | API key, golden set, classifier tuning |
| | V10 (XBRL wins over KPI values) in `docs/pipeline.py` | 🔲 | Map KPI names to XBRL names |
| | Embeddings | ⛔ | Provider undecided (open question 28.7) |
| 4 GenAI outputs | Tools (incl. model reader), calc, grounding check | 🟡 | |
| | Report loop (flash, note, initiation), Q&A, Word/PowerPoint writers | 🟡 | Prompt tuning on 10 companies |
| | Reports as Celery jobs, files in object storage | 🔲 | Run inline in the API today |
| | Web Reports and Q&A screens | 🔲 | Placeholders |
| 5 Discovery, IB, polish | Comps | 🟡 | EBITDA, debt, cash, book value not sourced |
| | Profile slide, pitch refresh | 🟡 | Branded templates |
| | Alerts, Office.js task pane, Streamlit admin | 🟡 | |
| | Web Comps and Settings screens | 🔲 | Placeholders |
| | Demo | 🔲 | |
| CI/CD | GitLab pipeline (lint, tests, web, security scans, image) | ✅ | Green on `main` |
| | Staging and production deploys, DAST | ⛔ | Runner tagged `india`, `STAGING_URL`, `PRODUCTION_URL` |
| Platform | Python 3.12 everywhere (`.python-version`, CI, Dockerfile) | ✅ | |
| | Upgrade to Python 3.15 | ⛔ | Windows wheels for pyyaml, playa-pdf, zope-interface, numpy-financial |

### Dev log

Newest first. One line per notable change: what moved, and what it unblocks.

- **2026-10-13** First local development instance. NSE's published archives respond from it,
  so the Phase 0 spike can run. Pinned Python 3.12 in `.python-version` to match CI and the
  Dockerfile; 53 tests pass locally, 15 skip without PostgreSQL. Python 3.15 waits for Windows
  wheels of four dependencies (see the tracker); to upgrade, change `.python-version`, the
  Dockerfile and `.gitlab-ci.yml` together.
- **2026-10-12** Skeleton of all phases committed; GitLab CI added, first green pipeline on `main`.

## Quick start

```bash
cp .env.example .env            # fill in ANTHROPIC_API_KEY, USER_AGENT and storage keys
docker compose up -d            # postgres, redis, minio, api, worker, beat, web
docker compose exec api alembic upgrade head
docker compose exec api analekh universe load      # published NSE equity lists (Indian network)
docker compose exec api analekh watch MUTHOOTFIN   # deep coverage for one company
docker compose exec api analekh build MUTHOOTFIN --out muthoot.xlsx
```

Without NSE access, load the universe from a file downloaded by hand:
`analekh universe load --file EQUITY_L.csv`.

API docs: http://localhost:8000/docs. Web app: http://localhost:5173.

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

See `office-addin/README.md`.

## Development

Python 3.12, pinned in `.python-version` (`uv python install 3.12` if you don't have it).

```bash
uv sync                  # dev group installs by default
uv run pytest            # DB tests need PostgreSQL + pgvector (docker compose up -d postgres)
uv run ruff check . && uv run ruff format --check . && uv run mypy analekh
cd web && npm install && npm run dev
pre-commit install       # ruff, gitleaks, no exchange files or workbooks
```

Pinned dependencies: `uv.lock`, with `requirements*.txt` exported from it (design doc
Appendix G). Front-end types are generated from the API: `cd web && npm run api-types`.

## CI/CD (GitLab)

`.gitlab-ci.yml` runs lint, tests (PostgreSQL + Redis services), the web build, GitLab SAST,
secret detection, dependency and container scanning, and builds the image. Jobs that need
infrastructure run only once it is configured (CI/CD variables, all masked and protected):

| Job | Needs |
|---|---|
| `deploy_staging`, `dast` | `STAGING_URL`, a runner tagged `india` |
| `deploy_production` | `PRODUCTION_URL`, a release tag, manual approval |
| `mirror_to_github` | `GITHUB_MIRROR_TOKEN`, `GITHUB_MIRROR_USER`, `GITHUB_MIRROR_REPO` |

## Data rules (design doc 23)

- Only NSE's **published RSS feeds**, the **published equity list CSVs** and the files they
  link to, at the published TTL. Never NSE's internal JSON endpoints, never crawling.
  `analekh/ingest/http.py` enforces a host allow-list.
- Raw exchange files, user models and keys are never committed (`.gitignore` and the
  pre-commit hooks cover `data/`, `import/`, `out/`, `*.xlsx`, `.env`).
- Get written confirmation from NSE, or license a feed, before any public or commercial use.
- No buy/sell/hold ratings or target prices in anything shared.
