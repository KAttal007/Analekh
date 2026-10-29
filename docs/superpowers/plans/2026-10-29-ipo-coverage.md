# IPO Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store the three restated years (plus stub) from SEBI-filed RHPs and Prospectuses, and add an "IPO Coverage" tab to the Reports page that drafts MD&A, financial performance, sector performance, strengths and risks, and valuation context, with the rating and rationale left as analyst placeholders.

**Architecture:** A new `analekh/ipo/` package, separate from `Company` and `Filing` (an unlisted company has no NSE symbol). A daily watcher reads SEBI's RHP and Prospectus lists, downloads each entry's PDF, locates the restated statements, and extracts figures with Claude into versioned `ipo_financials` rows. A coverage generator runs the existing grounded tool loop once per section against IPO-specific tools. A new API router and a third report kind on the Reports page expose it.

**Tech Stack:** Python 3.13, SQLAlchemy 2 + Alembic, FastAPI, Celery, PyMuPDF (`docs/pdf.py`), `genai/client.py` (`Claude.create_json`), `genai/grounding.py`, React + TypeScript + vitest.

**Spec:** [docs/superpowers/specs/2026-10-29-ipo-coverage-design.md](../specs/2026-10-29-ipo-coverage-design.md)

## Global Constraints

- Sources are the RHP list (smid 11) and Prospectus list (smid 12) only, newest page only, one request a day each. smid 10 (DRHP) is never fetched. Entry pages once per new filing; PDFs from `/sebi_data/attachdocs/`. Never widen `ALLOWED_HOSTS` or `ALLOWED_PATHS` (rule 1). Requests go through `PoliteClient` only.
- Money is `Decimal` / `NUMERIC`, never float (rule 4). Amounts stored in full rupees. EPS stored in rupees per share.
- Consolidated and standalone are both stored and shown, neither preferred.
- Stub period stored when the document presents one. DRHP unused.
- GenAI text may contain only numbers from tool results or `calc`; `genai/grounding.py` blocks the rest and must not be weakened (rule 3).
- No target price anywhere. No AI-written rating. The rating and the rationale are marked placeholders: `[Analyst to set rating]` and `[Analyst rationale]`. The placeholder is rendered, never stored as a value.
- No em-dashes or en-dashes in drafts (rule 8).
- Every route needs a signed-in user: register the router with `dependencies=[Depends(get_user)]` like the others (rule 9). Limits and cron strings come from `config.py` settings.
- No downloaded PDFs, SEBI captures or keys in git (rule 6). Test fixtures are small synthetic HTML and PDFs built in the test.
- Run `uv run ruff check . && uv run ruff format . && uv run mypy analekh && uv run pytest -q` before each commit; commits are signed by the owner, so the executor gives the message and the owner runs the commit.
- After modifying code, run `graphify update .`.

## Review Focus

- A table stated in "Rs. in lakhs" or "Rs. in million" sitting next to a crore table: amounts must land in rupees, and a figure that disagrees with the same figure elsewhere by a power of ten must be flagged, not stored clean (Task 4).
- Brackets mean negative, a dash means nil, and column order may be oldest-first: `(1,234.5)` is -1234.5, `-` is 0, and years map to the right column (Task 4).
- RHP and Prospectus titles for one company differ slightly ("Ltd" vs "Limited", "Pvt"): they must still join one issue, and two different companies must never join (Task 2).
- The watcher run twice, or the same PDF listed under two entries: no duplicate documents or figures (Task 3).
- SEBI answers 403 or 429: the watcher stops the run and records it, never retries across entries (Task 3).
- One section with an ungrounded number: that section comes back blocked with the unmatched numbers, the others are unaffected, and a blocked section is never shown as clean (Task 7).

---

### Task 1: Tables, models and settings

**Files:**
- Create: `analekh/db/migrations/versions/0014_ipo_offers.py` (use the `new-migration` skill)
- Modify: `analekh/db/models.py` (append after `Report`), `analekh/config.py`
- Test: `tests/test_ipo_schema.py`

