# Analekh roadmap

Status on **27 October 2026** (code and design at v0.0.5). This file holds the plan: what is
done, what comes next, and the new ideas with what each one needs. The build phases and their
exit criteria are in design doc 26; what changed in each update is in
[Commit-Info.md](../Commit-Info.md); open tasks are ticked off in
[pending-items.md](pending-items.md); how AI jobs run without paid APIs is in [AI.md](../AI.md).

Legend: ✅ done · 🟡 partly done · 🔲 planned · 💬 idea, needs a decision · ⛔ blocked

## 1. Where we are

| Phase | State | What finishes it |
|---|---|---|
| 0. Spike | 🟡 Data path proven at scale (54,350 filings, 2,756 companies, five results formats tying out) | Golden set: hand-check about 10 values per filing against the PDFs, then `analekh golden-test`; the 44 V11 unit suspects checked |
| 1. Data layer | 🟡 Universe, sectors, search, watcher, history from March 2023, validation V1 to V11, revisions, prices, Results desk, calendar, company pages, margins by company type (EBITDA, NIM, CPPPM), sign-in and roles, model locks; hosted on the Oracle Mumbai VM | The 290 companies with nothing on NSE; the 169 with no sector and the LSEG-to-NSE mapping; the Ind-AS profit tag decision (about 2,400 filings) |
| 2. Builder and sync | 🟡 Every engine has a working core; the Excel bridge links and scans a real workbook (Lemon Tree) | Real templates and models; `apply` on a real model; balance sheet and cash flow |
| 3. Document AI | 🟡 Pipeline built; Whisper transcribes recordings locally; embeddings local | A local model for extraction (see section 3); V10 wired; KPI golden set |
| 4. GenAI outputs | 🟡 Tools, calc, grounding check, report loop; Reports set-up screen | Word and PowerPoint writers for the quarterly update and initiation; Q&A screen; reports as jobs |
| 5. Discovery, IB, polish | 🟡 Comps (P/E, P/B), profile slide, alerts, add-in cores; Comps and Settings screens | Debt and cash for EV multiples; branded templates; demo |

**Done since the v0.0.5 documents (21 to 27 October):** sign-in, roles, first password by email
and model locks; LibreOffice moved to its own `recalc` container; RapidOCR in place of Tesseract;
security scan sweep; Excel bridge tested on a real workbook; hosting on Oracle Cloud Mumbai with
deploys from GitLab, the database and files restored, nightly database backups; CI on the VM's own
runners (no GitLab minutes), on uv's image with cached dependencies and retries; margins by
company type and interest ratios for lenders; chart and tab fixes for phone screens; the local AI
plan ([AI.md](../AI.md)).

## 2. Next, in order

1. **Phase 0 exit (v0.1.0):** golden set and `golden-test`; the 44 V11 suspects. Small, and it
   unblocks the version bump.
2. **Hosting hardening:** sign-in limit behind the proxies (real client address), SSH limited to
   the owner, backups off the box with one test restore, the domain and Cloudflare, a decision on
   scanning Arm64 images.
3. **Local AI stack (section 3):** Ollama on the VM and the laptop, the provider switch in
   `genai/client.py`, the `local_llm` queue, the golden-set quality gate.
4. **Report drafting:** the quarterly update and initiating coverage writers (Word, IB-style
   PowerPoint), the style check, the rating read from the analyst's model, reports as Celery jobs.
5. **Call highlights:** from transcribed recordings, with quotes and timestamps under the
   grounding check.
6. **Offer documents (section 4):** RHP and Prospectus financials for recent listings, after the
   owner approves the SEBI host.
7. **Balance sheet and cash flow** from the half-year and year-end filings; V4 for Ind-AS.
8. **Q&A screen**, last of the AI jobs.
9. **Peer view, red flags and alerts**; the sector editing screen.

## 3. AI without paid APIs

Full plan and deployment steps: [AI.md](../AI.md). In short:

| Job | Where | Model | State |
|---|---|---|---|
| Embeddings | VM | local (`docs/embeddings.py`) | ✅ built, local already |
| Whisper transcription | Laptop RTX 4060 (VM CPU as a slow fallback) | faster-whisper `large-v3` | ✅ built for recordings |
| Label matching, new-quarter KPI extraction | VM CPU overnight, or laptop | Qwen2.5 7B | 🔲 needs the provider switch |
| Results narrative, call highlights | Laptop | Qwen2.5 7B | 🔲 |
| Report and presentation drafts, comps commentary | Laptop, overnight | Qwen2.5 14B (partial offload) | 🔲 quality to prove |
| Q&A | Laptop, while it is on | Qwen2.5 7B | 🔲 weakest fit; last |
| Concall agent (join, record, relay) | Laptop | Playwright script + Whisper + 7B summary | 🔲 design doc 26.3 |

Rules that hold whatever the model: numbers only from tools or `calc`; XBRL wins; ratings and
targets from the analyst; no em-dashes; the analyst approves.

## 4. New sources

### 4.1 Offer documents for recent listings (SEBI) 💬

