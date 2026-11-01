# Report chat, publishing and lasting learning: design

Date: 2026-11-01. Status: draft for owner approval. Sources: conversation with the owner on
1 November 2026, `AI.md` sections 4 and 14, design doc 17 and 19.1, `CLAUDE.md` rules 2, 3, 7,
8, 9 and 11. Also covers the Q&A page (design doc 19.1, still a placeholder at `/qa`).

## Intent

A report is final only when the analyst agrees to it, after adding their own rating and
guidance (rule 8, SEBI). Today the Reports screen is a set-up page with placeholder previews:
"Generate drafts" is off, and the `reports` table has no draft or published state. Nothing can
be finalised, and nothing the analyst changes is captured, so the learning loop in AI.md
section 4 has nothing to learn from.

The owner's direction:

1. The analyst works with the AI in an **interactive chat window**. The AI posts the draft in
   the chat; the analyst types straight into it or asks the AI for changes. Analekh is about
   time and efficiency, so typing directly must be first class.
2. When the analyst approves the draft, it becomes a Word report or a PowerPoint (chosen at the
   start). From then on the analyst works **in the file itself**: content fixes, the rating, the
   guidance. No going back to the chat, no regenerating.
3. The analyst publishes. **The AI learns from the edits in chat and from the published file.**
4. **What the AI learns must survive a model upgrade**, when newer models or better open-weight
   models arrive.
5. The Q&A page is built in the same update, sharing the chat window.

## Goals

1. Reports: pick company, report type, basis, quarter and **format (Word report or PowerPoint)**
   first, then generate a draft into a chat thread.
2. In the chat: the analyst edits the draft directly or asks the AI for any change (language,
   content, charts, structure, anything; there is no fixed list of request types).
3. Approve: Analekh builds the chosen file from the approved draft, tagged so it can find its
   way back.
4. Publish by either of two routes, both supported: upload in Analekh, or a "Publish to
   Analekh" button in a Word/PowerPoint add-in.
5. Keep a complete, model-neutral record of every report's life (first draft, chat, every
   version, approved draft, published file).
6. Turn feedback into written **lessons** that any model reads, and that are enforced as tests.
7. A model-upgrade check: a candidate model is tried on past reports and must pass every lesson
   test before it replaces the current one.
8. The Q&A page: multi-turn chat over a company's filings with page links, using the same chat
   window.

## Non-goals (this update)

- Adapter (LoRA/QLoRA) training, the local Ollama provider, shadow drafting: AI.md phases D and
  I, still after the MVP. This update only makes the record and the export they will need.
- Agentic RAG, the context fetcher and conflict flags (AI.md sections 2 and 3): separate
  projects. Drafts here use the existing tools (design doc 17.1).
- House templates for Word and PowerPoint.
- Editing the file inside Analekh after approval. Post-approval editing is in Word/PowerPoint.
- Sharing a draft thread with colleagues or co-editing.
- A reporting hierarchy (supervisor or compliance read access). Firms will have one (owner,
  1 November 2026), but it is deferred: a to-do in `AI.md` section 14. Until then a thread and
  its files are visible only to the analyst who owns it. The upgrade check and the lesson job
  are system jobs and read threads without a user view.

## Anti-goals

- The AI writing or proposing a rating or target price, or training ever teaching one (rule 8).
- A generated number that is not from a tool result or `calc` reaching the draft unmarked
  (rule 3; never weaken `genai/grounding.py`).
- Running a macro, or opening an uploaded file in Word, PowerPoint or LibreOffice (rule 7).
- Learning that lives only in a model's weights, so an upgrade wipes it out.
- Two writers on one draft at once (the owner: "otherwise it's a mess").
- A chat that feels slower than editing a Word file by hand.

## Constraints

- Rules 2, 3, 4, 7, 8, 9 and 11 in `CLAUDE.md`. Every route needs a signed-in user; the add-in
  authenticates with a bridge token as the Excel add-in does (`office-addin/`, `Authorization:
  Bearer`).
