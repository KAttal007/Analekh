# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

Analekh (`analekh/`): any NSE-listed company in; validated XBRL facts, a built or updated Excel
model (analyst-approved) and grounded research drafts out. Section numbers in comments (e.g.
"design doc 12.3") refer to *Analekh Technical Design Document v0.0.4*
(`docs/design/technical-design.md`; the `.docx` and the architecture PDF are generated from it and
`architecture.html` with `scripts/design_docx.py` and `scripts/diagram_panels.py`; earlier versions
are kept as the record). Record every departure from it in `docs/design/deviations.md`.

Versions follow the build phases (design doc 26): v0.0.x during Phase 0, v0.1.x once Phase 0 is
complete, v0.2.x once Phase 1 is complete, and so on; v1.0.0-pre-release is the first release for
proper testing. "v1" in the design doc means that first release.

GitLab (`kaushal-self/Kaushal-Analekh`) is the source of truth. GitHub is a read-only mirror
fed only by the `mirror_to_github` CI job: never push to GitHub directly (design doc 22.5).

## Commands

```bash
uv sync                                   # install (dev group is the default)
uv run pytest -q                          # all tests; DB tests skip if PostgreSQL is down
uv run ruff check . && uv run ruff format . && uv run mypy analekh
docker compose up -d postgres             # PostgreSQL 16 + pgvector + pg_trgm for DB tests
docker compose up -d minio                # object storage (built from source on first run)
uv run alembic upgrade head               # migrations (analekh/db/migrations)
uv sync --group audio                     # Whisper for call recordings (analekh transcribe-audio)
uv run alembic revision --autogenerate -m "..."   # after changing analekh/db/models.py
uv run analekh --help                     # CLI: universe, search, watch, template, build, sync
uv run analekh recompute-latest          # newest FILED value of each line in use (after imports)
uv run python scripts/phase0_spike.py --limit 10  # needs NSE access (Indian network)
pnpm install                              # front ends (pnpm workspace: web/, office-addin/)
pnpm dev                                  # web app, proxies /api to :8000
pnpm api-types                            # regenerate web/src/api/schema.d.ts (API must be running)
pnpm lint && pnpm test && pnpm build      # what CI runs for the front ends
```

Run ruff, mypy and pytest before every commit; CI also runs `alembic check`, the web lint, tests
and build, GitLab's SAST, secret detection and container scanning, and an OSV-Scanner audit of
`uv.lock` and `pnpm-lock.yaml` (GitLab's own dependency scanning needs Ultimate). After changing
dependencies, run `uv lock` and re-export the `requirements*.txt` files (Appendix G):
`uv export --no-hashes --no-emit-project --frozen [--only-group bridge|optional|dev]`.
Front ends use pnpm (version pinned in the root `package.json`, Node 24 in `.node-version`);
commit `pnpm-lock.yaml` with any `package.json` change.

## Layout (request flow order)

- `universe/` loader (published equity and SME lists, renames, delistings), sectors (curated
  map, then published index lists -> sector; strong signals only -> results taxonomy), search (symbol, ISIN, pg_trgm name). `coverage.py` = watchlist and
  coverage levels (universe / numbers / deep).
- `ingest/` feeds (RSS watcher), integrated (NSE integrated-filing lookup: results XBRL per
  company), http (polite client + host allow-list), linking (feed item ->
  company), storage (hash-keyed S3/local), pipeline (hash -> parse -> validate -> facts,
  restatements), backfill.
- `xbrl/` lxml instance parser, element vocabulary per taxonomy. `validate/rules.py` V1-V10.
- `docs/` PDF read, page classifier, Claude KPI extraction, chunking, embeddings, transcripts.
- `facts.py` = one place that resolves a mapping row to a sourced value (XBRL, then KPI).
- `workbook/` understanding engine (design doc 12): periods (axis, A/E flags), labels
  (synonyms -> fuzzy -> AI, with confidence), reader (structure map, drivers, checks), mapping
  (Appendix B YAML), dependency graph, hygiene, fingerprint, tags (hidden custom properties),
  recalc (formulas lib / LibreOffice), locate, checks.
- `templates/` onboarding (upload, confirm mapping, test build, activate) and
  `templates_builtin/` (NBFC, consumer) generated from specs.
- `builder/` Coverage Builder: fill history with sources, propose assumptions, finalize.
- `discovery.py` identifies the company behind a workbook (tag, file name, contents).
- `modelsync/` change-set builder and headless apply for quarterly updates.
- `excel_bridge/` CLI on the analyst's machine: scan folders, link, watch, apply (xlwings).
- `genai/` Claude client (token logging, refusal fallbacks), tools (incl. `ModelReader`), calc,
  grounding check, report loop (flash, note, initiation), Q&A, Word/PowerPoint writers.
- `ib/` comps, profile slide, pitch refresh. `alerts/`. Daily prices: `ingest/bhavcopy.py`
  (NSE's bhavcopy after each close; market cap = close x shares from the latest results filing).
- `api/` FastAPI app with routers (design doc 20). `jobs/` Celery app, beat schedule, tasks.
  `cli.py` typer CLI. `admin/` Streamlit ops dashboard. `golden.py` golden-set runner.
- `web/` React + TypeScript (types generated from OpenAPI). `office-addin/` Excel task pane.

## Rules that must not be broken

1. **NSE access**: only the published RSS feeds, the published equity list CSVs and the files
   they link to, plus NSE Indices' published constituent CSVs (`niftyindices.com`, limited to
   `/IndexConstituent/` by `ALLOWED_PATHS`; added 2026-10-13 for sectors), plus the
   integrated-filing lookup on `www.nseindia.com`, limited by `ALLOWED_PATHS` to `/` (home page
   only, for cookies), `/api/integrated-filing-results` (approved by the owner 2026-10-14: the
   results feed stopped carrying filings) and `/api/corporates-financial-results` (approved by the
   owner 2026-10-15: results history before integrated filings, XBRL back to 2018). Both are
   queried per company, plus ONE request every 2 hours without a ticker for the latest results
   (`analekh results-watch`; owner's limit, once a day from 2026-10-14, every 2 hours from
   2026-10-16). NSE's daily bhavcopy on nsearchives (`/content/cm/BhavCopy_NSE_CM_…csv.zip`): ONE
   file per trading day after the close, for closing prices (`analekh prices`; approved by the owner
   2026-10-17; no live prices). Only the latest day's prices are kept: each file replaces the
   previous day's (owner's rule, 2026-10-18).
   No other NSE website page or internal API: never widen
   `ALLOWED_HOSTS` / `ALLOWED_PATHS` in `analekh/ingest/http.py` without the owner's approval;
   never crawl pages. Requests identify as Analekh: never disguise them as a browser.