Recently listed companies have few or no quarterly results, but their offer documents carry
three financial years of restated figures (often a stub period too).

- **Flow:** DRHP or RHP for early coverage; the Prospectus, filed once the price is fixed around
  the issue close, becomes the final record. Order of precedence: Prospectus > RHP > DRHP. Quarterly
  XBRL, once filed, wins over all of them (V10).
- **Changes are kept, not overwritten:** each document's figures are a version; a change from
  RHP to Prospectus shows as a restatement for the analyst, and reaches a model only through an
  approved change set.
- **Extraction:** digital PDFs, so OCR is rarely needed (RapidOCR covers scans). The risks are
  length (300 to 600 pages; the page classifier finds the restated statements, the KPI section
  and the peer table), tables split across pages, units mixed in one document (lakhs, crores,
  millions; a V11-style check), and restated versus proforma figures.
- **Source checked 27 October 2026:** SEBI's "Draft Offer Documents filed with SEBI" listing loads
  (2,277 records, 25 a page, newest first). Detail pages:
  `/filings/public-issues/{mon-yyyy}/{slug}_{id}.html`; PDFs under `/sebi_data/commondocs/`. No API;
  older pages are reached through a JavaScript form; `sebirss.xml` does not cover filings.
- **Needs (owner):** a rule 1 style approval for `www.sebi.gov.in`, limited to the listing page,
  `/filings/public-issues/` detail pages and `/sebi_data/commondocs/` PDFs; one listing request a
  day plus one detail page and one PDF per new filing; honest User-Agent. SEBI's website terms to
  be read first. Older listings: take the Prospectus from the NSE side instead of paging back
  (another NSE path to approve).
- **To check before building:** how RHPs and final Prospectuses appear in the listing; whether
  the abridged prospectus carries the summary financials.

### 4.2 Debt-segment filings 💬

Companies with listed bonds or NCDs file results under SEBI's rules for debt-listed entities
(believed to be Regulation 52, half-yearly with some quarterly; to be checked).

- Equity-listed companies: little gain, their results already come from equity filings.
- Debt-only companies (many NBFCs, HFCs, infrastructure firms): a real addition, but a change of
  universe. About 290 unmatched feed items are already from such issuers
  (`out/unmatched_feed_items.csv`).
- Needs an NSE path approval and a check of whether these results carry XBRL.

### 4.3 Investor presentations and transcripts 💬

Already proposed (design doc 28): NSE's announcements list, subject "Investor Presentation", one
request a day. Needs the owner's rule 1 approval. Also the source for finding calls automatically
for the concall agent.

## 5. New outputs and features

Lessons from the industry: large banks already turn analysts' approved scripts into video with
AI avatars of the analyst (reported for UBS in 2025; told first hand at a university session in
October 2026). The analyst keeps the view; the tool presents it. That is the same line as rule 8.
Avatar video itself is a bought product now, so Analekh competes on evidence, speed and coverage.

| Idea | What it gives | Needs | State |
|---|---|---|---|
| Source links shown in every report | Each figure links to its filing page; few research outputs show this | Report writers | 🔲 with drafting |
| Filing-to-draft time tracked | The headline speed claim, measured | Timestamps on jobs | 🔲 |
| Coverage from the RHP, before listing day | A grounded first pass and a starting model the day a company lists | Section 4.1 | 💬 |
| KPIs and peers from "Basis for Offer Price" | Seeds KPI mapping and the comps set from the company's own disclosure (believed required by SEBI ICDR since 2022; to check) | Section 4.1 | 💬 |
| DRHP to RHP to Prospectus change note | What changed in numbers, issue size, risks, use of proceeds | Section 4.1 | 💬 |
| Lock-in calendar | Anchor and promoter lock-in expiries as catalysts on the results calendar | Prospectus dates | 💬 |
| Use of proceeds tracked | Stated use against monitoring-agency reports | NSE announcements approval | 💬 |
| Slides with the analyst's voice | Approved script read over the deck by local text-to-speech, cloned only from the analyst's own voice with written consent; labelled AI-assisted | Report writers; a local TTS model | 💬 |
| Avatar video | Talking-head presenter | Weak on 8 GB locally; vendors cost money | 💬 later, if asked for |
| Phone model (OnePlus 13) | Offline personal assistant (PocketPal, Qwen2.5 3B) | Nothing in Analekh | personal use only |

Compliance before any voiced or AI-assisted output is shared: read SEBI's current rules for
research analysts and AI tools (disclosure to clients, the analyst's responsibility); the analyst
approves every script; outputs are labelled.

## 6. Decisions waiting on the owner

- SEBI host for offer documents (section 4.1); NSE paths for announcements (4.3) and debt filings (4.2).
- Moving each AI job off Claude, after the golden-set gate (AI.md).
- The Ind-AS profit tag (about 2,400 filings); the LSEG-to-NSE sector mapping (25 groups); the 250 BSE-only filers.
- Bank presentation and calculations (walkthrough); the domain name; the logo.

## 7. After v1 (design doc 26.3)

Live and intraday prices (paid data); NSE's finer industry classification (licensed data); the
live earnings-call listener; avatar video.
