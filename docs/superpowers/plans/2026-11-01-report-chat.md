# Report Chat, Publishing and Lasting Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the report chat thread (draft in chat, typed edits, approve to Word or PowerPoint, publish the final file), the learning record with tested lessons and an upgrade check, and the Q&A page on the same chat window.

**Architecture:** A thread holds a model-neutral JSON draft, versioned in MinIO with Postgres index rows. Chat turns run as Celery jobs under a per-thread lock, and every AI change passes the grounding and style checks. Approval builds the file through a writer; publishing reads the final file's XML safely (never opened in Office, macros never parsed) and feeds a learning job that proposes lessons. Lessons are plain text with tests, applied to every model.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 and Alembic, PostgreSQL 16, Celery, MinIO, lxml, python-docx, python-pptx, Anthropic client via `genai/client.py`; React, TypeScript, TanStack Query, ECharts; Office.js for the add-in (phase 10B only).

**Spec:** `docs/superpowers/specs/2026-11-01-report-chat-design.md` (approved 1 November 2026). Deviations: `docs/design/deviations.md` section 16.

## Global Constraints

- Rule 2: nothing writes to a model without approval; the original workbook is never overwritten.
- Rule 3: generated text contains only numbers from tool results or `calc`; `genai/grounding.py` is never weakened.
- Rule 4: money is `Decimal` or `NUMERIC`, never float.
- Rule 7: macros are never run; `.docm` and `.pptm` are stored byte for byte, the VBA part is never parsed.
- Rule 8: the AI never writes a rating, target price or guidance; these are masked from training data and examples.
- Rule 9: every route needs a signed-in user; every thread, message, version and file checked against its owner; limits come from `config.py` settings, never literals.
- Rule 11: validate every input at the boundary; parameterised queries only; no secrets or draft text in logs; size and time limits on files, bodies and loops; fail closed.
- Outbound requests: none added in this plan. No new host in `ALLOWED_HOSTS`.
- Every model call goes through `analekh/genai/client.py` (`Claude.create`) and is logged in `llm_calls`.
- No em-dashes in any generated text.
- Commits: the owner signs commits. The implementer writes the commit message and command for the owner; never runs `git commit`.

## Review Focus

1. **Analyst types a number that is correct but never fetched** → it is shown as "not sourced" only if it matches nothing in the company's facts, KPIs or linked model for the report's periods. Test in Task 6.
2. **Two chat messages sent at once, or an edit saved while the AI is replying** → second writer refused with 409; the draft stays locked during a reply. Test in Task 7.
3. **Uploaded file is a password-protected package, a zip bomb, a file renamed to .docx, or has a DOCTYPE with external entities** → refused with a clear message; nothing expanded beyond the limits; XML parsed without entities or network. Test in Task 9.
4. **Published file has no report tag, or a tag naming another analyst's thread** → refused; the analyst is offered only their own approved threads. Test in Task 9.
5. **Rating or target written in free text, outside the marked area, in an example or a lesson source** → masked by the text scan. Test in Task 4.

## File Structure

Backend (new):
- `analekh/reports/__init__.py`: package.
- `analekh/reports/draft.py`: draft document schema (dataclasses plus validation), block and slide types.
- `analekh/reports/mask.py`: rating, target and guidance masking.
- `analekh/reports/store.py`: MinIO bodies by hash, compressed; version rows.
- `analekh/reports/threads.py`: thread lifecycle (drafting, approved, published), lock, stale-version check.
- `analekh/reports/chat.py`: one chat turn: prompt assembly, tool loop, section checks, style check.
- `analekh/reports/sourced.py`: the "sourced number" lookup for analyst-typed figures.
- `analekh/reports/office_read.py`: safe OOXML reader for published files (text, tables, chart data, macro flag).
- `analekh/reports/publish.py`: publish step (routes A and B share it).
- `analekh/reports/lessons.py`: lesson store, lesson tests (phrase, structure, judged), learning job.
- `analekh/reports/upgrade.py`: upgrade check (replay).
- `analekh/reports/export.py`: JSONL export.
- `analekh/genai/writers.py`: extended only after decision gate (Task 8).
- `analekh/api/routers/threads.py`: thread, message, version, approve, publish, file routes.
- `analekh/api/routers/lessons.py`: lessons routes.
- `analekh/api/routers/qa.py`: multi-turn Q&A routes (replaces the one-shot `/qa` in `outputs.py`).
- `analekh/jobs/report_tasks.py`: Celery tasks for chat turns and the learning job.
- `analekh/cli.py`: `analekh ai export`, `analekh ai check` added.
- `analekh/db/migrations/versions/00xx_report_threads.py`: migration (next free number).