**Interfaces:**
- Produces (in `analekh.db.models`):
  - `IpoIssue(id, stem: str unique, name: str, symbol: str|None, company_id: int|None FK companies, created_at)`. `symbol` is entered by the analyst once NSE assigns it (at bid opening) or filled from the bhavcopy file after listing (matched by `issue_stem` against the bhavcopy company name); `company_id` follows when the symbol exists in `companies`.
  - `IpoDocument(id, issue_id FK, stage: 'rhp'|'prospectus', sebi_id: str unique, entry_url, pdf_url, file_sha256: str unique, storage_key, filed_on: date|None, page_count: int|None, status: 'new'|'read'|'extracted'|'flagged'|'failed', meta: dict (JSONB, default {}), created_at)`
  - `IpoFinancial(id, document_id FK, basis: 'consolidated'|'standalone', period_end: date, period_label: str, is_stub: bool, line: str, amount: Decimal NUMERIC(24,4), unit: 'INR'|'INR/share', page: int, flagged: bool default false)` with unique `(document_id, basis, period_end, line)`
  - `IpoChunk(id, document_id FK, page, ord, text, tsv Computed to_tsvector('english', text))` with a GIN index on `tsv`
  - `IpoDraft(id, issue_id FK, document_id FK, sections: dict (JSONB), created_by: str, created_at)`
- Produces (in `Settings`): `sebi_watch_cron: str = "30 8 * * *"`, `ipo_chunk_target_chars` reuses the existing chunking constants (no new setting).

- [ ] **Step 1: Write the failing test.** `test_ipo_schema.py::test_unique_figure_per_document_basis_period_line` inserts an issue, a document and one `IpoFinancial`, then a second with the same key and expects `IntegrityError`. `test_stage_and_status_checks` expects `IntegrityError` for `stage='drhp'` and for `status='bogus'`. `test_amount_is_decimal` reads a stored `Decimal("1234.5678")` back as the same `Decimal`.
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_schema.py -q`. Expected: FAIL (import error).
- [ ] **Step 3: Add the models** with `CheckConstraint`s on `stage`, `status`, `basis` and `unit`, then generate the migration with `uv run alembic revision --autogenerate -m "ipo offers"` and rename to `0014_ipo_offers.py`. Add `sebi_watch_cron` to `Settings`.
- [ ] **Step 4: Run** `uv run alembic upgrade head && uv run alembic check && uv run pytest tests/test_ipo_schema.py -q`. Expected: PASS.
- [ ] **Step 5: Commit message:** `Add IPO offer tables (issues, documents, financials, chunks, drafts)`.

---

### Task 2: SEBI list and entry-page parsing

**Files:**
- Create: `analekh/ipo/__init__.py`, `analekh/ipo/listing.py`
- Test: `tests/test_ipo_listing.py`

**Interfaces:**
- Produces:
  - `@dataclass ListEntry: sebi_id: str, title: str, entry_url: str, filed_on: date | None, stage: str`
  - `parse_list(html: str, stage: str) -> list[ListEntry]`: rows in page order (newest first). `sebi_id` is the number after the final `_` in the entry URL (`..._105427.html` gives `"105427"`). `entry_url` is absolute (`https://www.sebi.gov.in/filings/public-issues/...`).
  - `pdf_url(entry_html: str, entry_url: str) -> str`: the PDF under `/sebi_data/attachdocs/`, absolute. SEBI embeds it as `<iframe src='../../../web/?file=https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/<id>.pdf'>`; take the `file=` value and check host and path against the allow-list. Raises `ValueError` if none or if it points elsewhere.
  - `parse_list` reads the date as `Mon D, YYYY` and takes only the first anchor of a row (RHP rows nest an abridged-prospectus link under `/sebi_data/commondocs/`, which is not used and not allowed).
  - `issue_stem(title: str) -> str`: lowercase; drop punctuation; drop the stage words (`rhp`, `prospectus`, `red herring`, `draft`), drop company-form words (`ltd`, `limited`, `pvt`, `private`, `inc`); collapse spaces. Example: `issue_stem("Jio Platforms Limited - Prospectus") == "jio platforms"`, and `"Jio Platforms Ltd."` gives the same.

