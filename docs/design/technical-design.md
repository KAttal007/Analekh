**Analekh**

*The analyst's record, kept for you.*

Technical Design Document

| **Field** | **Detail** |
|---|---|
| Author | Kaushal Attal |
| Version | 0.0.4 (design, updated during the build) |
| Date | 18 October 2026 |
| Supersedes | Version 0.0.3 (15 October 2026) |
| Status | Phase 0 nearly complete; Phase 1 (data layer) in progress: results for 2,748 companies from March 2023, daily prices, the Results desk and company pages on real data |

**Purpose of this document.** It records every design decision for Analekh: what the system does, the data it depends on and the rules around that data, the architecture, the workflows, the database schema, each engine's internals, the interfaces and API, packaging and deployment, testing, costs, risks and the build plan. It is written for the engineer building the system and for anyone reviewing the design.

### What changed in 0.0.4

| **Change** | **Summary** |
|---|---|
| Workflows and data flows | Section 6 now describes every workflow, built or planned, step by step, each with its diagram: results collection, daily prices, the company list and sectors, opening the app and reading results, the quarterly model update, start coverage, template onboarding, documents and grounded drafts, and events and alerts. Section 9.6 shows when each job runs; section 22.7 where the system runs today and the hosting plan. Every diagram marks what is built and running on real data and what is not yet. |
| Results history | NSE's financial-results list (owner-approved on 15 October 2026) adds results from March 2023 to the integrated filings, about 15 quarters and four years of annuals per company. Older files leave out their main contexts and are rejected, never half-stored; a broken file is retried once and then skipped (sections 3.1, 4.1, 9.3, 10.1). |
| Daily prices | NSE's bhavcopy, one file per trading day after the close (owner-approved on 17 October 2026): close, previous close, open, high, low, volume and a market cap from the latest results filing's share count. Only the latest day is kept (owner's rule, 18 October 2026). Shown on the company page and the Results desk (sections 3.3, 9.5, 19.1, 20). |
| Sectors | NSE's own taxonomy first: NSE Indices' lists set 22 NSE sector names, which outrank the LSEG groups from the Stocks data type; the LSEG group is kept in its own column (sections 4.2, 8.2). |
| Results watcher | One request every 2 hours (owner's choice, 16 October 2026). A schedule that follows SEBI's results seasons is proposed, backed by a check of when NSE shows filings and when companies file (sections 3.1, 9.6). |
| Web app | A welcome screen on the first visit of a session; share price and market cap on the company page; a market-cap column and sort on the desk; a scrolling filings box. Motion only on what is clicked (tab highlight, switches); data appears at once and stays fresh in the browser for five minutes (section 19.1). |
| Hosting | Oracle Cloud and Azure for Students could not be set up; the plan is a server in India (a VPS, or an always-on home machine with Cloudflare Tunnel), after a test that NSE serves its address (section 22.7). |
| Status and next steps | Section 26 updated for 18 October 2026. |

### What changed in 0.0.3

| **Change** | **Summary** |
|---|---|
| Where results come from | NSE's results RSS feed has been frozen since 24 August 2026: SEBI moved quarterly results into integrated filings. Results XBRL now comes from NSE's integrated-filing lookup, queried per company and once a day without a ticker for the latest results; the files still come from nsearchives. The owner amended the exchange-data rule on 14 October 2026 to allow exactly this (sections 3.1, 3.2, 9, 23). |
| How NSE limits requests | NSE stalls after about 590 requests whatever the pace (20 minutes at one request every 2 seconds, 50 at one every 5) and answers again after a pause of about 10 minutes. Requests identify as Analekh, with the contact in the From header, because NSE's CDN silently stalls a User-Agent that contains an email address or a URL (sections 3.1, 9.3). |
| History available | Integrated filings start with the March 2025 quarter (Q4 FY25): six quarters to June 2026 per basis, plus each new quarter as it is filed. Both bases (standalone and consolidated) are stored for every quarter (sections 4.1, 9.4). |
| Results formats | Banks (RBI format), general insurers and life insurers (IRDAI formats) have their own element tables, detected from the line items a filing tags, because integrated filings use one schema for every filer. NBFCs use the Ind-AS names. Validation identities have per-format terms (sections 10.1, 10.2, Appendix A). |
| Revised results | The value in use for each line of each quarter is the one from the most recently filed filing, whatever order the files were downloaded in; superseded values are kept as history. NSE's Original or Revision flag is stored. The company page labels refiled quarters Restated, Revised or Superseded, with a popup listing the numbers that changed (sections 8.3, 9.3, 10.2, 19.1). |
| Late filing rule | V8 follows SEBI's results deadlines (LODR 33(3)): 45 days for a quarter, 60 for the year end, plus one day's grace (section 10.2). |
| Web app | Home is a Results desk: who reported the quarter, revenue, profit and EBITDA margin against a year ago, movers and progress by sector. The company page gains a Consolidated or Standalone switch, a Latest quarter column with QoQ and YoY changes (margins in basis points), amounts in lakhs for companies under Rs 10 crore of revenue, and notes and tags that open on hover or tap (sections 19.1, 20). |
| Call recordings | Earnings calls can be transcribed locally from the recording (Whisper), since recordings appear within 24 hours and transcripts within five working days (section 11, Appendix G). |
| Status and next steps | Section 26 records what is built, what blocks each next phase and what to build next. |

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
| F2a | Show each results season at a glance (who reported, growth, movers, sectors) and each company's latest quarter with QoQ and YoY change. | 1 |
| F2b | Load each trading day's closing prices once after the close, with market cap; keep only the latest day. | 1 |
| F3 | Poll NSE RSS feeds on a schedule and keep a permanent history of feed items. | 1 |
| F4 | Fetch and parse results XBRL for every company that files, on both bases; store raw files once (hash dedupe); use the most recently filed value when a quarter is refiled. | 1 |
| F5 | Validate every filing with accounting identities and sanity rules; flag failures. | 1 |
| F6 | Backfill results for every company, resumably: integrated filings from the March 2025 quarter and NSE's financial-results list from March 2023; older periods on demand. | 1 |
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

Verified while scoping on 11 and 12 October 2026 and extended during the Phase 0 spike and the build (13 to 18 October 2026). These findings drive the main design choice: core numbers come from NSE's published XBRL files, found through its published feeds and one lookup the owner has approved, not from scraping or paid feeds.

#### 3.1 Findings

- **No free, official developer API exists for Indian company filings.** NSE has no public developer API.
- **NSE terms of use** prohibit "systematic or automated data collection" and "scraping, data mining, data extraction and data harvesting" (clause 9), and bar copying or redistributing content without written permission (clause 8).
- **NSE publishes official RSS feeds** at nsearchives.nseindia.com/content/RSS/, including Financial_Results.xml, Online_announcements.xml, Board_Meetings.xml, Corporate_action.xml, Insider_Trading.xml, Related_Party_Trans.xml, Voting_Results.xml and brsr.xml. Channel TTL is 5 minutes; each feed is a rolling window of recent items. Financial_Results.xml has carried no new filing since 24 August 2026 (below).
- **The Financial Results feed links directly to XBRL instance files.** A sampled file used the BSE Ind-AS taxonomy (prefix in-bse-fin) and contained the P&L for the quarter and the year to date, balance sheet instants and the full cash flow statement, with values in full INR.
- **Phase 0 (13 October 2026):** the results feed held two Ind-AS filings, both parsed, and their element names matched the vocabulary. The feed's pubDate is DD-Mon-YYYY HH:MM:SS. One filing gave different values for the same dates under two contexts (OneD and FourD). The SME list writes dates as DD-Mon-YY.
- **The results feed stopped carrying filings on 24 August 2026** (its last four items are Asian Hotels (West)). SEBI moved quarterly results into integrated filings; the Announcements feed links their PDFs, not their XBRL.
- **NSE's integrated-filing lookup** (www.nseindia.com/api/integrated-filing-results, the list behind its integrated-filing page) returns every integrated financials filing per company: quarter end, basis, NSE's Original or Revision flag, broadcast time, and links to the XBRL instance, an iXBRL web page and sometimes a results PDF, all on nsearchives. Without a ticker it lists the latest filings across all companies. It answers without the home page's cookies; the home page itself answers 403 to an honest Analekh User-Agent.
- **Integrated filings start with the March 2025 quarter** (Q4 FY25): six quarters up to June 2026 for a company that files every quarter, on each basis it files. Of the first 1,292 companies stored, 1,036 file both standalone and consolidated results and 255 standalone only. Integrated XBRL carries the quarter and the year to date, but not the prior-year comparison columns of the PDF.
- **Some companies have no integrated filings listed**, mostly SME and recently listed companies (216 of the first 1,500 or so checked), and about one attached results PDF link in three reads ".../corporate/null"; a few XBRL links answer 404.
- **Revisions are common.** Of the first 1,292 companies, 564 had filed at least one quarter more than once on the same basis (1,108 quarters); about 4% of the values in those refilings differed from the earlier filing. A company's first results after listing can cover a half-year only, with the quarter added later by a revision (Canara Robeco AMC).
- **NSE limits the number of requests, not their pace.** The lookup and the archive stop answering (the connection stalls; nothing is refused) after about 590 requests, whether they come every 2 seconds or every 5, and answer again after a pause of about 10 minutes. The CDN also stalls any request whose User-Agent contains an email address or a URL, so the contact goes in the From header.
- **Integrated filings use one schema for every filer** (in-capmkt-ent, with the Ind-AS element names), so the schema no longer tells banks and insurers apart; their line items do. Banks file the RBI format, general and life insurers IRDAI's formats.
- **NSE's financial-results list** (www.nseindia.com/api/corporates-financial-results; owner-approved on 15 October 2026) returns, per company in one request, every results filing back to 2005 with XBRL links from 2018: period, basis, audited flag, the filing time (filingDate, broadCastDate) and NSE's dissemination time (exchdisstime). TCS lists 26 quarters from September 2018 to December 2024, ICICI Bank 28; the list ends where integrated filings start. Files up to December 2022 (the _WEB.xml publications) and some early-2023 bank files leave out the quarter, year-to-date and balance-sheet contexts most values point to, so their basis and main figures can't be placed; complete files start in March 2023. A link of "-" means NSE has no XBRL for that row.
- **When NSE shows a filing, and when companies file** (checked on 18 October 2026 for 24 established companies through the two lookups): integrated filings appear a median of 1 second after the company files (94% within a minute, 299 filings; the slowest, Maruti's December 2025 quarter, after 23.5 hours, within the 24 hours SEBI allows after the board meeting's outcome); the older list showed a median of 3 minutes. Since 2023 every first filing of a quarter came between day 8 and day 59 after the quarter end, none after SEBI's deadline. 61% are filed between 16:00 and 21:00 IST and under 1% between midnight and 09:00.
- **NSE's request limit varies:** runs stalled after 565 to 590 requests most often, but also after 1,504 and 4,195; NSE always answered again after about 10 minutes.
- **NSE's daily bhavcopy** (nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip) is one zip per trading day with every traded security: trade date, ISIN, symbol, series, open, high, low, close, previous close and volume. The 16 October 2026 file matched 3,044 of Analekh's companies by ISIN. A day without a file (a holiday, or not yet published) answers 404.
- **NSE's own sector taxonomy** has four levels: 12 macro-economic sectors, 22 sectors, 58 industries and about 200 basic industries. Company-level values appear only on NSE's quote pages and their API, which answer 403 to honest requests (and to one browser-like test request the owner allowed once); NSE Indices' published lists carry the 22 sector names for their constituents.
- **BSE's results API** refuses automated requests and changes its address; about 250 companies with nothing on NSE file their results only with BSE.
- **NSE's corporate announcements list** (www.nseindia.com/api/corporate-announcements) can be filtered by subject, for example "Investor Presentation", and links each PDF on nsearchives: one request on 14 October 2026 returned 1,211 presentations from 1,046 companies for the previous three months, almost all from the June 2026 quarter's results season. It is not used; linking each quarter's presentation is a proposal that needs the owner's approval (section 28).
- **The Announcements feed links to PDFs** (presentations, orders, management changes) with company, subject and summary; it holds only about 12 hours of items.
- **NSE publishes its equity list** as a CSV (EQUITY_L.csv) with columns SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE. It has no sector or industry column. SME companies are listed separately.
- **NSE Indices publishes index constituent lists** as CSVs on niftyindices.com (/IndexConstituent/), with an industry for each constituent. Eleven broad lists (Total Market, SME Emerge, IPO, Microcap 250, Smallcap 500 and others) plus the bank indices give NSE sector names for 1,430 companies (16 October 2026); a list that answers with an HTML page instead of a CSV is reported, not read.
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
| Sector | NSE Indices constituent lists (NSE's 22 sector names), then the Excel Stocks data type (LSEG industry group via Microsoft 365); a user override wins | Curated map; company disclosures | Precedence recorded per company; the LSEG group kept separately (section 4.2) |
| Results numbers | NSE integrated-filing lookup to XBRL: per company, plus one request every 2 hours for the latest filings | BSE results feed (paid) | Structured; no AI needed for core statements. The results RSS feed has been frozen since 24 August 2026 |
| Presentations, transcripts, annual reports | NSE Online_announcements RSS to PDF; company IR pages | BSE announcements feed (paid) | AI extraction on selected pages |
| Results calendar and events | Board_Meetings, Corporate_action, Insider_Trading, Related_Party_Trans RSS | None free | Alerts and red flags |
| Historical backfill | Integrated-filing lookup (from the March 2025 quarter) and NSE's financial-results list (complete XBRL from March 2023), per company; company IR pages or the import folder for older periods | Licensed data | About 15 quarters and four years of annuals per company |
| Prices and market cap | NSE's daily bhavcopy, one file per trading day after the close; market cap from the latest results filing's share count | Excel Stocks data type in the analyst's own workbook; Kite Connect (paid, not used) | End of day only; only the latest day kept (section 3.3) |
| Embeddings for search | Hosted embedding API or local open-source model |  | Anthropic does not offer an embeddings model |

Design rule: poll published RSS feeds at their stated refresh interval and fetch the files they link to. NSE Indices' constituent CSVs are fetched the same way, and the HTTP client allows only the /IndexConstituent/ path on that host. On www.nseindia.com the client allows only the home page, /api/integrated-filing-results (approved by the owner on 14 October 2026, because the results feed stopped carrying filings) and /api/corporates-financial-results (approved on 15 October 2026, for history before integrated filings): both queried per company, plus one request every 2 hours without a ticker for the latest results. On nsearchives, besides the files the lookups link to, ONE bhavcopy per trading day after the close (approved on 17 October 2026; no price history, no live prices). Requests always identify as Analekh and are never disguised as a browser; widening the allow-list needs the owner's approval. No other NSE internal endpoint is called and no exchange page is crawled. Obtain written confirmation from NSE (nsewebmaster@nse.co.in) or license a feed before any public or commercial release.

#### 3.3 Prices

Prices feed market cap, comps, the profile slide and valuation pages. Decided on 17 October 2026: end of day only, from NSE's bhavcopy; no live feed (no budget for one) and no price history.

- **Source.** NSE's daily bhavcopy (section 3.1): ONE file per trading day, fetched after the close (analekh prices; section 9.5). Equity series only (EQ, BE, BZ on the main board; SM, ST, SZ on SME), one row per ISIN, the main series first.
- **What is stored.** For each company the file matches by ISIN: trade date, open, high, low, close, previous close and volume, and a market cap: the close times the shares in issue, worked out as paid-up equity capital from the results filings divided by the face value in NSE's equity list. Filed face values are unreliable (tagged as 0, as the capital itself, or from before a split), and some filers tag paid-up capital 1,000 to 1,00,000 times too large, so: when the latest quarter and the one before differ by more than 50 times, the smaller is used; capital above 100 times total assets is ignored (Ind-AS and banks); a market cap above Rs 30 lakh crore is not shown. The results watcher recomputes market caps when new filings arrive (analekh prices --recompute does it by hand). On 16 October 2026, 3,044 companies matched and 2,624 had a market cap; Reliance came to Rs 16,39,117 crore.
- **Only the latest day** (owner's rule, 18 October 2026). Each new file replaces the previous day's prices; the day's change comes from the previous close in the same file. A company missing from the day's file (suspended, not traded) has no price rather than a stale one. An older day is never loaded over a newer one.
- **In Excel.** An analyst's workbook can still show a delayed price with the Stocks data type (=FIELDVALUE(cell,"Price")) on Microsoft 365; it stays in that workbook.
- **Not used:** Kite Connect (INR 2,000 a month), live quotes, and any NSE website page or internal API.

## 4. Company universe and coverage levels

Version 0.0.0 required each company to be added before anything happened. That was wrong: knowing a company exists and covering it deeply are different things. 0.0.1 separates them into three levels.

| **Level** | **What happens** | **Cost and trigger** |
|---|---|---|
| 1. Universe | Every NSE-listed company preloaded from EQUITY_L.csv and the SME list; new listings and delistings picked up weekly. | Free; automatic |
| 2. Numbers for everyone | Every results filing NSE lists is parsed and validated, for every company that files, from March 2023; closing prices daily. | Local parsing only; automatic |
| 3. Deep coverage | AI extraction of presentations and transcripts, model updates, Coverage Builder, reports, alerts. | AI and compute cost; watchlist or one-click Analyse on any company |

#### 4.1 History

- **Integrated filings** (from the March 2025 quarter) come through the integrated-filing lookup; **March 2023 to December 2024** through NSE's financial-results list. Together they give about 15 quarters and four years of annuals (FY23 to FY26) per company, on each basis it files. 1,567 companies had 14 or more quarters on 18 October 2026.
- **Full backfill:** analekh results-backfill fetches every company with a sector, one company per transaction, both bases; --history reads the financial-results list instead, by sector (--sector). Runs resume at the company they stopped on, skip companies listed as having no filings, and run at one request every 2 seconds, waiting 10 minutes each time NSE stops answering (section 9.4). The integrated backfill finished on 15 October 2026 and the history backfill on 17 October 2026.
- **Older periods:** files before March 2023 leave out their main contexts and are rejected (section 10.1). Rebuilding the missing contexts from the files' declared dates was considered and declined: it would match contexts by id, against the parsing rule. Older periods come from the company's IR site or the import folder, on demand.

#### 4.2 Sector classification

Neither the equity list nor the results XBRL carries a sector, and sector picks templates and peers. Three sources, in order of precedence (owner's choice on 16 October 2026: NSE's own taxonomy first); a lower source never overwrites a higher one, and companies.sector_source records which one set each sector:

- **User override** per company (the editing screen is still to be built).
- **NSE Indices constituent lists** (eleven broad lists and the bank indices), fetched by analekh universe sectors: NSE's 22 sector names. Older uppercase labels some lists still carry are ignored.
- **Excel's Stocks data type:** start from BSE's List of Securities, convert XBOM:<BSE code> IDs to the Stocks data type in Microsoft 365 and fill an Industry column (=FIELDVALUE(B2,"Industry")); analekh universe sectors --stocks-file imports the workbook by ISIN. It gives LSEG industry groups for dual-listed companies; SME companies are not on BSE's list. The LSEG group is always stored in companies.sector_lseg, and becomes the sector only where nothing better exists.

On 18 October 2026: 1,430 companies had an NSE sector, 1,587 an LSEG group only and 169 none. A mapping from LSEG groups to NSE sector names (28 clear groups covering 973 companies, 25 groups and 614 companies to decide) waits for the owner. NSE's basic industries can't be read: they appear only on NSE's quote pages, which refuse honest requests.

The results taxonomy (indas, banking, nbfc, insurance or life_insurance) is first guessed only on strong signals: membership of a bank index, or an NSE Indices industry that names NBFCs or insurance. LSEG groups never set it, because LSEG's Banking Services group includes NBFCs. The line items a filing tags then decide it, and correct an earlier guess (section 10.1).

#### 4.3 Limit

BSE-only companies (not listed on NSE) are not in NSE's feeds and BSE does not publish a free RSS equivalent. v1 covers every NSE-listed company, including dual-listed ones; BSE-only coverage would need a licensed BSE feed.

## 5. System architecture

Six layers read left to right: sources, ingestion, processing, core data, engines and interfaces. The Claude API is an external service used by the document pipeline and the engines.

*Figure 1. Components and data flow (v0.0.1). Solid lines carry data, dashed lines are control or return paths, amber lines are the analyst approval path, dotted blue lines are Claude API calls. Amber-bordered engines are the two that write to Excel. Updated in 0.0.2: Kite Connect and the Price Fetcher's live quotes are superseded (the price source is undecided, section 3.3), and sectors also come from the Stocks data type and NSE Indices (section 4.2). Updated in 0.0.3: results XBRL comes from NSE's integrated-filing lookup instead of the results feed, the Results Fetcher runs per company and once a day, validation decides which of several filings of a quarter is in use, and the Results desk and Latest quarter views read the latest values (sections 3.1, 9, 10, 19.1). Updated in 0.0.4: the financial-results list adds history from March 2023, the bhavcopy feeds the prices table with the latest close only, sectors follow NSE's taxonomy first, the watcher runs every 2 hours, and dashed boxes mark components whose core is built but which do not run on real data yet.*

#### 5.1 Layers and components

| **Layer** | **Component** | **Responsibility** |
|---|---|---|
| Sources | NSE integrated-filing lookup | Every integrated financials filing per company (quarter, basis, Original or Revision, links to XBRL, iXBRL and PDF); the latest filings across all companies without a ticker. |
| Sources | NSE financial-results list | Every results filing per company back to 2005; complete XBRL from March 2023 (history before integrated filings). |
| Sources | NSE RSS feeds | Announcements (PDF), board meetings and event feeds. The results feed has carried nothing since 24 August 2026. |
| Sources | NSE equity list | Every listed company, refreshed weekly. |
| Sources | Sector sources | NSE Indices constituent lists and the Excel Stocks data type workbook import (section 4.2). |
| Sources | Company IR pages | Fallback for missing documents and historical backfill. |
| Sources | NSE bhavcopy | One file per trading day after the close: every traded security's prices (section 3.3). |
| Ingestion | Scheduler | Triggers the results watcher every 2 hours, the price download after the close on weekdays, the weekly universe refresh and (planned) feed polling every 5 to 60 minutes. Locally, Windows scheduled tasks stand in for Celery beat (section 9.6). |
| Ingestion | Feed Watcher | Fetches feeds for all companies, dedupes items, stores them permanently, links items to companies. |
| Ingestion | Results Fetcher | Reads the integrated-filing lookup per company (refresh, backfill) and every 2 hours without a ticker, and the financial-results list per company for history; downloads each XBRL file once, hashes it, stores it in MinIO, with NSE's revision flag and source links. |
| Ingestion | Filing Fetcher | Downloads announcement PDFs once, hashes them, stores them in MinIO. |
| Ingestion | Universe Loader | Loads and refreshes the company universe; assigns sector by source precedence and the results taxonomy from strong signals (section 4.2). |
| Ingestion | Price Fetcher | Downloads the day's bhavcopy once, matches companies by ISIN, works out market cap from the latest filing's share count and replaces the previous day's prices (section 9.5). |
| Processing | Raw Filing Store | Immutable object storage keyed by hash. |
| Processing | XBRL Parser | Turns every filer's XBRL into normalised facts; detects the results format (Ind-AS, bank, general or life insurer) from the line items; no AI. |
| Processing | Document Pipeline | For watchlist or on-demand companies: reads PDFs locally, classifies pages, sends selected pages to Claude, stores KPIs and text chunks. |
| Processing | Validation | Accounting identities with per-format terms, period checks, SEBI deadlines, swing flags, AI versus XBRL conflicts. Decides which filing's value of each line is in use: the most recently filed. |
| Core data | PostgreSQL + pgvector | Companies, watchlist, filings, facts, KPIs, documents, prices, templates, models, versions, assumptions, change sets. |
| Engines | Model Sync Engine | Uses the workbook understanding engine to update linked models: mapping, write plan, dependency scan, roll-forward, change sets, versioned saves. |
| Engines | Analysis + GenAI Engine | Results flash, variance bridge, call digest, red flags, initiation draft, Q&A with citations. |
| Engines | Coverage Builder | Builds new models from sector templates with sourced history and proposed assumptions. |
| Engines | IB Output Engine | Comps, company profile slide, tagged pitch page refresh. |
| Interfaces | Excel | Bridge that finds and links models (xlwings now; Office.js add-in later). |
| Engines | Results views | Results desk (the quarter's reporters, YoY changes, market cap, movers, sector progress) and each company's latest quarter at a glance (QoQ and YoY, derived lines, revision status) and last close, read from the latest values. |
| Interfaces | Web App | Welcome screen, Results desk, search, company pages, review queue, templates, reports, Q&A, comps. |
| Interfaces | Word and PowerPoint | Notes, initiation drafts, slides. |
| Interfaces | Alerts | Email or Telegram for watchlist events. |

## 6. Workflows

Nine workflows, each with its data flow. The first four are built and run on real data; the rest have working cores with synthetic tests, or are planned. In every diagram solid boxes are built and running, dashed boxes are not running yet, grey boxes are external sources and amber marks the analyst's approval.

### 6.1 Results collection (built)

*Figure 2. Results collection: four triggers, two NSE lookups, one pipeline (sections 9.3, 9.4, 10).*

1. **A trigger starts a run:** the results watcher (one request without a ticker, every 2 hours, for the latest 500 filings), a refresh of one company (analekh refresh, or the API), the backfill of every company with a sector, or the history backfill (--history, by sector).
2. **The lookup answers:** the integrated-filing lookup for the watcher, refreshes and the backfill; NSE's financial-results list for history. Each row gives the quarter end, basis, NSE's Original or Revision flag, the filing time and links.
3. **Files to fetch are chosen:** links of "-", null or undefined are no links; _WEB.xml files are never fetched; files already stored are skipped. Originals come before revisions, oldest first.
4. **Each XBRL file is downloaded once** from nsearchives through the polite client (host and path allow-list, honest headers, one request every 2 seconds in bulk). A refusal or a stall stops the run at once.
5. **The file is hashed and stored** in MinIO at kind/yyyy/mm/sha256.xml; a file with a known hash is skipped.
6. **A guard checks it:** a file whose main contexts are missing is rejected and noted (never half-stored); broken XML is fetched once more, then skipped and noted.
7. **The parser** reads the facts, resolving contexts by their dates, and decides the results format from the line items.
8. **Validation** runs V1 to V10 with the format's own terms and sets the block flag on failure.
9. **Facts are inserted as history** and the newest filed value of each line becomes the one in use, whatever order files arrived in; refiled quarters get a revision status and the list of what changed.
10. **One transaction per company:** a stopped run keeps what it stored. When NSE stops answering, the watchdog waits 10 minutes and resumes at the company it stopped on. Each company's outcome is one JSON line in the run log.

### 6.2 Daily closing prices (built)

*Figure 3. Daily prices: one bhavcopy per trading day, the latest close only (sections 3.3, 9.5).*

1. **The job runs** on weekdays from 19:00 to 23:00 IST, hourly, until the day is stored (analekh prices).
2. **It picks the trading day:** today after 18:00 IST, otherwise the day before; weekends roll back to Friday.
3. **It skips** if that day, or a later one, is already stored; no request is made.
4. **ONE request** fetches the bhavcopy from nsearchives; 404 means a holiday or not published yet.
5. **The file is parsed:** equity series only, one row per ISIN, the main series first.
6. **Companies are matched by ISIN**; shares in issue are paid-up equity capital from the results filings divided by the face value in NSE's equity list (with the guards above) and market cap is the close times the shares.
7. **Today's rows are upserted and every older day deleted:** the table holds one day, about 3,000 rows.
8. **Read by** GET /companies/{symbol}/price, the company page's share price and market cap tiles, the desk's market-cap column and sort, and the comps export; the AI's get_prices tool will use it in Phase 4.

### 6.3 Company list and sectors (built)

*Figure 4. Company list and sectors: the universe weekly, sectors by precedence, the results format from the filings (sections 4, 9.1).*

1. **The universe loader** reads NSE's equity and SME lists weekly, upserts companies by ISIN and marks companies missing from the lists inactive.
2. **Sectors are imported by precedence** (analekh universe sectors): a user's value, then NSE Indices' lists (NSE's 22 sector names), then the LSEG group from a Stocks data type workbook. A lower source never overwrites a higher one; the LSEG group is always kept in sector_lseg.
3. **The results format is guessed** only from strong signals (bank indices, NBFC and insurer industries); the line items of the company's filings then decide it.
4. **The web app downloads the whole universe once** (GET /companies/index, with ETag and gzip) and searches it in the browser.
5. **Companies with a sector** are the desk's and the backfill's scope.
6. **Planned:** the mapping of LSEG groups to NSE sector names (owner's decision) and a sector editing screen.

### 6.4 Opening Analekh and reading results (built)

*Figure 5. Opening Analekh: the welcome screen, then the desk and company pages, over the read models (sections 19.1, 20).*

1. **The first visit of a browser session** to the home page shows the welcome screen with live counts (companies tracked, results filings, reporters this quarter). A link to any other page goes straight there.
2. **A scroll, swipe or tap unlocks it:** the mark flies to the sidebar and the Results desk settles in.
3. **The desk** (GET /desk) lists the quarter's reporters ten per page, newest filing or largest market cap first, with filters for quarter, sector, watchlist and filing date in the URL; movers and sector progress beside it.
4. **Search** ranks the universe in the browser; the server answers only before it loads and as a typo fallback.
5. **The company page** reads the company, its filings, facts by logical name, the latest quarter at a glance and the last close; a Consolidated or Standalone switch sits in the URL.
6. **Data stays fresh in the browser for five minutes,** so moving between tabs shows it at once. Motion is only on what is clicked: the sidebar highlight and the switches' thumbs glide; figures and screens appear immediately.

### 6.5 Quarterly model update (planned, Phase 2)

*Figure 6. Quarterly update. Steps 6 and 7 form the approval gate.*

1. **Search ticker** in the web app or Excel; the company is already in the universe.
2. **Newest filing?** The database returns the latest results filing for that company (collected automatically for every filer by workflow 6.1).
3. **Fetch if missing:** if the file was not yet fetched, it is downloaded, parsed and validated.
4. **Validated facts** are stored with source references.
5. **New-period facts plus the linked model** go to Model Sync. The model is located by discovery (section 13).
6. **Change set:** proposed writes, dependent-cell counts, roll-forwards and suggested assumption changes.
7. **Approve or edit** each item; nothing is written before this.
8. **Apply:** write, recalculate, save a new version; compute actuals versus estimates.
9. **Outputs:** flash, draft note, slides, with citations.

### 6.6 Start coverage (planned, Phase 2)

*Figure 7. Start coverage with the Coverage Builder. Steps 6 and 7 form the approval gate.*

1. **Start coverage** on any company and pick a template (the analyst's upload for that sector, or a built-in one).
2. **Build request** goes to the Coverage Builder.
3. **History and KPIs** are pulled from the database; anything missing is backfilled and run through the document pipeline.
4. **Sourced actuals** return with references.
5. **Propose drivers:** the GenAI engine suggests first-pass assumptions from history and management guidance.
6. **Assumptions with citations** are shown to the analyst.
7. **Accept or edit** each assumption.
8. **Tagged model** is written to Excel; checks must pass.
9. **Initiation draft, comps and slides** are generated. From the next results the quarterly update takes over.

### 6.7 Template onboarding (planned, Phase 2)

*Figure 8. Template onboarding: read, suggest, confirm once, test build.*

1. **Upload a workbook** (blank template or a model for another company) and tag it with sectors.
2. **The workbook understanding engine** reads its structure: periods, inputs versus formulas, labels, drivers, checks and the formula graph (section 12).
3. **A mapping is suggested** with a confidence per row: synonyms first, then fuzzy matching, then a small Claude model for labels neither can place.
4. **The analyst confirms or fixes the mapping** once per template.
5. **A test build** with one real company fills and recalculates the template.
6. **The test report** lists checks, blank rows, unmapped facts and broken formulas; a failure goes back to the mapping.
7. **On a pass the template becomes active**, versioned, for the Coverage Builder and Model Sync.

### 6.8 Documents, KPIs and grounded drafts (planned, Phases 3 and 4)

*Figure 9. Documents to KPIs, and drafts that only use numbers from the data (sections 11, 17).*

1. **Documents arrive** from the announcements feed (PDFs), company IR pages or the import folder; call recordings are transcribed locally.
2. **Each file is fetched once** and hashed into MinIO; only watchlist or on-demand companies' documents are read further.
3. **Pages are read locally** (PyMuPDF, Tesseract for scans) and classified; only the top pages per category are selected.
4. **Claude extracts** KPIs, guidance and red flags against a JSON schema, each value with its page, quote and confidence.
5. **V10 compares** them with XBRL: XBRL wins and the AI value is flagged.
6. **KPIs and text chunks** (with embeddings) are stored for search and Q&A.
7. **A report or question** runs a tool loop: Claude calls tools for facts, KPIs, prices, filings and the model, and calc for all arithmetic.
8. **A grounding check** blocks any number that did not come from a tool result or calc.
9. **The draft** is delivered as Word, PowerPoint or a web page, with citations and no ratings or targets.

### 6.9 Events, results calendar and alerts (planned, Phases 1 and 5)

*Figure 10. Events from NSE's published feeds: results calendar, red flags and alerts (sections 9.2, 26.2).*

1. **The feed watcher polls** NSE's Board Meetings, corporate actions, insider trading, related-party and announcements feeds at their stated intervals (5 to 60 minutes) and keeps every item.
2. **Items are linked to companies** by name, symbol or ISIN; unmatched items wait for review.
3. **Board meeting intimations** (at least two working days ahead, SEBI LODR 29) build the results calendar: who reports this week on the desk, and the days the results watcher should poll.
4. **Red flags** (pledges, insider trades, related-party deals, auditor changes) are picked out.
5. **Watchlist companies** get alerts, by email or Telegram, when they file results (workflow 6.1) or a red flag appears.

### 6.10 Exceptions

| **Situation** | **Handling** |
|---|---|
| Filing not listed by NSE (old or missed) | IR-page fallback or import folder. |
| Restated or refiled period | Both versions kept; the most recently filed is in use, whatever order the files arrived in; the company page tags the quarter Restated or Revised and lists what changed. |
| File missing its main contexts (most files before March 2023) | Rejected and noted, never half-stored. |
| Broken XBRL file (XML cut off) | Fetched once more, then skipped and noted; the company's other filings are kept. |
| NSE stops answering partway | The run stops at once; the watchdog resumes 10 minutes later at the company it stopped on. |
| Year-ago quarter never filed on its own (first results after listing covered a half-year) | YoY shown as a dash with a note saying why. |
| No bhavcopy for the day (holiday, not published yet) | Nothing stored; the next hourly run tries again. |
| Company missing from the day's bhavcopy | No price shown rather than a stale one. |
| No share count in a company's filings | Close shown, market cap left blank with a note. |
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
| Sectors | NSE Indices constituent lists; Stocks data type workbook import | companies (sector, sector_source, sector_lseg) |
| Results numbers (all filers) | Integrated-filing lookup to XBRL: per company on refresh and backfill, every 2 hours for the latest filings; the financial-results list for history | filings, facts |
| Presentations, annual reports, transcripts | Online_announcements RSS to PDF; IR pages fallback | filings, documents, chunks, kpis |
| Events | Board meeting, corporate action, insider, related party feeds | feed_items, alerts |
| Prices | NSE's daily bhavcopy, once per trading day after the close (section 3.3) | prices (latest day only) |
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
| companies | Whole NSE universe: nse_symbol, isin, name, series, listing_date, face_value, sector, industry, sector_source, sector_lseg (the LSEG group, kept whatever sets the sector), results_taxonomy, is_sme, is_active, source, refreshed_at. |
| watchlist | user_id, company_id, added_at, settings (alerts, auto-analyse). Replaces is_tracked. |
| feed_items | Every RSS item: feed, item_key, title, link, description, pub_date, company_id, processed_at. |
| filings | company_id, kind, period_start, period_end, period_type, consolidated, audited, source_url, file_sha256, storage_key, filed_at, status, meta (validation report, source links, NSE's revision flag: Original or Revision). |
| facts | Normalised XBRL facts: element, period, instant flag, consolidated, value NUMERIC, unit, context, dimensions, is_latest (true for the value from the most recently filed filing of that line). |
| kpis | AI or table-extracted metrics with page, quote, confidence, method, verified. |
| documents, chunks | PDF metadata; text chunks with embeddings and full-text search. |
| prices | The latest trading day only: open, high, low, close, previous close, volume and market cap per company (section 3.3). |
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
| job_status | When each scheduled job (results_watch, prices) last ran and last did its work, for Settings (migration 0006). |

#### 8.3 Indexes and constraints

- companies: unique nse_symbol and isin; check constraints on results_taxonomy and sector_source; trigram index on name, used when ranked search finds nothing (section 19.1).
- facts: (company_id, element, period_end) partial index where is_latest.
- filings: (company_id, period_end DESC); unique file_sha256.
- feed_items: unique (feed, item_key); index on pub_date.
- models: unique doc_tag.
- chunks: HNSW on embedding; GIN on full-text column.
- A refiled period inserts its facts and is_latest is re-decided for the company: for each line (element, dates, basis, dimensions) the value from the most recently filed filing wins, and a filing without a date counts as the oldest. Nothing is deleted; superseded values are history.

## 9. Ingestion layer

#### 9.1 Universe loader

- Downloads EQUITY_L.csv and the SME list weekly; upserts by ISIN; marks companies missing from the list as inactive. Listing dates come as DD-Mon-YYYY (main board) or DD-Mon-YY (SME).
- Sector comes from the sources in section 4.2, in order of precedence (analekh universe sectors): NSE Indices' lists outrank the Stocks data type import, and the LSEG group is kept in sector_lseg. results_taxonomy is guessed from strong signals only, and the filings' line items decide it.

#### 9.2 Feed polling

- Feeds: Financial_Results, Online_announcements, Board_Meetings, Corporate_action, Insider_Trading, Related_Party_Trans, Sast_ReasonForEncumbrance. Financial_Results has carried nothing since 24 August 2026; results come from the integrated-filing lookup (section 9.3).
- Interval: 5 minutes (published TTL) for results and announcements; 15 to 60 minutes for event feeds.
- Conditional requests where supported, descriptive User-Agent, timeouts, exponential backoff.
- Item key = SHA-256 of link plus pubDate; upsert on (feed, item_key).
- pubDate arrives as DD-Mon-YYYY HH:MM:SS (India time), not the RFC 822 form; it must be parsed in that format or V8 cannot run.
- Company linking by normalised name, then symbol or ISIN when present; unmatched items queued for review.
- Announcement PDFs are fetched for every company (cheap) but only processed by the document pipeline for watchlist or on-demand companies.

#### 9.3 Fetching and storage

- **Results:** the integrated-filing lookup (type "Integrated Filing- Financials", index equity or sme, pages of 50) lists a company's filings; each XBRL file not yet stored is downloaded, oldest first, original before revision. A link ending in null, undefined or none is no link; a file NSE lists but answers 404 or 410 for is skipped and noted, not fatal.
- **Results history:** NSE's financial-results list (one request per company) lists results back to 2005; only rows from March 2023 with a real XBRL link are fetched (section 4.1).
- **Results watcher** (watch_results, every 2 hours since 16 October 2026): ONE request to the lookup without a ticker (a page of 500), then the XBRL for every filing not yet stored. If every row is new, it logs a warning instead of asking for a second page. Section 9.6 proposes a schedule that follows the results seasons.
- **Guard:** a file whose main contexts are missing is rejected before it is stored (pipeline.IncompleteXbrl); broken XML is fetched once more, then skipped and noted like a 404.
- Each file downloaded once; SHA-256 computed; stored at kind/yyyy/mm/sha256.ext. Same hash: skip. Same period with a different hash: a revision, and the most recently filed value of each line is used (section 8.3).
- Requests identify as Analekh: User-Agent "Analekh/0.1", the contact in the From header (CONTACT_EMAIL), Accept and Referer headers. The client allows only listed hosts and, on www.nseindia.com and niftyindices.com, listed paths.
- Rate limited (default 1 request per second; the bulk backfill runs at one every 2 seconds) with retries. A 401, 403 or 429, a timeout or a stall stops a run at once instead of retrying into a block.

#### 9.4 Backfill

- **Results, every company:** analekh results-backfill fetches the integrated filings of every company with a sector (newest eight quarter ends by default, both bases), one company per transaction so a stopped run keeps what it stored. With --history it reads the financial-results list instead (quarters from March 2023), optionally one sector at a time (--sector, repeatable). Options: --start-at resumes at a ticker (the company a run stopped on had its transaction rolled back, so it is fetched again in full); companies listed in out/bulk/no-filings.csv as having nothing on NSE are skipped unless --recheck-no-filings is given; --symbols, --limit, --quarters, --one-basis and --interval narrow it. Each company's outcome is logged as one JSON line.
- **Unattended runs:** a local watchdog script restarts the backfill 10 minutes after each NSE stop, at the company it stopped on, keeps a tracker file up to date, and backs off for longer (1, 2 and 3 hours) if NSE stalls after only a few requests several times in a row, which would mean a block rather than the usual limit. Both full backfills have finished: integrated filings on 15 October 2026, history on 17 October 2026.
- **Older periods:** on demand when a company is first analysed in depth (3 to 5 years), from IR sites or the import folder, through the same parser and validation path; AI extraction for backfills uses the Batch API.
- After the element tables or the rules change, analekh revalidate re-reads stored files and analekh recompute-latest re-decides the values in use; neither downloads anything.

#### 9.5 Daily prices

- analekh prices (Celery task fetch_prices, beat entry fetch-prices; PRICES_CRON=0 19-23 * * 1-5) loads the latest trading day's bhavcopy: today after 18:00 IST, otherwise the day before, weekends rolled back to Friday; --date loads a given day.
- A day already stored, or older than the stored day, is skipped without a request. A 404 means a holiday or not published yet; the next hourly run tries again.
- Rows are parsed (equity series only, one per ISIN), matched to companies by ISIN, given a market cap from the latest filing's share count, upserted, and every older day is deleted in the same transaction (section 3.3).

#### 9.6 When each job runs

*Figure 11. The year's results seasons and each job's schedule, now and proposed, with the hours companies file.*

| **Job** | **Now** | **Proposed or planned** |
|---|---|---|
| Results watcher | One request every 2 hours, all year (a Windows scheduled task until the scheduler is deployed) | Every 2 hours from 09:00 to 23:00 IST during the four results seasons, once a day at 21:00 otherwise |
| Daily prices | Weekdays, hourly from 19:00 to 23:00 IST until the day is stored | Unchanged |
| Universe refresh | Weekly, Monday 06:00 | Unchanged |
| Feed watcher | Not running | Every 5 to 60 minutes, by feed (workflow 6.9) |
| Backfills | By hand, with the watchdog | Unchanged; new listings through the watcher |

**Results seasons.** SEBI requires quarterly results within 45 days of the quarter end and the year's results within 60 days (LODR 33). The proposed windows run from day 5 to two days past each deadline, so last-day filers' XBRL, which can follow the board meeting by up to 24 hours, is still caught:

| **Season** | **Quarter ends** | **Deadline** | **Window** |
|---|---|---|---|
| Q1 | 30 June | 14 August | 5 July to 16 August |
| Q2 (and SME first half) | 30 September | 14 November | 5 October to 16 November |
| Q3 | 31 December | 14 February | 5 January to 16 February |
| Q4 and the year (and SME second half) | 31 March | 30 May | 5 April to 1 June |

The check in section 3.1 supports it: NSE shows a filing about a second after it is filed, so any delay is the watcher's interval; since 2023 every first filing of the 24 companies sampled fell inside these windows; and under 1% of filings come between midnight and 09:00. The proposed schedule makes about 1,650 requests a year instead of about 4,400. Smaller companies file late more often, which the daily off-season run covers, as it does revisions. Later, the results calendar (workflow 6.9) can narrow polling to the days board meetings are announced for.

## 10. XBRL parsing and validation

#### 10.1 Parsing

- Arelle for full taxonomy support; lxml for fast extraction from plain instance files.
- Contexts resolved from actual start and end dates (duration for quarter and year to date; instant for balance sheet), never from context names.
- Values stored in full INR; display transforms (for example INR crore) live in mappings.
- Consolidated and standalone stored separately; mappings choose the basis.
- Dimensions stored in JSONB and hashed into the uniqueness key.
- Element names form a fixed vocabulary, so mapping to models is configuration, not AI. Integrated filings use the in-capmkt taxonomy with the Ind-AS names; typed dimensions are read from their child element.
- **Results format from the line items:** a filing that tags RevenueFromOperations is Ind-AS (NBFCs included, though they also tag InterestEarned); InterestEarned and InterestExpended without it mark a bank; GrossPremiumIncome, NetPremiumIncome or persistency ratios mark a life insurer; PremiumEarned or premiums written mark a general insurer. Each format has its own element table (banks: interest earned as the top line, provisions; general insurers: premium earned, operating profit through the shareholders' account; life insurers: net premium income, solvency, persistency, expenses of management).
- When two contexts carry the same dates but different values (seen in Phase 0: OneD and FourD), the parser keeps the first for now; how to flag the conflict is an open question (section 28).
- **Incomplete files are rejected:** a file whose main contexts (the quarter, year to date and balance sheet date) are not defined, and which has no metadata to place them, raises IncompleteXbrl before it is stored. Most files before March 2023 are like this.

#### 10.2 Validation rules

| **ID** | **Rule** | **On failure** |
|---|---|---|
| V1 | Revenue from operations plus other income equals total income (insurers add investment income; life insurers also the transfer from the shareholders' account). | Flag; block auto-apply |
| V2 | Profit before tax equals total income less total expenses, plus exceptional items as tagged (a charge is negative). Banks deduct provisions; general insurers go through the shareholders' account and deduct any transfer to reserves (seen at GIC Re); for life insurers PBT is the shareholders' account income less its expenses. | Flag; block auto-apply |
| V3 | Profit after tax equals profit before tax less tax. | Flag |
| V4 | Total assets equal equity plus liabilities for each instant. | Flag; block auto-apply |
| V5 | Quarter equals year to date less prior year to date where both exist. | Flag |
| V6 | Context dates agree with the declared reporting period. | Use declared period; warn |
| V7 | Quarter-on-quarter change above 50% in revenue or profit. | Highlight |
| V8 | Filed after SEBI's results deadline (LODR 33(3)): 45 days after a quarter (or an SME half-year), 60 days when the filing closes the financial year, plus one day's grace for the XBRL; filing date in IST. | Label late |
| V9 | Same period refiled with different values. | Keep both; the most recently filed is in use; tag the quarter and show what changed |
| V10 | AI value conflicts with XBRL for the same item. | XBRL wins; AI value flagged |

Insurers' balance sheets are not mapped yet, so V4 skips for them. A filing where an identity's elements are not tagged records the rule as skipped.

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

**Call recordings.** Companies post the call's audio within 24 hours but the transcript only within five working days (SEBI LODR). analekh transcribe-audio turns recordings placed in the import folder into timestamped text locally (Whisper large-v3 through faster-whisper, on the GPU when there is one; optional dependency group audio). Notes are generated from this text first and regenerated from the official transcript once it is filed, so each quarter's call highlights are written once and updated only when a new quarter's results and call arrive. Future scope (section 26.3): a listener that joins the call as it happens and transcribes it live, marked unverified, until the filed recording replaces it; Workflow 8 in the architecture diagrams shows where it fits.

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
| get_prices(company, from, to) | The latest close and market cap (section 3.3); only the latest trading day is stored. |
| calc(expression, inputs) | Deterministic arithmetic in Python. |

#### 17.2 Grounding rules

- Only numbers returned by tools or computed by calc may appear in output.
- A post-check matches every number in the text to tool results; any unmatched number blocks the output.
- Each claim carries a citation; prompt caching for long system prompts; tokens logged in llm_calls.

## 18. IB Output Engine

- **Comps:** saved peer lists (up to 30 companies each) and suggested peers (same NSE sector and results format, closest in market cap, the same LSEG group first); price, market cap, TTM revenue, revenue YoY, EBITDA and net margins, P/E and P/B, with median and mean; Excel export. TTM is the last four quarters back to back on one basis (consolidated when four exist, else standalone; the row says which). EBITDA is derived as on the company page and left out for lenders and insurers. Book value is the latest balance sheet's equity attributable to owners (capital plus reserves for banks; not yet for insurers). EV = market cap + debt − cash, shown only once debt and cash are sourced: until then EV multiples are blank, never market cap passed off as EV. A symbol that has left the universe is reported, not fatal.
- **Company profile slide:** business summary, shareholding, key financials, valuation, recent events. No price chart: only the latest close is kept.
- **Pitch page refresh:** placeholders such as {{MUTHOOTFIN.pat_q}} replaced with current values plus a change log.
- **Precedents (later):** curated set from deal announcements with AI extraction flagged for review.

## 19. User interfaces

#### 19.1 Web app

| **Screen** | **Contents and actions** |
|---|---|
| Welcome | The first visit of a browser session to the home page: the mark, a greeting, the tagline and live counts (companies tracked, results filings, reporters this quarter) on frosted cards over slowly drifting light. The page follows a scroll or swipe up with some resistance, springs back if let go early, and unlocks into the desk past a threshold or on a click, tap or Enter; the mark flies to the sidebar. Links to other pages skip it. |
| Home: Results desk | The quarter's reporters, newest filing first or largest market cap first, ten per page, with each company's market cap at the latest close: revenue (interest earned or premium for banks and insurers), net profit and EBITDA margin with the change on a year ago. Filters for quarter (newest by default), sector, filing date and watchlist, kept in the URL. Movers by revenue or profit (at least Rs 50 crore of quarterly revenue; profit growth needs a year-ago profit of at least 2% of revenue; turned profitable and turned to a loss listed apart) and progress by sector with median growth, each in a box that scrolls inside a fixed height. Rows become cards on phones. |
| Search and universe | Type-ahead over every NSE company, ranked: exact ticker or ISIN, ticker prefix, name prefix, words that start words in the name, then substrings. The universe (about 80 KB compressed) loads once and is searched in the browser; the server answers only before it loads and as a typo fallback. Open a company; add to watchlist. |
| Watchlist | Last filing, next board meeting, validation status, pending change sets. |
| Company page | Header with sector, results format and coverage level; Analyse and Start coverage buttons. A Consolidated or Standalone switch when the company files both (in the URL). Figure tiles and a quarterly chart of the top line with a value per bar; amounts in lakhs when the company's revenue is under Rs 10 crore, crore otherwise. A Latest quarter column (full window height on wide screens, after the tiles on phones): the quarter's lines in the company's format with QoQ and YoY change, derived EBITDA and margins (in basis points), notes behind an information icon, a dash with the reason when a comparison quarter was never filed, and a Restated or Revised tag when the quarter was refiled. A Call highlights card (empty until call notes exist). Share price and market cap tiles from the latest close (with the day's change and the face value). The filings table, in a box that scrolls inside the page with its headings pinned, links each period to its filing on NSE (iXBRL, PDF, XBRL) and tags refiled quarters Restated, Revised or Superseded with a popup listing what changed. KPIs and red flags to follow. |
| Change-set review | Grouped items with cell, old and new values, source and rationale, dependent-cell counts; accept, edit, skip, apply. |
| Assumption review | Proposed drivers with rationale and citations for new models; accept or edit. |
| Templates | Upload, sector tags, mapping confirmation, test-build report, versions. |
| Models | Discovered and built models, link status, versions. |
| Reports | Flash, digest, notes, initiation drafts; downloads. |
| Q&A | Chat over a company's filings with page links. |
| Comps | Saved peer lists (beside the table from 1,500 pixels, a row of buttons above it otherwise); companies added by search or from suggested peers; the table with a basis switch (auto, consolidated, standalone), median and mean rows and an Excel export. The working set lives in the URL. Rows become cards on phones. |
| Settings | Data status (the results watcher's season, last ask and next ask, with a warning when a scheduled start left no record; the latest close and its coverage; stored counts and database size; whether an Anthropic key is set, never the key). Alerts (Telegram and email set up or not, a test message per channel, recent alerts; errors are summarised, never echoed, as they can hold the bot token). Display preferences saved in the browser: theme, amounts (auto, crore or million), the company page's basis and the Results desk order. NSE schedules are not editable: they follow the owner's approvals. Watched folders and save mode come with the Excel bridge. |

Stack: React with TypeScript (Vite), TanStack Query, AG Grid Community for dense grids, ECharts, PDF.js for the side-by-side source viewer, and the Inter font bundled with the app. Layout: collapsible left sidebar; light, dark and system themes; clean, dense screens. Motion is for what is clicked, never for data (owner's rule, 17 October 2026): the sidebar highlight glides to the chosen tab, segmented switches have a sliding thumb (the theme switch a springy one), tabs dip when pressed and a faint light follows the pointer over the sidebar; screens and figures appear at once, and the browser keeps data fresh for five minutes so returning to a tab refetches nothing. All motion stops under the reduced-motion setting. Every screen works at phone width without sideways scrolling (checked at 390, 1,366 and 2,000 pixels); notes and tags open on hover, tap or keyboard focus, never on hover alone. The front end stays light: a new library has to earn its weight.

#### 19.2 Excel

- Phase 2: xlwings bridge (background service with a tray or terminal status) that discovers, links and writes models.
- Later: Office.js task pane showing the change set or assumptions beside the model; clicking an item highlights its cell.

#### 19.3 Developer and operator interfaces

- CLI: analekh universe load, analekh universe sectors [--stocks-file], analekh search, analekh watch, analekh refresh, analekh backfill, analekh results-backfill, analekh results-watch, analekh prices, analekh revalidate, analekh recompute-latest, analekh transcribe-audio, analekh template add, analekh build, analekh sync, analekh golden-sheet, analekh golden-import, analekh golden-test.
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
| GET /companies/{symbol}/filings \| facts \| kpis | Filings, facts and KPIs by period. Filings of a quarter filed more than once carry their revision status (original, revised or refiled), what they replaced or were superseded by, and the headline lines that changed. Facts accept logical names (revenue resolves to interest earned for a bank) and default to consolidated when the company files it, else standalone. |
| GET /companies/{symbol}/glance | The latest quarter's lines in the company's results format, with QoQ and YoY change, notes, the reason a comparison is missing and the quarter's revision status; consolidated or standalone. |
| GET /desk | Results desk: a quarter's reporters (paged, by filing time or market cap: sort=filed or market_cap) with market cap, movers, progress and medians by sector, the quarters available; filters for quarter, sector, watchlist and days since filing. |
| GET /companies/{symbol}/price | The latest close: trade date, open, high, low, close, previous close, the day's change and market cap; null before the first load. |
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
| GET, POST /peer-lists; PUT, DELETE /peer-lists/{id} | Saved peer lists (names unique ignoring case; symbols checked against the universe). |
| GET /companies/{symbol}/peers | Suggested peers. |
| POST /comps/table; POST /comps | The comps table as JSON, or as an Excel workbook. |
| GET /status | Data status for Settings; reads only, never contacts NSE. |
| GET /alerts/channels; POST /alerts/test; GET /alerts | Alert channels set up, a test message, recent alerts. |

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
| Market data | NSE's daily bhavcopy, latest day only (section 3.3) | Free; end of day is enough; no paid feed in v1 |
| Sector data | NSE Indices constituent CSVs (NSE's taxonomy); Excel Stocks data type (Microsoft 365) | Free; no scraping |
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
| beat | Scheduler: results watcher, daily prices, weekly universe refresh, feed polling |
| postgres | PostgreSQL with pgvector |
| redis | Queue broker |
| minio | Raw files and generated outputs |
| web | React build served by nginx |
| excel-bridge (host) | Runs on the analyst's machine; watches folders; drives Excel |

Until hosting is set up, the stack runs on the owner's laptop: PostgreSQL and MinIO in Docker Desktop, the API and the web app started by hand, and Windows scheduled tasks in place of the worker and beat (results watcher every 2 hours, prices after the close).

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
USER_AGENT=Analekh/0.1
CONTACT_EMAIL=you@example.com         # sent in the From header; NSE stalls a User-Agent with an email
RESULTS_WATCH_CRON=0 */2 * * *         # one request for NSE's latest results every 2 hours
PRICES_CRON=0 19-23 * * 1-5            # bhavcopy after the close; skipped once stored
DOWNLOAD_RATE_PER_SECOND=1.0
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
| Commits | Signed by the owner with an SSH key; the AI assistant prepares changes and messages but never commits. |
| GitHub repository settings | Public; description, topics and README point contributors to GitLab; Actions, Issues, Wiki and Projects disabled; ruleset on main blocks force pushes and deletion; optional CodeQL as an independent second scanner. |

#### 22.6 Distribution

- Public GitHub mirror with sample models and templates built on public companies, a demo video and the diagrams; GitLab remains the working repository.
- No raw exchange files, user models or keys committed; secret detection and pre-commit hooks enforce this before code leaves a developer's machine.

#### 22.7 Hosting

*Figure 12. Where Analekh runs today (the owner's laptop) and the planned server in India.*

- **Needs:** about 2 vCPUs, 4 GB of RAM and 60 to 80 GB of disk (the data is about 10 GB: PostgreSQL 5.9 GB, raw XBRL 4.5 GB, growing about 0.7 GB a results season), in an Indian region, with HTTPS and a login.
- **The gate:** NSE may refuse requests from data-centre addresses. One honest request from the new machine to the results lookup and one bhavcopy must succeed before anything moves.
- **Tried (October 2026):** Oracle Cloud's free tier (the card was charged for verification and no account was created); Azure for Students (the university email could not be verified). AWS and Google Cloud need a card, and their credits last three to six months.
- **Plan:** verify through GitHub Education (which issues an Azure for Students code), or run an always-on machine at home with Cloudflare Tunnel, which keeps the home connection NSE already serves; a VPS in India (about USD 20 to 25 a month) once there is a budget.
- **Moving:** the data goes by pg_dump and a MinIO copy, never downloaded from NSE again; the scheduler moves off the laptop; GitLab CI deploys from main and release tags.

## 23. Security, compliance and data rights

- **Exchange data:** only published RSS feeds at their stated interval and the files they link to; no redistribution of raw data; written confirmation or a licensed feed before public or commercial release. NSE Indices' published constituent CSVs are allowed on the same terms, limited to /IndexConstituent/ by the HTTP client's path allow-list. On www.nseindia.com only the home page, the integrated-filing lookup (approved by the owner on 14 October 2026) and the financial-results list (15 October 2026) are allowed: per company, plus one request every 2 hours without a ticker. One bhavcopy per trading day after the close (17 October 2026). No other internal endpoint; widening the list needs the owner's approval, and requests are never disguised as a browser. If NSE refuses the honest User-Agent, the owner decides what happens next.
- **Third-party data from Excel:** LSEG industry groups from Excel's Stocks data type come through Microsoft 365. They are kept in the local database only, never in git, and Microsoft's terms for this data must be checked before any public or commercial release.
- **Research regulation:** publishing buy or sell recommendations in India generally requires SEBI Research Analyst registration; NISM Series XV alone is not registration. Shared outputs carry no ratings or target prices.
- **User files:** models and templates stay on the user's machine or private storage; only structure maps and confirmed mappings are stored centrally; macros are never executed.
- **Secrets:** environment variables only; never logged.
- **AI data handling:** only public filings and the user's own workbook labels are sent to the Claude API; no client or employer data in the public build.
- **Audit:** every model change, assumption and report stored with sources and approver.
- **Code and supply chain:** GitLab SAST, secret detection and container scanning, plus OSV-Scanner for dependencies; DAST and merge request approval policies once the plan includes them; pre-commit secret scanning locally; pnpm blocks package install scripts unless allowed; the GitHub mirror token is scoped to one repository and rotated every 90 days.

## 24. Testing and quality

| **Test** | **Approach and target** |
|---|---|
| Golden set | 20 filings across sectors and every results format (Ind-AS standalone and consolidated, bank, NBFC, general insurer, life insurer) with hand-checked values. analekh golden-sheet copies their XBRL from storage and writes a worksheet (each line, Analekh's value, the results PDF link); the analyst marks every line against the PDF; analekh golden-import writes the manifest. Lines are resolved through the element tables, so the mapping is tested, not only the parser. A line Analekh cannot find stays on the sheet for the PDF's figure. |
| Results views | Revisions: a revision downloaded before its original must still be the value in use; the popup lists old and new values. Layout: no cell or page overflows at 390, 1,366 and 2,000 pixels (measured in a headless browser). |
| XBRL parsing | 100% exact match on mapped elements. |
| KPI extraction | 95% or better precision with correct pages. |
| Workbook understanding | 20 real-world models and templates with hand-labelled structure; mapping suggestion accuracy 90% or more. |
| Template test builds | Checks pass for each built-in template on five companies per sector. |
| Coverage Builder | Built models balance; every input has a Sources entry. |
| Model sync | Fixture workbooks with expected change sets and recalculated outputs. |
| Grounding | Every number in generated text matches a tool result. |
| Universe and feeds | Recorded feed samples; universe diff tests for listings and delistings. |
| Search | The browser's ranking matches the server's on real queries (22 of 22 at last check). |
| Prices | Bhavcopy parsing (one row per ISIN, main series first), market cap from the filing's share count, the previous day replaced, an older day refused; the latest-close endpoint and the desk's market-cap sort. |
| CI | GitLab CI on every push and merge request: ruff, mypy, pytest, alembic check, web lint, tests and build, security scanners and the dependency audit; golden-set accuracy on schedule and per release. |

## 25. Cost model

| **Item** | **Estimate** |
|---|---|
| Universe and all-company facts | No AI cost; local parsing. About 10 GB today (facts are 97% of the database); a results season adds roughly 0.5 GB to the database and 0.2 GB of files. |
| Prices | No cost: one public file a day; about 0.4 MB, since only the latest day is kept. |
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

#### 26.1 Status on 18 October 2026

| **Phase** | **Where it stands** | **What stops it finishing** |
|---|---|---|
| 0. Spike | Data path proven at scale: 54,242 results filings from 2,748 companies fetched, parsed and validated (10.1 million values); element tables for Ind-AS, banks, NBFCs, general and life insurers come from real filings and tie out; 14 filings are blocked by V2. | The hand-check of about 10 values per filing against the results PDF, for a golden set covering every results format, and the golden-set run (analekh golden-test). How to flag contexts with the same dates but different values is still to decide. |
| 1. Data layer | Universe (3,186 companies), NSE sectors for 1,430 and LSEG groups for 1,587, search, watchlist, both lookups, history from March 2023 (both backfills finished), validation, revisions, daily prices with market cap, the Results desk, company pages and the welcome screen. The September-quarter season: 109 companies reported by 17 October. | The scheduler on a server (the results watcher and prices run from Windows scheduled tasks on the laptop, paused since 17 October; the feed watcher not at all); the 290 companies with nothing on NSE (about 250 file only with BSE); the 169 without any sector and the LSEG-to-NSE mapping; the 14 V2-blocked filings. |
| 2. Builder and sync | Every engine has a working core with synthetic tests. | Real model templates and existing models from an analyst, to tune the workbook reader and template onboarding; balance sheet and cash flow history in the built-in templates; a machine with desktop Excel for the xlwings bridge; debt and cash for EV-based valuation. |
| 3. Document AI | Pipeline built with synthetic tests; call recordings can be transcribed locally. | A valid Anthropic API key; a source for investor presentations (NSE's announcements list needs the owner's approval; company IR pages otherwise) and transcripts; the embeddings provider; a golden set of KPIs. |
| 4. GenAI outputs | Tools, calc, grounding check and report loop built. | Phase 3's KPIs and call notes; the report structure decision (section 28). |
| 5. Discovery, IB, polish | Comps (market cap and P/E, P/B from the latest close), profile slide, alerts and the add-in have working cores. | Debt and cash for EV multiples; branded slide templates; hosting in an Indian region with a login so the app can be shared (section 22.7). |

#### 26.2 What to build next

Ordered by value:

- **The season schedule for the results watcher** (section 9.6), then re-enable the watcher and the price job.
- **Hosting** (section 22.7): the NSE test from a server's address, then the stack, the data, HTTPS and a login, and the scheduler off the laptop.
- **The 14 V2-blocked filings** (L&T, KIMS, MT Educare and four SME companies): likely one P&L line V2 does not include yet, such as the share of associates.
- **Golden set and hand-check** across the five results formats, then golden-test: this completes Phase 0 (v0.1.0).
- **Balance sheet and cash flow** from the half-year and year-end filings; V4 for Ind-AS filers.
- **Results history table** on the company page: every stored quarter's lines, on either basis, with the revision tags, and an Excel export.
- **Results calendar** from the Board Meetings feed (workflow 6.9); a **peer view** of growth and margins.
- **Sector editing screen** and the LSEG-to-NSE mapping.

Decisions waiting on the owner: the LSEG-to-NSE sector mapping (28 clear groups, 25 to decide); how banks are presented and calculated (the owner's walkthrough); hosting details (provider, domain, login); investor presentations through NSE's announcements list (section 28); the 250 BSE-only filers (manual import, or a note that NSE has no data); the logo; the Anthropic API key.

#### 26.3 Future scope (after v1)

Left out of v1 by the owner's choice, for a later release (the first two need paid data):

- **Live and intraday prices** through a paid market-data API (Kite Connect or similar), in place of the end-of-day bhavcopy (section 3.3).
- **NSE's finer classification** (industry and basic industry, such as Gems, Jewellery and Watches under Consumer Durables) for every company. NSE publishes only the 22 sectors in its index lists, and its per-company classification is not open to Analekh (section 4.2); setting thousands by hand is not worth it (owner, 18 October 2026). A licensed data feed would supply it.
- **Live earnings-call listener** (owner, 20 October 2026): Analekh's own agent that joins a company's earnings call as it happens and transcribes it live, instead of waiting for the recording on NSE (filed within a day). A call record (company, time, link) starts a headless browser a few minutes early; it registers with the analyst's own details (never a made-up identity, never past a captcha or an operator), records the webcast's audio stream with ffmpeg (or a virtual audio device when the page exposes no stream), and the local Whisper (section 11) transcribes 5 to 10 second pieces on the GPU, about 10 seconds behind the speaker. The company page's Call highlights card shows the transcript as it arrives, marked live and unverified; guidance, margin and capex remarks are extracted with their quotes under the grounding check, and XBRL still wins on any figure. The official recording's transcript replaces it once filed. Fixed scripts handle the common webcast hosts, with a browser agent for unknown registration pages; phone-only calls would need a telephony service (paid per minute) and come later. Transcripts stay in the analyst's own database, never republished, per the calls' terms. Open points: finding calls automatically needs NSE's announcements list (a rule 1 decision, as for investor presentations; until then the analyst pastes the link), and the listener needs an always-on machine (section 22.7). First step when picked up: replay an existing call recording as if live, to measure delay and accuracy.

Versions follow the build phases: v0.0.x while Phase 0 is under way, v0.1.x once Phase 0 is complete, v0.2.x once Phase 1 is complete, and so on (the middle number counts completed phases; the last counts revisions within a phase). The first release for proper testing is v1.0.0-pre-release. This document and the code are at v0.0.4.

## 27. Risks and mitigations

| **Risk** | **Mitigation** |
|---|---|
| NSE changes feeds or objects to polling | Polite polling; source adapters; IR fallback; written confirmation or licence before release. The results feed already stopped carrying filings once (24 August 2026); the integrated-filing lookup replaced it with the owner's approval. |
| NSE refuses the honest User-Agent or the lookup | Runs stop at the first refusal; the owner decides; requests are never disguised. |
| NSE's request limit (a few hundred to a few thousand requests, then a pause) | Runs resume at the company they stopped on after a 10-minute pause; the watcher needs one request; longer back-off if NSE stalls quickly several times in a row. |
| Revised filings change numbers already shown | The most recently filed value is used whatever the download order; superseded values kept; refiled quarters tagged with what changed. |
| XBRL varies by sector | results_taxonomy per company, detected from the filing's line items; element tables for Ind-AS, banks, general and life insurers; golden set per format. |
| Context or period errors | Rules V5, V6, V8; declared period wins. |
| AI extraction errors | Pages and quotes on every value; thresholds; XBRL wins; approval before writes. |
| Templates and models vary widely | Shared understanding engine; confidence scores; confirm once; test builds; built-in fallbacks. |
| Wrong model linked to a company | Hidden tag after confirmation; user confirmation for every new link. |
| Sector classification gaps | Stocks data type import and NSE Indices lists, with precedence; user override per company. SME companies remain the gap. |
| Excel dependency | Headless openpyxl and LibreOffice path; Office.js later. |
| Geo-restriction | Indian network or VM. |
| NSE hosts stop answering | Retry later with single requests; never work around a block; import folder as fallback. |
| Bhavcopy late, missing or changed in format | Hourly retries until 23:00; a missing day leaves the previous close in place; parsing by column name; core numbers do not need prices. |
| No host serves NSE, or none can be set up | The laptop keeps working meanwhile; an always-on home machine with Cloudflare Tunnel keeps the home connection NSE serves; the NSE test gates any move. |
| Regulatory exposure when sharing outputs | No ratings or targets in shared outputs. |
| Scope creep | Phase gates with exit criteria; each phase ends with a working demo. |
| Mirror diverges or leaks | GitHub main accepts only fast-forward pushes from the mirror job; mirror runs only after a green pipeline; secret detection and push protection run before anything leaves GitLab. |

## 28. Open questions

- Settled in 0.0.3: banks and insurers use their regulators' element sets (RBI, IRDAI general and life); NBFCs use the Ind-AS names. Still open: how stable the tags are across the full universe, which the completed backfill and the golden set will show.
- Should Analekh link each quarter's investor presentation from NSE's announcements list (subject "Investor Presentation"; one request a day, plus a backfill by date range or per company)? It needs the owner's approval to widen the allow-list. Some filings under that subject are only meeting intimations.
- How to cover the 290 companies with nothing on NSE (about 250 file only with BSE, whose API refuses automated requests): a manual import, or a note that NSE has no data? Periods before March 2023 need the company's own files.
- Which host: GitHub Education's Azure for Students route, an always-on home machine with Cloudflare Tunnel, or a paid VPS in India? Each must pass the NSE test first (section 22.7).
- Can annual statements be downloaded cleanly from NSE's annual report XBRL section for backfill?
- Is there a public shareholding pattern feed, or must shareholding come from filings?
- How should the 25 undecided LSEG groups map to NSE sector names, and how to classify the 169 companies with no sector at all? Do Microsoft's terms allow storing Stocks data type fields?
- Do transcripts appear in the announcements feed with a consistent subject line? (Recordings come first and can be transcribed locally.)
- xlwings or Office.js first for the demo machine?
- Hosted or local embeddings?
- Would NSE confirm in writing that polling its RSS feeds for a personal or open-source tool is acceptable?
- Settled in 0.0.4: prices come from NSE's bhavcopy, end of day, latest day only. Still open: whether a results season's schedule should follow the results calendar once the feed watcher runs.
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
sector_lseg TEXT,
results_taxonomy TEXT CHECK (results_taxonomy IN ('indas','banking','nbfc','insurance','life_insurance')),
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
prev_close NUMERIC(14,4), volume BIGINT, market_cap NUMERIC(24,2),
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
ingest/         feed watcher, integrated-filing lookup and financial-results list, polite HTTP client and host and path allow-list, fetcher, pipeline (incomplete-file guard, latest value by filing time), backfill, bhavcopy (daily prices)
xbrl/           parser, context mapping, taxonomies
docs/           page classifier, extraction, chunking, embeddings, call audio to text
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
desk.py         Results desk: reporters, movers, sector progress
glance.py       latest quarter at a glance, derived lines, missing-comparison notes
restatements.py revision status of refiled quarters and what changed
prices.py       latest close and market cap per company
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
.claude/          assistant settings and hooks (the owner's commands and skills are kept outside the repo)
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

Call recordings use a separate optional group, exported to requirements-audio.txt (uv sync --group audio): faster-whisper with CUDA libraries, no PyTorch.

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
| Integrated filing | SEBI's combined quarterly filing (financials and governance) that replaced separate results filings; NSE lists them with links to the XBRL. |
| Basis | Standalone (the listed company alone) or consolidated (with subsidiaries). Both are stored; the company page switches between them. |
| Revision, restatement | A quarter filed again on the same basis. Restated means headline numbers changed; superseded marks the filing replaced. The most recently filed values are used. |
| Basis point (bps) | One hundredth of a percentage point; margins and ratios change in bps. |
| Lakh, crore | Indian units: 1 lakh = 100,000; 1 crore = 10,000,000 (100 lakh). |

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
- [NSE integrated filings (financials)](https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials)
- [SEBI LODR regulation 33 (financial results)](https://www.sebi.gov.in/legal/regulations/)