Frontend (new or changed):
- `web/src/pages/Reports.tsx`: format switch, recent threads (changed).
- `web/src/pages/ReportThread.tsx`: thread page.
- `web/src/components/report/DraftPane.tsx`: editable blocks, locked during replies, highlights, undo.
- `web/src/components/report/ChatPane.tsx`: chat; shared with Q&A.
- `web/src/components/report/Charts.tsx`: ECharts spec renderer.
- `web/src/pages/Qa.tsx`: Q&A page (replaces placeholder).
- `web/src/pages/Lessons.tsx`: lessons list.

Tests: `tests/reports/` mirroring the modules; DB tests skip if PostgreSQL is down (CLAUDE.md).

---

### Task 1: Tables and migration

**Files:**
- Create: `analekh/db/migrations/versions/<next>_report_threads.py`
- Modify: `analekh/db/models.py` (add six classes after `Report`, line 388)
- Test: `tests/reports/test_models.py`

**Interfaces:**
- Produces: `ReportThread`, `ThreadMessage`, `ReportVersion`, `PublishedFile`, `Lesson`, `LessonCheck` (SQLAlchemy models). Columns follow the spec's record table. `ReportThread.status` is one of `drafting`, `approved`, `published`, enforced by a CHECK constraint. `ReportThread.format` is `word` or `ppt`. `ReportThread.owner_id` is a foreign key to `users.id`. Money-free; numbers in the draft are stored as JSON, never as float.

- [ ] **Step 1: Write the failing test** — insert a thread, a message, a version and a lesson; assert the status CHECK rejects `"done"`; assert `owner_id` is required.
- [ ] **Step 2: Run it** — `uv run pytest tests/reports/test_models.py -q`; expect fail (models missing).
- [ ] **Step 3: Add the models** to `models.py` and generate the migration with `uv run alembic revision --autogenerate -m "report threads"`; review the file by hand.
- [ ] **Step 4: Run the test** — expect pass; then `uv run alembic upgrade head` and `uv run alembic check`.
- [ ] **Step 5: Commit message for the owner** — `feat(reports): tables for threads, messages, versions, published files, lessons`.

---

### Task 2: Draft document schema

**Files:**
- Create: `analekh/reports/draft.py`
- Test: `tests/reports/test_draft.py`

**Interfaces:**
- Produces: `Draft` (fields `schema_version: int = 1`, `format: Literal["word","ppt"]`, `units: list[Unit]`), `Unit` (a Word section or a slide: `title`, `blocks`), `Block` union: `Heading`, `Paragraph`, `Bullets`, `Table`, `Chart`, `Placeholder`. Each `Paragraph` text holds citation markers `[fact:N]`, `[kpi:N]`, `[filing:N page:P]`, `[model:ID range]`, `[calc]`. `Chart` holds a spec: `type` (`bar`, `line`), `series` as a list of source references, `title`, `labels`. `Placeholder` holds `kind` in `rating`, `target`, `guidance` and never a value. Functions: `parse_draft(obj: dict) -> Draft` (raises `DraftError`), `to_json(draft) -> dict`.

- [ ] **Step 1: Write the failing tests** — round-trip a Word draft with each block type; reject unknown block types; reject a `Placeholder` with a `value` field; reject a `Chart` series with no source reference; reject more than 200 units or 5,000 blocks (limits from settings `draft_max_units`, `draft_max_blocks`).
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** with closed schemas (`extra="forbid"` if Pydantic is used, otherwise explicit checks). Add the two settings to `config.py`.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): model-neutral draft document schema`.

---

### Task 3: Rating, target and guidance masking

**Files:**
- Create: `analekh/reports/mask.py`
- Modify: `analekh/config.py` (`rating_words`, `target_patterns` as settings lists)
- Test: `tests/reports/test_mask.py`

**Interfaces:**
- Produces: `mask_text(text: str) -> MaskResult` where `MaskResult` has `text` (masked) and `hits: int`; `mask_draft(draft: Draft) -> Draft` masks every `Paragraph`, `Bullets` item, table cell and slide text, and replaces every `Placeholder` value with `[masked]`. `MaskResult` never includes the masked original text.

- [ ] **Step 1: Write the failing tests** — a sentence "We upgrade to Buy, TP 1,450" is masked entirely; "Rs 1,450 target price" is masked; "Net interest margin rose 40 bps" is untouched; a marked placeholder is replaced by `[masked]`; masking is idempotent.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** with a sentence splitter, the settings lists compiled once, case-insensitive whole-word matching. When in doubt, mask (fail closed).
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): mask ratings, targets and guidance before any reuse`.