- [x] **Step 1: Capture the real layout. Done 2026-10-29** (Jio Platforms Limited, RHP 105274 of 15 Oct and Prospectus 105427 of 26 Oct; captures in gitignored `out/sebi-captures/`). Findings are in the spec ("Still to confirm" section): row markup, nested abridged link in RHP rows, en dash in the RHP title, a Prospectus is a new entry, PDF in an iframe `file=` parameter. Copy them as a comment at the top of `listing.py`.
- [ ] **Step 2: Write the failing tests** with trimmed synthetic HTML in the test file, copied in shape from the capture (including the nested anchor in the RHP row and the iframe): `test_parse_list_returns_entries_in_order` (two rows, checks `sebi_id`, absolute `entry_url`, `filed_on`), `test_parse_list_ignores_nested_abridged_link`, `test_pdf_url_from_entry_page`, `test_pdf_url_missing_raises`, `test_pdf_url_off_allow_list_raises`, `test_issue_stem_joins_ltd_and_limited` (`"Jio Platforms Limited – RHP"` and `"Jio Platforms Ltd.- Prospectus"` give one stem), `test_issue_stem_keeps_different_companies_apart` (`"Jio Platforms"` vs `"Jio Financial Services"`).
- [ ] **Step 3: Run** `uv run pytest tests/test_ipo_listing.py -q`. Expected: FAIL.
- [ ] **Step 4: Implement** `parse_list`, `pdf_url`, `issue_stem` with lxml (already a dependency). No fetching here; this module is pure.
- [ ] **Step 5: Run** the tests. Expected: PASS. Commit message: `Parse SEBI offer-document lists and entry pages`.

---

### Task 3: The SEBI watcher

**Files:**
- Create: `analekh/ipo/watch.py`
- Modify: `analekh/jobs/tasks.py` (new task), `analekh/jobs/app.py` (beat entry), `analekh/cli.py` (command)
- Test: `tests/test_ipo_watch.py`

**Interfaces:**
- Consumes: `parse_list`, `pdf_url`, `issue_stem` (Task 2); `PoliteClient`, `refused` from `analekh.ingest.http`; `default_store`, `sha256`, `storage_key`, `pack` from `analekh.ingest.storage`; `IpoIssue`, `IpoDocument` (Task 1).
- Produces:
  - `STAGE_SMID = {"rhp": 11, "prospectus": 12}`; `list_url(stage: str) -> str`.
  - `@dataclass WatchResult: new: int, skipped: int, failed: int, stopped: str | None`
  - `watch(session: Session, store: ObjectStore, client: PoliteClient) -> WatchResult`: for each stage fetch the list once; for each entry whose `sebi_id` is not in `ipo_documents`, fetch its entry page, then the PDF, store it under `storage_key("ipo", digest, "pdf")`, find or create the `IpoIssue` by `issue_stem`, and insert the `IpoDocument` with `status='new'`. A PDF whose `file_sha256` already exists is skipped. On `refused(exc)` stop the whole run, return `stopped=str(exc)`.
  - Celery task `watch_sebi_offers() -> dict` on the `sebi_watch_cron` schedule; CLI `analekh ipo-watch`.

- [ ] **Step 1: Write failing tests** with an `httpx.MockTransport` through `PoliteClient(transport=...)` and `LocalStore(tmp_path)`: `test_new_entries_become_documents`, `test_second_run_adds_nothing`, `test_same_pdf_under_two_entries_stored_once`, `test_rhp_and_prospectus_join_one_issue`, `test_403_stops_the_run` (first entry page answers 403: `stopped` is set and no later entry is requested), `test_drhp_list_is_never_requested` (assert no request URL contains `smid=10`).
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_watch.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `watch` and `list_url`; record each run with `jobs.status.record("ipo_watch", ...)` as `watch_results` does. Add the task, the beat entry using `_cron(settings.sebi_watch_cron)`, and the CLI command.
- [ ] **Step 4: Run** the tests. Expected: PASS. Commit message: `Watch SEBI's RHP and Prospectus lists`.

---

### Task 4: Locate and extract the restated statements

**Files:**
- Create: `analekh/ipo/statements.py`
- Test: `tests/test_ipo_statements.py`

