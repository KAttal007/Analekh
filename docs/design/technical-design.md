**Analekh**

*The analyst's record, kept for you.*

Technical Design Document

| **Field** | **Detail** |
|---|---|
| Author | Kaushal Attal |
| Version | 0.0.6 (design, updated during the build) |
| Date | 29 October 2026 |
| Supersedes | Version 0.0.5 (21 October 2026) |
| Status | Phase 0 nearly complete; Phase 1 (data layer) in progress and hosted on Oracle Cloud, Mumbai: results for 2,748 companies from March 2023, daily prices, scheduler and feeds, Results desk, calendar, company pages, comps, settings, sign-in with roles, model locks, IPO coverage from SEBI offer documents. The agentic AI plan (local models, context sources, learning from the analyst) is proposed |

**Purpose.** Every design decision for Analekh: what it does, the data and the rules around it, architecture, workflows, schema, each engine, interfaces and API, deployment, testing, costs, risks and the build plan. Written for the engineer building it and for reviewers.

**How this version is kept short.** From 0.0.6 the document states the current design only. Copies of files that live in the repository (the DDL, Compose, CI pipeline, dependency lists, environment file) are replaced by a summary and a pointer to the file, which is the source of truth. History lives in `docs/design/deviations.md` (every departure, folded per version) and `Commit-Info.md` (every major update). Issues fixed since 0.0.5 are dropped; nothing else is.

### What changed in 0.0.6

| **Change** | **Summary** |
|---|---|
| Sign-in and roles | Every route needs a signed-in user, except sign-in, the reset flow and `/public/*`. Admin and analyst roles; first password generated and emailed; reset codes by email; bridge tokens; audit log (sections 19.1, 20, 23). |
| Model locks | One holder per model while an update, build or report runs; others see it read-only and are told when it frees (sections 16.4, 19.1, 20). |
| Recalculation | LibreOffice runs in its own `recalc` container on an internal network; Apply refuses cleanly when it is down or cannot compute a cell (sections 16.5, 22.1). |
| Margins by company type | One Margin column: EBITDA margin, NIM for lenders, core pre-provision profit margin for brokers and asset managers; interest ratios on the company page (sections 10.3, 19.1). |
| Hosting | Oracle Cloud free tier, Mumbai: the production stack, CI runners and nightly backups on one Arm64 VM (sections 22.1, 22.5, 22.7). |
| IPO coverage | SEBI's RHP and Prospectus lists (owner-approved host) feed restated statements, text and per-section grounded drafts for recent listings (sections 3, 6.11, 8.2, 17, 20, 23). |
| Security audit | The audit of 29 October 2026 found 7 issues, all fixed: uniform sign-in replies, redirect hops checked against the allow-list, reset-code lockout, tokens revoked on password change, mail certificate checks, body cap at nginx, the trusted proxy address (section 23). |
| Excel bridge | Linking patches only the tag parts of the workbook; open workbooks are read from a copy; tested on a real model (sections 13, 19.2). |
| Agentic AI (proposed) | Agentic RAG over official and research sources fetched ahead of time, conflict flags on the analyst's estimate changes, local models, and adapters trained on each firm's and analyst's accepted reports; Analekh as a platform each firm hosts itself (sections 3.4, 6.12, 17.3 to 17.6, 22.8; plan in `AI.md`). |
| Format | Compact: current design only; repository files referenced, not copied (Appendices A, D, F, G and section 22.3). |

### Earlier versions

| **Version** | **Date** | **Headline** |
|---|---|---|
| 0.0.5 | 21 Oct 2026 | Unit check V11; scheduler in Docker; results calendar; results history; Reports set-up; ratings only from the analyst's model |
| 0.0.4 | 18 Oct 2026 | Every workflow diagrammed; history from March 2023; bhavcopy prices; NSE sectors first |
| 0.0.3 | 15 Oct 2026 | Integrated-filing lookup replaces the frozen results feed; per-format element tables; revisions; Results desk |
| 0.0.2 | 14 Oct 2026 | Kite removed; sector sources with precedence; in-browser search; GitLab Free; pnpm; versioning by phase |
| 0.0.1 | 12 Oct 2026 | Renamed Analekh; preloaded universe; coverage levels; workbook engine; template onboarding; Coverage Builder |

Details of each: `deviations.md` ("Folded into" sections) and `Commit-Info.md`.

### Contents

- Overview and goals
- Requirements
- Data sources and access
- Company universe and coverage levels
- System architecture
- Workflows
- Inputs and outputs
- Data model (PostgreSQL)
- Ingestion layer
- XBRL parsing and validation
- Document pipeline
- Workbook understanding engine
- Model discovery and recognition
- Template onboarding
- Coverage Builder
- Model Sync Engine
- Analysis and GenAI Engine
- IB Output Engine
- User interfaces
- API design
- Technology stack
- Packaging, deployment and setup
- Security, compliance and data rights
- Testing and quality
- Cost model
- Build plan
- Risks and mitigations
- Open questions
- Appendices
- Sources

## 1. Overview and goals

Research and investment banking analysts spend much of their week on the same loop: find the newest results, copy numbers into a model, check what changed, roll forecasts forward, then write a note, a comps table or a pitch page. Starting coverage is the same work at a larger scale. Analekh automates both.

#### 1.1 One-line description

Search any NSE-listed company. If you have a model, the system finds it, proposes the exact changes from the newest results and applies them after your approval. If you do not, it builds one from your sector template with sourced history and proposed assumptions. Either way it then drafts the quarterly update or initiation, slides and comps, grounded in the filings and in the current context around the company.

#### 1.2 Users

| **User** | **What they need** |
|---|---|
| Equity research analyst | Fast model updates on results day, variance against own estimates, call digest, draft note in their own voice, Q&A over filings, quick builds when initiating. |
| Investment banking analyst | Comps, profile slides, pitch pages kept current, trigger alerts, quick models for new names (including recent listings). |
| Reviewer (associate, PM) | Every number traced to its XBRL tag or PDF page; an approval trail for every change. |
| Admin | Users, roles, templates, upload limit, model locks. |

#### 1.3 Goals

- Every NSE-listed company available from day one; no per-company setup to see its numbers.
- Ticker in, model updated: no manual PDF handling for core financials.
- New coverage in minutes: a sourced model from the analyst's template plus a draft initiation, including from an RHP before listing.
- Human in the loop: nothing written to a model without an approved change set or approved assumptions.
- Grounded GenAI: no number in generated text that did not come from the database, the model or `calc`.
- First drafts that need no pasted context and read in the analyst's voice (proposed, section 17.3).
- Traceability: each value carries its source (feed item, file hash, XBRL context or PDF page).
- One data foundation for research and banking.

#### 1.4 Non-goals

- No ratings or target prices generated by Analekh. A report carries one only when read from the analyst's own model or filled in by the analyst (owner's amendment, 21 October 2026; section 23).
- No real-time trading data or order execution; prices are end of day (section 3.3).
- No BSE-only companies in v1 (section 4.3).
- No crawling of exchange or regulator web pages; only owner-approved hosts and paths.
- The system never writes model formulas with AI; formulas come from templates the analyst controls.
- No facts trained into model weights: weights learn style, retrieval holds facts (section 17.4).

## 2. Requirements

#### 2.1 Functional requirements

| **ID** | **Requirement** | **Phase** |
|---|---|---|
| F1 | Preload every NSE-listed company (symbol, name, ISIN, series, listing date, face value); refresh weekly. | 1 |
| F2 | Search companies by symbol or name with autocomplete. | 1 |
| F2a | Each results season at a glance (who reported, growth, movers, sectors) and each company's latest quarter with QoQ and YoY. | 1 |
| F2b | Each trading day's closing prices once after the close, with market cap; keep only the latest day. | 1 |
| F3 | Poll NSE's published feeds on a schedule; keep a permanent history of items. | 1 |
| F4 | Fetch and parse results XBRL for every filer, both bases; store raw files once (hash); use the most recently filed value when a quarter is refiled. | 1 |
| F5 | Validate every filing with accounting identities and sanity rules; flag failures. | 1 |
| F6 | Backfill results for every company, resumably, from March 2023; older periods on demand. | 1 |
| F7 | Watchlist that controls AI extraction, updates, reports and alerts. | 1 |
| F7a | Sign-in for every user, admin and analyst roles, one holder per model at a time. | 1 |
| F8 | Read any workbook's structure: periods, inputs versus formulas, labels, drivers, checks, dependencies. | 2 |
| F9 | Upload templates by sector; suggest the mapping; confirm once; test-build before activation. | 2 |
| F10 | Build a new model from a template with sourced history, a Sources sheet and passing checks. | 2 |
| F11 | Propose first-pass assumptions with rationale and citations; analyst accepts or edits each. | 2 |
| F12 | Discover existing models in watched folders or the open workbook; identify the company; link once. | 2 to 5 |
| F13 | Change set for a linked model from new results: writes, dependents, roll-forwards, suggestions. | 2 |
| F14 | Apply approved changes, recalculate, save a new version; never overwrite the original. | 2 |
| F15 | Extract sector KPIs and narrative from presentations, annual reports and transcripts with pages. | 3 |
| F15a | Read RHPs and Prospectuses of recent listings: restated statements, price band, peers, text. | 3 |
| F15b | Fetch official and research context documents as they publish; tag them by sector and topic (proposed). | 3 |
| F16 | Results flash, variance bridge, call digest, red flags, quarterly update and slides. | 4 |
| F16a | Explain the analyst's estimate changes with evidence; flag estimates the evidence contradicts before drafting (proposed). | 4 |
| F17 | Draft initiation from the built model and sourced research; IPO coverage from the RHP or Prospectus. | 4 |
| F18 | Answer questions over a company's filings with page citations. | 4 |
| F18a | Learn each firm's and analyst's style from accepted reports and edits (proposed, after the MVP). | 5 |
| F19 | Refresh comps tables, profile slides and tagged pitch pages. | 5 |
| F20 | Alert the analyst when a watchlist company files results or a red flag appears. | 5 |

#### 2.2 Non-functional requirements

| **Area** | **Target** |
|---|---|
| Accuracy | 100% match on mapped XBRL elements; 95% or better precision on AI KPIs in the golden set; every AI value carries a page. |
| Recognition | Mapping suggestions correct for 90% or more of rows before review; zero silent writes to unconfirmed rows. |
| Latency | Newest filing detected within an hour in season; change set under 2 minutes for a cached filing; new build under 5 minutes with history cached. |
| Traceability | Any written value traces to feed item, file hash and XBRL context or PDF page. |
| Reliability | Idempotent jobs; re-running ingestion never duplicates facts; retries with backoff. |
| Cost | No AI cost for the all-company numbers layer; AI only on selected pages; aim for no API cost through local models (AI.md); tokens logged per call. |
| Security | Secrets only in the environment; sign-in on every route; inputs bounded at the boundary; macros never executed; user files private. |
| Portability | One `docker compose up` for the server; the Excel bridge on the analyst's machine; each firm can host its own instance (section 22.8). |

## 3. Data sources and access

Core numbers come from NSE's published XBRL, found through its published feeds and lookups the owner has approved, not from scraping or paid feeds. Checked from 11 October 2026 through the build.

#### 3.1 Findings

| **Topic** | **Finding** |
|---|---|
| APIs | No free official developer API for Indian filings; NSE has none. BSE's results API refuses automated requests; about 250 companies with nothing on NSE file only with BSE. |
| NSE terms | Prohibit systematic or automated collection and scraping (clause 9) and redistribution without permission (clause 8). |
| RSS feeds | nsearchives.nseindia.com/content/RSS/: Financial_Results, Online_announcements, Board_Meetings, Corporate_action, Insider_Trading, Related_Party_Trans, Voting_Results, brsr and others; TTL 5 minutes; rolling windows. Financial_Results has carried no filing since 24 August 2026. Announcements link PDFs and hold about 12 hours of items. Feed pubDate is DD-Mon-YYYY HH:MM:SS (IST). |
| Integrated filings | SEBI moved quarterly results into integrated filings. NSE's lookup (`/api/integrated-filing-results`) lists each company's filings (quarter, basis, Original or Revision, broadcast time, links to XBRL, iXBRL, sometimes a PDF); without a ticker, the latest across companies. Answers without the home page's cookies; the home page answers 403 to an honest User-Agent. One schema (`in-capmkt-ent`, Ind-AS names) for every filer. Starts with the March 2025 quarter; quarter and year to date, no prior-year columns. Of the first 1,292 companies, 1,036 file both bases, 255 standalone only. |
| Results history | NSE's financial-results list (`/api/corporates-financial-results`, approved 15 October 2026): every filing back to 2005, XBRL from 2018 (TCS 26 quarters, ICICI Bank 28), ending where integrated filings start. Files up to December 2022 (`_WEB.xml`) and some early-2023 bank files lack their main contexts; complete files start March 2023. A link of "-" means no XBRL. |
| Gaps and revisions | 216 of the first ~1,500 companies had no integrated filings (mostly SME, recent listings); about one PDF link in three reads ".../corporate/null"; a few XBRL links answer 404. 564 of 1,292 companies refiled at least one quarter (1,108 quarters; about 4% of values differed); a first result after listing can cover a half-year only. |
| Request limit | NSE limits the number of requests, not their pace: lookups and archives stall (nothing refused) after about 565 to 590 requests most often (sometimes 1,504 or 4,195) and answer again after about 10 minutes. The CDN stalls a User-Agent containing an email or URL, so the contact goes in the From header. |
| Timing | Integrated filings appear a median of 1 second after filing (94% within a minute; 299 filings, 24 companies, 18 October 2026). Since 2023 every first filing of a quarter came between day 8 and day 59; 61% between 16:00 and 21:00 IST, under 1% between midnight and 09:00. |
| Bhavcopy | nsearchives `/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`: one zip per trading day, every traded security (ISIN, symbol, series, OHLC, previous close, volume); 404 on a day without a file. Matched 3,044 companies by ISIN on 16 October 2026. |
| Equity lists | EQUITY_L.csv (symbol, name, series, listing date, paid-up value, lot, ISIN, face value); no sector column; SME listed separately with DD-Mon-YY dates. |
| Sectors | NSE's taxonomy: 12 macro sectors, 22 sectors, 58 industries, ~200 basic industries; company values only on quote pages, which refuse honest requests. NSE Indices' constituent CSVs (niftyindices.com `/IndexConstituent/`) give the 22 sector names for 1,430 companies. BSE's List of Securities has no industry. Excel's Stocks data type (Microsoft 365) gives LSEG industry groups: 2,458 of 2,606 main-board companies. |
| Announcements list | `/api/corporate-announcements` can filter by subject ("Investor Presentation": 1,211 from 1,046 companies in three months). Not used; needs approval (section 28). |
| SEBI offer documents | `sebi.gov.in` lists DRHPs (smid 10), RHPs (11) and Prospectuses (12), 25 a page, newest first, no API. Each entry page (`/filings/public-issues/`) embeds its PDF from `/sebi_data/attachdocs/<month>/<id>.pdf`; `/sebi_data/` itself answers 403. Approved 28 October 2026; layout confirmed on Jio Platforms, 29 October 2026. |
| Paid alternatives | BSE corporate feeds INR 3 to 9 lakh a year each; Kite Connect INR 2,000 a month (historical and live data; not used); Screener exports (no API); EODHD (paid, depth unverified). |
| Transcripts | SEBI LODR: audio within 24 hours, transcript within five working days. |
| Reachability | NSE's main site was geo-blocked from a foreign cloud region; archive hosts and niftyindices.com sometimes stopped answering an Indian connection for hours. From the Oracle Mumbai VM the lookup, feeds and bhavcopy answer. Fetchers retry later with single requests and never work around a block. |
| Claude PDF input | 32 MB and up to 600 pages a request (100 under a 1M context), about 1,500 to 3,000 text tokens a page plus images; Files API and batches. |