---

### Task 4: Section drafting with grounding and style checks

**Files:**
- Create: `analekh/reports/chat.py` (drafting part only; chat turns are Task 6)
- Modify: `analekh/genai/reports.py` (add prompt keys `thread_section` only; `run_report` signature unchanged)
- Test: `tests/reports/test_chat_draft.py`

**Interfaces:**
- Consumes: `run_report(claude, executor, kind, prompt=..., tools=..., system_text=...)` from `genai/reports.py`; `check(text, results)` from `genai/grounding.py`; `mask_draft` from Task 3; `parse_draft` from Task 2.
- Produces: `draft_section(claude, executor, thread, outline_item) -> SectionResult` where `SectionResult` has `unit` (a `Unit` or None), `blocked: bool`, `unmatched: list[str]`, `tool_calls: list[dict]`, `results: list[Any]` (kept so Task 6 can check typed numbers). Style check `style_problems(text) -> list[str]` returns em-dashes and banned phrases from settings.

- [ ] **Step 1: Write the failing tests** with a fake `Claude` that returns a canned reply: a reply with a grounded number → `blocked False`; a reply with `12.7` matching no tool result → `blocked True` and `unmatched == ["12.7"]`; a reply with an em-dash → `style_problems` non-empty and `blocked True`.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** `draft_section` by calling `run_report` with the outline's prompt; parse the reply into a `Unit`; mask it; run `check` and `style_problems`. Outline items come from the `SECTIONS` lists already in `Reports.tsx`, moved into `analekh/reports/outlines.py` so the server owns them.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): section drafting with grounding and style checks`.

---

### Task 5: Thread store and versions

**Files:**
- Create: `analekh/reports/store.py`, `analekh/reports/threads.py`
- Test: `tests/reports/test_threads.py`

**Interfaces:**
- Produces: `create_thread(db, owner, company_id, report_type, format, basis, quarter, model_id) -> ReportThread`; `save_version(db, store, thread, draft, trigger, parent_no, by_user) -> ReportVersion` (raises `StaleVersion` if `parent_no` is not the current version); `load_draft(store, version) -> Draft`. Bodies stored as gzip JSON under key `reports/<thread_id>/<version_no>.json.gz` with `sha256` recorded. Trigger is one of `first_draft`, `ai_reply`, `analyst_edit`, `approved`.
- Versions after the first are stored as a JSON patch against the previous version (`jsonpatch`-free: a list of `{path, before, after}` changes computed by walking the block lists). `load_draft` rebuilds by applying patches from the first draft.

- [ ] **Step 1: Write the failing tests** — create a thread; save three versions; `load_draft` on version 3 equals the input; saving with a stale `parent_no` raises `StaleVersion`; a version after the first is smaller in bytes than the first.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** with the existing MinIO helper used by `ingest/storage.py` (hash-keyed). No new dependency.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): versioned draft store with diffs between versions`.

---

### Task 6: Chat turn and analyst-typed numbers

**Files:**
- Modify: `analekh/reports/chat.py` (add `run_turn`)
- Create: `analekh/reports/sourced.py`
- Test: `tests/reports/test_chat_turn.py`, `tests/reports/test_sourced.py`

**Interfaces:**
- Consumes: `draft_section` (Task 4), `save_version` (Task 5), `mask_draft` (Task 3).
- Produces: `run_turn(claude, executor, thread, message, selection: Selection | None) -> TurnResult` where `Selection` names a unit index and optionally a block index, and `TurnResult` has `reply: str`, `changed_units: list[int]`, `version_no: int`, `blocked: list[str]` (unmatched numbers). A changed unit that fails grounding is NOT written into the draft; it appears in `blocked`. `sourced.py`: `unsourced_numbers(db, thread, text, results) -> list[str]` matches numbers against the thread's `results`, plus facts, KPIs and the linked model's values for the report's periods (a database read, no model call).

- [ ] **Step 1: Write the failing tests** — a turn that changes unit 2 with grounded text writes version 2 and lists `changed_units == [2]`; a turn whose change has an unmatched number writes nothing and returns it in `blocked`; a typed number that matches a KPI for the period is sourced; one that matches nothing is in `unsourced_numbers`.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** `run_turn` as one `run_report`-style loop scoped to the selection, with the thread's draft and the analyst's lessons (Task 10 supplies lessons; pass an empty list until then).
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): chat turn with grounded changes and sourced-number check`.