2. **Human in the loop**: nothing writes to an analyst's model without an approved change set
   (sync) or approved assumptions (build). The original workbook is never overwritten; every
   write saves a new `model_versions` row. A new model-to-company link needs user confirmation.
3. **Grounded GenAI**: generated text may only contain numbers from tool results or `calc`.
   `genai/grounding.py` blocks anything else. Do not weaken it to make output pass.
4. **Money is Decimal / NUMERIC**, never float, except at the Excel boundary.
5. **XBRL wins** over AI-extracted values (V10). Contexts are resolved by dates, never by id.
6. **No raw exchange files, user models, keys or downloaded filings in git.**
7. **Macros are never executed**; `.xlsm` files are read with VBA kept but never run.
8. No ratings or target prices in outputs.

## Where the skeleton stops

Search for `PHASE 0` .. `PHASE 5` and `# verify`:

- `xbrl/elements.py`: names marked `# verify` were never checked against a real file. Bank and
  general- and life-insurer tables come from real integrated filings; the insurers' balance
  sheet is not mapped yet. After changing tables or rules, run `analekh revalidate`.
- `universe/loader.py`: SME list path unconfirmed. `universe/sectors.py`: index list file names
  and columns checked against niftyindices.com on 2026-10-16 (the importer has not been run);
  `data/sector_map.csv` holds overrides only. `universe/data/nifty500.csv` (backfill priority) is still empty.
- Test fixtures (`tests/xbrl_factory.py`, built-in templates) are SYNTHETIC. Put real files
  under `tests/fixtures/golden/` (gitignored unless licensing is clear) with a `manifest.yaml`
  and run `uv run analekh golden-test`.
- `templates_builtin/specs.py`: P&L and KPIs only; balance sheet and cash flow need annual
  backfill.
- `docs/pipeline.py`: V10 not wired; embeddings provider undecided (open question 28.7).
- `ib/comps.py`: EBITDA, debt, cash, book value not yet sourced.
- Reports run inline in the API; move to Celery jobs and store files in object storage.

## Claude API usage

All calls go through `analekh/genai/client.py` (`Claude.create`), which sets the model from
`CLAUDE_MODEL`, enables server-side refusal fallbacks (`fallbacks="default"`, beta
`server-side-fallback-2026-07-01`), and logs tokens to `llm_calls`. Structured output uses
`output_config.format` JSON schemas with `additionalProperties: false`. Backfill extraction uses
the Batch API (`docs/extract.py: batch_params`, no fallbacks on batches). Label matching that
falls through to AI uses `CLAUDE_SMALL_MODEL`.
