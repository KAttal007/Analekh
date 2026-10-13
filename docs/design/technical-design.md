**Analekh**

*The analyst's record, kept for you.*

Technical Design Document

| **Field** | **Detail** |
|---|---|
| Author | Kaushal Attal |
| Version | 0.0.2 (design, updated during the build) |
| Date | 14 October 2026 |
| Supersedes | Version 0.0.1 (12 October 2026) |
| Status | Phase 0 spike run (13 October 2026); Phase 1 in progress |

**Purpose of this document.** It records every design decision for Analekh: what the system does, the data it depends on and the rules around that data, the architecture, the workflows, the database schema, each engine's internals, the interfaces and API, packaging and deployment, testing, costs, risks and the build plan. It is written for the engineer building the system and for anyone reviewing the design.

### What changed in 0.0.2

| **Change** | **Summary** |
|---|---|
| Prices | Kite Connect is removed (paid). The price source is undecided: an analyst's workbook can show a current price through Excel's Stocks data type, and NSE's daily bhavcopy can feed closing prices later. Analekh uses one static reference price at a time, never live quotes (section 3.3). |
| Sector classification | Three sources in a fixed order of precedence: the user's override, then sectors from Excel's Stocks data type (LSEG industry group, via Microsoft 365), then NSE Indices' published constituent lists (niftyindices.com, limited to /IndexConstituent/). companies.sector_source records which one set each sector (sections 4.2, 9.1). |
| Company search | Tiered type-ahead ranking. The web app downloads the whole universe once and searches it in the browser; trigram similarity is only a fallback for typos (sections 8.3, 19.1, 20). |
| Source control and CI/CD | GitLab Free instead of Ultimate. OSV-Scanner replaces GitLab's dependency scanning; DAST and security policies wait for a plan that includes them. Commits go straight to main while there is one developer (section 22.5, Appendix F). |
| Front-end tooling | pnpm workspace for the web app and the add-in instead of npm; Node 24 pinned; Inter font bundled; light and dark themes (sections 19.1, 21, Appendix G). |
| Schema and API | companies.sector_source, a peer_lists table, and endpoints for the company index and the model and template screens (sections 8, 20, Appendix A). |
| Phase 0 findings | Spike results recorded: Ind-AS element names confirmed, the feed's date format, duplicate contexts, NSE hosts that stop answering (sections 3.1, 10.1, 26, 28). |
| Versioning | Versions follow the build phases: v0.0.x while Phase 0 is under way, v0.1.x once Phase 0 is complete, v0.2.x once Phase 1 is complete, and so on (the middle number counts completed phases; the last counts revisions within a phase). The first release for proper testing is v1.0.0-pre-release. The earlier drafts 1.0, 1.0.1 and 1.0.2 are renumbered 0.0.0, 0.0.1 and 0.0.2. |

### What changed in 0.0.1

| **Change** | **Summary** |
|---|---|
| Name | The project is renamed from Ticker-to-Report to Analekh, with the tagline "The analyst's record, kept for you." The Python package, command-line tool, database and repository are renamed to analekh. |
| Preloaded company universe | Every NSE-listed company is loaded from NSE's equity list and refreshed weekly. Entering a ticker is a lookup, not a registration. Results XBRL is parsed for every company that files. |
| Coverage levels | "Track" is replaced by an optional watchlist. Numbers are collected for all companies; AI extraction, model updates, reports and alerts run for the watchlist or on demand. |
| Model discovery and recognition | The Excel bridge finds models in watched folders or the open workbook and identifies the company by a hidden tag, the file name or the contents. Mapping is suggested automatically and confirmed once. |
| Workbook understanding engine | One shared engine reads any workbook's structure (periods, inputs, formulas, labels, drivers, checks). It serves discovery, template onboarding and quarterly updates. |
| Template onboarding | Users upload their preferred model templates by sector. The system reads the structure, the user confirms the mapping once per template, and a test build must pass before use. |
| Coverage Builder | New feature: when no model exists, build one from a sector template with sourced history and proposed assumptions, then draft an initiation pack. |
| Inputs and outputs, interfaces | New sections listing every input and output and every user-facing screen. |
| Source control and CI/CD | GitLab (Ultimate) is the primary home for code, merge requests, CI/CD, registry, environments and security scanning. A pipeline job mirrors green builds of main and release tags to a public GitHub repository. |
| Dependencies and requirements files | New Appendix G lists every library by language (Python, TypeScript, PostgreSQL extensions) and the system packages, with version floors, how the files are generated, and licence notes. |
| Schema, API, build plan | Updated for the above; the Coverage Builder moves into Phase 2. |

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

Research analysts and investment banking analysts spend a large share of their week on the same mechanical loop: find a company's newest results, copy numbers into a model, check what changed, roll forecasts forward, then write it up as a note, a comps table or a pitch page. Starting coverage on a new company is the same work at a larger scale: build the model, fill years of history, set assumptions and write an initiation. Analekh automates both.

#### 1.1 One-line description

Search any NSE-listed company. If you already have a model, the system finds it, proposes the exact changes from the newest results and applies them after your approval. If you do not, it builds one from your sector template with sourced history and proposed assumptions. Either way it then drafts the results flash or initiation, note, slides and comps.

#### 1.2 Users

| **User** | **What they need from the system** |
|---|---|
| Equity research analyst | Fast model updates on results day, variance against own estimates, earnings call digest, draft note, Q&A over filings, and quick model builds when initiating coverage. |
| Investment banking analyst | Refreshed comps and precedents, company profile slides, pitch page numbers kept current, trigger alerts (fundraises, stake sales), quick models for new names. |
| Reviewer (associate, PM) | Traceability: every number linked to its XBRL tag or PDF page; an approval trail for every model change and assumption. |

#### 1.3 Goals

- Every NSE-listed company available from day one; no per-company setup to see its numbers.
- Ticker in, model updated: no manual PDF handling for core financials.
- New coverage in minutes: a sourced model from the analyst's own template plus a draft initiation.
- Human in the loop: nothing is written to a model without an approved change set or approved assumptions.
- Grounded GenAI: generated text never contains a number that did not come from the database or the model.
- Traceability: each value carries its source (feed item, file hash, XBRL context or PDF page).
- One data foundation serving both research and banking workflows.

#### 1.4 Non-goals