---

### Task 7: Thread lock, stale-version refusal and jobs

**Files:**
- Modify: `analekh/reports/threads.py` (lock helpers)
- Create: `analekh/jobs/report_tasks.py`
- Modify: `analekh/api/routers/threads.py` (created in Task 8; this task adds the chat route)
- Test: `tests/reports/test_thread_lock.py`

**Interfaces:**
- Produces: `thread_busy(db, thread_id) -> bool`; a Celery task `run_chat_turn(thread_id, message, selection, user_id)` that runs `run_turn` under the thread lock and stops after `settings.chat_turn_timeout_s`. `POST /threads/{id}/messages` returns 202 with a job id, 409 when the thread is busy or the `base_version` in the body is stale, 422 when the message is over `settings.chat_message_max_chars`. `GET /threads/{id}/jobs/{job_id}` returns status and, when done, the new version number.

- [ ] **Step 1: Write the failing tests** — a second message while busy → 409; a stale `base_version` → 409; a 10,001-character message → 422 (limit from settings); a message on another analyst's thread → 404 (not 403, to avoid revealing existence).
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** the lock with a row lock on the thread (`SELECT ... FOR UPDATE`), released in `finally`.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): one writer per thread, stale-version refusal, chat jobs`.

---

### Task 8: Thread routes and approval

**Files:**
- Create: `analekh/api/routers/threads.py`
- Modify: `analekh/api/main.py` (include router with `dependencies=[Depends(get_user)]`, as the others)
- Modify: `analekh/api/schemas.py` (request and response models)
- Test: `tests/reports/test_thread_routes.py`

**Interfaces:**
- Produces: `POST /threads` (company, report type, format, basis, quarter, model; starts a first draft job, returns thread id); `GET /threads/{id}` (status, draft at the current version, lessons count, chat history page); `POST /threads/{id}/approve` (requires the thread's `sourced` check to be run, returns the count of "not sourced" numbers, freezes the thread, queues the file build); `GET /threads/{id}/file` (download of the built file for `approved` or `published`). Ownership check on every route through the thread's `owner_id`.

- [ ] **Step 1: Write the failing tests** — create a thread as user A; user B gets 404 on GET, POST messages and approve; approve then POST message → 409 (frozen); download before approval → 409.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement.** Reuse `company_or_404`-style helpers from `api/deps.py`.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): thread routes with owner checks and approval`.

---

### Task 9: Build the file from the approved draft

**Decision made (owner, 1 November 2026): option B with a plain fallback.** When a template for the company's sector exists, the report-writing model fills it from the approved draft (`analekh/reports/fill_template.py`). When none exists, code builds a plain default file from the draft (`genai/writers.py`, extended). Recorded in `deviations.md` section 16. Background: `deviations.md` section 15 (owner, 31 October 2026) says Word and PowerPoint templates are uploaded per sector and the report-writing model fills them; `genai/writers.py` is left as it is. The approved design (1 November) has code build the file from the draft. The options were:

- **A.** Code builds the file from the draft (`writers.py` extended; templates from section 15 used as the base document styles when present).
- **B.** Section 15 stands: the model fills the uploaded template from the draft; `writers.py` stays unchanged.

Build both paths; `build_file` picks by whether a template exists for the sector.

**Files:**
- Modify: `analekh/genai/writers.py` (default file when no template); create `analekh/reports/fill_template.py` (fills the uploaded template)
- Create: `analekh/reports/tag.py` (report tag in custom document properties, modelled on `analekh/workbook/tags.py`)
- Test: `tests/reports/test_build_file.py`