#### 3.2 Source matrix

| **Need** | **Chosen source** | **Alternative** | **Notes** |
|---|---|---|---|
| Company universe | NSE EQUITY_L.csv plus SME list, weekly | BSE scrip master (paid) | No sector column |
| Sector | NSE Indices lists (22 NSE sectors), then Excel Stocks data type (LSEG group); user override wins | Curated map | Precedence per company (section 4.2) |
| Results numbers | Integrated-filing lookup to XBRL: per company, plus one request without a ticker per watcher run | BSE feed (paid) | No AI for core statements |
| Results history | Financial-results list, per company, complete XBRL from March 2023 | Licensed data; IR pages | About 15 quarters and 4 years per company |
| Presentations, transcripts, annual reports | Announcements RSS to PDF; IR pages; import folder | BSE (paid) | AI on selected pages |
| Calendar and events | Board_Meetings, Insider_Trading, Related_Party_Trans, encumbrance RSS | None free | Calendar, red flags, alerts |
| Prices | NSE bhavcopy, one file per trading day; market cap from the latest filing's share count | Stocks data type in the analyst's workbook; Kite (paid) | Latest day only (section 3.3) |
| Recent listings | SEBI RHP and Prospectus lists, entry pages and PDFs, once a day | NSE side (not approved) | DRHP not used (section 6.11) |
| Current context | Official and research publishers (section 3.4) | None | Proposed; each host needs approval |
| Embeddings | Local model (default) | Hosted API | Anthropic has no embeddings model |

**Access rule (CLAUDE.md rule 1).** Published RSS feeds at their interval and the files they link to; the equity list CSVs; NSE Indices' `/IndexConstituent/` CSVs; on www.nseindia.com only `/`, `/api/integrated-filing-results` (14 October 2026) and `/api/corporates-financial-results` (15 October 2026), per company plus one request without a ticker per watcher run (hourly 09:00 to 23:00 in season, 21:00 otherwise); ONE bhavcopy per trading day (17 October 2026); on sebi.gov.in the three list pages (once a day, newest page only), entry pages and `/sebi_data/attachdocs/` PDFs (28 October 2026). Requests identify as Analekh, never as a browser. No other page or internal API; widening `ALLOWED_HOSTS` or `ALLOWED_PATHS` needs the owner's approval. Written confirmation from NSE or a licensed feed before any public or commercial release.

#### 3.3 Prices

Decided 17 October 2026: end of day only, from the bhavcopy; no live feed and no price history.