- All model calls through `genai/client.py`; tokens logged in `llm_calls`.
- Limits and timings from `config.py` settings, never literals (rule 9). Upload size uses the
  existing admin upload limit (`max_upload_default_bytes`, ceiling `max_upload_ceiling_bytes`).
- Reports run inline in the API today (`api/routers/outputs.py`). AI work for the chat runs as
  Celery jobs (`jobs/`), with time limits, so the API never blocks on a model call.
- Front end stays light: a new library must earn its weight (design doc 19.1). Motion only on
  what is clicked.
- No em-dashes or stock phrases in drafts (rule 8); the style filter runs on AI output.

## Owner's decisions (1 November 2026)

1. The draft lives in the chat window and is edited there, by typing or by asking the AI.
2. The analyst can type straight into the draft.
3. While the AI is replying, the draft is locked. The analyst edits again when it finishes.
4. The format (Word report or PowerPoint) is chosen first, before the draft.
5. Approval in chat builds the file. After that the analyst edits only in the file, including
   content fixes, rating and guidance. No back and forth, no regenerated documents. Same for
   PowerPoint.
6. The AI learns from the chat edits and from the published document.
7. Both publish routes are built: upload, and a Word/PowerPoint add-in.
8. Macro-enabled files (.docm, .pptm) are accepted. Macros are never run.
9. Learning is kept in three layers so it survives upgrades (below); the owner accepted this.
10. The Q&A page is part of this update.

## The flow

```
Reports set-up            Chat (drafting)                        File (approved)      Published
company, type, basis, ->  AI posts first draft             ->    .docx or .pptx  ->   final file in
quarter, FORMAT           analyst types / asks AI                analyst edits in     Analekh;
                          draft locked while AI replies          Word/PowerPoint:     learning job
                          grounding + style checks               content, rating,     runs
                          [Approve]                              guidance  [Publish]
```

Status of a report thread: `drafting` -> `approved` -> `published`. There is no way back from
`approved` to `drafting`; a new thread is started instead. A published report may be published
again (a corrected file), which keeps both files and reruns the learning job on the newest.

## Screens

### Reports set-up (changed)

The existing card (company, report type, basis, quarter, inputs) gains **Format: Word report /
PowerPoint**. The Word note and PowerPoint preview cards are reduced to the outline of the
chosen format only. **Generate draft** is enabled when the inputs allow it (an initiating
report needs a linked model, as today) and opens the thread at `/reports/:id`. **Recent
reports** lists the analyst's threads: company, type, format, quarter, status, updated, a
"Contains macros" badge on a published macro file.

The IPO coverage tab is unchanged in this update.

### Report thread `/reports/:id` (new)

One screen, two parts:

- **The draft**, shaped for its format: sections (Word report) or slides (PowerPoint). The
  analyst can click into any paragraph, bullet, table cell or slide text and type. Charts are
  shown rendered (ECharts, already in the stack); changing a chart is done by asking the AI.
  Citations stay visible as small markers and link to their source.
- **The chat**, beside the draft on wide screens and below it on phones. The analyst can select
  a part of the draft (a paragraph, a section, a slide, a chart) and ask about or change just
  that, or ask about the whole draft. While the AI replies, a clear "AI is writing" state shows
  and the draft is read-only. When the reply changes the draft, the changed parts are
  highlighted and the change can be undone in one click.

Grounding:
- AI output: a part with an unmatched number is not inserted silently. It is shown in the chat
  with its unmatched numbers, and the analyst can ask again or type the text in themselves.
- Analyst typing: every number the analyst types is checked on save. A number that matches no
  tool result is highlighted as "not sourced". The analyst is the author, so this flags, it does
  not block.

**Approve** asks for one confirmation, shows how many "not sourced" numbers remain, freezes the
thread (read-only from then on) and builds the file. The file is downloadable from the thread.

### Publish (new, on the thread)