**Interfaces:**
- Produces: `build_file(draft: Draft, thread: ReportThread, template: bytes | None) -> bytes`; `write_tag(file_bytes, thread_id: int, version_no: int) -> bytes`; `read_tag(file_bytes) -> ReportTag | None`. Rating, target and guidance are a marked placeholder: a content control in Word, a named shape in PowerPoint. The disclaimer from `writers.py` is removed for these files.

- [ ] **Step 1: Write the failing tests** — a built .docx opens with python-docx and contains the placeholder control; `read_tag` returns the thread id after `write_tag`; a file with no tag returns None; the built file contains no macro part.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** both paths: template present → `fill_template`; absent → `writers`.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): build the approved draft into Word or PowerPoint with a report tag`.

---

### Task 10: Safe reader and publish step (route A, upload)

**Files:**
- Create: `analekh/reports/office_read.py`, `analekh/reports/publish.py`
- Modify: `analekh/api/routers/threads.py` (publish route)
- Modify: `analekh/config.py` (`publish_max_entries`, `publish_max_expanded_bytes`, `publish_max_ratio`)
- Test: `tests/reports/test_office_read.py`, `tests/reports/test_publish.py`

**Interfaces:**
- Produces: `read_package(data: bytes) -> PackageText` (`text: list[str]`, `tables`, `chart_data`, `has_macros: bool`); raises `PackageRefused(reason)`. `publish(db, store, owner, thread_id, data: bytes, filename: str, route: str) -> PublishedFile`. Route `POST /threads/{id}/publish` (multipart with the file) returns the published file summary. Uses the upload limit from the existing admin setting (`max_upload_default_bytes`, ceiling `max_upload_ceiling_bytes`), checked on arrival.

- [ ] **Step 1: Write the failing tests** — a password-protected file (OLE container, not zip) → refused; a zip with 20,000 entries → refused; a zip whose expanded size exceeds the setting → refused; a `.docx` whose XML contains `<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>` → refused or entity not expanded (assert no network or file read); a `.docm` with `vbaProject.bin` → accepted, `has_macros True`, macro bytes never parsed; a file with no report tag → refused with the message "pick the report"; a tag naming another analyst's thread → refused.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** `office_read` with `lxml.etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)`; check extension against the package's main content type; never open with Office or LibreOffice; ignore external relationships.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): publish the final file by upload with safe package reading`.

---

### Task 11: Lessons: store, tests, learning job

**Files:**
- Create: `analekh/reports/lessons.py`, `analekh/jobs/report_tasks.py` (add `learn_from_publish`)
- Test: `tests/reports/test_lessons.py`

**Interfaces:**
- Produces: `LessonTest` = `{kind: "phrase"|"structure"|"judged", spec: dict}`; `run_lesson_tests(lessons, draft_text_or_units, judge=None) -> list[LessonResult]`. `propose_lessons(claude, thread, first_draft, chat_messages, approved, published_text) -> list[ProposedLesson]` (closed JSON schema; input is content, never instructions). `add_or_strengthen(db, owner_or_firm, proposal)` merges a duplicate instead of adding one. Lesson statuses `active` / `retired`. The learning job runs on publish, after `publish()`.

- [ ] **Step 1: Write the failing tests** — a phrase lesson "never call margins robust" fails a draft containing "robust margins"; a structure lesson "charts show eight quarters" fails a chart with 6 points; a duplicate proposal increments `strength` instead of adding a row; a proposal with a rating in its text is rejected (masking applied first, Task 3).
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement.** Judged tests call the model with `CLAUDE_SMALL_MODEL` through `client.py`, and only the model named in the current production settings may judge (design section 13).
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): lessons with tests and a learning job on publish`.

---

### Task 12: Lessons in drafting and chat, with conflict handling

**Files:**
- Modify: `analekh/reports/chat.py` (`draft_section`, `run_turn` take `lessons`)
- Modify: `analekh/reports/chat.py` (retry once on lesson failure; flag if it fails again; analyst's explicit request wins)
- Test: `tests/reports/test_lesson_flow.py`

**Interfaces:**
- Consumes: `run_lesson_tests` (Task 11), `mask_draft` (Task 3).
- Produces: examples passed to the model are two or three of the analyst's past published reports of the same type, masked. A reply that fails a phrase or structure lesson is retried once with the failure text; if it fails again it is returned with `blocked` containing `lesson:<id>`. If the analyst's message explicitly asks for the banned thing, the text is inserted and the lesson id is returned in `conflicts` for an offer to retire it.

- [ ] **Step 1: Write the failing tests** — a fake model that breaks a lesson once then complies → inserted after one retry; breaks twice → flagged, not inserted; explicit request → inserted with a `conflicts` entry; a past report sent as an example has its rating masked.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): lessons applied in drafting, with one retry and visible conflicts`.