- **Source:** ONE bhavcopy per trading day after the close (section 9.5). Equity series only (EQ, BE, BZ; SM, ST, SZ on SME), one row per ISIN, main series first.
- **Stored:** trade date, OHLC, previous close, volume and market cap = close x shares in issue (paid-up equity capital from the results filings / face value from the equity list). Guards for tagging errors: when the latest two quarters' capital differ more than 50 times the smaller is used; capital above 100 times total assets is ignored; a market cap above Rs 30 lakh crore is not shown. The results watcher recomputes market caps when filings arrive (`analekh prices --recompute` by hand).
- **Only the latest day** (owner's rule, 18 October 2026): each file replaces the previous day; a company missing from the file has no price rather than a stale one; an older day never replaces a newer one.
- **In Excel:** the Stocks data type can still show a delayed price inside the analyst's workbook.
- **Not used:** Kite Connect, live quotes, any NSE page or internal API.

#### 3.4 Context sources (proposed, not built)

For agentic drafting (section 17.3) each instance fetches official and research documents as soon as they publish, so the agent retrieves rather than searches. Owner's direction, 29 October 2026: official sites over media; no Bloomberg or news channels; leading private research included.

| **Source** | **Kind** | **Content** | **Cadence** |
|---|---|---|---|
| RBI | Official | MPC statements and minutes, circulars, notifications | Calendar for MPC days (schedule published ahead; statement on the meeting's last day), daily poll otherwise |
| Government of India | Official | Policies, schemes, subsidies, mandates, gazette notifications; ministries chosen per sector | Daily poll |
| OPEC, World Bank | Intergovernmental | Oil market reports; outlooks, commodity reports | Calendar plus weekly poll |
| World Economic Forum, IBEF | Public research, industry body | Reports, sector reports | Weekly poll |
| CRISIL, EY, McKinsey, BCG, Bain | Private research | Free public reports only | Weekly poll |
| Gartner | Private, paywalled | Reports a firm licenses | Analyst upload only, never fetched |

Conditions: each host and path set approved by the owner and recorded in `deviations.md` before code; site terms read first; listing pages and linked files only, through `PoliteClient`; no logins, paywalls or crawling. Documents are stored once by hash, read, chunked, embedded and tagged with sectors, companies and topics at ingest. Each firm's instance fetches for itself; nothing is shipped centrally (no knowledge packs). Details: AI.md section 3.

## 4. Company universe and coverage levels

Knowing a company exists and covering it deeply are different things, so there are three levels.

| **Level** | **What happens** | **Cost and trigger** |
|---|---|---|
| 1. Universe | Every NSE-listed company preloaded from EQUITY_L.csv and the SME list; listings and delistings weekly. | Free; automatic |
| 2. Numbers for everyone | Every results filing NSE lists parsed and validated from March 2023; closing prices daily. | Local parsing; automatic |
| 3. Deep coverage | AI extraction, model updates, Coverage Builder, reports, alerts. | AI and compute; watchlist or one-click Analyse |

Recent listings without quarterly history are covered from their offer documents (section 6.11), as their own records until NSE assigns a symbol.

#### 4.1 History

- **Integrated filings** (from March 2025) through the lookup; **March 2023 to December 2024** through the financial-results list: about 15 quarters and four years (FY23 to FY26) per company and basis. 1,567 companies had 14 or more quarters on 18 October 2026.
- **Backfill:** `analekh results-backfill` covers every company with a sector, both bases, one company per transaction, one request every 2 s, waiting 10 minutes when NSE stops; `--history` reads the list instead, by sector. Integrated backfill finished 15 October, history 17 October 2026.
- **Older periods:** files before March 2023 lack their main contexts and are rejected (rebuilding contexts by id was declined: rule 5). Older periods come from IR sites or the import folder, on demand.

#### 4.2 Sector classification

Neither the equity list nor the XBRL carries a sector, and sector picks templates and peers. Precedence (owner, 16 October 2026: NSE's taxonomy first); a lower source never overwrites a higher one; `companies.sector_source` records which set it:

- **User override** (editing screen still to build).
- **NSE Indices lists** (eleven broad lists and the bank indices): the 22 NSE sector names; stale uppercase labels ignored.
- **Excel Stocks data type:** BSE's List of Securities converted to `XBOM:<code>` records in Microsoft 365, `=FIELDVALUE(B2,"Industry")`, imported by ISIN (`analekh universe sectors --stocks-file`). The LSEG group is always kept in `sector_lseg` and becomes the sector only where nothing better exists.

On 18 October 2026: 1,430 companies with an NSE sector, 1,587 with an LSEG group only, 169 with none. The LSEG-to-NSE mapping (28 clear groups covering 973 companies; 25 groups and 614 companies to decide) waits for the owner.

The results taxonomy (indas, banking, nbfc, insurance, life_insurance) is guessed only from strong signals (bank index membership, NBFC or insurer industries; never LSEG groups, whose Banking Services includes NBFCs); a filing's line items decide it and correct a guess (section 10.1).

#### 4.3 Limit

BSE-only companies are not in NSE's feeds and BSE has no free equivalent. v1 covers every NSE-listed company, dual-listed included; BSE-only coverage needs a licensed feed.

## 5. System architecture

Six layers left to right: sources, ingestion, processing, core data, engines, interfaces. Language models (Claude today; local models planned) serve the document pipeline and the engines.

*Figure 1. Components and data flow (v0.0.6). Solid lines carry data, dashed lines are control or return paths, amber lines the analyst's approval path, dotted blue lines language-model calls. Solid boxes are built and running on real data; dashed boxes are built cores not yet running, or planned.*

#### 5.1 Layers and components

| **Layer** | **Component** | **Responsibility** |
|---|---|---|
| Sources | NSE integrated-filing lookup | Integrated filings per company; the latest across companies without a ticker. |
| Sources | NSE financial-results list | Results per company back to 2005; complete XBRL from March 2023. |
| Sources | NSE RSS feeds | Announcements (PDF), board meetings, event feeds. |
| Sources | NSE equity list; sector sources | Every listed company weekly; NSE Indices lists and the Stocks data type import. |
| Sources | NSE bhavcopy | One file per trading day (section 3.3). |
| Sources | SEBI offer documents | RHP and Prospectus lists, entry pages, PDFs (section 6.11). |
| Sources | Context publishers (proposed) | RBI, Government of India, OPEC, World Bank, WEF, IBEF, private research (section 3.4). |
| Sources | Company IR pages, import folder | Fallback for missing documents and older history; analyst uploads (Gartner). |
| Ingestion | Scheduler | Celery beat: results watcher by season, prices after the close, weekly universe, feeds every 5 to 30 minutes, SEBI lists daily, session purge (section 9.6). |
| Ingestion | Feed Watcher | Fetches the published feeds, dedupes, keeps every item, links items to companies. |
| Ingestion | Results Fetcher | Lookups per company and per watcher run; each XBRL downloaded once, hashed, stored with NSE's revision flag. |
| Ingestion | Filing Fetcher, IPO watcher | Announcement PDFs and offer documents downloaded once, hashed, stored. |
| Ingestion | Context Fetcher (proposed) | Calendar plus polling per publisher; stores, reads and tags each document once. |
| Ingestion | Universe Loader, Price Fetcher | Company list and sectors; the day's bhavcopy and market caps. |
| Processing | Raw Filing Store | Immutable object storage keyed by hash; XBRL compressed. |
| Processing | XBRL Parser | Normalised facts for every filer; results format from the line items; no AI. |
| Processing | Document Pipeline | PDFs read locally, pages classified, selected pages to the model; KPIs, chunks, embeddings; offer-document statements. |
| Processing | Validation | V1 to V11 per format; decides the value in use (the most recently filed). |
| Core data | PostgreSQL + pgvector | Companies, filings, facts, KPIs, documents, prices, users, templates, models, versions, locks, change sets, IPO records. |
| Engines | Model Sync Engine | Updates linked models: mapping, write plan, dependencies, roll-forward, change sets, versions. |
| Engines | Analysis + GenAI Engine | Reports, Q&A, IPO coverage; proposed: agentic RAG, estimate conflicts, learning per firm and analyst. |
| Engines | Coverage Builder | New models from sector templates with sourced history and proposed assumptions. |
| Engines | IB Output Engine | Comps, profile slide, pitch refresh. |
| Engines | Results views | Desk, calendar, latest quarter, history, margins by company type, prices. |
| Interfaces | Web App | Welcome and sign-in, desk, search, watchlist, company pages, IPO coverage, reviews, templates, reports, Q&A, comps, settings, admin. |
| Interfaces | Excel | Bridge that finds and links models (xlwings; Office.js later). |
| Interfaces | Word, PowerPoint, Alerts | Notes and slides; email or Telegram. |

## 6. Workflows

Twelve workflows. The first four run on real data, as do the feed watcher and calendar of the ninth and the IPO watcher and reader of the eleventh. Others have working cores with synthetic tests, or are planned. In every diagram solid boxes are built and running, dashed are not running yet, grey are external sources, amber is the analyst's approval.

### 6.1 Results collection (built)

*Figure 2. Results collection: four triggers, two NSE lookups, one pipeline (sections 9.3, 9.4, 10).*

1. **A trigger starts a run:** the results watcher (one request without a ticker, latest 500 filings), a refresh of one company (`analekh refresh`, the API), the backfill of every company with a sector, or the history backfill (`--history`, by sector).
2. **The lookup answers** (integrated-filing lookup, or the financial-results list for history): quarter end, basis, Original or Revision, filing time, links.
3. **Files are chosen:** links of "-", null or undefined are no links; `_WEB.xml` never fetched; stored files skipped; originals before revisions, oldest first.
4. **Each XBRL is downloaded once** from nsearchives through the polite client (allow-list, honest headers, 2 s pace in bulk); a refusal or stall stops the run.
5. **Hashed and stored** in MinIO at kind/yyyy/mm/sha256.xml; a known hash is skipped.
6. **Guard:** missing main contexts are rejected and noted; broken XML is retried once, then skipped and noted.
7. **Parsed:** contexts resolved by dates; results format from the line items.
8. **Validated:** V1 to V11 with the format's terms; block flag on failure; V11 corrects wrong units when two signals agree.
9. **Inserted as history:** the newest filed value of each line is in use, whatever the arrival order; refiled quarters get a revision status and what changed.
10. **One transaction per company;** a stopped run keeps what it stored; the watchdog resumes 10 minutes later at the company it stopped on; one JSON log line per company.

### 6.2 Daily closing prices (built)

*Figure 3. Daily prices: one bhavcopy per trading day, the latest close only (sections 3.3, 9.5).*

1. **Runs** on weekdays hourly 19:00 to 23:00 IST until the day is stored (`analekh prices`).
2. **Picks the trading day:** today after 18:00 IST, else the day before; weekends roll back to Friday.
3. **Skips** without a request if that day or a later one is stored.
4. **ONE request** for the bhavcopy; 404 means a holiday or not yet published.
5. **Parses** equity series, one row per ISIN, main series first.
6. **Matches by ISIN;** shares = paid-up capital / face value (with the guards); market cap = close x shares.
7. **Upserts today and deletes every older day:** about 3,000 rows.
8. **Read by** the price endpoint, the company page tiles, the desk's market-cap column and sort, comps, and later the AI's `get_prices`.

### 6.3 Company list and sectors (built)

*Figure 4. Company list and sectors: the universe weekly, sectors by precedence, the results format from the filings (sections 4, 9.1).*

1. **The universe loader** reads the equity and SME lists weekly, upserts by ISIN, marks missing companies inactive.
2. **Sectors by precedence** (`analekh universe sectors`): user, then NSE Indices, then LSEG; the LSEG group is always kept.
3. **Results format** guessed from strong signals only; filings' line items decide it.
4. **The web app downloads the universe once** (`GET /companies/index`, ETag, gzip) and searches it in the browser.
5. **Companies with a sector** are the desk's and the backfill's scope.
6. **Planned:** the LSEG-to-NSE mapping and a sector editing screen.

### 6.4 Opening Analekh and reading results (built)

*Figure 5. Opening Analekh: welcome and sign-in, then the desk and company pages, over the read models (sections 19.1, 20).*

1. **Signed out,** Analekh opens on the welcome screen with live counts (`/public/welcome`); a scroll, swipe, tap, drag or Enter hands off to sign-in. A live session opens the Results desk directly.
2. **After sign-in** the desk's data loads first, then a short unlock (about 0.35 s) plays, so the table never fills in mid-animation.
3. **The desk** (`GET /desk`, one request) lists the quarter's reporters ten per page by filing time or market cap, filters in the URL; movers, sector progress and the results calendar (`GET /calendar`) beside it.
4. **Search** ranks the universe in the browser; the server answers before it loads and for typos. Screens with their own company picker, or not about one company, hide the top search.
5. **The company page** reads the company, filings, latest quarter, results history (one request for tiles, chart and table) and the last close, with a basis switch in the URL. Each quarter heading links the filing in use on NSE (iXBRL) and opens its details; filings without a column fold out below. Raw XBRL is never linked.
6. **The watchlist** shows the desk's columns for the companies followed, with their coming results.
7. **Data stays fresh five minutes** in the browser; motion only on what is clicked.

### 6.5 Quarterly model update (core built, Phase 2)

*Figure 6. Quarterly update. Steps 6 and 7 form the approval gate.*

1. **Search the ticker** in the web app or Excel; the company is already in the universe.
2. **Newest filing?** The database returns it (collected by workflow 6.1); only the newest filing drafts an update, and when it is blocked nothing is drafted and the analyst is told.
3. **Fetch if missing:** download, parse, validate.
4. **Validated facts** stored with source references.
5. **New-period facts and the linked model** go to Model Sync, which takes the model's lock; the model is located by discovery (section 13).
6. **Change set:** writes, dependent-cell counts, roll-forwards, suggested assumption changes.
7. **Approve or edit** each item; nothing is written before this.
8. **Apply:** write, recalculate (recalc service or Excel), save a new version; a set drafted on an older version is refused (409); actuals versus estimates computed.
9. **Outputs:** flash, quarterly update, slides, with citations (and, proposed, the agentic flow of 6.12).

### 6.6 Start coverage (core built, Phase 2)

*Figure 7. Start coverage with the Coverage Builder. Steps 6 and 7 form the approval gate.*

1. **Start coverage** on any company; pick a template (the analyst's upload for the sector, or built-in).
2. **Build request** to the Coverage Builder (holds the model's lock).
3. **History and KPIs** from the database; anything missing backfilled and run through the document pipeline.
4. **Sourced actuals** return with references.
5. **Propose drivers** from history and management guidance.
6. **Assumptions with citations** shown to the analyst.
7. **Accept or edit** each.
8. **Tagged model** written; checks must pass.
9. **Initiation draft, comps and slides;** from the next results the quarterly update takes over.

### 6.7 Template onboarding (core built, Phase 2)

*Figure 8. Template onboarding: read, suggest, confirm once, test build.*

1. **Upload** a workbook (blank template or another company's model), tagged with sectors; admins only.
2. **The workbook engine** reads periods, inputs, formulas, labels, drivers, checks and the formula graph (section 12).
3. **A mapping is suggested** per row with confidence: synonyms, then fuzzy, then a small model for labels neither places.
4. **The analyst confirms or fixes it** once per template.
5. **A test build** with one real company fills and recalculates it (admins only).
6. **The test report** lists checks, blank rows, unmapped facts and broken formulas; a failure goes back to the mapping.
7. **On a pass the template becomes active,** versioned, for the Coverage Builder and Model Sync.

### 6.8 Documents, KPIs and reports (set-up built; drafting planned, Phases 3 and 4)

*Figure 9. Documents to KPIs, and reports that only use numbers from the data (sections 11, 17).*

1. **Documents arrive** from the announcements feed, IR pages or the import folder; call recordings are transcribed locally.
2. **Each file is fetched once** and hashed into MinIO; only watchlist or on-demand companies' documents are read further.
3. **Pages are read locally** (PyMuPDF, RapidOCR for scans) and classified; only top pages per category are selected.
4. **A model extracts** KPIs, guidance and red flags against a JSON schema, each with page, quote and confidence.
5. **V10 compares** with XBRL: XBRL wins, the AI value is flagged.
6. **KPIs and chunks** (with embeddings) are stored for search and Q&A.
7. **The analyst sets up a report** on the Reports screen (built): company, report (quarterly update, initiating coverage or IPO coverage), basis and quarter, in the URL; input readiness shown (filed results, comps, the linked model and its rating; transcripts, presentations, MD&A and house template marked as being built).
8. **A report or question** runs a tool loop over facts, KPIs, prices, comps, filings and the model, with `calc` for arithmetic.
9. **Two checks** before anything is shown: grounding (every number from a tool or `calc`) and style (no em-dashes or stock phrases).
10. **Drafts:** a Word note and a dense IB-style PowerPoint, with citations; the recommendation and target price come from the analyst's model or are left blank (section 23).

### 6.9 Events, results calendar and alerts (feeds and calendar built; red flags and alerts planned, Phase 5)

*Figure 10. Events from NSE's published feeds: results calendar, red flags and alerts (sections 9.2, 26.2).*

1. **The feed watcher polls** Board Meetings, insider trading, related-party, encumbrance and announcements feeds every 5 to 30 minutes and keeps every item.
2. **Items are linked to companies** by name, symbol or ISIN; unmatched items wait for review.
3. **Board meeting intimations** (at least two working days ahead, SEBI LODR 29) build the results calendar (`GET /calendar`): purpose and meeting date read from each item; results meetings told apart; a past day shows who actually filed. Shown as a day strip, week or month on the desk and watchlist. A read over the feed items; nothing else stored. Earnings calls have no source yet (rule 1).
4. **Red flags** (pledges, insider trades, related-party deals, auditor changes) picked out.
5. **Watchlist companies** get alerts by email or Telegram when they file or a red flag appears.

### 6.10 Exceptions

| **Situation** | **Handling** |
|---|---|
| Filing not listed by NSE | IR-page fallback or import folder. |
| Restated or refiled period | Both kept; the most recently filed is in use; the quarter tagged Restated or Revised with what changed. |
| File missing its main contexts | Rejected and noted, never half-stored. |
| Broken XBRL file | Fetched once more, then skipped and noted. |
| Amounts in the wrong unit | V11: corrected by the exact power of ten when both signals agree; one signal: suspect, blocked, out of growth figures until the PDF is checked. |
| NSE stops answering | The run stops; the watchdog resumes 10 minutes later. |
| Year-ago quarter never filed on its own | YoY shown as a dash with the reason. |
| No bhavcopy for the day; company missing from it; no share count | Nothing stored, retried hourly; no price shown; market cap blank with a note. |
| Validation failure | Filing flagged; automatic changes blocked; the rule explained. |
| Low-confidence AI value | Flagged in the change set with the source page beside it. |
| Model edited outside the system | Fingerprint mismatch; structure and dependencies rescanned before planning. |
| Template row the company lacks; item the template lacks | Left blank and flagged; listed as unmapped for the analyst. |
| Model or template contains macros | Kept, never executed. |
| Model held by a colleague | Start refused (423); read-only view naming the holder; told when it frees. |
| Recalculation service down, or a cell it cannot compute | Apply refused (503 or 422), nothing saved, lock released; the Excel bridge is the way round. |
| Offer-document figures that do not tie | Flagged, never stored clean (section 6.11). |
| Evidence contradicts an analyst's estimate (proposed) | Flagged to the analyst before drafting; the estimate is never changed (section 6.12). |

### 6.11 IPO coverage from offer documents (built; first real run pending)

*Figure 11. IPO coverage: SEBI's RHP and Prospectus lists to restated statements and per-section grounded drafts (sections 3.1, 17, 20).*

1. **Once a day** (beat `sebi_watch_cron`, 08:30 IST; `analekh ipo-watch`) the watcher reads the newest page of SEBI's RHP (smid 11) and Prospectus (smid 12) lists only. The DRHP list is never requested; the abridged prospectus is not used.
2. **For each new entry** it fetches the entry page once, takes the PDF from the embedded viewer (`?file=<attachdocs URL>`, checked against the host and path allow-list) and stores it once by hash.
3. **An IPO issue is its own record** (`ipo_issues` with documents, financials, chunks and drafts), not a row in `companies`. It gets an NSE symbol when the analyst enters it, or after listing when exactly one listed company has the same name stem (`ipo/symbols.py`).
4. **The reader** (`analekh ipo-read`) chunks the text for search and has the model read the restated statements (three years plus the stub period, both bases, Decimal, full rupees), the price band and the peers. Figures that disagree (a power of ten off; total income less expenses against PBT; PBT less tax against PAT) are flagged, never stored clean.
5. **The Prospectus supersedes the RHP** for display; changes between them show as restatements. Quarterly XBRL wins once the company files (V10; offer figures live in their own tables).
6. **Coverage drafts** run one grounded loop per section (MD&A, financial performance, sector, strengths and risks, valuation) against IPO-only tools; a section with an unmatched number comes back blocked with the numbers. Rating and rationale are marked blanks for the analyst; no target price anywhere.
7. **Shown** on the Reports screen's IPO coverage tab (`/ipo` routes). Not built: Word export of the draft, linking to the listed company after the daily prices, a golden case from a real RHP.

### 6.12 Agentic report flow (proposed, not built)

*Figure 12. Agentic RAG: context fetched ahead, "why" questions on every movement, conflict flags on the analyst's estimates, and learning from what the analyst accepts (sections 3.4, 17.3 to 17.6).*

1. **Context arrives ahead of time:** the context fetcher stores, reads and tags official and research documents as they publish (section 3.4).
2. **Results arrive** and the analyst approves the model changes (workflow 6.5).
3. **The agent explains the movement** in the approved numbers with standing "why" questions (macro, sector or company; one-off or structural; cost direction and timing; does management agree), each answer citing a retrieved document or saying the evidence is missing.
4. **The analyst tweaks next year's estimates;** the agent diffs the approved model versions line by line (growth rates, costs, margins, drivers).
5. **Each changed assumption is tested** against the evidence. Where the evidence points the other way, the conflict is flagged to the analyst before drafting; the analyst keeps the estimate, changes the model or adds a note. The agent never changes an estimate.
6. **The draft** explains the analyst's estimates and reasoning with cited evidence, section by section, in the analyst's voice (the firm's and analyst's adapters, section 17.4); grounding and style checks follow.
7. **The analyst reviews and accepts.** The accepted version, the edits and the conflict answers are indexed for retrieval at once and feed adapter training later.

Numbers are not the only evidence: every report weighs the numbers against macro, policy, sector and management evidence.

## 7. Inputs and outputs

#### 7.1 Inputs from the analyst

| **Input** | **How** | **Used for** |
|---|---|---|
| Sign-in | Email and password; first password by email | Every route |
| Company | Search (web app or Excel) | Everything |
| Watchlist | Web app | Deep coverage, alerts |
| Existing models | Watched folders or the open workbook; confirmed once | Quarterly updates |
| Templates by sector | Upload (admins) | Coverage Builder |
| Mapping confirmation | Once per template or model | Where each number goes |
| Own estimates and their changes | The model's estimate columns | Variance; suggestions; estimate diff and conflict flags (proposed) |
| Approvals; conflict answers | Accept, edit or skip per item; keep, change or note per flag | Every write; drafts |
| Accepted reports and edits | Final version of each report (proposed) | Retrieval and adapter training |
| Licensed research | Upload (for example Gartner) | Context retrieval |
| Peer lists, alerts, IPO symbol | Web app | Comps; notifications; linking an issue |

#### 7.2 Inputs collected automatically

| **Input** | **Source and method** | **Lands in** |
|---|---|---|
| Company universe | EQUITY_L.csv and SME list, weekly | companies |
| Sectors | NSE Indices lists; Stocks data type import | companies (sector, sector_source, sector_lseg) |
| Results numbers | Integrated-filing lookup per company and per watcher run; financial-results list for history | filings, facts |
| Presentations, annual reports, transcripts | Announcements RSS to PDF; IR pages | documents, chunks, kpis |
| Events | Board meeting, insider, related-party, encumbrance feeds | feed_items, alerts |
| Prices | Bhavcopy, once per trading day | prices (latest day only) |
| Offer documents | SEBI RHP and Prospectus lists, daily | ipo_* tables |
| Context documents (proposed) | Publishers in section 3.4 | context documents and chunks |

#### 7.3 Outputs

| **Output** | **Format** | **Delivered to** | **Produced by** |
|---|---|---|---|
| Change set; updated model version | Review screen; .xlsx | Web app or Excel; analyst's folder | Model Sync |
| New model; proposed assumptions | .xlsx with Sources and Checks; review list | Analyst's folder; web app | Coverage Builder, GenAI |
| Results flash, variance bridge, call digest, red flags | Page, table, text | Web app, alerts | GenAI, feeds |
| Quarterly update | .docx: results and concall highlights, risks and guidance, investment rationale | Reports | GenAI |
| Initiating coverage note | .docx: investment summary, MD&A and business, financial and sector performance, outlook, strengths and risks, rationale | Reports | GenAI |
| IPO coverage draft | Sections (MD&A, financials, sector, strengths and risks, valuation); Word export planned | Reports, IPO tab | GenAI |
| IB-style slides | Dense .pptx | Reports | GenAI |
| Conflict flags (proposed) | List of estimates the evidence contradicts, with sources | Web app, before drafting | GenAI |
| Results history | .xlsx, up to 12 quarters | Company page | Results views |
| Q&A answers | Text with citations | Web app | GenAI |
| Comps table; profile slide; pitch pages | .xlsx; .pptx; .pptx and change log | Download | IB Output |
| Alerts | Email or Telegram | Inbox or phone | Feed watcher |
| Validation and template test reports | Pass or fail per rule | Web app | Validation; onboarding |

## 8. Data model (PostgreSQL)

PostgreSQL with pgvector is the single source of truth. Raw files live in MinIO; Redis (Valkey in production) holds the job queue only. Money is NUMERIC, never float, except at the Excel boundary. Schema: Appendix A.

#### 8.1 Why PostgreSQL

Relational integrity across companies, filings, facts, templates, models and change sets; exact NUMERIC arithmetic and DATE periods; JSONB for irregular payloads (XBRL dimensions, AI output, structure maps); pgvector for search and Q&A without a separate vector database; a full audit trail; standard tooling (SQLAlchemy, Alembic, one container).

#### 8.2 Tables

| **Table** | **Purpose and key columns** |
|---|---|
| companies | Whole NSE universe: nse_symbol, isin, name, series, listing_date, face_value, sector, industry, sector_source, sector_lseg, results_taxonomy, is_sme, is_active, source, refreshed_at. |
| watchlist | user_id, company_id, added_at, settings (alerts, auto-analyse). |
| feed_items | Every RSS item: feed, item_key, title, link, description, pub_date, company_id, processed_at, fetch attempts. |
| filings | company_id, kind, period_start, period_end, period_type, consolidated, audited, source_url, file_sha256, storage_key, filed_at, status, meta (validation report, links, revision flag, V11 scale). |
| facts | Normalised XBRL facts: element, period, instant flag, consolidated, value NUMERIC, unit, context, dimensions, is_latest. |
| kpis | AI or table-extracted metrics with page, quote, confidence, method, verified. |
| documents, chunks | PDF metadata; text chunks with embeddings and full-text search. |
| prices | The latest trading day only: OHLC, previous close, volume, market cap. |
| templates, template_tests | Templates (owner, sectors, version, storage_key, structure, mapping, driver and check cells, status) and their test builds. |
| models, model_builds, model_versions | Linked or built models (doc_tag, file_path, fingerprint, structure, mapping, origin), build history, every saved version with parent, author and time. |
| model_locks | One holder per model while an update, build or report runs (migration 0012). |
| assumptions | model_id, driver, proposed_value, rationale, citations, decision, final_value. |
| change_sets, change_items | Proposed changes per sync, decision per item. |
| reports | Generated outputs with citations and prompt hash. |
| ipo_issues, ipo_documents, ipo_financials, ipo_chunks, ipo_drafts | Offer-document coverage: issue (symbol, company once listed), each RHP or Prospectus, restated figures per version with flags, text chunks, per-section drafts (migration 0014). |
| users, auth_sessions, api_tokens, password_resets | Accounts and roles, sessions, hashed bridge tokens, hashed reset codes with failure counts (migrations 0009 to 0013). |
| app_settings, audit_log | Admin settings (upload limit); every admin and lock action. |
| llm_calls, alerts, peer_lists, job_status | Token use per call; sent notifications; saved peer lists; when each scheduled job last ran and last worked. |
| Proposed | Context documents and chunks (source, published date, tags); report drafts and accepted versions with edits; adapters per firm and analyst (sections 17.3, 17.4). |

#### 8.3 Indexes and constraints

- companies: unique nse_symbol and isin; checks on results_taxonomy and sector_source; trigram index on name (search fallback).
- facts: (company_id, element, period_end) partial index where is_latest.
- filings: (company_id, period_end DESC); unique file_sha256; read indexes for the desk (migration 0007).
- feed_items: unique (feed, item_key); index on pub_date. models: unique doc_tag. chunks: HNSW on embedding; GIN on full text.
- A refiled period inserts its facts and is_latest is re-decided for the company: per line (element, dates, basis, dimensions) the value from the most recently filed filing wins; a filing without a date counts as oldest. Nothing is deleted.

## 9. Ingestion layer

#### 9.1 Universe loader

- Downloads EQUITY_L.csv and the SME list weekly; upserts by ISIN; marks missing companies inactive. Dates as DD-Mon-YYYY (main board) or DD-Mon-YY (SME).
- Sector by the precedence in section 4.2; results_taxonomy guessed from strong signals, decided by the filings.

#### 9.2 Feed polling

- Feeds: Financial_Results, Online_announcements, Board_Meetings, Insider_Trading, Related_Party_Trans, Sast_ReasonForEncumbrance. Corporate_action is not polled (its items link an NSE web page, which rule 1 does not allow, and nothing read them; 22 October 2026). Financial_Results has carried nothing since 24 August 2026.
- Celery beat task poll_feed: every 5 minutes (published TTL) for results and announcements, 30 minutes for event feeds (FEED_POLL_SECONDS, EVENT_FEED_POLL_SECONDS). Board_Meetings descriptions hold the purpose, then `|Meeting Date: DD-Mon-YYYY`.
- Conditional requests where supported, honest User-Agent, timeouts, exponential backoff. Item key = SHA-256 of link plus pubDate; upsert on (feed, item_key). pubDate parsed as DD-Mon-YYYY HH:MM:SS IST.
- Company linking by normalised name, then symbol or ISIN; unmatched items queued for review. Announcement PDFs fetched for every company, read only for watchlist or on-demand companies.

#### 9.3 Fetching and storage

- **Results:** the integrated-filing lookup (type "Integrated Filing- Financials", equity or sme, pages of 50) per company; each new XBRL downloaded oldest first, original before revision. Null, undefined or none links are no links; a listed file answering 404 or 410 is skipped and noted.
- **History:** the financial-results list, one request per company; only rows from March 2023 with a real XBRL link.
- **Watcher** (watch_results): ONE request without a ticker (page of 500), then each new XBRL; a page of all-new rows logs a warning rather than asking again. `analekh/seasons.py` decides each run; `analekh results-watch --force` asks regardless.
- **Guard:** missing main contexts raise IncompleteXbrl before storage; broken XML is retried once, then skipped.
- **Storage:** each file once; SHA-256; kind/yyyy/mm/sha256.ext; XBRL gzipped (about 12 times smaller; reads return the original bytes, so key and hash match); PDFs and workbooks as they are. Same hash: skip. Same period, new hash: a revision.
- **Client:** `PoliteClient` identifies as Analekh (User-Agent "Analekh/0.1", contact in From, Accept, Referer); allows only listed hosts and, where set, listed paths; checks every redirect hop and every embedded URL against the allow-list. 1 request a second by default, one every 2 s in bulk. A 401, 403, 429, timeout or stall stops a run instead of retrying into a block.

#### 9.4 Backfill

- `analekh results-backfill`: integrated filings of every company with a sector (newest eight quarter ends, both bases), one company per transaction; `--history` reads the list (quarters from March 2023), optionally `--sector`. `--start-at` resumes (the stopped company is fetched again in full); companies in out/bulk/no-filings.csv are skipped unless `--recheck-no-filings`; `--symbols`, `--limit`, `--quarters`, `--one-basis`, `--interval` narrow it.
- A local watchdog restarts 10 minutes after each NSE stop and backs off 1, 2, then 3 hours if NSE stalls quickly several times in a row.
- Older periods on demand from IR sites or the import folder, through the same parser and validation; AI extraction for backfills uses the Batch API.
- After element tables or rules change: `analekh revalidate` (re-reads stored files) and `analekh recompute-latest`; neither downloads.
- No nightly backfill (removed 21 October 2026; the task stays for when new Nifty 500 constituents need history).

#### 9.5 Daily prices

- `analekh prices` (task fetch_prices; PRICES_CRON=0 19-23 * * 1-5) loads the latest trading day; `--date` loads a given day.
- A stored or older day is skipped without a request; 404 means retry next hour.
- Rows parsed, matched by ISIN, given a market cap, upserted; every older day deleted in the same transaction.

#### 9.6 When each job runs

*Figure 13. The year's results seasons and each job's schedule, with the hours companies file.*

Every job runs from Celery beat in Docker on the VM. Times IST.

| **Job** | **Now** | **Planned** |
|---|---|---|
| Results watcher | Hourly 09:00 to 23:00 in the four results seasons; 21:00 daily otherwise | Narrow to announced board-meeting days (workflow 6.9) |
| Daily prices | Weekdays, hourly 19:00 to 23:00 until stored | Unchanged |
| Universe refresh | Monday 06:00 | Unchanged |
| Feed watcher | Every 5 or 30 minutes; pending items every 2 minutes; documents every 10 | Unchanged |
| SEBI offer documents | Daily 08:30 (`sebi_watch_cron`) | Unchanged |
| Session purge | Daily 03:30 | Unchanged |
| Context fetcher | Not built | Calendar days more often; daily or weekly polls (section 3.4) |
| Local-model jobs, adapter training | Not built | Overnight on the `local_llm` queue; training nightly on the GPU (AI.md) |
| Backfills | By hand, with the watchdog | New listings through the watcher |

**Results seasons.** SEBI requires quarterly results within 45 days and the year's within 60 (LODR 33). Windows run from day 5 to two days past each deadline, so last-day filers' XBRL (up to 24 hours after the board meeting) is caught:

| **Season** | **Quarter ends** | **Deadline** | **Window** |
|---|---|---|---|
| Q1 | 30 June | 14 August | 5 July to 16 August |
| Q2 (SME first half) | 30 September | 14 November | 5 October to 16 November |
| Q3 | 31 December | 14 February | 5 January to 16 February |
| Q4 and the year (SME second half) | 31 March | 30 May | 5 April to 1 June |

NSE shows a filing about a second after it is filed, so any delay is the watcher's interval; every sampled first filing since 2023 fell inside these windows. About 3,000 requests a year. Late filers and revisions are caught by the daily off-season run.

## 10. XBRL parsing and validation

#### 10.1 Parsing

- lxml for plain instance files (Arelle available for full taxonomy work).
- Contexts resolved from actual dates (duration for quarter and year to date; instant for the balance sheet), never from context names (rule 5).
- Values in full INR (V11 corrections recorded on the filing); display transforms live in mappings. Consolidated and standalone stored separately; dimensions in JSONB and in the uniqueness key; typed dimensions read from their child element.
- Element names are a fixed vocabulary per format, so mapping is configuration, not AI.
- **Results format from the line items:** RevenueFromOperations means Ind-AS (NBFCs included, though they also tag InterestEarned); InterestEarned and InterestExpended without it, a bank; GrossPremiumIncome, NetPremiumIncome or persistency, a life insurer; PremiumEarned or premiums written, a general insurer. Each format has its own element table.
- Two contexts with the same dates and different values (OneD and FourD, seen once): the first is kept; how to flag it is open (section 28).
- Files whose main contexts are undefined raise IncompleteXbrl before storage.

#### 10.2 Validation rules

| **ID** | **Rule** | **On failure** |
|---|---|---|
| V1 | Revenue from operations + other income = total income (insurers add investment income; life insurers the transfer from the shareholders' account). | Flag; block auto-apply |
| V2 | PBT = total income - total expenses + exceptional items as tagged (either Ind-AS name; a charge is negative) + extraordinary items for Ind-AS filers only. Banks deduct provisions; general insurers go through the shareholders' account and deduct any transfer to reserves; life insurers: shareholders' account income less its expenses. | Flag; block auto-apply |
| V3 | PAT = PBT - tax. | Flag |
| V4 | Total assets = equity + liabilities at each instant (insurers skipped: balance sheet not mapped). | Flag; block auto-apply |
| V5 | Quarter = year to date - prior year to date where both exist. | Flag |
| V6 | Context dates agree with the declared period. | Use declared; warn |
| V7 | Quarter-on-quarter change above 50% in revenue or profit. | Highlight |
| V8 | Filed after SEBI's deadline (LODR 33(3)): 45 days after a quarter or SME half-year, 60 when closing the year, plus one day's grace; date in IST. | Label late |
| V9 | Same period refiled with different values. | Keep both; most recently filed in use; tag and show changes |
| V10 | AI value conflicts with XBRL. | XBRL wins; AI value flagged |
| V11 | Rupee amounts in the wrong unit (100 to 1 crore times off; Metro Brands' September 2025 consolidated revenue Rs 6.51 crore for Rs 651.14 crore, with V1 to V3 passing). Signals: the other basis, and the median of at least three neighbouring quarters. | Both agree on one power of ten: amounts corrected by it, per-share values and ratios as filed, factor recorded. One signal: suspect, blocked, out of growth, Movers and comps until checked. In line with its own quarters: pass |

A filing whose identity elements are not tagged records the rule as skipped.

#### 10.3 Margins and ratios by company type

The desk's Margin column and the company page follow the company type (owner, 26 October 2026):

| **Type** | **Shown** | **How** |
|---|---|---|
| Companies outside finance | EBITDA margin | EBITDA derived from the filed lines (with exceptional items) / revenue |
| Banks and NBFCs (LSEG Banking Services, the bank format, named primary dealers and finance companies) | NIM; on the company page yield, cost of borrowing and spread ("Interest ratios") | NIM = (interest earned - interest expense) x 4 / average interest-earning assets (advances or loans, investments, bank and call balances); yield = interest earned x 4 / the same; cost = interest expense x 4 / average deposits, borrowings, debt securities and subordinated liabilities; spread = yield - cost. Interest expense is InterestExpended (banks) or FinanceCosts (NBFCs). Averages of opening and closing balances; balance sheets come in March and September, so June and December are interpolated by days, and those quarters show a dash until the next half-year is filed. Consolidated when it allows, else standalone. A dash when interest is under 40% of revenue or balance sheets are missing |
| Brokers, wealth and asset managers (`interest.FEE_FINANCE`, by symbol) | Core pre-provision profit margin; operating leverage on the company page | (revenue from operations - operating expenses) / revenue; operating expenses = total expenses - finance costs - impairment on financial instruments; leverage = revenue growth - opex growth, year on year, in points |
| Exchanges | EBITDA margin | |
| Holding and investment companies | Operating income (rupees) on the company page; no desk margin | |

EBITDA is hidden for every financial sector. A ratio above 100% is dropped as a tagging problem. Computed figures, not the lender's reported NIM (which uses daily averages).

## 11. Document pipeline

XBRL covers statutory statements but not sector KPIs or commentary. Those come from presentations, annual reports and transcripts, for watchlist or on-demand companies, and from offer documents for recent listings. The user never selects pages.

#### 11.1 Read and select

- **Local read** of every page with PyMuPDF; RapidOCR (bundled ONNX models, no system binary; settings in `analekh/docs/rapidocr.yaml`) for scanned pages.
- **Page classification** by keyword patterns, table density and position; ambiguous pages may go to a small model as text.
- **Selection** of the top pages per category (typically 10 to 25 of a 300-page annual report; the restated statements, price band and peers of an offer document).

#### 11.2 Extract and store

- **Extraction** against a JSON schema; each value with page, quote and confidence.
- **Chunking and embedding** (local embedder by default) for search and Q&A; **validation** of units, periods and conflicts with XBRL.

```
{"company": "MUTHOOTFIN", "period_end": "2026-06-30",
 "kpis": [{"name": "gold_loan_aum", "value": 0, "unit": "INR crore", "page": 7, "quote": "...", "confidence": 0.0}],
 "guidance": [{"topic": "...", "statement": "...", "page": 0}],
 "red_flags": [{"type": "...", "detail": "...", "page": 0}]}
```

Zeros are placeholders. KPI lists are per sector (banks, NBFCs, consumer, industrials, IT services). Transcripts get speaker-aware parsing for guidance changes, analyst concerns and deflected topics, with pages.

#### 11.3 Call recordings

Audio is posted within 24 hours, the transcript within five working days. `analekh transcribe-audio` turns recordings in the import folder into timestamped text locally (Whisper large-v3 through faster-whisper, GPU when present; optional group `audio`). Notes come from this text first and are regenerated from the official transcript once filed. Future scope: a live listener (section 26.3).

## 12. Workbook understanding engine

One engine reads any workbook; discovery, onboarding, the Coverage Builder and quarterly updates depend on it. It also finds the drivers whose changes the agentic flow explains (section 6.12).

| **Capability** | **Method** |
|---|---|
| Period axis | Header rows with period patterns (Q2FY27, 2QFY27, Sep-26, FY27E, dates); an A/E row; the last actual column. |
| Inputs versus formulas | Cell types from the file; colour convention (blue inputs, black formulas, green links) as a secondary signal. |
| Row labels to standard fields | Synonyms first, then fuzzy matching, then a small model; confidence per row. |
| Drivers | Input cells on assumption sheets referenced by forecast formulas. |
| Checks | Cells comparing totals or labelled checks. |
| Dependencies | Formula graph across sheets (formulas or pycel); dependents of every input; INDIRECT and OFFSET reported as unknown impact. |
| Hygiene | External links, macros, hardcodes in formula areas, inconsistent formulas across a row. |
| Fingerprint | Hash of structure and values to detect edits made outside the system. |

Output: a structure map (JSONB) stored with the template or model, plus a suggested mapping the user confirms.

## 13. Model discovery and recognition

#### 13.1 Finding models

- The Excel bridge watches folders the user chooses and indexes .xlsx and .xlsm files. A file open in Excel is read from a copy of the saved file; anything unreadable is listed with its reason, never skipped silently.
- Later: OneDrive or SharePoint through Microsoft Graph.

#### 13.2 Identifying the company

- **Hidden tag:** after the first link, the symbol and a model ID go into the workbook's custom document properties, written by patching only `docProps/custom.xml`, `[Content_Types].xml` and `_rels/.rels` inside the zip; every other part is copied byte for byte and the swap is atomic. For an open workbook the tag goes in through Excel and the analyst saves.
- **File name** matched against the universe; **contents** (name, ISIN or symbol on a cover sheet).

New files get a suggested match that the user confirms once (rule 2).

#### 13.3 Staying in step

- Before planning a change set, the fingerprint and modified time are compared; any difference triggers a rescan.
- Save options: new versioned copy (default) or in place with backup. With Office.js the pane reads the open workbook's tag directly.

## 14. Template onboarding

#### 14.1 Upload

Admins upload a blank template or another company's model, with sectors, name and version. For a model, historical hardcoded inputs are cleared while formulas are kept; uncertain cells are shown, not deleted.

#### 14.2 Structure and mapping

The workbook engine reads periods, inputs, labels, drivers and checks; a suggested mapping with confidence per row is confirmed once per template and reused for every company.

#### 14.3 Test build

The template is filled with one real company's history and recalculated. The report lists checks passing or failing, rows the company does not report, items with no row, and broken formulas. Only after acceptance is the template active. Admins only.

#### 14.4 Requirements for uploaded templates

Historical periods across columns with labels in one column; forecast formulas reference the input area; no external links (flagged); macros kept, never executed; INDIRECT and OFFSET flagged.

#### 14.5 Versioning and sharing

A default template per sector, per-company overrides; editing creates a new version and models keep theirs; personal or team templates; built-ins as fallback.

## 15. Coverage Builder

#### 15.1 Flow

- Pick a company and Start coverage; the sector's default template is preselected.
- Gather 8 to 12 quarters and 3 to 5 years, backfilling what is missing; KPIs, segments, shareholding and description from presentations and annual reports (or the offer document for a recent listing).
- Generate the workbook: inputs filled, formulas untouched, each input commented with its source.
- Propose first-pass assumptions per driver from history (three-year averages and trends) and guidance, each with rationale and citation; the analyst accepts or edits.
- Recalculate and require the Checks sheet to pass; write the hidden tag and mapping; save; draft the initiation pack.

#### 15.2 Built-in template structure

| **Sheet** | **Contents** |
|---|---|
| Cover / Index | Company, date, sheet map, hidden tag |
| Data | Historical actuals in blue with source comments |
| Drivers | Growth, margins, yields, costs, capex, working capital, payout |
| Model | Linked P&L, balance sheet and cash flow; balance via cash or debt |
| Sector KPIs | Template-specific metrics |
| Valuation | DCF and relative; for banks and NBFCs, P/B versus ROE and residual income |
| Sensitivities | Cost of capital, terminal growth, key drivers |
| Checks | Balance sheet balances, cash flow ties, no stray hardcodes |
| Sources | Every input traced to document and page |

#### 15.3 Initiation pack

Draft initiation (Word): investment summary, business and segments, industry backdrop, management and governance, financial analysis, forecasts, valuation, risks; charts, comps and profile slide. Every number from the database or model with citations; industry context from public sources cited and marked for verification until the context sources of section 3.4 exist. Valuation computed; rating and target price read from the analyst's model or left for the analyst (SEBI Research Analyst rules apply to publication).

#### 15.4 Hand-off

The built model carries its tag and mapping, so the next results flow into the quarterly update with no setup.

## 16. Model Sync Engine

#### 16.1 Write plan

Writes only into input cells mapped to facts or KPIs; formula cells change only through explicit roll-forward items; dependents of every written cell listed.

#### 16.2 Roll-forward

A new period column marked E with formulas: actuals proposed into input rows and the flag switched to A; the forecast horizon extended by copying the last forecast column; hardcoded estimates and labels needing a shift listed.

#### 16.3 Assumption suggestions

For each driver, actual versus estimate is compared and a revision suggested with a grounded one-line rationale, as a change item like any other.

#### 16.4 Change set and apply

- Items by kind (actual_write, roll_forward, assumption_suggestion, label_shift), each with cell, old and new value or formula, rationale and source; reviewed in the web app or Excel pane, bulk accept per kind.
- Drafting, deciding and applying hold the model's lock (one holder; others get 423 and a read-only view naming the holder; a decision on an item no longer pending gets 409).
- Apply writes in one pass, recalculates, saves a new model_version; the original is never overwritten. A set whose base is no longer the latest version is refused (409 `change_set_stale`, never rebased); the analyst drafts a new one.

#### 16.5 Excel integration options

| **Option** | **How** | **Trade-offs** |
|---|---|---|
| xlwings (v1) | Local bridge drives desktop Excel. | Native recalc; needs Excel; runs outside Docker. |
| openpyxl + recalc service | Headless edits; LibreOffice in its own `recalc` container. | No Excel; formatting edge cases; cells LibreOffice cannot compute are refused. |
| Office.js add-in (later) | Task pane in Excel. | Best experience; more front-end work. |

**Recalc service.** `recalc_file(bytes) -> bytes` is the one entry point. With RECALC_URL set it POSTs the workbook to the `recalc` container (a small HTTP server, non-root, read-only root, all capabilities dropped, on an internal network with no internet, database or object storage, and no published port; token in the `X-Recalc-Token` header only). It retries once on a refused or reset connection, read timeout or busy 503, then falls back to a local LibreOffice (RECALC_FALLBACK=local, dev and CI) or raises: Apply answers 503 `recalc_unavailable`, saves nothing, releases the lock and keeps the change set approved. A 200 that is not an xlsx counts as unavailable. Cells LibreOffice cannot compute (a VBA function, an add-in) give 422 `recalc_cannot_compute` naming the cells. `.xlsm` keeps its VBA project; macros never run. The service's limits come from its own environment (RECALC_TIMEOUT_SECONDS, RECALC_CONCURRENCY, RECALC_MAX_BYTES). Saving without recalculating was rejected: stale cached values would feed Checks and the report tools.

## 17. Analysis and GenAI Engine

| **Output** | **Content** |
|---|---|
| Results flash | Actuals versus last quarter, last year and estimates; KPIs; three to five bullets. |
| Variance bridge | Price, volume, mix and cost effects where data allows. |
| Call digest | Guidance changes, analyst concerns, deflected topics, tone shift, with pages. |
| Red flags | Auditor qualifications, pledges, related-party deals, insider sales, late filings, restatements. |
| Quarterly update | Word: results highlights, concall highlights, risks and guidance, investment rationale. |
| Initiating coverage note | Word: investment summary, MD&A and business, financial and sector performance, outlook, strengths and risks, rationale. |
| IPO coverage | Per-section drafts from the RHP or Prospectus (section 6.11). |
| IB-style slides | Dense PowerPoint for either report. |
| Q&A | Answers over filings with citations. |

**What feeds a report,** best first: filed numbers (on the chosen basis), comps, the analyst's model (estimates, recommendation, target price), then MD&A, transcripts and presentations; proposed, the context documents (section 3.4) and the firm's and analyst's accepted reports (section 17.4). Later: house templates for Word and PowerPoint.

**How it must read.** Professional, the analyst's own work: no em-dashes, stock phrases or signatures. A style check after the grounding check blocks a failing draft the same way. Recommendation and target price copied from the analyst's model or left as a marked blank (section 23).

**How reports run.** Today the flash, note and initiation run one open tool loop (all tools, up to 20 turns); IPO coverage runs one grounded loop per section, each grounded separately. Proposed for every report: a fixed outline, core data fetched by code, a short loop and a grounding check per section, so one section can be redone; the open loop stays for Q&A.

#### 17.1 Tools exposed to the model

| **Tool** | **Returns** |
|---|---|
| get_facts(company, elements, periods) | Fact values with source references. |
| get_kpis(company, names, periods) | KPI values with pages and confidence. |
| get_model_values(model_id, ranges) | Values and estimates from the model (`ModelReader`). |
| search_filings(company, query, k) | Chunks with document and page. |
| get_prices(company) | The latest close and market cap. |
| calc(expression, inputs) | Deterministic arithmetic in Python. |
| IPO tools | An issue's restated figures, terms, peers and text chunks (`ipo/tools.py`). |
| Proposed | search_context(sector, topic, since); get_estimate_changes(model_id, from, to); get_analyst_notes(company). |

#### 17.2 Grounding rules

- Only numbers returned by tools or computed by `calc` may appear; a post-check matches every number and blocks on any unmatched one (`genai/grounding.py`; never weakened to make output pass).
- Each claim carries a citation; long system prompts cached; tokens logged in llm_calls. All calls go through `genai/client.py` (refusal fallbacks on; structured output with closed JSON schemas).
- A style check follows: em-dashes and stock phrases block like an unmatched number.
- No recommendation or target price generated; one appears only when read from the analyst's model.

#### 17.3 Agentic RAG (proposed)

The agent plans, retrieves and explains before it writes (workflow 6.12; AI.md sections 1 to 3):

- **Plan in code:** per report, a fixed set of sections, standing "why" questions per section, and sources per sector (a bank: RBI; an oil marketer: OPEC and fuel policy). The model reads and writes within the plan; no open-ended agent loops on small models.
- **Retrieve, never search the web:** context documents are fetched ahead (section 3.4) and retrieved by sector, topic and date.
- **Explain the analyst's estimates:** the approved model's versions are diffed; each changed growth rate, cost line, margin and driver is explained with evidence.
- **Flag conflicts before drafting:** where the evidence contradicts a changed estimate, the analyst is told first and decides; the agent never changes an estimate (rules 2 and 8).
- **Cite every context claim;** say "no evidence" rather than reason from memory. Numbers are not the only evidence.

#### 17.4 Learning from the analyst (proposed, after the MVP)

- **Training material:** accepted reports, the draft-to-final edits, answers to conflict flags and the analyst's notes. Indexed for retrieval at once; used for training later.
- **Method:** LoRA adapters trained 4-bit (QLoRA) on a local base model: a firm layer (house style and frameworks) and an analyst layer (voice), a few MB each, swapped per request. A new analyst uses the firm layer until enough accepted reports exist.
- **Weights learn how to write; retrieval holds what is true.** Facts are never trained in; ratings, target prices and numbers are masked out of training data.
- **Training runs in the background** (nightly or every N accepted reports). An **automatic check** compares a new adapter with the current one on a fixed set of the firm's past reports (grounding rejections, broken structured output, banned phrasing, missing sections); worse means not swapped in. The last few adapters are kept for rollback. The golden-set test comes after the MVP.
- **Guardrails are code** in front of every model; no training run can remove them.

#### 17.5 Local models (proposed)

Aim: no API cost (owner, 27 October 2026). A local provider (Ollama) beside Claude in `genai/client.py`, chosen per job: Qwen2.5 7B on the VM's CPU for overnight extraction, labels and tagging; the laptop's GPU (RTX 4060, 8 GB) for Whisper, drafts, Q&A and training, over a private tunnel. Same token logging and the same grounding check for every provider. Each job moves only after it passes the golden set. Per-job placement, setup and deployment steps: AI.md.

#### 17.6 Order

Retrieval and the agent first (they remove the pasted-context step), then local models job by job, then the learning loop once the MVP's features are done.

## 18. IB Output Engine

- **Comps:** saved peer lists (up to 30 companies) and suggested peers (same NSE sector and results format, closest in market cap, same LSEG group first); price, market cap, TTM revenue, revenue YoY, EBITDA and net margins, P/E, P/B, median and mean; Excel export. TTM = last four quarters back to back on one basis (consolidated when four exist, else standalone; the row says which). EBITDA derived as on the company page, left out for lenders and insurers. Book value = latest equity attributable to owners (capital plus reserves for banks; not yet for insurers). EV = market cap + debt - cash, shown only once debt and cash are sourced; until then EV multiples are blank, never market cap passed off as EV. A symbol that left the universe is reported, not fatal.
- **Company profile slide:** business summary, shareholding, key financials, valuation, recent events; no price chart (only the latest close is kept).
- **Pitch page refresh:** placeholders such as {{MUTHOOTFIN.pat_q}} replaced with current values plus a change log.
- **Precedents (later):** curated deal announcements with AI extraction flagged for review.

## 19. User interfaces

#### 19.1 Web app

| **Screen** | **Contents and actions** |
|---|---|
| Welcome and sign-in | Signed out, Analekh opens on the welcome screen: the mark, greeting, tagline and live counts on frosted cards over drifting light; a scroll or swipe up (with resistance, springing back if let go early), click, tap, drag or Enter hands off to sign-in. Sign-in by email and password; the first sign-in only allows choosing a new password; a reset sends a 6-digit code. After sign-in the desk's data loads, then a short unlock plays. Sign out returns to the welcome page once the server confirms. |
| Home: Results desk | The quarter's reporters, newest filing or largest market cap first, ten per page, with market cap: revenue (interest earned or premium for lenders and insurers), net profit and Margin (section 10.3) with the change on a year ago. Filters for quarter, sector, filing date and watchlist on one row, in the URL. Movers (at least Rs 50 crore of quarterly revenue; profit growth needs a year-ago profit of at least 2% of revenue; turned profitable or loss-making listed apart) and progress by sector with median growth, each scrolling inside a fixed height. The results calendar (day strip, week or month; a past day shows who filed). Rows become cards on phones. |
| Search | Type-ahead over every NSE company: exact ticker or ISIN, ticker prefix, name prefix, words starting words in the name, then substrings. The universe (about 80 KB compressed) loads once and is searched in the browser. One company search per screen at most: hidden where a screen has its own picker (Reports, Comps, "/" focuses it) or is not about one company. |
| Watchlist | The desk's columns for followed companies (price and change, market cap, latest quarter, YoY, basis, Blocked or "N to review"), with their coming results and those not yet announced. |
| Company page | Header with sector, results format and coverage level; Analyse (disabled with the reason when the job queue is down) and Start coverage. Basis switch in the URL. Figure tiles and a chart of the top line, net profit or a margin, with values on the bars; for lenders NIM and an Interest ratios view (cost of borrowing with the spread stacked to the yield); for brokers and asset managers operating leverage; amounts in lakhs under Rs 10 crore of revenue. A Latest quarter column (full height on wide screens) with QoQ and YoY, derived lines, notes behind an information icon, dashes with reasons and Restated or Revised tags. Share price and market cap tiles. A results history table (up to 12 quarters, the company's own lines, one unit, Excel export; keyboard scrolling): each heading links the filing in use on NSE (iXBRL), opens its details and shows one status mark; filings without a column fold out below. Call highlights card (empty until notes exist). |
| Change-set review | Grouped items with cell, old and new, source, rationale, dependent counts; accept, edit, skip, apply. Read-only, naming the holder, when a colleague holds the model. |
| Assumption review | Proposed drivers with rationale and citations; accept or edit. |
| Conflict review (proposed) | Before drafting: each changed estimate the evidence contradicts, with sources; keep, change in the model, or add a note. |
| Templates | Upload, sectors, mapping confirmation, test report, versions (admins). |
| Models | Discovered and built models, link status, versions, lock holder. |
| Reports | Set-up: company, report (Quarterly update, Initiating coverage, IPO coverage), basis (Standalone default; Consolidated or Both when filed), quarter, in the URL. Input readiness (filed results, comps, the model and its rating; transcripts, presentations, MD&A, house template marked "Being built"). What each output will contain. The IPO coverage tab lists issues, their documents, restated figures with flags, and per-section drafts (blocked sections show their numbers). Generate stays off, with the reason, until drafting is built; recent reports below. Soft pulsing placeholders for work in progress (stopped under reduced motion). |
| Q&A | Chat over a company's filings with page links. |
| Comps | Saved peer lists (beside the table from 1,500 px, buttons above it otherwise), companies by search or suggested peers, basis switch, median and mean, Excel export; the set in the URL; cards on phones. |
| Settings | Data status (watcher season, last and next ask, a warning when a scheduled start left no record; latest close and coverage; counts and database size; whether a model key is set, never the key). Alerts (channels, a test per channel, recent alerts; errors summarised, never echoed). Bridge tokens (made, shown once, revoked). Sign out everywhere. Display preferences in the browser (theme, amounts, basis, desk order, lock chime). NSE schedules are not editable. |
| Admin | Users (add with email, name and role; send first password; pause, unblock), Templates, Settings (upload limit 1 to 100 MB, default 25), Model locks (see and release any, audited). |

Stack: React and TypeScript (Vite), TanStack Query, AG Grid Community, ECharts, PDF.js, Inter bundled. Collapsible left sidebar; light, dark and system themes. Width up to 1,400 px, 1,840 from a 1,500 px window (company page from 1,280). Motion only on what is clicked (owner, 17 October 2026): sidebar highlight, sliding switch thumbs, pressed tabs, a faint light following the pointer; data and screens appear at once and stay fresh five minutes; all motion stops under reduced motion. Every screen works at phone width without sideways scrolling (checked at 390, 1,366 and 2,000 px); notes open on hover, tap or focus. The front end stays light: a new library has to earn its weight.

#### 19.2 Excel

- Phase 2: xlwings bridge (`analekh-bridge`: scan, link, watch, apply) on the analyst's machine, authenticated with a bridge token. Link and scan tested on a real model (Lemon Tree, 24 October 2026); `apply` on a real model still to test.
- Later: Office.js task pane beside the model; clicking an item highlights its cell.

#### 19.3 Developer and operator interfaces

- CLI (`analekh --help`): universe load and sectors, search, watch, refresh, backfill, results-backfill, results-watch, prices, revalidate, recompute-latest, transcribe-audio, ipo-watch, ipo-read, template add, test and activate, build, sync, golden-sheet, golden-import, golden-test, create-admin.
- Swagger at /docs. Streamlit admin dashboard: feed health, failed jobs, validation failures, token spend.

## 20. API design

Every route needs a signed-in user except `/auth/login`, the reset flow and `/public/*` (rule 9). Changes carry the `X-Analekh-CSRF` header. The authoritative list is the OpenAPI schema at /docs (and `web/src/api/schema.d.ts`).

| **Endpoint** | **Purpose** |
|---|---|
| POST /auth/login, /auth/logout, /auth/logout-everywhere; GET /auth/me, /auth/password-rules | Sign-in and sessions; the password rules shown live in the web app. |
| POST /auth/first-password; POST /auth/reset/request, /auth/reset/confirm | First password change; reset by emailed code. |
| GET, POST /auth/tokens; DELETE /auth/tokens/{id} | Bridge tokens (shown once, stored hashed). |
| GET, POST /users; PATCH /users/{id}; POST /users/{id}/send-first-password, /unblock | User management (admins). |
| GET, PUT /settings/upload-limit | Upload limit (admins set it); also carries the lock poll and idle-reminder timings. |
| GET /models/{id}/lock; POST /models/{id}/lock/release; GET /me/locks; GET /admin/locks; POST /admin/locks/{id}/release | Model locks. |
| GET /public/auth-status, /public/welcome | Signed-out welcome data. |
| GET /companies/search?q=; GET /companies/index | Ranked type-ahead; the whole universe for the browser (ETag, gzip). |
| GET /companies/{symbol} | Company and coverage level. |
| GET, POST /watchlist; DELETE /watchlist/{symbol} | Watchlist. |
| POST /companies/{symbol}/analyse, /refresh | Deep coverage on demand; find, fetch and validate the newest filing. |
| GET /companies/{symbol}/filings, /facts, /kpis | Filings (slim metadata unless full=true; revision status and changes), facts (logical names, consolidated by default when filed), KPIs. |
| GET /companies/{symbol}/glance, /history, /history.xlsx, /price | Latest quarter; up to 12 (at most 28) quarters on one basis; the latest close. |
| GET /desk; GET /calendar | Results desk in one request; results and board meetings by day. |
| GET /system/jobs; GET /status | Whether the job queue answers; data status for Settings (never contacts NSE). |
| GET /jobs/{id} | Job status. |
| POST /templates; POST /templates/{id}/mapping, /test, /activate; GET /templates | Template onboarding (admins). |
| POST /coverage; GET /models/{id}/assumptions; POST decisions; POST /models/{id}/finalize | Start coverage and assumptions. |
| POST /models/discover, /models/link, /models/{id}/link; GET /models, /models/{id}/builds, /models/{id}/versions/{v} | Discovery, linking, versions. |
| POST /models/{id}/sync; GET /change-sets/{id}; POST decisions, apply | Change sets (lock held; 409 when stale; 503 or 422 from recalc). |
| POST /reports; GET /reports/{id} | Reports (inline today; to become jobs); planned: GET /reports and downloads. |
| GET /ipo/issues, /ipo/issues/{id}; POST, GET /ipo/issues/{id}/coverage; POST /ipo/issues/{id}/symbol | IPO issues, coverage drafts, the analyst's NSE symbol. |
| POST /qa | Question over filings with citations. |
| GET, POST /peer-lists; PUT, DELETE /peer-lists/{id}; GET /companies/{symbol}/peers; POST /comps/table, /comps | Peer lists, suggested peers, comps as JSON or Excel. |
| GET /alerts/channels, /alerts; POST /alerts/test | Alerts. |
| Proposed | Context documents (list, upload), conflict flags and answers, accepted report versions. |

## 21. Technology stack

| **Layer** | **Choice** | **Reason** |
|---|---|---|
| Language | Python 3.12, uv | Finance, PDF and XBRL libraries; lockfile |
| API | FastAPI (uvicorn) | Typed, async, OpenAPI |
| Jobs | Celery + Redis (Valkey in production); beat | Retries, rate limits, schedules |
| Database | PostgreSQL 16 + pgvector + pg_trgm; SQLAlchemy; Alembic | Section 8 |
| Object storage | MinIO (built from source) | Immutable raw files and outputs |
| XBRL | lxml (Arelle available) | Fast parsing |
| PDF | PyMuPDF, pdfplumber, Camelot; RapidOCR (ONNX) | Local text, tables, OCR without a system binary |
| Language models | Claude API today (tool use, structured output, Batch, caching, refusal fallbacks); local models through Ollama proposed (Qwen2.5 7B and 14B) | Grounded writing; no API cost as the aim |
| Fine-tuning (proposed) | LoRA / QLoRA adapters on the local base model | Firm and analyst style |
| Embeddings | Local sentence-transformers model (default) | Search, Q&A, context retrieval |
| Speech | faster-whisper (large-v3) | Call recordings |
| Excel | xlwings; openpyxl; formulas or pycel; LibreOffice in the `recalc` container | Live writes, structure, dependencies, headless recalc |
| Documents | python-docx, python-pptx, XlsxWriter | Notes, slides, workbooks |
| Auth | argon2id passwords; HttpOnly SameSite=Strict cookies; CSRF header | Rule 9 |
| Market and sector data | Bhavcopy (latest day); NSE Indices CSVs; Excel Stocks data type | Free; no scraping |
| Front end | React (Vite), TypeScript; pnpm workspace; Node 24 | Dense review screens |
| Quality | pytest, ruff, mypy, pre-commit | Tests, lint, types |
| Source control and CI | GitLab Free (primary), self-hosted runners; GitHub mirror; OSV-Scanner | Free tier, no compute minutes |
| Deployment | Docker Compose; Caddy for HTTPS | One command |

## 22. Packaging, deployment and setup

#### 22.1 Services

| **Service** | **Role** |
|---|---|
| api | FastAPI application |
| worker | Celery workers: fetch, parse, extract, build, sync, report |
| beat | Scheduler (section 9.6) |
| migrate | Runs `alembic upgrade head` before the API starts (production) |
| postgres | PostgreSQL 16 with pgvector |
| redis / valkey | Queue broker (Valkey in production) |
| minio | Raw files and outputs |
| recalc | Headless LibreOffice on an internal network, no published port (section 16.5) |
| web | React build served by nginx (body cap; passes the client address on) |
| caddy | HTTPS and the only published ports (80, 443), production |
| excel-bridge (host) | On the analyst's machine; watches folders; drives Excel |

Development runs the same stack in Docker Desktop (`docker-compose.yml`), with the API and web app started by hand; containers reach each other by service name, and `.env` on the host uses 127.0.0.1. Production: `deploy/compose.production.yml` (section 22.7).

#### 22.2 Requirements

- Docker with 8 GB RAM (4 vCPU, 20 GB disk to start). Python 3.12 and uv; Node 24 and pnpm for the front ends.
- Microsoft Excel desktop for the xlwings route; Microsoft 365 (Excel for the web is enough) for the Stocks data type import.
- A model key while Claude is used; for local models, Ollama and (for drafting at speed and for training) a GPU with about 8 GB (AI.md).
- An Indian network or VM for NSE access. Optional: SMTP (needed for first passwords and resets) or a Telegram bot.
- Libraries and system packages: Appendix G.

#### 22.3 Environment variables

The source of truth is `.env.example` (development), `deploy/production.env.example` (production, written on the server by `deploy/make-production-env.sh`, secrets prompted, never in git) and `analekh/config.py` (every setting, its default and its bounds; limits and timings come from settings, never literals). Groups:

| **Group** | **Variables** |
|---|---|
| Stores | DATABASE_URL, REDIS_URL, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET |
| Models | ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_SMALL_MODEL, EMBEDDINGS_PROVIDER (proposed: provider, Ollama hosts, model and adapter tags) |
| Sources and schedules | USER_AGENT, CONTACT_EMAIL (sent in From), FEED_POLL_SECONDS, EVENT_FEED_POLL_SECONDS, UNIVERSE_REFRESH_CRON, RESULTS_WATCH_CRON, PRICES_CRON, SEBI_WATCH_CRON, SESSION_PURGE_CRON, DOWNLOAD_RATE_PER_SECOND, BACKFILL_PRIORITY, IMPORT_DIR |
| Sign-in and limits | ENV, CORS_ORIGINS, AUTH_ENABLED (dev only), session, pause, reset and lock timings (for example RESET_MAX_FAILURES, RESET_LOCKOUT_HOURS, IDLE_REMINDER_MINUTES, LOCK_POLL_SECONDS), MAX_UPLOAD_CEILING_BYTES |
| Mail and alerts | SMTP_URL, SMTP_FROM, ALERT_EMAIL_TO, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID |
| Recalc | RECALC_URL, RECALC_TOKEN, RECALC_FALLBACK |
| Excel bridge (host) | ANALEKH_API, ANALEKH_TOKEN, WATCH_FOLDERS, SAVE_MODE |

#### 22.4 Setup

- Clone the repository from GitLab; copy `.env.example` to `.env` and fill it in.
- `docker compose up -d`; run migrations (`alembic upgrade head`).
- Front ends: `pnpm install`, then `pnpm dev` (proxies /api to port 8000).
- Create the first admin: `analekh create-admin EMAIL "Name" [--adopt-local]`.
- Load the universe (`analekh universe load`) and sectors (`analekh universe sectors [--stocks-file]`); feeds start on the next beat tick.
- Upload sector templates or use the built-ins.
- On the analyst's machine: `uv sync`, make a bridge token in Settings, start the bridge with watched folders.
- Search a company: Start coverage, or link an existing model and sync.

#### 22.5 Source control, CI/CD and mirroring

GitLab (Free) is the single source of truth; GitHub is a read-only public mirror fed only by the pipeline.

| **Area** | **Configuration** |
|---|---|
| Branching | Protected main; feature branches merged into main (squash), or direct commits while there is one developer. |
| Pipeline | Stages lint, test, build, scan, deploy-staging, dast, release, mirror (Appendix F). Python jobs on uv's image (Python 3.12, Debian 13), `.venv` cached on `uv.lock`, two retries. |
| Quality gates | ruff, ruff format, mypy, pytest with coverage, `alembic check`; web lint, tests and build; golden-set accuracy on schedule and on demand. |
| Security scanning | GitLab SAST, secret detection, container scanning (app and recalc images); OSV-Scanner on `uv.lock` and `pnpm-lock.yaml`. DAST and security policies need Ultimate and a staging URL; not in effect. |
| Runners | Both on the Oracle VM: a shell runner (`india`) builds the Arm64 images and deploys; a Docker runner takes untagged jobs (images kept, `if-not-present`). Shared runners off; no compute minutes. |
| Registry and environments | Images in the GitLab registry by commit and tag. Production deploys manually from main or a tag (`deploy_production`, which runs `down` first when the live network subnet differs from the compose file); staging when STAGING_URL is set. |
| Secrets | Protected, masked CI variables per environment (mirror token, SSH key, runtime keys). |
| Mirror | After a green pipeline on main and on tags: fast-forward push only, no force, token scoped to one repository, resource group against concurrent pushes; skipped without the token. |
| Commits | Signed by the owner with an SSH key; the assistant prepares changes and messages but never commits. |
| GitHub settings | Public; points contributors to GitLab; Actions, Issues, Wiki, Projects off; ruleset blocks force pushes and deletion. |

#### 22.6 Distribution

Public GitHub mirror with sample models on public companies, a demo video and the diagrams. No raw exchange files, user models, keys or downloaded filings committed; secret detection and pre-commit hooks enforce it.

#### 22.7 Hosting

*Figure 14. Where Analekh runs: the Oracle Cloud VM in Mumbai, the laptop's GPU over a private tunnel (planned), and the analyst's machine.*

- **Since 26 October 2026:** one Arm64 VM on Oracle Cloud's free tier, Mumbai (4 OCPU, 24 GB, Ubuntu 24.04 LTS, reserved address). NSE's lookup, feeds and bhavcopy answered from it before anything moved; the www.nseindia.com home page does not, and the app never requests it. The production stack (section 22.1) deploys from GitLab; only 80 and 443 are published; HTTPS on an sslip.io name until a domain. Data moved by pg_dump and a MinIO copy (59,366 files), never downloaded again. Nightly pg_dump, 7 days kept.
- **Needs met:** an Indian region, HTTPS and sign-in. Data about 5.4 GB on 21 October 2026, growing about 0.5 GB a results season.
- **Left:** backups off the box with one test restore; SSH limited to the owner's address; a domain with Cloudflare in front; failed-sign-in counts shared across API processes (in Redis).
- **GPU work:** the VM has no GPU. Speech, larger local models and adapter training run on the owner's laptop (RTX 4060) when it is on, over a private tunnel; the VM's CPU is the fallback for small batch jobs (AI.md).
- **Tried first:** Azure for Students (verification failed); AWS and Google need a card with short credits; Oracle's second sign-up succeeded.

#### 22.8 Self-hosted per firm (proposed)

The end goal is Analekh as a platform each firm hosts itself (owner, 29 October 2026):

- Each instance holds its own documents, edits, accepted reports and adapters; its data trains only its own model; nothing flows back to Analekh or between firms.
- Analekh ships the software and the base model; no client data, no knowledge packs. Each instance fetches its own sources and can add its own, with its own approval.
- A firm needs a GPU machine to train (about 8 GB for a 7B adapter); without one it drafts slowly on CPU and does not train.
- Training, the automatic check and rollback run inside the instance without Analekh.
- More features come later as add-ons or sister products (roadmap section 8).

## 23. Security, compliance and data rights

- **Exchange and regulator data:** only the sources and paths in section 3.2's access rule (CLAUDE.md rule 1), at their stated intervals; no redistribution of raw data; written confirmation or a licence before public or commercial release. If NSE refuses the honest User-Agent, the owner decides. Proposed context sources (section 3.4) need each host approved and its terms read.
- **Third-party data:** LSEG groups from the Stocks data type stay in the local database, never in git; Microsoft's terms to check before release. Licensed research (Gartner) enters only by analyst upload.
- **Research regulation:** publishing recommendations in India generally needs SEBI Research Analyst registration (NISM Series XV alone is not). Analekh never generates a rating or target price; a report carries the one in the analyst's own model or a marked blank (owner's amendment, 21 October 2026); the publisher carries the registration duty. No model is trained to produce one.
- **Sign-in (rule 9):** every route needs a signed-in user except `/auth/login`, the reset flow and `/public/*`. Passwords argon2id, 15 to 30 characters with 8 letters, a number, a special, upper and lower case, no spaces. Credentials, tokens and codes travel only in POST bodies, the session cookie or the Authorization header, never in a URL or log. Session cookie HttpOnly, SameSite=Strict, Secure outside dev, plus a CSRF header on changes; sessions end after 9 hours idle or 24 in all. Wrong password, unknown email, paused and blocked accounts get the same reply. Three failures pause an account 15 minutes, five block it until a reset; failures also counted per client address (behind Caddy and nginx, the address is trusted only from the web container's fixed address on a fixed network). First passwords are generated (20 characters, 24 hours, emailed); reset codes are 6 digits, hashed, 2 minutes, single use, 5 tries, one mail per 2 minutes, and 20 wrong codes stop new codes for 24 hours. Any password change revokes bridge tokens. "Sign out everywhere" ends every session.
- **Authorisation:** admin and analyst roles; only admins manage users, templates and the upload limit; every route checks the objects it touches; admin and lock actions written to `audit_log`.
- **Inputs and outbound requests:** every input bounded at the boundary (one upload limit; bodies over the ceiling refused as they arrive, at nginx and in the API); parameterised queries only; no eval, shell strings or unsafe deserialisation; outbound requests only through `PoliteClient`, with redirect hops and embedded URLs checked against the allow-list; mail over STARTTLS with certificate checks.
- **User files:** models and templates stay on the user's machine or private storage; macros never executed; workbooks recalculated only in the isolated `recalc` container.
- **Secrets:** environment variables only; never logged or echoed in errors.
- **AI data handling:** with Claude, only public filings, public context documents and the user's own workbook labels are sent. With local models (proposed) nothing leaves the instance; each firm's training data stays in its instance.
- **Audits:** security audits run when the owner decides (rule 10); the audit of 29 October 2026 (commit e0a260b, two runs) found 7 issues, all fixed; three unconfirmed leads remain open (reset attempt counter race, unbounded discovery hints, runner settings). Accepted findings are recorded in `deviations.md`. All new code is written as if the audit were coming (rule 11).
- **Supply chain:** SAST, secret detection, container and dependency scanning; images take Debian security updates and carry no setuid programs; pnpm blocks install scripts unless allowed; the mirror token is scoped to one repository and rotated every 90 days.

## 24. Testing and quality

| **Test** | **Approach and target** |
|---|---|
| Golden set | 20 filings across every results format with hand-checked values: `analekh golden-sheet` (XBRL from storage plus a worksheet), the owner marks it against the PDFs, `golden-import` writes the manifest, `golden-test` runs it through the element tables. Real filings live in `tests/fixtures/golden/` (gitignored). |
| Results views | A revision downloaded before its original is still in use; history headings link the newest filing; every filing appears once; no overflow at 390, 1,366 and 2,000 px. |
| Unit check | V11 fixtures: corrected only when both signals agree; one signal gives a suspect; real jumps pass; never applied twice. |
| Margins | NIM, yield, cost and spread on fixtures, interpolated quarters, the 40% interest rule, fee-finance companies. |
| Sign-in and locks | Uniform replies, pause and block, reset lockout, CSRF, token revocation, lock contention (423), stale decisions and sets (409), admin release. |
| Recalc | Service unavailable, non-xlsx replies, uncomputable cells (422), VBA kept. |
| IPO | Watcher (lists 11 and 12 only, allow-list on the embedded PDF), reader flags, versions and restatements, per-section grounding, API. |
| Test database | Tests use `analekh_test` (live tables, no data), never the working database; about 50 s instead of 6 minutes. |
| XBRL parsing; KPI extraction | 100% exact on mapped elements; 95% KPI precision with correct pages. |
| Workbook understanding; templates; builder; sync | 20 real models with hand-labelled structure (90% mapping accuracy); built-in templates pass on five companies per sector; built models balance with full Sources; fixture workbooks with expected change sets. |
| Grounding | Every number in generated text matches a tool result. |
| Local models and adapters (proposed) | The golden-set gate per job; the automatic check before an adapter goes live (section 17.4). |
| Universe, feeds, search, prices | Recorded feed samples; listing and delisting diffs; browser ranking matches the server (22 of 22); bhavcopy parsing, market cap, day replacement. |
| CI | Every push and merge request: ruff, mypy, pytest, `alembic check`, web lint, tests and build, scanners and the dependency audit; golden-set accuracy on schedule. |

## 25. Cost model

| **Item** | **Estimate** |
|---|---|
| Universe and facts | No AI cost; about 5.4 GB (facts 97% of the database); about 0.5 GB a results season. |
| Prices | One public file a day; about 0.4 MB stored. |
| Hosting, CI | Oracle free tier; GitLab Free on self-hosted runners: no cost. |
| Document extraction | 5 to 25 selected pages per document, watchlist or on demand. |
| Label mapping | AI only for ambiguous labels, once per template or model. |
| Reports, initiations, IPO coverage | Per company per quarter or per issue; cached system prompts. |
| Local models (proposed) | No API cost; electricity and the laptop's or firm's GPU. |
| Backfill | Batch API at a lower price, if ever needed. |

Check current Claude API pricing before budgeting; real cost per company is measured from llm_calls.

## 26. Build plan

| **Phase** | **Scope** | **Exit criteria** |
|---|---|---|
| 0. Spike | Universe; two feeds; XBRL for 10 tickers including a bank and an NBFC. | Data path proven; taxonomy differences documented; golden set passing |
| 1. Data layer | Loader, watcher, fetcher, parser, validation, schema, watchlist, backfill, search, sign-in. | Every NSE filer's results in the database |
| 2. Builder and sync | Workbook engine, onboarding, Coverage Builder (NBFC and consumer templates), Model Sync, review screens, xlwings bridge. | Start coverage then quarterly update end to end |
| 3. Document AI | Page classifier, KPI extraction for three sectors, transcript digest, embeddings, offer documents; context fetcher (proposed). | KPI precision target met |
| 4. GenAI outputs | Flash, bridge, red flags, update and slides, initiation, IPO coverage, Q&A, grounding; agentic RAG and conflict flags (proposed). | Grounded outputs on 10 companies |
| 5. Discovery, IB, polish | Model discovery, comps, profile slide, pitch refresh, alerts, Office.js, demo; learning loop (proposed, after the MVP). | Demo-ready repository |

Versions follow the phases: v0.0.x during Phase 0, v0.1.x once Phase 0 is complete, v0.2.x after Phase 1, and so on; v1.0.0-pre-release is the first release for proper testing. This document and the code are at v0.0.6.

#### 26.1 Status on 29 October 2026

| **Phase** | **Where it stands** | **What stops it finishing** |
|---|---|---|
| 0. Spike | 54,350 filings from 2,756 companies parsed and validated (10.1 million values); element tables for every format tie out; V11 corrected 28 filings. | The golden set hand-check and `golden-test`; the 44 V11 suspects against their PDFs; flagging same-date contexts. |
| 1. Data layer | Universe (3,186), sectors, search, watchlist, both lookups, history from March 2023, V1 to V11, revisions, prices, scheduler and feeds, desk, calendar, company pages, margins by type, comps, settings, sign-in, roles, first password by email, model locks; hosted on the Oracle Mumbai VM with nightly backups; security audit fixes in. | The 290 companies with nothing on NSE; 169 without a sector and the LSEG-to-NSE mapping; the Ind-AS profit tag (ProfitLossForThePeriod, about 2,400 filings). |
| 2. Builder and sync | Every engine has a working core; recalc in its own container; the bridge links and scans a real workbook. | Real templates and models; `apply` on a real model; balance sheet and cash flow history; debt and cash for EV. |
| 3. Document AI | Pipeline built; RapidOCR; recordings transcribed locally; local embeddings; offer documents read (synthetic tests; layout confirmed live). | A local model passing the golden set (AI.md); V10 wired; KPI golden set; a presentation and transcript source; the first real RHP run; the context fetcher. |
| 4. GenAI outputs | Tools, calc, grounding, report loop; Reports set-up; IPO per-section drafts. | Word and PowerPoint writers; the style check; rating read from the model; reports as jobs; the agentic flow and conflict screen. |
| 5. Discovery, IB, polish | Comps, profile slide, alerts, add-in cores. | EV multiples; branded templates; domain; the learning loop after the MVP. |

#### 26.2 What to build next

Order of work (with new ideas in `docs/roadmap.md`):

- **Phase 0 exit (v0.1.0):** golden set and `golden-test`; the 44 V11 suspects.
- **Hosting hardening:** backups off the box with a test restore, SSH limited, domain and Cloudflare, shared sign-in counts.
- **Local AI stack:** Ollama on the VM and laptop, the provider switch, the `local_llm` queue, the golden-set gate (AI.md phases A to E).
- **Context sources:** host and terms approvals, then the fetcher for RBI, Government of India, OPEC and World Bank first (section 3.4).
- **Report drafting with the agentic flow:** writers for Word and PowerPoint, style check, rating from the model, estimate diff and conflict flags, reports as jobs; call highlights.
- **IPO coverage finish:** a real RHP run and hand-check, Word export, linking on listing.
- **Balance sheet and cash flow** from half-year and year-end filings; V4 for Ind-AS.
- **Q&A screen;** peer view, red flags and alerts; sector editing.
- **Learning loop** once the MVP's features are done.

Decisions waiting on the owner: the Ind-AS profit tag; the LSEG-to-NSE mapping; bank presentation; hosts and paths for each context source; NSE's announcements list (presentations, transcripts, call links); debt-segment results; the 250 BSE-only filers; the domain and the logo.

#### 26.3 Future scope (after v1)

- **Live and intraday prices** through a paid market-data API, in place of the bhavcopy.
- **NSE's finer classification** (industry, basic industry) through a licensed feed; NSE publishes only the 22 sectors openly (owner, 18 October 2026).
- **Live earnings-call listener** (owner, 20 October 2026): an agent joins the call, registers with the analyst's own details (never a made-up identity, never past a captcha), records the stream with ffmpeg, and local Whisper transcribes 5 to 10 s pieces about 10 s behind the speaker. Call highlights show it marked live and unverified, with quotes under the grounding check; the filed recording replaces it. Fixed scripts for common webcast hosts; phone-only calls need a paid telephony service. Transcripts stay in the firm's database. Needs a call source (rule 1) and an always-on machine. First step: replay a recording as if live.
- **Proposed, not decided** (roadmap): debt-segment results; KPIs and peers from "Basis for Offer Price"; a lock-in calendar; the analyst's approved script voiced over slides by local text-to-speech, with consent and labelling. Each new host or path needs the owner's approval.

## 27. Risks and mitigations

| **Risk** | **Mitigation** |
|---|---|
| NSE changes feeds or objects to polling | Polite polling; source adapters; IR fallback; confirmation or licence before release. The results feed already stopped once; the lookup replaced it with approval. |
| NSE refuses the honest User-Agent | Runs stop at the first refusal; the owner decides; never disguised. |
| NSE's request limit | Runs resume after a 10-minute pause; the watcher needs one request; longer back-off on repeated quick stalls. |
| Revised filings change shown numbers | Most recently filed value used; superseded values kept; quarters tagged with what changed. |
| XBRL varies by sector | Format from line items; element tables per format; golden set per format. |
| Context or period errors | V5, V6, V8; declared period wins. |
| AI extraction errors | Pages and quotes on every value; XBRL wins; approval before writes; offer-document figures that do not tie are flagged. |
| Templates and models vary | Shared engine; confidence scores; confirm once; test builds; built-ins. |
| Wrong model linked | Hidden tag after confirmation; confirmation for every new link. |
| Sector gaps | Two sources with precedence; user override; SME companies remain the gap. |
| Excel dependency | Headless recalc container; Office.js later. |
| Recalc cannot compute a workbook | Refused with the cells named; the Excel bridge applies it. |
| Geo-restriction; hosts stop answering | Mumbai VM; retry later with single requests; import folder. |
| Bhavcopy late or changed | Hourly retries; parsing by column name; core numbers need no prices. |
| Regulatory exposure | No generated rating or target; one only from the analyst; publisher carries the duty. |
| Account takeover, data exposure | Sign-in on every route, uniform replies, lockouts, CSRF, scoped tokens, audit log, audits when the owner decides. |
| Local model quality | Golden-set gate per job; Claude as fallback; grounding never weakened. |
| A training run makes drafts worse | Automatic check before swap; previous adapters kept for rollback. |
| Context sources change terms or layout | Per-source adapters; terms read before fetching; a refused source is dropped, never worked around. |
| Training leaks one firm's style or data to another | Each firm self-hosts; training data and adapters never leave the instance. |
| Scope creep | Phase gates; each phase ends with a working demo; extras as add-ons later. |
| Mirror diverges or leaks | Fast-forward only from the mirror job after a green pipeline; secret detection before anything leaves GitLab. |

## 28. Open questions

- How stable element tags are across the full universe (the golden set will show).
- Investor presentations, transcripts and call links through NSE's announcements list (one request a day)? Needs approval under rule 1.
- The 290 companies with nothing on NSE (about 250 BSE-only): manual import or a note?
- Exact hosts and paths for each context source (section 3.4), their terms, and which ministries count for each sector.
- How the accepted version of a report comes back: an upload of the final Word file, or edits in the web app.
- A starter adapter trained only on public material, or each firm from the base model? Minimum accepted reports before an analyst's own adapter?
- Can annual statements come cleanly from NSE's annual-report XBRL for backfill? Is there a public shareholding feed?
- The 25 undecided LSEG groups and the 169 companies without a sector; Microsoft's terms on stored Stocks data type fields.
- xlwings or Office.js first for the demo machine?
- Would NSE confirm in writing that polling its feeds for this tool is acceptable?
- How to flag XBRL contexts with the same dates but different values (OneD versus FourD)?
- Settled: element sets per regulator (0.0.3); prices from the bhavcopy (0.0.4); ratings only from the analyst, two report types, the watcher by season (0.0.5); hosting on Oracle Mumbai, SEBI offer documents, local embeddings, and per-section reports for IPO coverage (0.0.6).

## 29. Appendices

### Appendix A. Schema (PostgreSQL)

Source of truth: `analekh/db/models.py` (SQLAlchemy) and the Alembic migrations in `analekh/db/migrations/versions/` (0001 initial schema to 0014 IPO offers); CI runs `alembic check` so the two cannot drift. Extensions: `vector`, `pg_trgm`. Tables and indexes are summarised in sections 8.2 and 8.3.

| **Migration** | **Adds** |
|---|---|
| 0001 | Initial schema: companies, watchlist, feed_items, filings, facts, kpis, documents, chunks, prices, templates, models, versions, assumptions, change sets, reports, llm_calls, alerts, peer_lists |
| 0002 to 0005 | sector_source; life_insurance taxonomy; sector_lseg; previous close |
| 0006 to 0008 | job_status; filings read indexes; feed item fetch attempts |
| 0009 to 0011 | users, sessions, tokens, settings; first password and its mail status |
| 0012 | model_locks |
| 0013 | reset-code failure counter and lockout |
| 0014 | ipo_issues, ipo_documents, ipo_financials, ipo_chunks, ipo_drafts |

### Appendix B. Template mapping (example)

```
template: nbfc_quarterly
version: 3
sectors: [NBFC, Gold Finance]
basis: consolidated
period_axis:
  sheet: Data
  header_row_label: "Period"        # e.g. Q2FY27
  flag_row_label: "A/E"             # A = actual, E = estimate
units:
  default_transform: "div:10000000"  # INR to INR crore
rows:
  - {source: xbrl:RevenueFromOperations, sheet: Data, row_label: "Revenue from operations", confidence: 0.98}
  - {source: xbrl:FinanceCosts, sheet: Data, row_label: "Finance costs", confidence: 0.99}
  - {source: xbrl:ProfitLossForPeriod, sheet: Data, row_label: "PAT", confidence: 0.95}
  - {source: kpi:gold_loan_aum, sheet: Data, row_label: "Gold loan AUM", transform: none, confidence: 0.90}
drivers:
  - {name: loan_yield, actual_row_label: "Yield on loans", forecast_sheet: Drivers, forecast_row_label: "Yield assumption"}
checks:
  - {sheet: Checks, cell_label: "Balance sheet difference", expect: 0}
```

### Appendix C. Change set (example)

```
{"change_set_id": 42, "model": "MUTHOOTFIN nbfc_quarterly v3", "base_version": 7,
 "filing": "Q2FY27 consolidated results (XBRL)",
 "summary": {"writes": 18, "dependents_affected": 214, "roll_forwards": 3, "suggestions": 2, "warnings": 1},
 "items": [
  {"kind": "actual_write", "sheet": "Data", "cell": "M12", "old": "=L12*(1+Drivers!M5)", "new": "<actual value>",
   "source": "RevenueFromOperations, 2026-07-01 to 2026-09-30"},
  {"kind": "roll_forward", "sheet": "Data", "cell": "M3", "old": "E", "new": "A"},
  {"kind": "assumption_suggestion", "sheet": "Drivers", "cell": "N8", "old": "<current yield>",
   "new": "<suggested yield>", "rationale": "Actual yield came in below the estimate for the quarter"}]}
```

### Appendix D. Docker Compose

Source of truth: `docker-compose.yml` (development: postgres, redis, minio, recalc, api, worker, beat, web) and `deploy/compose.production.yml` (production: postgres, valkey, minio, web, caddy, recalc, migrate, api, worker, beat, on a fixed `10.89.0.0/24` network with the web container at `10.89.0.10`, plus an internal `recalc` network). MinIO is built from source (`deploy/minio`), the recalc service from `deploy/recalc`, HTTPS from `deploy/Caddyfile`. Only Caddy publishes ports (80, 443).

### Appendix E. Repository layout

```
analekh/
  api/              FastAPI app, routers (auth, users, tokens, locks, public, companies, models,
                    change_sets, templates, outputs, ipo, comps, settings, system), body limit
  auth/             passwords (argon2id), sign-in service, per-address limit, reset codes, bridge tokens
  jobs/             Celery app, beat schedule, tasks
  universe/         equity lists, sectors (precedence, Stocks import, index lists), search
  ingest/           feeds, integrated lookup and results list, PoliteClient and allow-list,
                    storage, pipeline, backfill, bhavcopy
  ipo/              SEBI watcher, reader, statements, terms, versions, symbols, coverage, tools
  xbrl/             parser, element tables per format
  validate/         rules V1 to V11
  docs/             PDF read and OCR, page classifier, extraction, chunking, embeddings, audio
  workbook/         periods, labels, reader, mapping, graph, hygiene, fingerprint, tags, recalc, checks
  templates/, templates_builtin/, builder/, modelsync/, excel_bridge/
  genai/            client, tools, calc, grounding, reports, Q&A, writers
  ib/, alerts/, admin/, db/ (models, migrations)
  cli.py, config.py, coverage.py, discovery.py, facts.py, golden.py, desk.py, glance.py,
  history.py, interest.py, restatements.py, prices.py, schedule.py, seasons.py
deploy/             production and staging compose, Caddyfile, minio, recalc, env scripts
docs/               design (this document, deviations, architecture.html), roadmap, pending items,
                    superpowers specs and plans, runbooks
scripts/            Phase 0 spike, Stocks helper, design_docx.py, diagram_panels.py, graphify_clean.py
web/, office-addin/ front ends (pnpm workspace)
tests/              unit, integration, golden set (gitignored), workbook fixtures
AI.md, CLAUDE.md, Commit-Info.md, README.md
docker-compose.yml, pyproject.toml, uv.lock, requirements*.txt, package.json, pnpm-*.yaml
.gitlab-ci.yml, .pre-commit-config.yaml, .env.example, .python-version, .node-version
```

### Appendix F. GitLab CI/CD pipeline

Source of truth: `.gitlab-ci.yml`. Stages: lint, test, build, scan, deploy-staging, dast, release, mirror. Jobs: `lint` (ruff, format, mypy), `unit_and_integration` (pytest with PostgreSQL, `alembic check`), `web` (pnpm lint, test, build), `dependency_audit` (OSV-Scanner, allowed to fail), `golden_set` (scheduled), `build_image` (Arm64 app, web, MinIO and recalc images on the `india` runner), SAST and secret detection templates, `container_scanning` and `container_scanning_recalc`, `deploy_staging` and `dast` (only with their URL variables), `deploy_production` (manual, from main or a tag), `mirror_to_github` (last stage, fast-forward only, skipped without the token). A `workflow:` block avoids duplicate branch and merge-request pipelines.

### Appendix G. Dependencies and requirements files

Source of truth: `pyproject.toml` (locked in `uv.lock`) and `package.json` files (locked in `pnpm-lock.yaml`). The requirements files are exported from the lock: `uv export --no-hashes --no-emit-project --frozen [--only-group bridge|optional|dev]`.

| **File** | **Installs** |
|---|---|
| requirements.txt | API, workers, scheduler (the application image) |
| requirements-bridge.txt | Excel bridge (xlwings, openpyxl, watchdog, httpx), kept small |
| requirements-optional.txt | Local embeddings (sentence-transformers) and the Streamlit dashboard |
| requirements-audio.txt | faster-whisper for call recordings (group `audio`) |
| requirements-dev.txt | pytest, respx, time-machine, ruff, mypy, pre-commit, stubs |
| web/package.json, office-addin/package.json | React app and Excel add-in (Office.js loads from Microsoft's CDN) |

Main Python groups: web API (FastAPI, uvicorn, pydantic), database (SQLAlchemy, Alembic, psycopg, pgvector), jobs (Celery with Redis), storage and HTTP (boto3, httpx, feedparser, tenacity), XBRL (lxml, Arelle), PDF and OCR (PyMuPDF, pdfplumber, Camelot, RapidOCR, onnxruntime), AI (anthropic), Excel and documents (openpyxl, formulas, XlsxWriter, python-docx, python-pptx, matplotlib), data (pandas, numpy, rapidfuzz), auth (argon2), CLI and logging (typer, structlog). Front end: React, TanStack Query, AG Grid Community, ECharts, PDF.js, zod, Inter; TypeScript held at 5.9 until openapi-typescript and typescript-eslint support newer versions.

#### G.7 PostgreSQL extensions

`vector` (pgvector, in the pgvector/pgvector:pg16 image) for embeddings; `pg_trgm` (contrib) for fuzzy name search.

#### G.8 System packages and services

Python 3.12, uv, Node 24 LTS (pinned in `.node-version`), pnpm (pinned in `package.json`), PostgreSQL 16 + pgvector, Redis 7 or Valkey, MinIO, LibreOffice (in the recalc image only), nginx, Caddy, Docker Engine and Compose, Microsoft Excel desktop (bridge; Microsoft 365 for the Stocks data type). Proposed: Ollama; an NVIDIA GPU driver where training runs.

#### G.9 Licence notes

Everything is free for an open-source public repository. Before a closed or commercial release:

| **Component** | **Licence and action** |
|---|---|
| PyMuPDF | AGPL-3.0 or a commercial licence from Artifex; or move text extraction to pypdfium2 with pdfplumber. |
| MinIO server | AGPL-3.0; hosted deployments can use a managed S3 service (boto3, configuration only). |
| Redis server | Licence changed from 7.4; Valkey (BSD) is the drop-in replacement, already used in production. |
| psycopg | LGPL-3.0; fine used unmodified as a library. |
| formulas | EUPL-1.1; review obligations before distributing a modified copy. |
| AG Grid | Community edition (MIT) only. |
| Local models (proposed) | Check each base model's licence (for example Qwen2.5's) before shipping it to firms. |
| Market data | NSE bhavcopy and NSE Indices terms before redistribution; Stocks data type fields for the account holder's own use; serving others needs a market data licence. |
| Context sources (proposed) | Each publisher's terms before fetching; no redistribution of their documents. |

### Appendix H. Glossary

| **Term** | **Meaning** |
|---|---|
| Universe | Every NSE-listed company, preloaded from the equity list. |
| Watchlist | Companies that get deep coverage, alerts and background work. |
| XBRL; taxonomy; context | Tagged financial statements; the dictionary of element names (in-capmkt with Ind-AS names for integrated filings); the period and dimensions a fact belongs to. |
| Integrated filing | SEBI's combined quarterly filing that replaced separate results filings. |
| Basis | Standalone or consolidated; both stored. |
| Revision, restatement | A quarter filed again on the same basis; restated means headline numbers changed; the most recently filed values are used. |
| Template; structure map; hidden tag | A sector model structure onboarded once; the engine's reading of a workbook; model ID and symbol in the workbook's custom properties. |
| Change set; roll-forward | Proposed model edits awaiting approval; turning an estimate period into an actual and extending the forecast. |
| Model lock | One holder per model while an update, build or report runs. |
| Comps | Comparable companies by trading multiples. |
| NIM; CPPPM | Net interest margin; core pre-provision profit margin (section 10.3). |
| RHP; Prospectus; DRHP | Red herring prospectus (before pricing); the final offer document; the draft (not used). |
| Agentic RAG | Retrieval-augmented generation where an agent, following a plan in code, decides what context to retrieve and which questions to answer before drafting. |
| Context source | An official or research publisher fetched ahead for agentic drafting (section 3.4). |
| Conflict flag | A changed analyst estimate that the retrieved evidence contradicts, shown before drafting. |
| Adapter (LoRA, QLoRA) | A small trained layer on top of a base model that carries a firm's or analyst's style. |
| Bhavcopy | NSE's daily end-of-day price file. |
| Sector source; Stocks data type | Where a sector came from (user, nse_indices, excel_stocks); Excel's linked record type with fields like Industry and Price. |
| LODR; TTL | SEBI's listing regulations; the refresh interval a feed publishes. |
| bps; lakh, crore | One hundredth of a percentage point; 1 lakh = 100,000, 1 crore = 10,000,000. |

## 30. Sources

- [NSE RSS feeds page](https://www.nseindia.com/static/rss-feed)
- [NSE Financial Results RSS feed](https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml)
- [NSE Online Announcements RSS feed](https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml)
- [List of NSE RSS feeds (Feedspot)](https://rss.feedspot.com/nseindia_rss_feeds/)
- [NSE equity list (EQUITY_L.csv)](https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv)
- [Sample results XBRL file (NSE archives)](https://archives.nseindia.com/corporate/xbrl/INDAS_121282_1717387_24082026053915.xml)
- [NSE integrated filings (financials)](https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials)
- [NSE Annual Report XBRL filings](https://www.nseindia.com/companies-listing/corporate-filings-annual-reports-xbrl)
- [NSE Terms of Use](https://www.nseindia.com/static/nse-terms-of-use)
- [NSE Indices (index constituent lists)](https://www.niftyindices.com)
- [SEBI public issues (offer documents)](https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=11)
- [SEBI LODR regulation 33 (financial results)](https://www.sebi.gov.in/legal/regulations/)
- [SEBI LODR call disclosures (TaxGuru)](https://taxguru.in/?p=1067323)
- [BSE Information Products Pricing Sheet](https://mock.bseindia.com/downloads1/Information_Products_Pricing_Sheet.pdf)
- [BSE Market Data Products](https://www.bseindia.com/market_data_products.html)
- [BSE List of Securities](https://www.bseindia.com/corporates/List_Scrips.html)
- [Zerodha Kite Connect pricing change (Marketcalls)](https://www.marketcalls.in/fintech/zerodha-makes-trading-api-free-for-personal-use-bundles-historical-data-with-connect-api.html)
- [NseIndiaApi, unofficial Python library](https://github.com/BennyThadikaran/NseIndiaApi)
- [Screener.in export help](https://support.screener.in/article/28-export-screen-results)
- [EODHD financial summary, BSE.NSE](https://eodhd.com/financial-summary/BSE.NSE)
- [Best Financial Data API for Indian Stocks 2026 (DalalAI)](https://dalalai.com/blog/best-financial-data-api-india)
- [Excel data types: Stocks and Geography (Microsoft Support)](https://support.microsoft.com/en-us/office/excel-data-types-stocks-and-geography-61a33056-9935-484f-8ac8-f1a89e210877)
- [Claude API PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- [OSV-Scanner](https://google.github.io/osv-scanner/)
- [GitLab features by tier](https://about.gitlab.com/pricing/feature-comparison/)
- [Ollama](https://ollama.com)