**Interfaces:**
- Consumes: `PageText`, `read_pages`, `subset` (`analekh.docs.pdf`); `Claude.create_json` (`analekh.genai.client`).
- Produces:
  - `LINES: tuple[str, ...]` = `revenue_from_operations, other_income, total_income, total_expenses, finance_costs, depreciation, profit_before_tax, tax_expense, profit_after_tax, eps_basic, eps_diluted, total_assets, total_equity, total_borrowings, cash_from_operations, cash_from_investing, cash_from_financing`.
  - `UNIT_FACTORS: dict[str, Decimal]` = `INR 1, INR thousand 1e3, INR lakh 1e5, INR million 1e6, INR crore 1e7, INR billion 1e9`.
  - `select_statement_pages(pages: list[PageText]) -> list[int]`: 1-based page numbers whose text matches "restated (consolidated |standalone )?(financial information|statement of (profit and loss|assets and liabilities|cash flows))" or "summary of (restated )?financial information", ranked by numeric density, at most 40 pages, in page order.
  - `@dataclass ExtractedFigure: basis: str, period_end: date, period_label: str, is_stub: bool, line: str, amount: Decimal, unit: str, page: int, flagged: bool = False`
  - `to_rupees(raw: str, unit_label: str) -> Decimal`: `"(1,234.5)"` gives `-1234.5 * factor`; `"-"` and `"—"` give `0`; raises `ValueError` on an unknown unit label or text that is not a number.
  - `extract_figures(claude: Claude, pdf: bytes, page_numbers: list[int]) -> list[ExtractedFigure]`: sends `subset(pdf, page_numbers)` text with a JSON schema (`additionalProperties: false`; numbers returned as strings, with each table's stated unit label and source page), converts with `to_rupees`.
  - `check_figures(figures: list[ExtractedFigure]) -> list[str]`: returns problems and sets `flagged=True` on the offending figures: (a) `total_income - total_expenses` differs from `profit_before_tax` by more than 1 percent; (b) `profit_before_tax - tax_expense` differs from `profit_after_tax` by more than 1 percent; (c) the same `(basis, period_end, line)` appearing twice with amounts whose ratio is an exact power of ten (a unit slip, the V11 pattern).
  - `store_figures(session, document: IpoDocument, figures: list[ExtractedFigure]) -> None`: inserts `IpoFinancial` rows and sets `document.status` to `extracted`, or `flagged` when any figure is flagged.

- [ ] **Step 1: Write failing tests**: `test_to_rupees_lakh_crore_million`, `test_brackets_are_negative_and_dash_is_zero`, `test_unknown_unit_raises`, `test_select_pages_finds_restated_statements` (a PDF built with `make_pdf` from `tests/test_docs.py` style, three pages: cover, restated P&L with numbers, risk factors), `test_check_flags_unit_slip` (same revenue 100 times too small in a second table: both flagged, `document.status == "flagged"`), `test_check_flags_pbt_mismatch`, `test_extract_orders_years_by_period_end_not_column` (a fake `Claude` returning columns oldest-first), `test_stub_period_is_marked`.
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_statements.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Use `Decimal` throughout; `check_figures` skips a check when either side is missing. The fake `Claude` in tests only needs `create_json(purpose, schema, **kw) -> dict`.
- [ ] **Step 4: Run** the tests. Expected: PASS. Commit message: `Extract restated statements from offer documents`.

---

### Task 5: Read a document end to end, with versions and restatements

**Files:**
- Create: `analekh/ipo/read.py`, `analekh/ipo/versions.py`
- Modify: `analekh/jobs/tasks.py` (task `read_ipo_documents`), `analekh/cli.py` (`analekh ipo-read`)
- Test: `tests/test_ipo_versions.py`

**Interfaces:**
- Consumes: Task 4 functions; `chunk_pages` (`analekh.docs.chunking`); `IpoChunk`.
- Produces:
  - `read_document(session: Session, store: ObjectStore, claude: Claude, document: IpoDocument) -> None`: loads the PDF, `read_pages`, stores `IpoChunk` rows (`chunk_pages`), sets `page_count`, runs `select_statement_pages`, `extract_figures`, `check_figures`, `store_figures`, then `terms.extract_terms` (Task 6) into `document.meta["terms"]`. Any exception sets `status='failed'` and `meta["error"]`; one failing document never stops the others.
  - `read_pending(session, store, claude) -> int`: runs `read_document` for each document with `status='new'`, each in its own savepoint.
  - `@dataclass Restatement: basis: str, period_end: date, line: str, old: Decimal, new: Decimal`
  - `restatements(session: Session, issue_id: int) -> list[Restatement]`: compares the Prospectus figures with the RHP figures of the same issue by `(basis, period_end, line)`; only differing amounts, in `period_end` then `line` order. Empty when the issue has only one stage.
  - `current_document(session, issue_id) -> IpoDocument | None`: the Prospectus if present, else the RHP.

- [ ] **Step 1: Write failing tests**: `test_prospectus_figures_supersede_rhp` (`current_document` returns the Prospectus), `test_restatements_list_only_changed_amounts`, `test_no_restatements_with_one_stage`, `test_failed_document_does_not_stop_the_batch`, `test_chunks_are_searchable` (full-text query on `tsv` finds a page).
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_versions.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the four functions as specified. `read_pending` is called from the watcher task after `watch`.
- [ ] **Step 4: Run** the tests. Expected: PASS. Commit message: `Read offer documents into versioned figures`.

---

### Task 6: Offer terms and peers

**Files:**
- Create: `analekh/ipo/terms.py`
- Test: `tests/test_ipo_terms.py`

**Interfaces:**
- Consumes: `Claude.create_json`, `PageText`, `to_rupees`.
- Produces:
  - `select_terms_pages(pages: list[PageText]) -> list[int]`: pages matching "price band", "basis for offer price", "comparison with listed industry peers", "objects of the offer", capped at 20.
  - `extract_terms(claude: Claude, pdf: bytes, page_numbers: list[int]) -> dict`: returns `{"price_band_low": str, "price_band_high": str, "face_value": str, "fresh_issue_amount": str, "offer_for_sale_amount": str, "post_issue_shares": str, "peers": [{"name": str, "pe": str|None, "eps": str|None, "ronw": str|None, "page": int}], "page": int}`. All numbers are strings (Decimal-safe), amounts converted to rupees with `to_rupees`.

- [ ] **Step 1: Write failing tests**: `test_select_terms_pages`, `test_terms_amounts_in_rupees` (crore amount returns rupees), `test_peers_kept_with_page`, `test_missing_price_band_returns_none_not_zero`.
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_terms.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** with a JSON schema, `additionalProperties: false`.
- [ ] **Step 4: Run** the tests. Expected: PASS. Commit message: `Extract price band and peers from offer documents`.

---

### Task 7: IPO tools and the coverage generator

**Files:**
- Create: `analekh/ipo/tools.py`, `analekh/ipo/coverage.py`
- Modify: `analekh/genai/reports.py` (`run_report` gets three keyword-only parameters)
- Test: `tests/test_ipo_coverage.py`

**Interfaces:**
- Consumes: `ToolExecutor` (for `_t_calc`), `run_report`, `check`, `current_document`, `IpoFinancial`, `IpoChunk`, `IpoDraft`.
- Produces:
  - `run_report(..., *, tools: list[dict] = TOOL_DEFS, system_text: str = SYSTEM, prompt: str | None = None)`: when `prompt` is given it is used instead of `PROMPTS[kind]`. Defaults keep every existing call unchanged.
  - `IPO_TOOL_DEFS`: `calc` (reused definition), `get_ipo_financials(basis: 'consolidated'|'standalone', lines: [str])` returning rows `{period_label, period_end, line, amount, unit, source: "ipo_doc:<id> page:<n>"}`, `get_offer_terms()` returning `document.meta["terms"]` with a `source`, `search_offer_text(query: str, k: int)` returning `{page, text, source}` from `ipo_chunks` full-text.
  - `IpoToolExecutor(session: Session, issue_id: int)`, a `ToolExecutor` subclass adding `_t_get_ipo_financials`, `_t_get_offer_terms`, `_t_search_offer_text`; reads only the issue's current document.
  - `SECTIONS = ("mdna", "financial_performance", "sector_performance", "strengths_and_risks", "valuation")`; `RATING_PLACEHOLDER = "[Analyst to set rating]"`; `RATIONALE_PLACEHOLDER = "[Analyst rationale]"`.
  - `@dataclass SectionResult: key: str, text: str, blocked: bool, unmatched: list[str], style_issues: list[str], tool_calls: list[dict]`
  - `generate(session: Session, claude: Claude, issue_id: int, user: str) -> IpoDraft`: raises `ValueError("no offer document yet")` when the issue has no extracted RHP or Prospectus; drafts from `current_document` (the Prospectus if present, else the RHP) and records its stage in `IpoDraft.sections["stage"]`; runs one `run_report` per section with `IPO_TOOL_DEFS` and a section prompt (valuation prompt: compute multiples at the price band against the document's own peers with `calc`, never state a target price or a rating); stores `IpoDraft.sections` as `{key: SectionResult as dict, "rating": RATING_PLACEHOLDER, "rationale": RATIONALE_PLACEHOLDER}`. A section's `style_issues` lists any `—` or `–` found in its text.

- [ ] **Step 1: Write failing tests** with the `FakeClaude` pattern from `tests/test_genai.py`: `test_generate_works_from_rhp_alone` (stage recorded as `rhp`), `test_generate_needs_a_document` (none extracted: `ValueError`), `test_each_section_grounded_separately` (one fake text carries an unmatched number: only that section is `blocked`, with `unmatched` set), `test_blocked_section_is_never_clean` (`blocked` is true and `text` is kept for the analyst to see), `test_placeholders_present_and_no_value_stored` (draft has both placeholders; no key holds a rating or price), `test_dash_is_flagged`, `test_tool_reads_only_current_document` (figures from the RHP are not returned once a Prospectus exists), `test_run_report_defaults_unchanged` (existing `tests/test_genai.py` still passes).
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_coverage.py tests/test_genai.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** The section prompts name the section, the tools to use, and the rule "state only numbers returned by a tool; no rating, no target price, no em-dashes". Reuse `SYSTEM` for `system_text`.
- [ ] **Step 4: Run** the tests. Expected: PASS. Commit message: `Generate IPO coverage sections with grounding per section`.

---

### Task 8: API

**Files:**
- Create: `analekh/api/routers/ipo.py`
- Modify: `analekh/api/main.py` (register next to `outputs`), `analekh/api/schemas.py`
- Test: `tests/test_ipo_api.py`

**Interfaces:**
- Consumes: Tasks 1, 5, 7.
- Produces (all behind `get_user`):
  - `GET /ipo/issues` -> `[{id, name, stages: ["rhp","prospectus"], current_stage, status, filed_on, company_symbol}]`, newest first.
  - `GET /ipo/issues/{id}` -> `{id, name, current_stage, financials: {consolidated: [...], standalone: [...]}, restatements: [...], terms}`; each financial row `{period_label, period_end, is_stub, line, amount, unit, page, flagged}`; amounts as strings.
  - `POST /ipo/issues/{id}/coverage` -> the draft (`{draft_id, stage, sections, rating, rationale}`); 409 `{"detail": "no offer document yet"}` when nothing is extracted.
  - `GET /ipo/issues/{id}/coverage` -> latest draft or 404.
  - `POST /ipo/issues/{id}/symbol` body `{symbol: str}` -> sets `symbol` (validated: uppercase letters, digits, `&`, `-`, at most 20 characters) and `company_id` when the symbol exists in `companies`. Also, `ipo.symbols.link_listed(session)` (run after `analekh prices`) fills `symbol` from the bhavcopy rows by `issue_stem` match, only when exactly one candidate matches.

- [ ] **Step 1: Write failing tests** with the `client`/`db` fixtures from `tests/test_api.py`: `test_requires_sign_in` (401 on all five routes with no session), `test_issues_list_newest_first`, `test_detail_shows_both_bases_and_restatements`, `test_coverage_409_without_document`, `test_coverage_returns_placeholders` (monkeypatch `generate`), `test_symbol_is_validated`, `test_bhavcopy_link_needs_one_match` (two candidates: no link).
- [ ] **Step 2: Run** `uv run pytest tests/test_ipo_api.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the router and schemas; `coverage` runs inline, the same way `/reports` does today.
- [ ] **Step 4: Run** the tests, then `uv run alembic check`. Expected: PASS. Commit message: `Add IPO coverage API`.

---

### Task 9: The IPO Coverage tab

**Files:**
- Modify: `web/src/pages/Reports.tsx`, `web/src/api/client.ts`; regenerate `web/src/api/schema.d.ts`
- Create: `web/src/pages/IpoCoverage.tsx`, `web/src/pages/IpoCoverage.test.tsx`

**Interfaces:**
- Consumes: Task 8 routes via new `api.ipoIssues()`, `api.ipoIssue(id)`, `api.ipoCoverage(id)`, `api.generateIpoCoverage(id)`.
- Produces:
  - `Kind` in `Reports.tsx` becomes `"quarterly" | "initiating" | "ipo"`; the Segmented control gets a third option `{ value: "ipo", label: "IPO coverage" }`; `?kind=ipo` selects it. For `ipo` the page renders `<IpoCoverage />` in place of the company, quarter and input cards; the other kinds are unchanged.
  - `IpoCoverage()`: an issue picker (name, stage badge), the existing `Basis` control (consolidated, standalone, both; default both when both exist), a financials table (rows are lines, columns are years then the stub, amounts in rupees crore for display), a restatements list when present, a "Generate coverage" button (enabled once the issue has an extracted RHP or Prospectus; the draft shows which stage it came from), a symbol field, the five generated sections each with a "Blocked: unmatched numbers" badge when blocked, and the two placeholders rendered as visibly marked blanks.

- [ ] **Step 1: Write failing tests** (vitest, `mockApi`/`renderAt` from `web/src/test-utils`): `shows the three years and the stub for both bases`, `generate is enabled for an RHP-only issue and the draft names its stage`, `a blocked section shows its unmatched numbers`, `the rating and rationale are marked blanks`, `?kind=ipo selects the tab and the other kinds are unchanged`.
- [ ] **Step 2: Run** `pnpm test -- IpoCoverage`. Expected: FAIL.
- [ ] **Step 3: Implement.** With the API running, `pnpm api-types`. Follow the existing page's `Segmented`, `Badge`, `PageHeader`, `EmptyState` components and the motion rule (tabs slide, data appears instantly).
- [ ] **Step 4: Run** `pnpm lint && pnpm test && pnpm build`. Expected: all pass. Commit message: `Add the IPO Coverage tab to Reports`.

---

### Task 10: Records and full checks

**Files:**
- Modify: `docs/design/deviations.md` (new section 13), `Commit-Info.md` (top entry), `docs/pending-items.md`, `docs/roadmap.md` (4.1 state), `docs/superpowers/specs/2026-10-29-ipo-coverage-design.md` (decision 4)

- [ ] **Step 1: Record departures in `deviations.md`:** the IPO issue is its own table and is not added to `companies`; it links by symbol (entered at bid opening, or taken from bhavcopy after listing); extraction of restated statements uses Claude with Decimal-safe string numbers; section-by-section generation for this report only.
- [ ] **Step 2: Add the `Commit-Info.md` entry** (what moved, what it unblocks) and update `pending-items.md` and `roadmap.md` 4.1.
- [ ] **Step 3: Run** `/check` (ruff, mypy, pytest, alembic check, web lint/test/build) and `graphify update .`. Expected: all green.
- [ ] **Step 4: Security.** This adds a new outbound source and a new route set. Code to rule 11 (secure by default) throughout; the owner decides when a formal audit runs (rule 10). Commit message: `Record IPO coverage in deviations, roadmap and pending items`.

---

## Self-review

- **Spec coverage:** three years plus stub (Task 4); both bases equal (Tasks 4, 8, 9); source flow, RHP and Prospectus only, DRHP never fetched (Tasks 2, 3); versions, restatements, Prospectus supersedes RHP (Task 5); XBRL precedence needs no code because offer figures live in their own table and the tab shows only offer-document figures; sections, grounding per section, valuation without target (Tasks 6, 7); rating and rationale placeholders rendered, not stored (Task 7, 9); Reports tab (Task 9); linking by symbol (Task 8); records (Task 10). Word export is not built (the spec only asks for placeholders "in any export", and no export is requested).
- **Types:** `ListEntry`, `ExtractedFigure`, `Restatement`, `SectionResult` and the function names are used identically across tasks.
- **Departure from the spec (spec decision 4 now matches):** the IPO is not added to the `companies` table until it has a symbol. Drafting works from the RHP (owner, 29 October).