- No buy, sell or hold ratings or target prices in anything shared publicly (see section 23).
- No real-time trading data or order execution; prices are a static reference (section 3.3).
- No BSE-only companies in v1 (they are not in NSE's feeds; see section 4).
- No crawling of NSE or BSE internal web endpoints.
- The system never writes model formulas with AI; formulas come from templates the analyst controls.

## 2. Requirements

#### 2.1 Functional requirements

| **ID** | **Requirement** | **Phase** |
|---|---|---|
| F1 | Preload every NSE-listed company (symbol, name, ISIN, series, listing date, face value) and refresh weekly. | 1 |
| F2 | Search companies by symbol or name with autocomplete. | 1 |
| F3 | Poll NSE RSS feeds on a schedule and keep a permanent history of feed items. | 1 |
| F4 | Fetch and parse results XBRL for every company that files; store raw files once (hash dedupe). | 1 |
| F5 | Validate every filing with accounting identities and sanity rules; flag failures. | 1 |
| F6 | Backfill history on demand for a company, and in the background for the Nifty 500 first. | 1 |
| F7 | Maintain a watchlist that controls AI extraction, model updates, reports and alerts. | 1 |
| F8 | Read any workbook's structure: period axis, input versus formula cells, row labels, drivers, checks, dependencies. | 2 |
| F9 | Upload model templates by sector; suggest the mapping; confirm once per template; test-build before activation. | 2 |
| F10 | Build a new model from a template with sourced history, a Sources sheet and passing checks. | 2 |
| F11 | Propose first-pass assumptions with rationale and citations; analyst accepts or edits each. | 2 |
| F12 | Discover existing models in watched folders or the open workbook; identify the company; link once. | 2 to 5 |
| F13 | Build a change set for a linked model from new results: writes, dependents, roll-forwards, assumption suggestions. | 2 |
| F14 | Apply approved changes, recalculate and save a new version; never overwrite the original. | 2 |
| F15 | Extract sector KPIs and narrative from presentations, annual reports and transcripts with page references. | 3 |
| F16 | Generate a results flash, variance bridge, call digest, red flags, draft note and slides. | 4 |
| F17 | Generate a draft initiation report from the built model and sourced research. | 4 |
| F18 | Answer questions over a company's filings with page citations. | 4 |
| F19 | Refresh comps tables, company profile slides and tagged pitch pages. | 5 |
| F20 | Alert the analyst when a watchlist company files results or a red-flag event appears. | 5 |

#### 2.2 Non-functional requirements

| **Area** | **Target** |
|---|---|
| Accuracy | 100% match on mapped XBRL elements against the source file; 95% or better precision on AI-extracted KPIs in the golden set; every AI value carries a page reference. |
| Recognition | Template and model mapping suggestions correct for 90% or more of rows before user review; zero silent writes to unconfirmed rows. |
| Latency | Newest filing detected within 15 minutes of publication; change set in under 2 minutes for a cached filing; new model build in under 5 minutes when history is cached. |
| Traceability | Any value the system writes can be traced to feed item, file hash and XBRL context or PDF page. |
| Reliability | Idempotent jobs; re-running ingestion never duplicates facts; failed jobs retry with backoff. |
| Cost | No AI cost for the all-company numbers layer; AI limited to selected pages for watchlist or on-demand work; token use logged per call. |
| Security | Secrets only in environment variables; uploaded templates and models stay on the user's machine or private storage; macros never executed. |
| Portability | Server stack runs with one docker compose up; the Excel bridge runs on the analyst's machine. |

## 3. Data sources and access

Verified while scoping on 11 and 12 October 2026 and extended during the Phase 0 spike and the first build days (13 and 14 October 2026). These findings drive the main design choice: core numbers come from NSE's published RSS feeds and XBRL files, not from scraping or paid feeds.

#### 3.1 Findings

- **No free, official developer API exists for Indian company filings.** NSE has no public developer API.
- **NSE terms of use** prohibit "systematic or automated data collection" and "scraping, data mining, data extraction and data harvesting" (clause 9), and bar copying or redistributing content without written permission (clause 8).
- **NSE publishes official RSS feeds** at nsearchives.nseindia.com/content/RSS/, including Financial_Results.xml, Online_announcements.xml, Board_Meetings.xml, Corporate_action.xml, Insider_Trading.xml, Related_Party_Trans.xml, Voting_Results.xml and brsr.xml. Channel TTL is 5 minutes; each feed is a rolling window of recent items.
- **The Financial Results feed links directly to XBRL instance files.** A sampled file used the BSE Ind-AS taxonomy (prefix in-bse-fin) and contained the P&L for the quarter and the year to date, balance sheet instants and the full cash flow statement, with values in full INR.
- **Phase 0 (13 October 2026):** the results feed held two Ind-AS filings, both parsed, and their element names matched the vocabulary. The feed's pubDate is DD-Mon-YYYY HH:MM:SS. One filing gave different values for the same dates under two contexts (OneD and FourD). The SME list writes dates as DD-Mon-YY.
- **The Announcements feed links to PDFs** (presentations, orders, management changes) with company, subject and summary.
- **NSE publishes its equity list** as a CSV (EQUITY_L.csv) with columns SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE. It has no sector or industry column. SME companies are listed separately.
- **NSE Indices publishes index constituent lists** as CSVs on niftyindices.com (/IndexConstituent/), with an industry for each constituent. The Nifty 500 and Nifty Microcap 250 lists cover most of the main board; file names and columns are still to be checked against a live download.
- **BSE's List of Securities** (a free download) has security code, issuer, ISIN, status, group and instrument, but no industry column and no industry filter.
- **Excel's Stocks data type** (Microsoft 365 only; Office 2024 does not have it) turns an exchange ID such as XBOM:500325 or XNSE:RELIANCE into a record with fields including Industry (LSEG industry group) and Price (a delayed quote). Filled for BSE's 4,748 active equities in Excel for the web, it gave a sector for 2,458 of the 2,606 NSE main-board companies.
- **BSE sells corporate data feeds**: Corporate Announcements INR 5 to 9 lakh a year, Financial Results INR 3 to 5 lakh, Annual Report EOD INR 75,000, bhavcopy INR 35,000 for individual use (prices exclude taxes). No free RSS equivalent was found.
- **Zerodha Kite Connect** costs INR 2,000 a month and, since 8 February 2025, includes historical data (up to 10 years of intraday) and live WebSocket quotes. Not used in v1: a paid dependency, and its pinned autobahn release had known vulnerabilities (section 3.3).
- **Screener.in** has no API; premium users can export screen results as CSV. **EODHD** lists fundamentals for NSE tickers on paid plans; depth of Indian history not verified.
- **SEBI LODR** requires listed companies to post earnings call transcripts on their website and submit them to the exchanges within five working days; audio within 24 hours.
- **NSE's main website was geo-blocked** from the cloud region used for testing; the RSS and archive hosts were reachable. During the build the archive hosts and niftyindices.com also stopped answering an Indian home connection for hours while other sites worked; fetchers retry later with single requests and never work around a block.
- **Claude API PDF support**: 32 MB per request, up to 600 pages (100 when the context window is under 1M tokens), roughly 1,500 to 3,000 text tokens per page plus image tokens; Files API and batch processing available.

#### 3.2 Source matrix

| **Need** | **Chosen source** | **Alternative** | **Notes** |
|---|---|---|---|
| Company universe | NSE EQUITY_L.csv (plus SME list), weekly | BSE scrip master (paid) | No sector column; classification needs a separate source |
| Sector | Excel Stocks data type (LSEG industry via Microsoft 365), then NSE Indices constituent lists; a user override wins | Curated map; company disclosures | Precedence recorded per company (section 4.2) |
| Results numbers | NSE Financial_Results RSS to XBRL | BSE results feed (paid) | Structured; no AI needed for core statements |
| Presentations, transcripts, annual reports | NSE Online_announcements RSS to PDF; company IR pages | BSE announcements feed (paid) | AI extraction on selected pages |
| Results calendar and events | Board_Meetings, Corporate_action, Insider_Trading, Related_Party_Trans RSS | None free | Alerts and red flags |
| Historical backfill | Manual downloads and company IR pages; on demand and Nifty 500 first | Licensed data | Feeds only show recent items |
| Prices and market cap | Undecided (section 3.3) | Excel Stocks data type in the analyst's workbook now; NSE daily bhavcopy later; Kite Connect (paid, not used) | One static reference price at a time, not live quotes |
| Embeddings for search | Hosted embedding API or local open-source model |  | Anthropic does not offer an embeddings model |

Design rule: poll published RSS feeds at their stated refresh interval and fetch the files they link to. NSE Indices' constituent CSVs are fetched the same way, and the HTTP client allows only the /IndexConstituent/ path on that host. Never call NSE's internal JSON endpoints or crawl exchange pages. Obtain written confirmation from NSE (nsewebmaster@nse.co.in) or license a feed before any public or commercial release.

#### 3.3 Prices (undecided)

Prices feed comps, market cap, the profile slide's chart and valuation pages. No source is fixed yet; this section records the current thinking, not a decision.

- **Static reference price.** Analekh uses one price per company at a time, never a live feed: after the close, that day's closing price (end of day); before the open and while the market is open, the day's opening price once the pre-open session sets it, and the previous close until then. Every stored price carries its date and type (open or close).
- **In Excel, now.** An analyst's workbook can show a current, delayed price with the Stocks data type (=FIELDVALUE(cell,"Price")) on Microsoft 365. It needs no Analekh code, but the price stays in that workbook: the web app, comps and reports cannot use it, and Microsoft's terms limit the data to the account holder's own use.
- **From NSE data, later.** NSE's daily bhavcopy, a file published in NSE's archives, gives open, high, low, close and volume for every traded security after the close and would fill the prices table. It is end of day only, so it cannot give today's opening price during market hours. Using it needs the exchange-data rule (section 23) extended to name the file, and NSE's archive hosts reachable to confirm its format.
- **Not used:** Kite Connect (INR 2,000 a month), live quotes, and any NSE website page or internal API.
- Until a source is chosen, get_prices returns nothing, and comps and the profile slide show prices as missing instead of guessing.

## 4. Company universe and coverage levels

Version 0.0.0 required each company to be added before anything happened. That was wrong: knowing a company exists and covering it deeply are different things. 0.0.1 separates them into three levels.

| **Level** | **What happens** | **Cost and trigger** |
|---|---|---|
| 1. Universe | Every NSE-listed company preloaded from EQUITY_L.csv and the SME list; new listings and delistings picked up weekly. | Free; automatic |
| 2. Numbers for everyone | Every results XBRL in the feed is parsed and validated, for every company that files. History accumulates from go-live. | Local parsing only; automatic |
| 3. Deep coverage | AI extraction of presentations and transcripts, model updates, Coverage Builder, reports, alerts. | AI and compute cost; watchlist or one-click Analyse on any company |

#### 4.1 History

- Feeds only carry recent items, so automatic history starts at go-live.
- **On demand:** the first time a company is analysed in depth, the system backfills 8 to 12 quarters and 3 to 5 years from the company's IR site or files placed in the import folder.
- **Background:** Nifty 500 constituents are backfilled gradually so the most-used companies have history before anyone asks.

#### 4.2 Sector classification

Neither the equity list nor the results XBRL carries a sector, and sector picks templates and peers. Three sources, in order of precedence; a lower source never overwrites a higher one, and companies.sector_source records which one set each sector:

- **User override** per company (the editing screen is still to be built).
- **Excel's Stocks data type:** start from BSE's List of Securities, convert XBOM:<BSE code> IDs to the Stocks data type in Microsoft 365 and fill an Industry column (=FIELDVALUE(B2,"Industry")); analekh universe sectors --stocks-file imports the workbook by ISIN. Gives LSEG industry groups for dual-listed companies; SME companies are not on BSE's list.
- **NSE Indices constituent lists** (Nifty 500, Nifty Microcap 250 and the bank indices), fetched by analekh universe sectors.

The results taxonomy is set only on strong signals: membership of a bank index, or an NSE Indices industry that names NBFCs or insurance. Stocks data type sectors never set it, because LSEG's Banking Services group includes NBFCs; otherwise the first parsed filing decides. On 14 October 2026, 2,458 of 2,606 main-board companies had a sector; 148 main-board and 580 SME companies did not.

#### 4.3 Limit

BSE-only companies (not listed on NSE) are not in NSE's feeds and BSE does not publish a free RSS equivalent. v1 covers every NSE-listed company, including dual-listed ones; BSE-only coverage would need a licensed BSE feed.

## 5. System architecture

Six layers read left to right: sources, ingestion, processing, core data, engines and interfaces. The Claude API is an external service used by the document pipeline and the engines.

*Figure 1. Components and data flow (v0.0.1). Solid lines carry data, dashed lines are control or return paths, amber lines are the analyst approval path, dotted blue lines are Claude API calls. Amber-bordered engines are the two that write to Excel. Updated in 0.0.2: Kite Connect and the Price Fetcher's live quotes are superseded (the price source is undecided, section 3.3), and sectors also come from the Stocks data type and NSE Indices (section 4.2).*

#### 5.1 Layers and components

| **Layer** | **Component** | **Responsibility** |
|---|---|---|
| Sources | NSE RSS feeds | Financial results (XBRL), announcements (PDF), board meetings and event feeds. |
| Sources | NSE equity list | Every listed company, refreshed weekly. |
| Sources | Sector sources | Excel Stocks data type workbook import and NSE Indices constituent lists (section 4.2). |
| Sources | Company IR pages | Fallback for missing documents and historical backfill. |
| Sources | Price source (undecided) | One static reference price at a time (section 3.3). |
| Ingestion | Scheduler | Triggers feed polling every 5 to 15 minutes and nightly or weekly jobs. |
| Ingestion | Feed Watcher | Fetches feeds for all companies, dedupes items, stores them permanently, links items to companies. |
| Ingestion | Filing Fetcher | Downloads each linked file once, hashes it, stores it in MinIO. |
| Ingestion | Universe Loader | Loads and refreshes the company universe; assigns sector by source precedence and the results taxonomy from strong signals (section 4.2). |
| Ingestion | Price Fetcher | Loads daily reference prices once a source is chosen (section 3.3). |
| Processing | Raw Filing Store | Immutable object storage keyed by hash. |
| Processing | XBRL Parser | Turns every filer's XBRL into normalised facts; no AI. |
| Processing | Document Pipeline | For watchlist or on-demand companies: reads PDFs locally, classifies pages, sends selected pages to Claude, stores KPIs and text chunks. |
| Processing | Validation | Accounting identities, period checks, swing flags, AI versus XBRL conflicts. |
| Core data | PostgreSQL + pgvector | Companies, watchlist, filings, facts, KPIs, documents, prices, templates, models, versions, assumptions, change sets. |
| Engines | Model Sync Engine | Uses the workbook understanding engine to update linked models: mapping, write plan, dependency scan, roll-forward, change sets, versioned saves. |
| Engines | Analysis + GenAI Engine | Results flash, variance bridge, call digest, red flags, initiation draft, Q&A with citations. |
| Engines | Coverage Builder | Builds new models from sector templates with sourced history and proposed assumptions. |
| Engines | IB Output Engine | Comps, company profile slide, tagged pitch page refresh. |
| Interfaces | Excel | Bridge that finds and links models (xlwings now; Office.js add-in later). |
| Interfaces | Web App | Search, company pages, review queue, templates, reports, Q&A, comps. |
| Interfaces | Word and PowerPoint | Notes, initiation drafts, slides. |
| Interfaces | Alerts | Email or Telegram for watchlist events. |

## 6. Workflows

### 6.1 Quarterly update (existing model)

*Figure 2. Quarterly update. Steps 6 and 7 form the approval gate.*

- **Search ticker** in the web app or Excel; the company is already in the universe.
- **Newest filing?** The database returns the latest results filing for that company (collected automatically for every filer).
- **Fetch if missing:** if the file was not yet fetched, it is downloaded, parsed and validated.
- **Validated facts** are stored with source references.
- **New-period facts plus the linked model** go to Model Sync. The model is located by discovery (section 13).
- **Change set:** proposed writes, dependent-cell counts, roll-forwards and suggested assumption changes.
- **Approve or edit** each item; nothing is written before this.
- **Apply:** write, recalculate, save a new version; compute actuals versus estimates.
- **Outputs:** flash, draft note, slides, with citations.

### 6.2 Start coverage (no model yet)

*Figure 3. Start coverage with the Coverage Builder. Steps 6 and 7 form the approval gate.*

- **Start coverage** on any company and pick a template (the analyst's upload for that sector, or a built-in one).
- **Build request** goes to the Coverage Builder.
- **History and KPIs** are pulled from the database; anything missing is backfilled and run through the document pipeline.
- **Sourced actuals** return with references.
- **Propose drivers:** the GenAI engine suggests first-pass assumptions from history and management guidance.
- **Assumptions with citations** are shown to the analyst.
- **Accept or edit** each assumption.
- **Tagged model** is written to Excel; checks must pass.
- **Initiation draft, comps and slides** are generated. From the next results the quarterly update flow takes over.

### 6.3 Template onboarding

- Upload a workbook (blank template or a model for another company) and tag it with sectors.
- The workbook understanding engine reads its structure and suggests a mapping with confidence scores.
- The analyst confirms or fixes the mapping once for the template.
- A test build with one real company recalculates the template and reports checks, blank rows, unmapped facts and broken formulas.
- On acceptance the template becomes available to the Coverage Builder, with versioning.

### 6.4 Exceptions

| **Situation** | **Handling** |
|---|---|
| Filing not in the feed (old or missed) | IR-page fallback or import folder. |
| Restated or refiled period | Both versions kept; newest marked latest; difference shown. |
| Validation failure | Filing flagged; automatic changes blocked; report explains the rule. |
| Low-confidence AI value | Flagged in the change set with the source page side by side. |
| Model edited by the analyst since last sync | Fingerprint mismatch detected; structure and dependencies rescanned before planning. |
| Template row the company does not report | Left blank and flagged. |
| Company reports an item the template lacks | Listed as unmapped; analyst chooses a target row or skips. |
| Model or template contains macros | Kept, never executed. |

## 7. Inputs and outputs

#### 7.1 Inputs from the analyst

| **Input** | **How it is supplied** | **Used for** |
|---|---|---|
| Company | Search box (web app or Excel) | Everything; the company already exists in the universe |
| Watchlist | Add or remove in the web app | Deep coverage, alerts, background work |
| Existing models | Watched folders or the open workbook; confirmed once | Quarterly updates |
| Templates by sector | Upload in the web app | Coverage Builder |
| Mapping confirmation | Once per template or model | Where each number goes |
| Own estimates | Already in the model's estimate columns | Actual versus estimate; assumption suggestions |
| Approvals | Accept, edit or skip per item | Every write and every assumption |
| Peer lists, alert settings | Web app settings | Comps; notifications |

#### 7.2 Inputs collected automatically

| **Input** | **Source and method** | **Lands in** |
|---|---|---|
| Company universe | EQUITY_L.csv and SME list, weekly | companies |
| Sectors | Stocks data type workbook import; NSE Indices constituent lists | companies (sector, sector_source) |
| Results numbers (all filers) | Financial_Results RSS to XBRL; polled every 5 minutes | filings, facts |
| Presentations, annual reports, transcripts | Online_announcements RSS to PDF; IR pages fallback | filings, documents, chunks, kpis |
| Events | Board meeting, corporate action, insider, related party feeds | feed_items, alerts |
| Prices | Undecided: Stocks data type in the workbook now, NSE daily bhavcopy later (section 3.3) | prices (bhavcopy route only) |
| History | On-demand and background backfill | Same tables |

#### 7.3 Outputs

| **Output** | **Format** | **Delivered to** | **Produced by** |
|---|---|---|---|
| Change set | Review screen; JSON | Web app or Excel pane | Model Sync |
| Updated model version | .xlsx | Analyst's folder or storage | Model Sync |
| New model from template | .xlsx with Sources and Checks sheets | Analyst's folder | Coverage Builder |
| Proposed assumptions | Review list with citations | Web app | Coverage Builder and GenAI |
| Results flash | 1 page | Web app; export | GenAI |
| Variance bridge | Table and text | Web app; note | GenAI |
| Call digest | Text with page references | Web app | GenAI |
| Red flags | List with sources | Web app and alerts | GenAI and feeds |
| Draft earnings note | .docx | Download | GenAI |
| Draft initiation report | .docx | Download | GenAI |
| Slides | .pptx | Download | GenAI |
| Q&A answers | Text with citations | Web app | GenAI |
| Comps table | .xlsx | Download | IB Output |
| Company profile slide | .pptx | Download | IB Output |
| Refreshed pitch pages | .pptx and change log | Download | IB Output |
| Alerts | Email or Telegram | Phone or inbox | Feed watcher |
| Validation and template test reports | Pass or fail per rule | Web app | Validation; template onboarding |

## 8. Data model (PostgreSQL)

PostgreSQL with pgvector is the single source of truth. Raw files live in MinIO; Redis holds the job queue only. Monetary values use NUMERIC. Full DDL in Appendix A.

#### 8.1 Why PostgreSQL

- Relational integrity across companies, filings, facts, templates, models, assumptions and change sets.
- Exact arithmetic with NUMERIC; proper DATE columns for periods.
- JSONB for irregular payloads (XBRL dimensions, AI output, workbook structure maps).
- pgvector for filing search and Q&A without a separate vector database.
- Full audit trail of every write and every approved assumption.
- Standard tooling: SQLAlchemy, Alembic, one container.

#### 8.2 Tables

| **Table** | **Purpose and key columns** |
|---|---|
| companies | Whole NSE universe: nse_symbol, isin, name, series, listing_date, face_value, sector, industry, sector_source, results_taxonomy, is_sme, is_active, source, refreshed_at. |
| watchlist | user_id, company_id, added_at, settings (alerts, auto-analyse). Replaces is_tracked. |
| feed_items | Every RSS item: feed, item_key, title, link, description, pub_date, company_id, processed_at. |
| filings | company_id, kind, period_start, period_end, period_type, consolidated, audited, source_url, file_sha256, storage_key, filed_at, status, meta. |
| facts | Normalised XBRL facts: element, period, instant flag, consolidated, value NUMERIC, unit, context, dimensions, is_latest. |
| kpis | AI or table-extracted metrics with page, quote, confidence, method, verified. |
| documents, chunks | PDF metadata; text chunks with embeddings and full-text search. |
| prices | Daily OHLC and market cap; empty until a price source is chosen (section 3.3). |
| templates | owner, name, sectors, version, storage_key, structure (JSONB), mapping (JSONB), driver_cells, check_cells, status (draft, tested, active). |
| template_tests | template_id, company_id, result, issues (JSONB), created_at. |
| models | company_id, template_id (null for user-built models), name, doc_tag (hidden workbook tag), file_path, fingerprint, last_seen, structure, mapping, origin (discovered, built). |
| model_builds | model_id, template_id, history range, status, created_at. |
| assumptions | model_id, driver, proposed_value, rationale, citations, decision, final_value. |
| model_versions | Every saved workbook version with parent version, storage key, author, time. |
| change_sets, change_items | Proposed changes per sync with decision per item. |
| reports, initiation_reports | Generated outputs with citations and prompt hash. |
| llm_calls, alerts | Token and cost tracking; sent notifications. |
| peer_lists | Saved peer lists for comps: name, symbols. |

#### 8.3 Indexes and constraints

- companies: unique nse_symbol and isin; check constraints on results_taxonomy and sector_source; trigram index on name, used when ranked search finds nothing (section 19.1).
- facts: (company_id, element, period_end) partial index where is_latest.
- filings: (company_id, period_end DESC); unique file_sha256.
- feed_items: unique (feed, item_key); index on pub_date.
- models: unique doc_tag.
- chunks: HNSW on embedding; GIN on full-text column.
- Restatements insert new facts and flip is_latest; nothing is deleted.

## 9. Ingestion layer

#### 9.1 Universe loader

- Downloads EQUITY_L.csv and the SME list weekly; upserts by ISIN; marks companies missing from the list as inactive. Listing dates come as DD-Mon-YYYY (main board) or DD-Mon-YY (SME).
- Sector comes from the sources in section 4.2, in order of precedence (analekh universe sectors); results_taxonomy is set from strong signals only, and otherwise from the first parsed filing.

#### 9.2 Feed polling

- Feeds: Financial_Results, Online_announcements, Board_Meetings, Corporate_action, Insider_Trading, Related_Party_Trans, Sast_ReasonForEncumbrance.
- Interval: 5 minutes (published TTL) for results and announcements; 15 to 60 minutes for event feeds.
- Conditional requests where supported, descriptive User-Agent, timeouts, exponential backoff.
- Item key = SHA-256 of link plus pubDate; upsert on (feed, item_key).
- pubDate arrives as DD-Mon-YYYY HH:MM:SS (India time), not the RFC 822 form; it must be parsed in that format or V8 cannot run.
- Company linking by normalised name, then symbol or ISIN when present; unmatched items queued for review.
- Results XBRL is fetched and parsed for every company. Announcement PDFs are fetched for every company (cheap) but only processed by the document pipeline for watchlist or on-demand companies.

#### 9.3 Fetching and storage

- Each file downloaded once; SHA-256 computed; stored at kind/yyyy/mm/sha256.ext.
- Same hash: skip. Same period with a different hash: revised or restated filing.
- Rate limited (default 1 request per second) with retries.

#### 9.4 Backfill

- On demand when a company is first analysed in depth: 8 to 12 quarters and 3 to 5 years.
- Background queue for Nifty 500 constituents, lowest priority.
- Files from IR sites or the import folder go through the same parser and validation path; AI extraction for backfills uses the Batch API.

## 10. XBRL parsing and validation

#### 10.1 Parsing

- Arelle for full taxonomy support; lxml for fast extraction from plain instance files.
- Contexts resolved from actual start and end dates (duration for quarter and year to date; instant for balance sheet), never from context names.
- Values stored in full INR; display transforms (for example INR crore) live in mappings.
- Consolidated and standalone stored separately; mappings choose the basis.
- Dimensions stored in JSONB and hashed into the uniqueness key.
- Element names form a fixed vocabulary, so mapping to models is configuration, not AI.
- When two contexts carry the same dates but different values (seen in Phase 0: OneD and FourD), the parser keeps the first for now; how to flag the conflict is an open question (section 28).

#### 10.2 Validation rules

| **ID** | **Rule** | **On failure** |
|---|---|---|
| V1 | Revenue from operations plus other income equals total income. | Flag; block auto-apply |
| V2 | Profit before tax equals total income less total expenses, adjusted for exceptional items. | Flag; block auto-apply |
| V3 | Profit after tax equals profit before tax less tax. | Flag |
| V4 | Total assets equal equity plus liabilities for each instant. | Flag; block auto-apply |
| V5 | Quarter equals year to date less prior year to date where both exist. | Flag |
| V6 | Context dates agree with the declared reporting period. | Use declared period; warn |
| V7 | Quarter-on-quarter change above 50% in revenue or profit. | Highlight |
| V8 | Filed more than 180 days after period end. | Label late |
| V9 | Same period refiled with different values. | Keep both; mark latest; show diff |
| V10 | AI value conflicts with XBRL for the same item. | XBRL wins; AI value flagged |

## 11. Document pipeline

XBRL covers statutory statements but not sector KPIs or management commentary. Those come from presentations, annual reports and transcripts, processed for watchlist or on-demand companies. The user never selects pages.

- **Local read** of every page with PyMuPDF; Tesseract for scanned pages.
- **Page classification** by keyword patterns, table density and position; ambiguous pages may go to a smaller Claude model as text.
- **Selection** of the top pages per category (typically 10 to 25 of a 300-page annual report).
- **Extraction** by Claude against a JSON schema; each value with page, quote and confidence.
- **Chunking and embedding** for search and Q&A.
- **Validation** of units, periods and conflicts with XBRL.

```
{
"company": "MUTHOOTFIN",
"period_end": "2026-06-30",
"kpis": [{"name": "gold_loan_aum", "value": 0, "unit": "INR crore",
"page": 7, "quote": "...", "confidence": 0.0}],
"guidance": [{"topic": "...", "statement": "...", "page": 0}],
"red_flags": [{"type": "...", "detail": "...", "page": 0}]
}
```

Zeros are schema placeholders. Sector KPI lists are defined per sector (banks, NBFCs, consumer, industrials, IT services). Transcripts get speaker-aware parsing and outputs for guidance changes, analyst concerns and deflected topics, each with page references.

## 12. Workbook understanding engine

One engine reads any workbook. Model discovery, template onboarding, the Coverage Builder and quarterly updates all depend on it, which keeps the codebase small and makes it the technical core of the system.

| **Capability** | **Method** |
|---|---|
| Period axis | Find header rows with period patterns (Q2FY27, 2QFY27, Sep-26, FY27E, dates); detect an A/E row; infer the last actual column. |
| Inputs versus formulas | Cell types from the file; colour convention (blue inputs, black formulas, green links) as a secondary signal. |
| Row labels to standard fields | Synonym dictionary first ("Net sales", "Revenue from operations", "Income from operations"); AI for ambiguous labels; confidence score per row. |
| Drivers | Input cells on assumption sheets referenced by forecast formulas. |
| Checks | Cells comparing totals (assets versus liabilities, cash flow versus cash) or labelled checks. |
| Dependencies | Formula graph across sheets (formulas or pycel library); dependents of every input; INDIRECT and OFFSET reported as unknown impact. |
| Hygiene | External links, macros, hardcodes inside formula areas, inconsistent formulas across a row. |
| Fingerprint | Hash of structure and values to detect edits made outside the system. |

Output is a structure map (JSONB) stored with the template or model, plus a suggested mapping the user confirms.

## 13. Model discovery and recognition

#### 13.1 Finding models

- The Excel bridge watches folders the user chooses (for example ~/Models or a OneDrive folder) and indexes .xlsx and .xlsm files.
- If a workbook is open in Excel, the bridge attaches to the live workbook rather than the file on disk.
- Later: cloud files on OneDrive or SharePoint through Microsoft Graph.

#### 13.2 Identifying the company

- **Hidden tag:** after the first link, the system writes the company symbol and a model ID into the workbook's custom document properties. Renames and moves keep working.
- **File name:** matched against the universe ("Muthoot_Model_FY27.xlsx" to MUTHOOTFIN).
- **Contents:** company name, ISIN or symbol on a cover sheet or headers.

For a new file the system suggests the match ("This looks like your MUTHOOTFIN model. Link it?") and the user confirms once.

#### 13.3 Staying in step

- Before planning a change set, the current fingerprint and modified time are compared with the last seen version; any difference triggers a rescan.
- Save options: new versioned copy (default) or in place with automatic backup.
- With the Office.js add-in the task pane works on the open workbook directly and reads its tag, so no lookup is needed.

## 14. Template onboarding

#### 14.1 Upload

- Upload a blank template or an existing model for another company; tag sectors, name and version.
- For an existing model, historical hardcoded inputs are identified and cleared while formulas are kept; uncertain cells are shown, not deleted.

#### 14.2 Structure and mapping

- The workbook understanding engine reads periods, inputs, labels, drivers and checks.
- Suggested mapping with confidence per row; the user confirms once per template; reused for every company built from it.

#### 14.3 Test build

The template is filled with one real company's history and recalculated. The report lists: checks passing or failing, template rows the company does not report, reported items with no template row, and broken formulas. Only after acceptance is the template active.

#### 14.4 Requirements for uploaded templates

- Historical periods across columns with labels in one column.
- Forecast formulas reference the input area, not typed numbers.
- No external workbook links (flagged on upload).
- Macros are kept but never executed; INDIRECT and OFFSET allowed but flagged.

#### 14.5 Versioning and sharing

- Each sector has a default template; per-company overrides allowed.
- Editing creates a new version; models keep the version they were built on.
- Templates can be personal or shared within a team. Built-in templates ship as a fallback.

## 15. Coverage Builder

#### 15.1 Flow

- Pick a company from the universe and choose Start coverage; the sector's default template is preselected.
- Gather 8 to 12 quarters and 3 to 5 years from the database, backfilling what is missing; sector KPIs, segments, shareholding and business description from presentations and annual reports.
- Generate the workbook from the template: inputs filled, formulas untouched, each input cell commented with its source.
- Propose first-pass assumptions per driver from history (three-year averages and trends) and management guidance, each with rationale and citation; analyst accepts or edits.
- Recalculate (Excel or LibreOffice) and require the Checks sheet to pass.
- Write the hidden tag and confirmed mapping; save the model.
- Draft the initiation pack.

#### 15.2 Built-in template structure

| **Sheet** | **Contents** |
|---|---|
| Cover / Index | Company, date, sheet map, hidden tag |
| Data | Historical actuals in blue with source comments |
| Drivers | Growth, margins, yields, costs, capex, working capital, payout |
| Model | Linked P&L, balance sheet and cash flow; balance via cash or debt |
| Sector KPIs | Template-specific metrics |
| Valuation | DCF and relative valuation; for banks and NBFCs, P/B versus ROE and residual income |
| Sensitivities | Cost of capital, terminal growth, key drivers |
| Checks | Balance sheet balances, cash flow ties, no stray hardcodes |
| Sources | Every input traced to document and page |

#### 15.3 Initiation pack

- Draft initiation report (Word): investment summary, business and segments, industry backdrop, management and governance, financial analysis, forecasts, valuation, risks.
- Charts, comps table and company profile slide.
- Every number from the database or model with citations; industry context drafted from public sources with citations and marked for verification.
- Valuation is computed; rating and target price are left for the analyst (SEBI Research Analyst rules apply to publication).

#### 15.4 Hand-off

The built model carries its tag and confirmed mapping, so the next results flow straight into the quarterly update with no setup.

## 16. Model Sync Engine

#### 16.1 Write plan

- Writes only into input cells mapped to facts or KPIs; formula cells change only through explicit roll-forward items.
- Dependents of every written cell are listed from the dependency graph.

#### 16.2 Roll-forward

- New period column marked E with formulas: propose actual values in input rows and switch the flag to A, keeping calculation rows.
- Propose extending the forecast horizon by copying the last forecast column one column right.
- List hardcoded estimates next to new actuals and period labels needing a shift.

#### 16.3 Assumption suggestions

For each driver, actual versus estimate is compared and the GenAI engine suggests a revision with a grounded one-line rationale. Suggestions are change items like any other.

#### 16.4 Change set and apply

- Items grouped by kind: actual_write, roll_forward, assumption_suggestion, label_shift; each with cell, old and new value or formula, rationale and source.
- Review in the web app or Excel pane; bulk accept per kind.
- Apply writes in one pass, recalculates, saves a new model_version; the original is never overwritten.

#### 16.5 Excel integration options

| **Option** | **How it works** | **Trade-offs** |
|---|---|---|
| xlwings (v1) | Local bridge drives desktop Excel on Windows or macOS. | Native recalc and formatting; needs Excel; runs outside Docker. |
| openpyxl + LibreOffice | Headless edits; LibreOffice recalculation. | No Excel needed; formatting edge cases. |
| Office.js add-in (later) | Task pane inside Excel (Windows, Mac, web). | Best experience; more front-end work. |

## 17. Analysis and GenAI Engine

| **Output** | **Content** |
|---|---|
| Results flash | Actuals versus last quarter, same quarter last year and estimates; key KPIs; three to five bullets. |
| Variance bridge | Changes split into price, volume, mix and cost effects where data allows. |
| Call digest | Guidance changes, analyst concerns, deflected topics, tone shift, with pages. |
| Red flags | Auditor qualifications, pledges, related party transactions, insider sales, late filings, restatements. |
| Draft note and slides | Word (three to five pages) and PowerPoint. |
| Initiation draft | Full initiation structure from the Coverage Builder's model. |
| Q&A | Answers over filings with citations. |

#### 17.1 Tools exposed to the model

| **Tool** | **Returns** |
|---|---|
| get_facts(company, elements, periods) | Fact values with source references. |
| get_kpis(company, names, periods) | KPI values with pages and confidence. |
| get_model_values(model_id, ranges) | Values and estimates from the model. |
| search_filings(company, query, k) | Chunks with document and page references. |
| get_prices(company, from, to) | Static reference prices and market cap (section 3.3); empty until a source is chosen. |
| calc(expression, inputs) | Deterministic arithmetic in Python. |

#### 17.2 Grounding rules

- Only numbers returned by tools or computed by calc may appear in output.
- A post-check matches every number in the text to tool results; any unmatched number blocks the output.
- Each claim carries a citation; prompt caching for long system prompts; tokens logged in llm_calls.

## 18. IB Output Engine

- **Comps:** saved peer lists; EV/Sales, EV/EBITDA, P/E, P/B; EV = market cap + debt − cash from the latest balance sheet; trailing twelve months from quarterly facts; fiscal-year alignment; Excel export. Market cap, and so every multiple, waits for a price source (section 3.3).
- **Company profile slide:** business summary, shareholding, key financials, valuation, price chart, recent events. The price chart waits for the same.
- **Pitch page refresh:** placeholders such as {{MUTHOOTFIN.pat_q}} replaced with current values plus a change log.
- **Precedents (later):** curated set from deal announcements with AI extraction flagged for review.

## 19. User interfaces

#### 19.1 Web app

| **Screen** | **Contents and actions** |
|---|---|
| Search and universe | Type-ahead over every NSE company, ranked: exact ticker or ISIN, ticker prefix, name prefix, words that start words in the name, then substrings. The universe (about 80 KB compressed) loads once and is searched in the browser; the server answers only before it loads and as a typo fallback. Open a company; add to watchlist. |
| Watchlist | Last filing, next board meeting, validation status, pending change sets. |
| Company page | Filings timeline, facts and KPIs by period and basis, sector and coverage level, price chart (once a price source exists), red flags; Analyse and Start coverage buttons. |
| Change-set review | Grouped items with cell, old and new values, source and rationale, dependent-cell counts; accept, edit, skip, apply. |
| Assumption review | Proposed drivers with rationale and citations for new models; accept or edit. |
| Templates | Upload, sector tags, mapping confirmation, test-build report, versions. |
| Models | Discovered and built models, link status, versions. |
| Reports | Flash, digest, notes, initiation drafts; downloads. |
| Q&A | Chat over a company's filings with page links. |
| Comps builder | Peer lists, multiples table, export. |
| Settings | Watched folders, alert channels, API keys. |

Stack: React with TypeScript (Vite), TanStack Query, AG Grid Community for dense grids, ECharts, PDF.js for the side-by-side source viewer, and the Inter font bundled with the app. Layout: collapsible left sidebar; light, dark and system themes; clean, dense screens; motion that respects the reduced-motion setting. The front end stays light: a new library has to earn its weight.

#### 19.2 Excel

- Phase 2: xlwings bridge (background service with a tray or terminal status) that discovers, links and writes models.
- Later: Office.js task pane showing the change set or assumptions beside the model; clicking an item highlights its cell.

#### 19.3 Developer and operator interfaces

- CLI: analekh universe load, analekh universe sectors [--stocks-file], analekh search, analekh watch, analekh refresh, analekh backfill, analekh template add, analekh build, analekh sync, analekh golden-test.
- Swagger at /docs for every endpoint.
- Internal Streamlit admin: feed health, failed jobs, validation failures, token spend.

## 20. API design

| **Endpoint** | **Purpose** |
|---|---|
| GET /companies/search?q= | Ranked type-ahead over the universe; limit and offset for paging. |
| GET /companies/index | The whole universe (id, symbol, name, ISIN, sector) for search in the browser; ETag and 304, gzip. |
| GET /companies/{symbol} | Company record and coverage level. |
| POST /watchlist / DELETE /watchlist/{symbol} | Add or remove a company. |
| GET /watchlist | Watchlist with coverage levels. |
| POST /companies/{symbol}/analyse | On-demand deep coverage (backfill, document pipeline). |
| POST /companies/{symbol}/refresh | Find newest filing; fetch and validate if missing. |
| GET /companies/{symbol}/filings \| facts \| kpis | Filings, facts and KPIs by period. |
| GET /jobs/{id} | Job status. |
| POST /templates | Upload a template with sectors. |
| POST /templates/{id}/mapping | Confirm or edit the suggested mapping. |
| POST /templates/{id}/test | Run a test build for a company. |
| GET /templates; POST /templates/{id}/activate | List templates; activate after a passing test build. |
| POST /coverage | Start coverage: company and template; returns a model build. |
| GET /models/{id}/assumptions; POST decisions | Review proposed assumptions. |
| POST /models/{id}/finalize | Write the built model once its assumptions are decided. |
| POST /models/discover; POST /models/link; POST /models/{id}/link | Index watched folders; confirm a model-to-company link for a new or a registered model. |
| GET /models; GET /models/{id}/builds; GET /models/{id}/versions/{version} | Models screen, build history, version download. |
| POST /models/{id}/sync | Build a change set for a filing. |
| GET /change-sets/{id}; POST decisions; POST apply | Review and apply. |
| POST /reports | Flash, note, slides, digest or initiation. |
| GET /reports/{id} | Fetch a generated report. |
| POST /qa | Question over filings with citations. |
| POST /comps | Comps for a peer list. |
| GET /alerts | Recent alerts. |

## 21. Technology stack

| **Layer** | **Choice** | **Reason** |
|---|---|---|
| Language and environment | Python 3.12, uv | Finance, PDF and XBRL libraries; reproducible lockfile |
| API | FastAPI (uvicorn) | Typed, async, OpenAPI docs |
| Jobs and scheduling | Celery + Redis; Celery beat | Retries, rate limits, polling |
| Database | PostgreSQL + pgvector; SQLAlchemy; Alembic | See section 8 |
| Object storage | MinIO | Immutable raw files and generated outputs |
| XBRL | Arelle; lxml | Taxonomy support; fast parsing |
| PDF | PyMuPDF, pdfplumber, Camelot; Tesseract | Local text, tables, OCR |
| AI | Claude API (PDF input, tool use, structured output, Batch API, prompt caching) | Irregular tables, label matching, grounded writing |
| Embeddings | Hosted API or local sentence-transformers model | Search and Q&A |
| Excel | xlwings; openpyxl; formulas or pycel; LibreOffice for headless recalc | Live writes, structure reading, dependency graphs |
| Documents | python-docx, python-pptx, XlsxWriter | Notes, slides, workbooks |
| Market data | Undecided: Stocks data type in the workbook; NSE daily bhavcopy later (section 3.3) | No paid feed in v1 |
| Sector data | Excel Stocks data type (Microsoft 365); NSE Indices constituent CSVs | Free; no scraping |
| Front end | React (Vite), TypeScript; pnpm workspace; Node 24 | Review screens and dashboards; strict, fast installs |
| Quality | pytest, ruff, mypy, pre-commit | Tests, linting, typing |
| Source control and CI/CD | GitLab Free (primary); GitHub (public mirror); OSV-Scanner for dependencies | Integrated CI/CD, registry and the scanners the Free tier includes; public visibility via mirror |
| Container registry | GitLab container registry | Images built and scanned in the same pipeline |
| Deployment | Docker Compose | One command |

## 22. Packaging, deployment and setup

#### 22.1 Services

| **Service** | **Role** |
|---|---|
| api | FastAPI application |
| worker | Celery workers: fetch, parse, extract, build, sync, report |
| beat | Scheduler for feeds, weekly universe refresh, nightly backfill |
| postgres | PostgreSQL with pgvector |
| redis | Queue broker |
| minio | Raw files and generated outputs |
| web | React build served by nginx |
| excel-bridge (host) | Runs on the analyst's machine; watches folders; drives Excel |

#### 22.2 Requirements

- Docker Desktop with 8 GB RAM (4 vCPU, 20 GB disk to start; more as the all-company facts table grows).
- Python 3.12 and uv for development and the Excel bridge. Node.js 24 and pnpm for the front ends (fnm is a convenient way to install Node).
- Microsoft Excel desktop for the xlwings route; LibreOffice for headless recalculation. Microsoft 365 (Excel for the web is enough) for the Stocks data type used by the sector import.
- Anthropic API key.
- Indian network or VM in an Indian region for NSE access.
- Optional: Tesseract; SMTP or Telegram bot token.
- Every library by language, with versions, and every system package: Appendix G.

#### 22.3 Environment variables

```
# Copy .env.example to .env and fill in; never commit .env.
DATABASE_URL=postgresql+psycopg://app:app@postgres:5432/analekh
REDIS_URL=redis://redis:6379/0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=analekh
ANTHROPIC_API_KEY=...
CLAUDE_MODEL=claude-opus-5-5
CLAUDE_SMALL_MODEL=claude-haiku-5-5
EMBEDDINGS_PROVIDER=local
FEED_POLL_SECONDS=300
EVENT_FEED_POLL_SECONDS=1800
UNIVERSE_REFRESH_CRON=0 6 * * 1
BACKFILL_PRIORITY=NIFTY500
USER_AGENT=Analekh/0.1 (contact: you@example.com)
IMPORT_DIR=./import
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SMTP_URL=
ALERT_EMAIL_TO=
# Excel bridge (host)
ANALEKH_API=http://localhost:8000
WATCH_FOLDERS=~/Models;~/OneDrive/Models
SAVE_MODE=versioned
```

#### 22.4 Setup

- Clone the repository from GitLab; copy .env.example to .env and fill in keys.
- docker compose up -d.
- Front ends: pnpm install, then pnpm dev for the web app (it proxies /api to port 8000).
- Run migrations (alembic upgrade head).
- Load the universe (analekh universe load); feeds start on the next scheduler tick.
- Load sectors (analekh universe sectors, with --stocks-file for a Stocks data type workbook; section 4.2).
- Upload sector templates or use the built-in ones.
- On the analyst machine: uv sync, then start the Excel bridge with watched folders configured.
- Search a company: Start coverage, or link an existing model and sync.

#### 22.5 Source control, CI/CD and mirroring

GitLab (Free tier) is the single source of truth. GitHub hosts a read-only public mirror for visibility; it never receives direct pushes from developers.

| **Area** | **Configuration** |
|---|---|
| Branching | Protected main. While there is one developer, commits go straight to main and the pipeline runs on every push. With collaborators: feature branches, merge requests only, pipeline must succeed, squash on merge, source branch deleted after merge. |
| Pipeline stages | lint, test, build, scan, deploy-staging, dast, release, mirror (Appendix F). The test stage also runs the web job (pnpm lint, test and build) and the dependency audit. |
| Quality gates | ruff, ruff format check, mypy, pytest with coverage and JUnit report; golden-set accuracy on a schedule and on demand. |
| Security scanning | GitLab templates for SAST, secret detection and container scanning (on the built image), which run on Free. Dependencies: OSV-Scanner on uv.lock and pnpm-lock.yaml, with findings shown as a warning. DAST against staging needs Ultimate and a staging URL; not in effect yet. |
| Security policies | Merge request approval and scan execution policies need Ultimate and are not in effect on Free. Until then, scanner warnings are reviewed in each pipeline. |
| Registry | Images pushed to the GitLab container registry, tagged by commit SHA and release tag. |
| Environments | staging deploys automatically from main; production deploys from release tags with manual approval; deployment history per environment. Not set up yet; the deploy jobs run only when STAGING_URL or PRODUCTION_URL is set. |
| Runner | Self-hosted GitLab Runner on a VM in an Indian region (tag: india) for deployments and live smoke tests; GitLab-hosted runners for lint, test, build and scans. The self-hosted India runner is not set up yet. |
| Secrets | Protected and masked CI/CD variables scoped per environment: GITHUB_MIRROR_TOKEN, GITHUB_MIRROR_USER, GITHUB_MIRROR_REPO, deployment SSH key, runtime keys. |
| Mirror to GitHub | A pipeline job runs after a green pipeline on main and on release tags, and pushes the commit (fast-forward only, no force) and tags to GitHub using a fine-grained token limited to that one repository with contents read and write. A resource group prevents concurrent mirror pushes. A pipeline job is used instead of GitLab's built-in push mirroring so that only green builds reach the public repository. The job clears the alpine/git image's entrypoint (it is git, and the runner needs a shell) and is skipped when GITHUB_MIRROR_TOKEN is not set. |
| GitHub repository settings | Public; description, topics and README point contributors to GitLab; Actions, Issues, Wiki and Projects disabled; ruleset on main blocks force pushes and deletion; optional CodeQL as an independent second scanner. |

#### 22.6 Distribution

- Public GitHub mirror with sample models and templates built on public companies, a demo video and the diagrams; GitLab remains the working repository.
- No raw exchange files, user models or keys committed; secret detection and pre-commit hooks enforce this before code leaves a developer's machine.

## 23. Security, compliance and data rights

- **Exchange data:** only published RSS feeds at their stated interval and the files they link to; no internal endpoints; no redistribution of raw data; written confirmation or a licensed feed before public or commercial release. NSE Indices' published constituent CSVs are allowed on the same terms, limited to /IndexConstituent/ by the HTTP client's path allow-list.
- **Third-party data from Excel:** sectors (and prices, if that route is used) from Excel's Stocks data type come from LSEG through Microsoft 365. They are kept in the local database only, never in git, and Microsoft's terms for this data must be checked before any public or commercial release.
- **Research regulation:** publishing buy or sell recommendations in India generally requires SEBI Research Analyst registration; NISM Series XV alone is not registration. Shared outputs carry no ratings or target prices.
- **User files:** models and templates stay on the user's machine or private storage; only structure maps and confirmed mappings are stored centrally; macros are never executed.
- **Secrets:** environment variables only; never logged.
- **AI data handling:** only public filings and the user's own workbook labels are sent to the Claude API; no client or employer data in the public build.
- **Audit:** every model change, assumption and report stored with sources and approver.
- **Code and supply chain:** GitLab SAST, secret detection and container scanning, plus OSV-Scanner for dependencies; DAST and merge request approval policies once the plan includes them; pre-commit secret scanning locally; pnpm blocks package install scripts unless allowed; the GitHub mirror token is scoped to one repository and rotated every 90 days.

## 24. Testing and quality

| **Test** | **Approach and target** |
|---|---|
| Golden set | 20 filings across sectors including banks and NBFCs with hand-checked values. |
| XBRL parsing | 100% exact match on mapped elements. |
| KPI extraction | 95% or better precision with correct pages. |
| Workbook understanding | 20 real-world models and templates with hand-labelled structure; mapping suggestion accuracy 90% or more. |
| Template test builds | Checks pass for each built-in template on five companies per sector. |
| Coverage Builder | Built models balance; every input has a Sources entry. |
| Model sync | Fixture workbooks with expected change sets and recalculated outputs. |
| Grounding | Every number in generated text matches a tool result. |
| Universe and feeds | Recorded feed samples; universe diff tests for listings and delistings. |
| Search | The browser's ranking matches the server's on real queries (22 of 22 at last check). |
| CI | GitLab CI on every push and merge request: ruff, mypy, pytest, alembic check, web lint, tests and build, security scanners and the dependency audit; golden-set accuracy on schedule and per release. |

## 25. Cost model

| **Item** | **Estimate** |
|---|---|
| Universe and all-company facts | No AI cost; local parsing; modest storage growth each results season. |
| Prices | No cost while undecided; the Excel route needs Microsoft 365, which the sector import also uses. |
| GitLab | Free tier; Ultimate only if DAST, dependency scanning and security policies are needed. |
| Presentation extraction | About 5 to 15 selected pages per filing, watchlist or on demand only. |
| Annual report extraction | About 10 to 25 selected pages instead of 300. |
| Label mapping | AI only for ambiguous labels; once per template or model. |
| Reports and initiations | Per company per quarter or per initiation; cached system prompts. |
| Backfill | Batch API at a lower price. |

Check current Claude API pricing before budgeting; real cost per company is measured from llm_calls from the first spike.

## 26. Build plan

| **Phase** | **Scope** | **Exit criteria** |
|---|---|---|
| 0. Spike (2 to 3 days) | Load the universe; poll two feeds; parse XBRL for 10 tickers including a bank and an NBFC. (The price pull was dropped with Kite Connect; section 3.3.) | Data path proven; taxonomy differences documented |
| 1. Data layer (1 to 2 weeks) | Universe loader, watcher, fetcher, parser, validation, schema, watchlist, on-demand and Nifty 500 backfill, search. | Every NSE filer's results in the database |
| 2. Builder and sync (2 to 3 weeks) | Workbook understanding engine, template onboarding, Coverage Builder for two templates (NBFC and manufacturing or consumer), Model Sync on built models, review screens, xlwings bridge. | Start coverage then quarterly update works end to end |
| 3. Document AI (2 weeks) | Page classifier, KPI extraction for three sectors, transcript digest, embeddings. | KPI precision target met |
| 4. GenAI outputs (1 to 2 weeks) | Flash, variance bridge, red flags, note and slides, initiation draft, Q&A, grounding check. | Grounded outputs on 10 companies |
| 5. Discovery, IB outputs, polish (2 weeks) | Discovery and linking of existing user models, comps, profile slide, pitch refresh, alerts, Office.js pane, demo video. | Demo-ready public repository |

Phase 0 is time-boxed to two to three days and decides whether the full build proceeds. December-quarter results, filed from late January, provide a live test window for Phases 1 and 2.

Status on 14 October 2026: the Phase 0 spike ran on 13 October. The feed held only two Ind-AS filings, so the bank and NBFC element tables wait for the October results season, and the hand-check of values against the results PDFs is still open. Phase 1 is in progress: universe, sectors, search, watchlist and the web app's shell are built; the feed watcher and backfill have not yet run against live feeds.

Versions follow the build phases: v0.0.x while Phase 0 is under way, v0.1.x once Phase 0 is complete, v0.2.x once Phase 1 is complete, and so on (the middle number counts completed phases; the last counts revisions within a phase). The first release for proper testing is v1.0.0-pre-release.

## 27. Risks and mitigations

| **Risk** | **Mitigation** |
|---|---|
| NSE changes feeds or objects to polling | Polite polling; source adapters; IR fallback; written confirmation or licence before release. |
| XBRL varies by sector | results_taxonomy per company; sector mappings; golden set per taxonomy. |
| Context or period errors | Rules V5, V6, V8; declared period wins. |
| AI extraction errors | Pages and quotes on every value; thresholds; XBRL wins; approval before writes. |
| Templates and models vary widely | Shared understanding engine; confidence scores; confirm once; test builds; built-in fallbacks. |
| Wrong model linked to a company | Hidden tag after confirmation; user confirmation for every new link. |
| Sector classification gaps | Stocks data type import and NSE Indices lists, with precedence; user override per company. SME companies remain the gap. |
| Excel dependency | Headless openpyxl and LibreOffice path; Office.js later. |
| Geo-restriction | Indian network or VM. |
| NSE hosts stop answering | Retry later with single requests; never work around a block; import folder as fallback. |
| No price source settled | Core numbers do not need prices; one static reference price at a time; analysts can use the Stocks data type in their own workbooks meanwhile. |
| Regulatory exposure when sharing outputs | No ratings or targets in shared outputs. |
| Scope creep | Phase gates with exit criteria; each phase ends with a working demo. |
| Mirror diverges or leaks | GitHub main accepts only fast-forward pushes from the mirror job; mirror runs only after a green pipeline; secret detection and push protection run before anything leaves GitLab. |

## 28. Open questions

- Do bank and NBFC results XBRL files use a different element set, and how stable are tags across companies? (Phase 0 found no bank or NBFC filings in the feed; rerun during the results season.)
- Can annual statements be downloaded cleanly from NSE's annual report XBRL section for backfill?
- Is there a public shareholding pattern feed, or must shareholding come from filings?
- How to classify the 728 companies still without a sector (148 main board, 580 SME), and do Microsoft's terms allow storing Stocks data type fields?
- Do transcripts appear in the announcements feed with a consistent subject line?
- xlwings or Office.js first for the demo machine?
- Hosted or local embeddings?
- Would NSE confirm in writing that polling its RSS feeds for a personal or open-source tool is acceptable?
- Price source: the Stocks data type, NSE's bhavcopy, or both? And where does the day's opening price come from during market hours, given that bhavcopy is end of day only?
- How should XBRL contexts with the same dates but different values (OneD versus FourD) be flagged?
- Report generation: one open tool loop per report (today), or a fixed outline from a report template with a short tool loop and a grounding check per section, keeping the open loop for Q&A?

## 29. Appendices

### Appendix A. Core DDL (PostgreSQL)

```
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE companies (
id BIGSERIAL PRIMARY KEY,
nse_symbol TEXT UNIQUE NOT NULL,
isin CHAR(12) UNIQUE,
name TEXT NOT NULL,
series TEXT, listing_date DATE, face_value NUMERIC(12,2),
sector TEXT, industry TEXT,
sector_source TEXT CHECK (sector_source IN ('user','excel_stocks','nse_indices')),
results_taxonomy TEXT CHECK (results_taxonomy IN ('indas','banking','nbfc','insurance')),
is_sme BOOLEAN NOT NULL DEFAULT FALSE,
is_active BOOLEAN NOT NULL DEFAULT TRUE,
source TEXT NOT NULL DEFAULT 'nse_equity_list',
refreshed_at TIMESTAMPTZ
);
CREATE INDEX ON companies USING gin (name gin_trgm_ops);
CREATE TABLE watchlist (
user_id TEXT NOT NULL,
company_id BIGINT NOT NULL REFERENCES companies(id),
added_at TIMESTAMPTZ DEFAULT now(),
settings JSONB NOT NULL DEFAULT '{}',
PRIMARY KEY (user_id, company_id)
);
CREATE TABLE feed_items (
id BIGSERIAL PRIMARY KEY,
feed TEXT NOT NULL, item_key CHAR(64) NOT NULL,
title TEXT, link TEXT, description TEXT, pub_date TIMESTAMPTZ,
company_id BIGINT REFERENCES companies(id), processed_at TIMESTAMPTZ,
UNIQUE (feed, item_key)
);
CREATE INDEX ON feed_items (pub_date);
CREATE TABLE filings (
id BIGSERIAL PRIMARY KEY,
company_id BIGINT NOT NULL REFERENCES companies(id),
feed_item_id BIGINT REFERENCES feed_items(id),
kind TEXT NOT NULL,
period_start DATE, period_end DATE, period_type TEXT,
consolidated BOOLEAN, audited BOOLEAN,
source_url TEXT,
file_sha256 CHAR(64) UNIQUE NOT NULL,
storage_key TEXT NOT NULL,
filed_at TIMESTAMPTZ,
status TEXT NOT NULL DEFAULT 'fetched',
meta JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ON filings (company_id, period_end DESC);
CREATE TABLE facts (
id BIGSERIAL PRIMARY KEY,
filing_id BIGINT NOT NULL REFERENCES filings(id),
company_id BIGINT NOT NULL REFERENCES companies(id),
element TEXT NOT NULL,
period_start DATE, period_end DATE NOT NULL,
is_instant BOOLEAN NOT NULL, consolidated BOOLEAN NOT NULL,
value NUMERIC(24,4), unit TEXT, decimals INT, context_ref TEXT,
dimensions JSONB NOT NULL DEFAULT '{}', dims_hash CHAR(64) NOT NULL,
is_latest BOOLEAN NOT NULL DEFAULT TRUE,
UNIQUE (filing_id, element, period_start, period_end, consolidated, dims_hash)
);
CREATE INDEX ON facts (company_id, element, period_end) WHERE is_latest;
CREATE TABLE kpis (
id BIGSERIAL PRIMARY KEY,
filing_id BIGINT NOT NULL REFERENCES filings(id),
company_id BIGINT NOT NULL REFERENCES companies(id),
name TEXT NOT NULL, value NUMERIC(24,4), unit TEXT, period_end DATE,
page INT, quote TEXT, confidence NUMERIC(3,2), method TEXT,
verified BOOLEAN DEFAULT FALSE
);
CREATE TABLE documents (
id BIGSERIAL PRIMARY KEY,
filing_id BIGINT NOT NULL REFERENCES filings(id),
page_count INT
);
CREATE TABLE chunks (
id BIGSERIAL PRIMARY KEY,
document_id BIGINT NOT NULL REFERENCES documents(id),
page INT NOT NULL, ord INT NOT NULL, text TEXT NOT NULL,
embedding vector(1024),
tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING gin (tsv);
CREATE TABLE prices (
company_id BIGINT REFERENCES companies(id), trade_date DATE,
open NUMERIC(14,4), high NUMERIC(14,4), low NUMERIC(14,4), close NUMERIC(14,4),
volume BIGINT, market_cap NUMERIC(24,2),
PRIMARY KEY (company_id, trade_date)
);
CREATE TABLE templates (
id BIGSERIAL PRIMARY KEY,
owner TEXT NOT NULL, name TEXT NOT NULL, sectors TEXT[] NOT NULL,
version INT NOT NULL DEFAULT 1,
storage_key TEXT NOT NULL,
structure JSONB, mapping JSONB,
driver_cells JSONB, check_cells JSONB,
status TEXT NOT NULL DEFAULT 'draft',  -- draft, tested, active
is_default BOOLEAN NOT NULL DEFAULT FALSE,
created_at TIMESTAMPTZ DEFAULT now(),
UNIQUE (owner, name, version)
);
CREATE TABLE template_tests (
id BIGSERIAL PRIMARY KEY,
template_id BIGINT NOT NULL REFERENCES templates(id),
company_id BIGINT NOT NULL REFERENCES companies(id),
result TEXT NOT NULL, issues JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE models (
id BIGSERIAL PRIMARY KEY,
company_id BIGINT NOT NULL REFERENCES companies(id),
template_id BIGINT REFERENCES templates(id),
name TEXT NOT NULL,
origin TEXT NOT NULL,           -- discovered, built
doc_tag UUID UNIQUE NOT NULL,   -- written into workbook custom properties
file_path TEXT, fingerprint CHAR(64), last_seen TIMESTAMPTZ,
structure JSONB, mapping JSONB
);
CREATE TABLE model_builds (
id BIGSERIAL PRIMARY KEY,
model_id BIGINT NOT NULL REFERENCES models(id),
template_id BIGINT NOT NULL REFERENCES templates(id),
history_from DATE, history_to DATE,
status TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE assumptions (
id BIGSERIAL PRIMARY KEY,
model_id BIGINT NOT NULL REFERENCES models(id),
driver TEXT NOT NULL, period TEXT,
proposed_value NUMERIC(18,6), rationale TEXT, citations JSONB,
decision TEXT NOT NULL DEFAULT 'pending', final_value NUMERIC(18,6)
);
CREATE TABLE model_versions (
id BIGSERIAL PRIMARY KEY,
model_id BIGINT NOT NULL REFERENCES models(id),
version INT NOT NULL, parent_version INT,
storage_key TEXT NOT NULL, created_by TEXT,
created_at TIMESTAMPTZ DEFAULT now(),
UNIQUE (model_id, version)
);
CREATE TABLE change_sets (
id BIGSERIAL PRIMARY KEY,
model_id BIGINT NOT NULL REFERENCES models(id),
base_version INT NOT NULL,
filing_id BIGINT REFERENCES filings(id),
status TEXT NOT NULL DEFAULT 'proposed',
summary JSONB, created_at TIMESTAMPTZ DEFAULT now(), decided_at TIMESTAMPTZ
);
CREATE TABLE change_items (
id BIGSERIAL PRIMARY KEY,
change_set_id BIGINT NOT NULL REFERENCES change_sets(id),
kind TEXT NOT NULL, sheet TEXT, cell TEXT,
old_value TEXT, new_value TEXT, formula_before TEXT, formula_after TEXT,
rationale TEXT, source_fact_id BIGINT REFERENCES facts(id),
decision TEXT NOT NULL DEFAULT 'pending', final_value TEXT
);
CREATE TABLE reports (
id BIGSERIAL PRIMARY KEY,
company_id BIGINT REFERENCES companies(id),
filing_id BIGINT REFERENCES filings(id),
model_id BIGINT REFERENCES models(id),
kind TEXT NOT NULL,             -- flash, note, slides, digest, initiation, qa
storage_key TEXT, model_used TEXT, prompt_hash CHAR(64),
citations JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE llm_calls (
id BIGSERIAL PRIMARY KEY, purpose TEXT, model TEXT,
input_tokens INT, output_tokens INT, request_hash CHAR(64),
created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE alerts (
id BIGSERIAL PRIMARY KEY,
company_id BIGINT REFERENCES companies(id),
kind TEXT, payload JSONB, channel TEXT, sent_at TIMESTAMPTZ
);
CREATE TABLE peer_lists (
id BIGSERIAL PRIMARY KEY,
name TEXT UNIQUE NOT NULL,
symbols TEXT[] NOT NULL
);
```

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
- source: xbrl:RevenueFromOperations
sheet: Data
row_label: "Revenue from operations"
confidence: 0.98
- source: xbrl:FinanceCosts
sheet: Data
row_label: "Finance costs"
confidence: 0.99
- source: xbrl:ProfitLossForPeriod
sheet: Data
row_label: "PAT"
confidence: 0.95
- source: kpi:gold_loan_aum
sheet: Data
row_label: "Gold loan AUM"
transform: none
confidence: 0.90
drivers:
- name: loan_yield
actual_row_label: "Yield on loans"
forecast_sheet: Drivers
forecast_row_label: "Yield assumption"
checks:
- sheet: Checks
cell_label: "Balance sheet difference"
expect: 0
```

### Appendix C. Change set (example)

```
{
"change_set_id": 42,
"model": "MUTHOOTFIN nbfc_quarterly v3",
"base_version": 7,
"filing": "Q2FY27 consolidated results (XBRL)",
"summary": {"writes": 18, "dependents_affected": 214,
"roll_forwards": 3, "suggestions": 2, "warnings": 1},
"items": [
{"kind": "actual_write", "sheet": "Data", "cell": "M12",
"old": "=L12*(1+Drivers!M5)", "new": "<actual value>",
"source": "RevenueFromOperations, 2026-07-01 to 2026-09-30"},
{"kind": "roll_forward", "sheet": "Data", "cell": "M3", "old": "E", "new": "A"},
{"kind": "assumption_suggestion", "sheet": "Drivers", "cell": "N8",
"old": "<current yield>", "new": "<suggested yield>",
"rationale": "Actual yield came in below the estimate for the quarter"}
]
}
```

### Appendix D. Docker Compose skeleton

```
services:
postgres:
image: pgvector/pgvector:pg16
environment: [POSTGRES_USER=app, POSTGRES_PASSWORD=app, POSTGRES_DB=analekh]
volumes: [pgdata:/var/lib/postgresql/data]
redis:
image: redis:7
minio:
image: minio/minio
command: server /data --console-address :9001
volumes: [minio:/data]
api:
build: .
command: uvicorn analekh.api.main:app --host 0.0.0.0 --port 8000
env_file: .env
depends_on: [postgres, redis, minio]
worker:
build: .
command: celery -A analekh.jobs worker -l info
env_file: .env
depends_on: [postgres, redis, minio]
beat:
build: .
command: celery -A analekh.jobs beat -l info
env_file: .env
depends_on: [redis]
web:
build: ./web
depends_on: [api]
volumes:
pgdata:
minio:
```

### Appendix E. Repository layout

```
analekh/
analekh/
api/            FastAPI routers and schemas
jobs/           Celery app, tasks, schedules
universe/       equity list loader, sectors (precedence, Stocks import, index lists), search
ingest/         feed watcher, polite HTTP client and host allow-list, fetcher, backfill
xbrl/           parser, context mapping, taxonomies
docs/           page classifier, extraction, chunking, embeddings
validate/       rules V1 to V10
workbook/       structure reader, label matcher, dependency graph, fingerprint
templates/      onboarding, mapping confirmation, test builds
templates_builtin/  NBFC and manufacturing or consumer templates
builder/        Coverage Builder, assumption proposals, Sources sheet
modelsync/      write plan, roll-forward, change sets
genai/          tools, prompts, grounding check, report and initiation builders
ib/             comps, profile slide, pitch refresh
alerts/         email and Telegram alerts
admin/          Streamlit ops dashboard
excel_bridge/   folder watcher, model discovery, xlwings writer
db/             SQLAlchemy models, Alembic migrations
cli.py, coverage.py, discovery.py, facts.py, golden.py
deploy/           compose files per environment
docs/             design document, deviations log, runbooks
mappings/         example template mapping (Appendix B)
scripts/          Phase 0 spike, Stocks workbook helper
web/              React front end (package.json)
office-addin/     Excel task pane, Phase 5 (package.json)
tests/            unit, integration, golden set, workbook fixtures
docker-compose.yml
pyproject.toml    Python dependencies (source of truth; uv.lock pins them)
requirements*.txt exported from uv.lock (Appendix G)
package.json      pnpm workspace root (with pnpm-workspace.yaml, pnpm-lock.yaml)
.python-version, .node-version
.env.example
.gitlab-ci.yml    pipeline (Appendix F)
.gitlab/          merge request templates
.pre-commit-config.yaml
CLAUDE.md         project brief for the AI coding assistant
.claude/          assistant settings, hooks and commands
```

### Appendix F. GitLab CI/CD pipeline (skeleton)

```
stages: [lint, test, build, scan, deploy-staging, dast, release, mirror]
variables:
GIT_DEPTH: "0"                 # full history, required for the mirror push
include:
- template: Jobs/SAST.gitlab-ci.yml
- template: Jobs/Secret-Detection.gitlab-ci.yml
- template: Jobs/Container-Scanning.gitlab-ci.yml
- template: Security/DAST.gitlab-ci.yml
.py:
image: python:3.12-slim
before_script:
- pip install --quiet uv
- uv sync --frozen
lint:
extends: .py
stage: lint
script:
- uv run ruff check .
- uv run ruff format --check .
- uv run mypy analekh
unit_and_integration:
extends: .py
stage: test
services:
- name: pgvector/pgvector:pg16
alias: postgres
- name: redis:7
alias: redis
variables:
POSTGRES_USER: app
POSTGRES_PASSWORD: app
POSTGRES_DB: analekh
DATABASE_URL: postgresql+psycopg://app:app@postgres:5432/analekh
REDIS_URL: redis://redis:6379/0
script:
- uv run alembic upgrade head
- uv run pytest --junitxml=report.xml --cov=analekh
artifacts:
reports:
junit: report.xml
golden_set:
extends: .py
stage: test
rules:
- if: $CI_PIPELINE_SOURCE == "schedule"
- when: manual
allow_failure: true
script:
- uv run analekh golden-test --report golden.json
artifacts:
paths: [golden.json]
web:
stage: test
image: node:24-alpine
before_script:
- npm install -g "$(node -p "require('./package.json').packageManager")"
script:
- pnpm install --frozen-lockfile
- pnpm lint
- pnpm test
- pnpm build                   # web app and Excel task pane
dependency_audit:                  # replaces Dependency-Scanning (Ultimate only)
stage: test
image:
name: ghcr.io/google/osv-scanner:v2.7.0
entrypoint: [""]
allow_failure: true              # findings show as a warning
script:
- /osv-scanner scan source --lockfile uv.lock --lockfile pnpm-lock.yaml
build_image:
stage: build
image: docker:27
services: [docker:27-dind]
script:
- echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"
- docker build -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA" .
- docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
container_scanning:
stage: scan
needs: [build_image]
variables:
CS_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
deploy_staging:
stage: deploy-staging
tags: [india]                    # self-hosted runner on the Indian VM
environment: { name: staging, url: $STAGING_URL }
rules:
- if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
script:
- IMAGE_TAG=$CI_COMMIT_SHA docker compose -f deploy/compose.staging.yml pull
- IMAGE_TAG=$CI_COMMIT_SHA docker compose -f deploy/compose.staging.yml up -d
dast:
stage: dast
variables:
DAST_TARGET_URL: $STAGING_URL
rules:
- if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
deploy_production:
stage: release
tags: [india]
environment: { name: production, url: $PRODUCTION_URL }
rules:
- if: $CI_COMMIT_TAG
when: manual
script:
- IMAGE_TAG=$CI_COMMIT_SHA docker compose -f deploy/compose.production.yml pull
- IMAGE_TAG=$CI_COMMIT_SHA docker compose -f deploy/compose.production.yml up -d
mirror_to_github:
stage: mirror
image:
name: alpine/git:latest
entrypoint: [""]           # the image's entrypoint is git; the runner needs a shell
resource_group: github-mirror
rules:
- if: $GITHUB_MIRROR_TOKEN == null || $GITHUB_MIRROR_TOKEN == ""
when: never
- if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
- if: $CI_COMMIT_TAG
script:
- REMOTE="https://${GITHUB_MIRROR_USER}:${GITHUB_MIRROR_TOKEN}@github.com/${GITHUB_MIRROR_REPO}.git"
- if [ -n "$CI_COMMIT_TAG" ]; then git push "$REMOTE" "refs/tags/$CI_COMMIT_TAG"; else git push "$REMOTE" "HEAD:refs/heads/main"; fi
```

Notes: scanner template paths follow GitLab's documentation at the time of writing and should be checked against the current docs. The mirror job runs in the last stage, so it only executes when every earlier job has passed. The push has no force flag, so any divergence on GitHub fails the job instead of overwriting history. On GitLab Free the Dependency-Scanning template is replaced by the dependency_audit job (OSV-Scanner); DAST and the security policies stay off until the plan includes them. The real file also has a workflow block, caches, and rules that run deploy and DAST jobs only when their URL variables are set.

### Appendix G. Dependencies and requirements files

The project uses three languages: Python for the back end, workers and Excel bridge; TypeScript for the web app and the Excel add-in; and SQL on PostgreSQL. Python dependencies are declared in pyproject.toml and locked in uv.lock; the requirements files below are exported from the lock so the project also installs with plain pip. Version floors reflect current releases in October 2026; exact versions always come from the lockfiles (uv.lock, pnpm-lock.yaml).

| **File** | **Installs** |
|---|---|
| requirements.txt | API, Celery workers and scheduler; the application Docker image. |
| requirements-bridge.txt | Excel bridge on the analyst's Windows or macOS machine; kept small and separate. |
| requirements-optional.txt | Local embeddings and the internal admin dashboard; installed only when used. |
| requirements-dev.txt | Tests, linting and type checks; includes requirements.txt. |
| web/package.json | React web app (Node.js 24 LTS), in the pnpm workspace. |
| office-addin/package.json | Excel task pane add-in (Phase 5). |
| package.json, pnpm-workspace.yaml | Root of the pnpm workspace: pinned pnpm version, install-script policy, one pnpm-lock.yaml for the web app and the add-in. |

#### G.1 Python: requirements.txt

```
# requirements.txt: API, Celery workers and scheduler (the application image)
# Python 3.12. pyproject.toml is the source of truth; exact pins live in uv.lock.
# Regenerate a fully pinned copy with:  uv export --no-dev --no-hashes -o requirements.txt
# Web API
fastapi>=0.143,<1.0
uvicorn[standard]>=0.54,<1.0
pydantic>=2.14,<3
pydantic-settings>=2.15,<3
python-multipart>=0.0.32          # template and model uploads
# Database
sqlalchemy>=2.1,<3
alembic>=1.20,<2
psycopg[binary]>=3.3,<4
pgvector>=0.5,<1.0
# Jobs and scheduling (pulls in a compatible redis client)
celery[redis]>=5.6,<6
# Object storage, HTTP and feeds
boto3>=1.43,<2                    # S3 API: MinIO locally, any S3 service when hosted
httpx>=0.28,<1.0
feedparser>=6.0,<7
tenacity>=9.2,<10                 # retries with backoff
# XBRL
arelle-release>=2.46,<3
lxml>=6.1,<7
# PDF and OCR
pymupdf>=1.28,<2
pdfplumber>=0.11,<1.0
camelot-py>=2.0,<3
pytesseract>=0.3.13,<1.0          # needs the Tesseract binary (see system packages)
# AI
anthropic>=1.13,<2
# Excel and documents
openpyxl>=3.1.5,<4
formulas>=1.3,<2                  # dependency graph and headless recalculation checks
xlsxwriter>=3.2,<4
python-docx>=1.2,<2
python-pptx>=1.0.2,<2
matplotlib>=3.11,<4               # charts for notes and slides
# Data handling and matching
pandas>=3.0,<4
numpy>=2.5,<3
rapidfuzz>=3.14,<4                # label matching
python-dateutil>=2.9,<3
# CLI and logging
typer>=0.27,<1.0
structlog>=26.1
```

#### G.2 Python: requirements-bridge.txt

```
# requirements-bridge.txt: Excel bridge on the analyst's machine (Windows or macOS with desktop Excel)
# Kept separate so the bridge stays small. Regenerate with:
#   uv export --only-group bridge --no-hashes -o requirements-bridge.txt
xlwings>=0.37,<1.0
openpyxl>=3.1.5,<4
watchdog>=6.0,<7                  # watched model folders
httpx>=0.28,<1.0                  # talks to the ANALEKH API
pydantic-settings>=2.15,<3
typer>=0.27,<1.0
structlog>=26.1
```

#### G.3 Python: requirements-optional.txt

```
# requirements-optional.txt: install only when needed
sentence-transformers>=6.1,<7     # local embeddings (EMBEDDINGS_PROVIDER=local); pulls in PyTorch, large
streamlit>=1.65,<2                # internal admin dashboard
```

#### G.4 Python: requirements-dev.txt

```
# requirements-dev.txt: tests, linting and typing. Regenerate with:
#   uv export --only-dev --no-hashes -o requirements-dev.txt
-r requirements.txt
pytest>=9.1,<10
pytest-cov>=7.1
pytest-asyncio>=1.4
respx>=0.23                       # mocks httpx; tests never hit the network
time-machine>=3.5                 # freezes time for scheduler and period tests
ruff>=0.17
mypy>=2.4
pre-commit>=4.6
types-python-dateutil
pandas-stubs
boto3-stubs[s3]
```

#### G.5 TypeScript: web/package.json

```
{
"name": "analekh-web",
"private": true,
"type": "module",
"engines": { "node": "^22.22.2 || ^24.15.0 || >=26" },
"scripts": {
"dev": "vite",
"build": "tsc -b && vite build",
"lint": "eslint .",
"format": "prettier --write src",
"test": "vitest run",
"api-types": "openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts"
},
"dependencies": {
"@fontsource-variable/inter": "^5.3.0",
"@tanstack/react-query": "^5.104.2",
"ag-grid-community": "^36.2.0",
"ag-grid-react": "^36.2.0",
"echarts": "^6.1.0",
"echarts-for-react": "^3.0.6",
"pdfjs-dist": "^6.4.299",
"react": "^19.3.0",
"react-dom": "^19.3.0",
"react-router-dom": "^7.18.4",
"zod": "^4.6.6"
},
"devDependencies": {
"@eslint/js": "^10.0.1",
"@testing-library/dom": "^10.4.2",
"@testing-library/react": "^16.3.3",
"@types/react": "^19.3.0",
"@types/react-dom": "^19.3.0",
"@vitejs/plugin-react": "^6.1.2",
"eslint": "^10.12.0",
"eslint-plugin-react-hooks": "^7.1.1",
"jsdom": "^30.1.2",
"openapi-typescript": "^7.13.0",
"prettier": "^3.9.10",
"typescript": "~5.9.3",
"typescript-eslint": "^8.71.1",
"vite": "^8.3.4",
"vitest": "^5.0.4"
}
}
```

TypeScript is held at 5.9 because openapi-typescript does not yet support TypeScript 6 and typescript-eslint does not yet support TypeScript 7. The api-types script generates front-end types from the FastAPI OpenAPI schema so the two sides cannot drift. Both front ends install with pnpm (version pinned in the root package.json).

#### G.6 TypeScript: office-addin/package.json

```
{
"name": "analekh-excel-addin",
"private": true,
"type": "module",
"scripts": {
"dev-certs": "office-addin-dev-certs install",
"start": "office-addin-debugging start manifest.xml desktop",
"stop": "office-addin-debugging stop manifest.xml",
"validate": "office-addin-manifest validate manifest.xml",
"build": "tsc -b && vite build"
},
"dependencies": {
"react": "^19.3.0",
"react-dom": "^19.3.0"
},
"devDependencies": {
"@types/office-js": "^1.0.611",
"@types/react": "^19.3.0",
"@types/react-dom": "^19.3.0",
"@vitejs/plugin-react": "^6.1.2",
"office-addin-debugging": "^7.0.1",
"office-addin-dev-certs": "^3.0.1",
"office-addin-manifest": "^3.0.1",
"typescript": "~5.9.3",
"vite": "^8.3.4"
}
}
```

Office.js itself is not an npm dependency: Microsoft requires add-ins to load it from its CDN in the task pane HTML.

#### G.7 SQL: PostgreSQL extensions

| **Extension** | **Use** |
|---|---|
| vector (pgvector) | Embeddings and similarity search on chunks; shipped in the pgvector/pgvector:pg16 image. |
| pg_trgm | Fuzzy company-name search; part of PostgreSQL contrib. |

#### G.8 System packages and services

| **Package** | **Version** | **Needed by** |
|---|---|---|
| Python | 3.12 | Back end, workers, Excel bridge |
| uv | Current | Environments and lockfile |
| Node.js | 24 LTS (24.15 or later) | Web app and add-in builds, Prettier |
| pnpm | 12.x (pinned in package.json) | Front-end installs (workspace) |
| PostgreSQL + pgvector | 16 (pgvector/pgvector:pg16) | Database |
| Redis | 7 | Celery broker |
| MinIO | Current | Local S3-compatible object storage |
| Tesseract OCR + English data | 5.x (apt: tesseract-ocr) | OCR for scanned pages |
| LibreOffice | Current, headless | Recalculating workbooks without Excel |
| nginx | Stable | Serving the web build |
| Docker Engine + Compose | Current | Running all services |
| Microsoft Excel (desktop) | Microsoft 365 | xlwings bridge; the Stocks data type for the sector import (Excel for the web also works) |

#### G.9 Licence notes

Everything is free for an open-source public repository. Before any closed or commercial release, these need attention:

| **Component** | **Licence and action** |
|---|---|
| PyMuPDF | AGPL-3.0 or a commercial licence from Artifex. A closed product needs that licence, or PDF text extraction moves to pypdfium2 with pdfplumber. |
| MinIO server | AGPL-3.0. Hosted deployments use a managed S3 service instead; the code talks to the S3 API through boto3, so only configuration changes. |
| Redis server | Licence changed from version 7.4. Hosted deployments can use Valkey (BSD), a drop-in replacement. |
| psycopg | LGPL-3.0; fine when used unmodified as a library. |
| formulas | EUPL-1.1; review obligations before distributing a modified copy. |
| AG Grid | Community edition (MIT) only; Enterprise features are paid and not used. |
| Market data | No price feed in v1. Prices and sectors from Excel's Stocks data type (LSEG via Microsoft 365) are for the account holder's own use; NSE bhavcopy and NSE Indices terms need checking before redistribution. Serving other users needs a market data licence from an authorised vendor. |

### Appendix H. Glossary

| **Term** | **Meaning** |
|---|---|
| Universe | Every NSE-listed company, preloaded from the equity list. |
| Watchlist | Companies that get deep coverage, alerts and background work. |
| XBRL | Machine-readable tagged financial statements filed with the exchanges. |
| Taxonomy | Dictionary of XBRL element names; here in-bse-fin for Ind-AS results. |
| Context | XBRL definition of the period and dimensions a fact belongs to. |
| Template | A user's model structure for a sector, onboarded once and reused. |
| Structure map | The engine's reading of a workbook: periods, inputs, labels, drivers, checks. |
| Hidden tag | Model ID and symbol stored in workbook custom document properties. |
| Change set | Proposed model edits awaiting approval. |
| Roll-forward | Turning an estimate period into an actual and extending the forecast. |
| Comps | Comparable companies analysis using trading multiples. |
| LODR | SEBI Listing Obligations and Disclosure Requirements regulations. |
| TTL | Refresh interval a feed publishes (5 minutes for NSE feeds). |
| Sector source | Where a company's sector came from: user, excel_stocks or nse_indices. A lower source never overwrites a higher one. |
| Stocks data type | Excel (Microsoft 365) data type that turns an exchange ID such as XBOM:500325 into a record with fields like Industry and Price. |
| Static reference price | The one price Analekh uses for a company at a time: the day's close after the market closes, the day's open during market hours (section 3.3). |
| Bhavcopy | NSE's daily end-of-day price file for every traded security. |

## 30. Sources

- [NSE RSS feeds page](https://www.nseindia.com/static/rss-feed)
- [NSE Financial Results RSS feed](https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml)
- [NSE Online Announcements RSS feed](https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml)
- [List of NSE RSS feeds (Feedspot)](https://rss.feedspot.com/nseindia_rss_feeds/)
- [NSE equity list (EQUITY_L.csv)](https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv)
- [Sample results XBRL file (NSE archives)](https://archives.nseindia.com/corporate/xbrl/INDAS_121282_1717387_24082026053915.xml)
- [NSE Terms of Use](https://www.nseindia.com/static/nse-terms-of-use)
- [NSE Annual Report XBRL filings](https://www.nseindia.com/companies-listing/corporate-filings-annual-reports-xbrl)
- [BSE Information Products Pricing Sheet](https://mock.bseindia.com/downloads1/Information_Products_Pricing_Sheet.pdf)
- [BSE Market Data Products](https://www.bseindia.com/market_data_products.html)
- [Zerodha Kite Connect pricing change (Marketcalls)](https://www.marketcalls.in/fintech/zerodha-makes-trading-api-free-for-personal-use-bundles-historical-data-with-connect-api.html)
- [NseIndiaApi, unofficial Python library](https://github.com/BennyThadikaran/NseIndiaApi)
- [Screener.in export help](https://support.screener.in/article/28-export-screen-results)
- [EODHD financial summary, BSE.NSE](https://eodhd.com/financial-summary/BSE.NSE)
- [SEBI LODR call disclosures (TaxGuru)](https://taxguru.in/?p=1067323)
- [Claude API PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- [Best Financial Data API for Indian Stocks 2026 (DalalAI)](https://dalalai.com/blog/best-financial-data-api-india)
- [NSE Indices (index constituent lists)](https://www.niftyindices.com)
- [BSE List of Securities](https://www.bseindia.com/corporates/List_Scrips.html)
- [Excel data types: Stocks and Geography (Microsoft Support)](https://support.microsoft.com/en-us/office/excel-data-types-stocks-and-geography-61a33056-9935-484f-8ac8-f1a89e210877)
- [OSV-Scanner](https://google.github.io/osv-scanner/)
- [GitLab features by tier](https://about.gitlab.com/pricing/feature-comparison/)