When the thread is `approved`, the thread shows **Publish**: choose the final file (.docx,
.docm, .pptx or .pptm, matching the thread's format). After the checks (below) the thread shows
`published`, the published file, and a "Contains macros" badge when it has one.

### Lessons (new)

A list per analyst, reachable from Settings and from each thread: each lesson in plain words,
where it came from (link to the thread and the edit), when it was learnt, active or retired.
The analyst can edit the wording, retire or delete a lesson. Admins can mark an analyst's lesson
as a firm lesson, so it applies to every analyst.

### Q&A `/qa` (new, replaces the placeholder)

A company picker and the same chat window, without a draft pane. Multi-turn: the question and
the earlier turns of the thread go to the model. Answers carry citations; `[filing:4 page:7]`
links open the filing page. A blocked answer (unmatched numbers) is shown as blocked with its
numbers, as reports are. Past Q&A threads are listed per user. Q&A threads are stored but are
not used for lessons.

## The draft document (model-neutral)

A draft is one JSON document with a `schema_version`, not markdown and not a Word file:

- Word report: a list of sections; each section a list of blocks.
- PowerPoint: a list of slides; each slide a title and a list of blocks.
- Blocks: heading, paragraph, bullet list, table, chart, citation markers inside text.
- A table cell or chart series refers to its source (fact id, KPI id, model range, `calc`
  result) as well as holding the displayed value.
- A chart is a spec (type, series by source reference, labels, title), never an image.
- The rating, target price and guidance are a marked placeholder block the AI never fills.

The first draft is generated **section by section** (or slide by slide) from the outlines on
the Reports screen (`SECTIONS` in `web/src/pages/Reports.tsx`), each with its own short tool
loop and grounding check, as design doc 17 proposes. A section that fails grounding comes back
as a blocked section in the chat, not as a hole in silence.

The writers in `genai/writers.py` are extended to build the .docx and .pptx from this document.
PowerPoint charts are native charts (python-pptx). Word charts are rendered images. The writer
writes the report tag (below) into the file's custom document properties, the way
`workbook/tags.py` tags workbooks.

## The record: what is stored and how

Everything learnt must be rebuildable from the record. Stored in PostgreSQL (index rows) and
MinIO (bodies, compressed, keyed by hash as filings are today):

| Table | Holds |
|---|---|
| `report_threads` | company, report type, format, basis, quarter, model id, owner (user), status, the tool results snapshot key, created/approved/published times |
| `thread_messages` | role (analyst or AI), text, the selection it was about, model and provider that answered, prompt hash, tool calls and their results (MinIO key), grounding result |
| `report_versions` | version number, parent version, trigger (first draft, AI reply, analyst edit), body key in MinIO; the first draft and the approved draft stored in full, versions in between as diffs |
| `published_files` | thread, file hash and MinIO key, original name, format, macro flag, extracted text key, comparison result key, uploaded by, route (upload or add-in) |
| `lessons` | text, scope (analyst or firm), owner, status (active, retired), test kind and spec, links to the messages and versions it came from |
| `lesson_checks` | each model-upgrade check run: candidate, reports used, per-lesson results, verdict |

The existing `reports` table stays for the older one-shot kinds (flash, digest, red flags); the
builder decides whether threads extend it or sit beside it.

Rough size: about 100 to 200 MB a year per analyst (an estimate, text only, charts as specs).
To keep it lean: in-between versions as diffs and bodies compressed. A later option is a
compaction command that, for published threads whose lessons are taken,
drops in-between versions but keeps the first draft, approved draft, chat and published file.
Dropped from the first build (owner, 1 November 2026); a later option.

**Export:** `analekh ai export` writes the record as JSONL training pairs (first draft from its
inputs; draft plus analyst request to the kept AI revision; approved draft to published), with
a documented, versioned schema. Ratings, target prices and guidance are masked out; numbers can
be masked to placeholders for style training. This is what any future model or adapter is
trained from.

## Lessons: learning that any model keeps

Layer 1 is the record (above). Layer 2 is written lessons. Layer 3 is adapters, out of scope
here, always rebuilt from layer 1.

**When lessons are drawn:** at publish, a job compares the AI's first draft, the analyst's
requests and typed edits in chat, the approved draft and the published file, and proposes
lessons in plain words ("Lead bank notes with NIM, not PAT"; "Never call margins robust";
"Charts show eight quarters"). New lessons are active at once and listed for the analyst to
edit or retire. Duplicates of an existing lesson strengthen it instead of adding a new one.

**How they are used:** every first draft and every chat reply includes the analyst's active
lessons and the firm's lessons, plus two or three of the analyst's past published reports of
the same type (and sector where possible) as examples, with ratings and target prices removed.
A new model therefore drafts with everything learnt from its first report, with no training.

**How they are enforced:** every lesson carries a test:

- phrase: a banned or required word or phrase, checked by code;
- structure: a section or element that must or must not appear, or an order, checked by code;
- judged: anything else, checked by a model against the lesson's wording.

Phrase and structure tests also run on every AI reply in the chat, as part of the style check.

## Moving to a new model

`analekh ai check --candidate <provider:model>` replays first-draft generation for a fixed set
of the firm's past published threads, using each thread's stored tool results (so the data is
the same and the comparison is fair). It scores the candidate and the current model on:
grounding rejections, broken structured output, banned phrasing, missing sections, and every
active lesson test. The run is stored in `lesson_checks`. A candidate goes live (a settings
change) only if it is no worse on every count and passes every lesson test. The old setting is
kept for rollback.

This works today for a Claude model change (`CLAUDE_MODEL`) and later for local models and
adapters, which plug into the same check (AI.md section 4).

## Publish routes

Both routes call the same publish step.

**A. Upload.** On the thread, Publish takes the file in a POST body under the session cookie.

**B. Word/PowerPoint add-in.** An Office.js task pane for Word and PowerPoint, built like the
Excel add-in (`office-addin/`), with a "Publish to Analekh" button that sends the open document.
It authenticates with a bridge token. Whether it is the same add-in with more hosts in the
manifest or a second one is the builder's call.

**The publish step:**

1. Size within the admin upload limit, checked on arrival (`api/body_limit.py`).
2. The extension and the package's main content type agree and match the thread's format
   (.docx or .docm for a Word report; .pptx or .pptm for a PowerPoint). Password-protected
   files (not a zip package) are refused with a message.
3. Zip limits: number of entries, total expanded size, expansion ratio. Over a limit: refused.
4. Read the report tag from the custom document properties. The tag must name a thread owned by
   the signed-in user (or the bridge token's user) in `approved` or `published` state.
   Missing, unknown or someone else's: refused, and the analyst is asked to pick the thread (only
   their own approved threads are offered).
5. Store the original bytes by hash in MinIO, untouched, macro part included.
6. Extract text, tables and chart data by reading the package XML with lxml (no entity
   resolution, no network). Never open the file in Office or LibreOffice, never follow external
   relationships (linked images, remote templates), never parse or run `vbaProject.bin`; only
   note that it exists (the macro flag). python-docx refuses .docm by content type, so the
   builder reads the XML directly or works around that check, and confirms python-pptx with
   .pptm.
7. Mark the thread `published` and queue the comparison and lesson job.

Grounding and style checks are not blocking on the published file: it is the analyst's work.
The comparison notes numbers that differ from the approved draft, for the record only.

## Safety summary (rule 11)

- New routes (threads, messages, versions, approve, file download, publish, lessons, Q&A
  threads) all need a signed-in user, and every object is checked against its owner: a thread,
  its messages, versions and files belong to one analyst. Admins manage firm lessons only.
- New file parser: size, entry, expansion and type limits; XML read without entities or network;
  nothing executed; external relationships ignored; macros stored, never parsed.
- Saves carry the version they edit; a save on a stale version, or while the AI is replying, is
  refused (409).
- Chat input bounded in length; the model's reply time and tool turns bounded by settings.
- No draft text, file content or tokens in logs.
- Text from an uploaded file is data. When it is fed to a model for the comparison and lesson
  job, it is passed as content to analyse, never as instructions, and the job's output is a
  closed JSON schema.

## Existing documents to update

- `AI.md`: section 4 (three layers; adapters are derived), section 14 (how the accepted version
  comes back: answered), section 13 phase H and I steps that this update covers.
- Design doc 17 (report chat, publish, lessons, upgrade check), 17.4, 19.1 (Reports, a new
  Report thread row, Q&A, Lessons), and the data section that lists proposed tables. Edit the
  `.md` only; the `.docx` is rebuilt on a version bump.
- `docs/design/deviations.md`: the change from "accepted report" to "approved in chat, edited in
  the file, published", and the Word/PowerPoint add-in.
- `docs/pending-items.md`, `Commit-Info.md` at the end.

## Left to the builder

- The in-browser editor: how blocks become editable (a light per-block editor is preferred over
  a large editor framework; justify any library).
- Job transport for chat replies (polling or server-sent events).
- How lesson extraction is prompted and how duplicates are matched.
- Whether threads extend `reports` or sit beside it; table and column names.
- Chart rendering for Word images.
- The fixed set of past threads for the upgrade check (size and choice).
- Whether the Word/PowerPoint add-in is the same add-in or a second one.

## Calls made by Claude, not the owner

These follow from the conversation but were not stated by the owner; check them while reading:

1. One thread is one format. A Word report and a PowerPoint on the same results are two threads.
2. No way back from `approved` to `drafting`; a correction after approval is made in the file.
3. AI changes are applied to the draft at once, highlighted, with one-click undo (not a separate
   accept step), for speed.
4. Analyst-typed numbers that match no source are flagged "not sourced", not blocked; Approve
   shows how many remain.
5. Charts are changed by asking the AI, not by a chart editor.
6. New lessons are active at once, editable and retirable in the Lessons list.
7. Admins can promote an analyst's lesson to a firm lesson.
8. Q&A threads are stored but do not feed lessons.
9. The generated file carries a marked blank for rating, target price and guidance; it is not
   pre-filled from the analyst's Excel model, though rule 8 would allow that.
10. The current `DISCLAIMER` in `genai/writers.py` ("no rating or target price") is dropped from
    these files, since the analyst adds a rating; the firm's own disclosures come with house
    templates later.
11. Compaction of old versions is not built in the first version.
12. **Masking ratings, targets and guidance** uses two methods. The writer puts them in a tagged
    region (a content control in Word, a named shape in PowerPoint), and that region is always
    masked. As a backstop, every extracted text is scanned for rating words and target-price
    patterns (the list is a setting, so a firm's own rating scale fits), and any sentence that
    matches is masked too. Masking runs before anything reaches the export, the examples in
    prompts, or the lesson job. If in doubt, mask (fail closed).
13. **The upgrade check is relative.** A candidate must be no worse than the current model on
    every count. It must also pass every lesson test the current model passes. A lesson the
    current model already fails does not block, but it is reported. The current production model
    judges "judged" lessons, never the candidate, set by its own setting. Analyst lessons run
    only on that analyst's threads; firm lessons run on all of them.
14. **Replay data.** Each thread stores the core data fetched by code for each section and every
    tool call with its result. On replay, a recorded call returns its recorded result. A call
    that was never recorded is answered from live data and counted separately as "new data
    asked for". It is reported, not failed, and the stored threads are never changed.
15. **When an AI reply breaks a phrase or structure lesson,** it is retried once with the
    failure fed back. If it fails again, it is shown in the chat flagged, as a blocked grounding
    section is, and not inserted. When the analyst explicitly asks for something a lesson bans,
    the analyst wins: the text goes in, the conflict is shown, and the lesson is offered for
    retiring.
16. **"Sourced" numbers** are every tool result fetched during the thread, plus a lookup at save
    time over the company's facts, KPIs and the linked model's values for the report's periods,
    and anything `calc` can derive from those. The lookup is a cheap database read, so a correct
    figure the AI never fetched is not flagged.