---

### Task 13: Upgrade check and JSONL export

**Files:**
- Create: `analekh/reports/upgrade.py`, `analekh/reports/export.py`
- Modify: `analekh/cli.py` (`analekh ai check --candidate`, `analekh ai export`)
- Test: `tests/reports/test_upgrade.py`, `tests/reports/test_export.py`

**Interfaces:**
- Produces: `check_candidate(db, store, claude_current, claude_candidate, threads: list[ReportThread]) -> CheckResult` with per-count results (grounding rejections, schema failures, banned phrasing, missing sections, lesson tests passed by the current model) and `verdict: "pass" | "fail"`; rule: candidate is no worse on each count and passes every lesson the current model passes; lessons the current model fails are reported, not blocking. Replays stored tool results; a call not recorded is answered from live data and counted as `new_data_asked`. `export_jsonl(db, store, path, schema_version=1)` writes three pair types, masking ratings, targets and guidance. Results stored in `lesson_checks`.

- [ ] **Step 1: Write the failing tests** — a candidate with more grounding rejections → `fail`; equal results → `pass`; a lesson the current model already fails does not block; export contains no rating or target text from a fixture thread; export's first line has `schema_version`.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement.** The check never changes stored threads.
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(reports): upgrade check against past threads and JSONL export`.

---

### Task 14: Q&A on the chat window

**Files:**
- Create: `analekh/api/routers/qa.py`, `analekh/genai/qa_chat.py`
- Modify: `analekh/api/routers/outputs.py` (remove the one-shot `/qa` route, keep `hybrid_search` in `genai/qa.py`)
- Modify: `analekh/db/models.py` (`QaThread`, `QaMessage` reuse the thread and message pattern; no lessons link)
- Test: `tests/reports/test_qa.py`

**Interfaces:**
- Produces: `POST /qa/threads` (company), `POST /qa/threads/{id}/messages` (question, 202 with job id; 409 when busy; limits from settings), `GET /qa/threads/{id}`. `qa_turn(claude, executor, qa_thread, question) -> QaTurnResult` with `answer`, `citations`, `blocked`. Uses `hybrid_search` for retrieval and the tool loop from `genai/reports.py` with the existing `qa` prompt, given prior turns as context. Owner checks as Task 8.

- [ ] **Step 1: Write the failing tests** — a second question while busy → 409; another user's Q&A thread → 404; an answer with an ungrounded number → `blocked True`; Q&A messages are never read by `learn_from_publish` (assert the job's input query excludes them).
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — expect pass.
- [ ] **Step 5: Commit message** — `feat(qa): multi-turn Q&A threads on the chat window`.

---

### Task 15: Front end: Reports changes and the thread page

**Files:**
- Modify: `web/src/pages/Reports.tsx` (format switch; enable "Generate draft" with reasons; recent threads list; remove the placeholder previews)
- Create: `web/src/pages/ReportThread.tsx`, `web/src/components/report/DraftPane.tsx`, `web/src/components/report/ChatPane.tsx`, `web/src/components/report/Charts.tsx`
- Modify: `web/src/router.tsx` (`reports/:id` route inside `Layout`)
- Test: `web/src/pages/ReportThread.test.tsx`, `web/src/components/report/DraftPane.test.tsx`
- Regenerate: `pnpm api-types` after the API tasks.

**Interfaces:**
- Consumes: the thread routes (Task 8), the job status route (Task 7).
- Produces: `DraftPane` props `{ units, locked, onType(unitIndex, blockIndex, text), highlights, onUndo }`; typed text is saved on blur or after 1.5 seconds idle, with `base_version`. `ChatPane` props `{ messages, busy, onSend(text, selection) }`, shared with Q&A. A "not sourced" marker on numbers from the save check. Approve button shows the count first. No new library beyond what is already in the stack (ECharts for charts).

- [ ] **Step 1: Write the failing tests** (Vitest and Testing Library) — typing in a paragraph calls `onType`; the draft is read-only while `busy`; a "not sourced" number shows a marker; Approve asks for confirmation and shows the count; the format switch changes the Generate label.
- [ ] **Step 2: Run** — `pnpm --filter analekh-web test -- ReportThread DraftPane` (or the workspace's test command); expect fail.
- [ ] **Step 3: Implement.** Motion only on clicks (rule in design doc 19.1). Phone width works without sideways scroll.
- [ ] **Step 4: Run** — expect pass; then `pnpm lint && pnpm build`.
- [ ] **Step 5: Commit message** — `feat(web): report thread with editable draft, chat and approval`.

---

### Task 16: Front end: Q&A page and Lessons page

**Files:**
- Create: `web/src/pages/Qa.tsx`, `web/src/pages/Lessons.tsx`
- Modify: `web/src/router.tsx` (replace `/qa` placeholder; add `/lessons`)
- Test: `web/src/pages/Qa.test.tsx`, `web/src/pages/Lessons.test.tsx`

**Interfaces:**
- Consumes: `ChatPane` (Task 15), Q&A routes (Task 14), lessons routes (`GET /lessons`, `PATCH /lessons/{id}` for text, retire, delete; `POST /lessons/{id}/promote` for admins).
- Produces: `Qa` page: company picker, `ChatPane`, citation links opening the filing page. `Lessons` page: list with source link, status, edit, retire, delete; a firm-level badge.

- [ ] **Step 1: Write the failing tests** — Qa sends a question through `ChatPane`; a retired lesson is listed under "Retired"; only admins see Promote.
- [ ] **Step 2: Run** — expect fail.
- [ ] **Step 3: Implement** and add the lessons routes in `analekh/api/routers/lessons.py` (owner checks; admin only for promote).
- [ ] **Step 4: Run** — expect pass; `pnpm lint && pnpm build`.
- [ ] **Step 5: Commit message** — `feat(web): Q&A page and lessons list`.

---

### Task 17: Office add-in publish (route B)

Deferred until Tasks 1 to 16 pass. Spec says: same publish step as route A; bridge token, `Authorization: Bearer`; manifest hosts for Word and PowerPoint. Plan this as its own short plan when started, following `office-addin/README.md`.

---

### Task 18: Documents and log

**Files:**
- Modify: `AI.md` (section 4: three layers; section 14: how the accepted version comes back, answered; phases H and I status)
- Modify: `docs/design/technical-design.md` (Reports, Q&A, Lessons screens and proposed tables; edit the `.md` only, no `.docx` rebuild until a version bump, per the owner's rule)
- Modify: `docs/design/deviations.md` (section 16: record the decision-gate outcome in Task 9 and any change made during build)
- Modify: `docs/pending-items.md`
- Modify: `Commit-Info.md` (entry for the build, replacing the design-approved line when merged)

- [ ] **Step 1:** Update each document as listed.
- [ ] **Step 2:** `uv run ruff check . && uv run ruff format . && uv run mypy analekh && uv run pytest -q`; `pnpm lint && pnpm test && pnpm build`.
- [ ] **Step 3:** Run `graphify update .` (AST only).
- [ ] **Step 4:** Commit message: `docs: report chat, publishing and lasting learning`.

---

## Self-Review

1. **Spec coverage:** Format choice → 15; drafting → 4; chat and typed edits → 6, 7, 15; locked during reply → 7, 15; approve and file build → 8, 9; publish upload → 10; publish add-in → 17 (deferred, stated); record → 1, 5; lessons and tests → 11, 12; upgrade check → 13; export → 13; masking → 3; Q&A → 14, 16; Lessons page → 16; hierarchy → not built (AI.md §14, intentionally). Compaction of old versions is dropped from this build (owner, 1 November 2026) and left as a later option.
2. **Type consistency:** `Draft`, `Unit`, `Block`, `SectionResult`, `TurnResult`, `publish` and `PublishedFile` names are used the same across tasks.
3. **Review Focus:** each of the five lines has a test in Tasks 6, 7, 10, 3 and 10 respectively.
4. **Gaps:** the add-in route is deferred; the Word/PowerPoint writer depends on the decision gate.

## Execution

**Native** (owner, 1 November 2026: subagent-driven costs too many tokens). Use superpowers:executing-plans, one task at a time, ruff/mypy/pytest after each, a single fresh reviewer on the whole branch at the end. The security-sensitive tasks (3, 7, 10) get the extra care the Review Focus lists ask for.
