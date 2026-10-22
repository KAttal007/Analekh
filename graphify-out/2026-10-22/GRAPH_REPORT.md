# Graph Report - Kaushal-Analekh  (2026-10-22)

## Corpus Check
- 227 files · ~168,176 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 10, .example 1, .ini 1)

## Summary
- 2185 nodes · 6622 edges · 121 communities (86 shown, 35 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 548 edges (avg confidence: 0.92)
- Token cost: 406,493 input · 0 output

## Community Hubs (Navigation)
- CI and Compose Deploy
- CompanyPage.tsx
- tasks.py
- test_builder.py
- Golden Set Runner
- Design Doc Core Components
- Analekh CLI
- Company Page UI
- ToolExecutor
- db/models.py (1)
- NSE Integrated Filings
- json
- DB Migrations and Admin
- API Schemas (1) (1)
- Validation Rules V1-V11
- test_workbook.py (1)
- Companies API (1) (1)
- reader.py
- bhavcopy.py
- Filing (1)
- test_universe.py (1)
- Office Add-in Task Pane (1) (1)
- XBRL Validation Tests
- assumptions.py (1)
- test_ib.py (1) (1)
- Results History UI
- test_ib.py (2)
- Object Storage (1)
- Results Calendar UI
- db/models.py (2)
- ResultsDesk.tsx
- io
- Results Seasons
- Polite HTTP Client (1) (1)
- design_docx.py (1) (1)
- history.py (1)
- dataclasses (1)
- changeset.py (1)
- Company (1)
- desk.py (1)
- Latest Results Paging
- Router and Welcome
- System Status and Alerts (1)
- test_ingest.py
- Search and Reports UI
- ingest/pipeline.py
- changeset.py (2)
- V11 Scale Check Tests
- dataclasses (2)
- Layout and Theme
- change_sets.py
- test_universe.py (2)
- Company (2)
- dataclasses (3)
- Events Schedule
- dataclasses (4)
- XBRL Parser
- Settings UI
- Polite HTTP Client (1) (2)
- FastAPI App
- System Status and Alerts (2)
- Watchlist Coverage
- history.py (2)
- assumptions.py (2)
- Workbook Engine Design
- test_workbook.py (2)
- API Settings and Health
- Product Rules and Workflows
- Universe and Sector Design
- Build Plan Phases
- testbuild.py (1)
- testbuild.py (2)
- Results Collection Design
- Object Storage (3)
- design_docx.py (1) (2)
- test_ib.py (1) (2)
- Example NBFC Mapping
- test_ib.py (4)
- dataclasses (5)
- Grounded GenAI Design
- API Schemas (1) (2)
- Office Add-in Task Pane (1) (2)
- desk.py (2)
- Companies API (1) (2)
- Rule 8 Ratings and target prices from th
- Deployment today and planned hosting
- Job schedule by results season
- Only latest day's prices kept
- Workflow 4 Opening Analekh and reading r
- Call recordings transcription (Whisper)
- Section 22.5 Source control, CI/CD and G
- Phase tracker tables
- GitLab source of truth, GitHub read-only
- Package layout in request-flow order
- Rule 7 Macros never executed
- Analekh (system)
- Comps (peer lists, TTM, multiples)
- Decisions waiting on the owner
- Golden set
- NSE test gate for hosting
- Section 19 User interfaces (web app, Exc
- graphify usage rules
- Versioning by build phase
- GitLab Free CI (OSV-Scanner replaces dep
- Gzipped XBRL in Raw Filing Store
- MinIO built from source
- Type-ahead search ranked in browser
- V8 late filing tied to SEBI LODR 33(3)
- Section 12 Workbook understanding engine
- Section 1 Overview and goals
- Section 21 Technology stack
- Section 22 Packaging, deployment and set
- Section 25 Cost model
- Section 7 Inputs and outputs
- Section 9 Ingestion layer
- Target users: equity research and IB ana

## God Nodes (most connected - your core abstractions)
1. `Company` - 124 edges
2. `Filing` - 66 edges
3. `ValidationContext` - 53 edges
4. `PoliteClient` - 53 edges
5. `ingest_results_xbrl()` - 53 edges
6. `parse_instance()` - 52 edges
7. `get_settings()` - 44 edges
8. `Mapping` - 42 edges
9. `get()` - 42 edges
10. `q2_instance()` - 40 edges

## Surprising Connections (you probably didn't know these)
- `Filing` --uses--> `test_discover_and_link()`  [INFERRED]
  analekh/db/models.py → tests/test_api.py
- `PeerList` --uses--> `test_peer_lists_and_the_comps_table()`  [INFERRED]
  analekh/db/models.py → tests/test_api.py
- `Company` --uses--> `company()`  [INFERRED]
  analekh/db/models.py → tests/test_ingest.py
- `Company` --uses--> `company()`  [INFERRED]
  analekh/db/models.py → tests/test_latest_page.py
- `Company` --uses--> `company()`  [INFERRED]
  analekh/db/models.py → tests/test_queues.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Report drafting guardrails** — docs_design_technical_design_grounded_genai, docs_design_technical_design_style_check, docs_design_technical_design_no_ratings_rule, docs_design_technical_design_genai_tools [EXTRACTED 0.90]
- **NSE endpoints approved under the access rule** — docs_design_technical_design_integrated_filing_lookup, docs_design_technical_design_financial_results_list, docs_design_technical_design_bhavcopy, docs_design_technical_design_nse_indices_lists, docs_design_technical_design_nse_rss_feeds [EXTRACTED 0.95]
- **Results ingestion flow** — docs_design_technical_design_results_watcher, docs_design_technical_design_results_fetcher, docs_design_technical_design_raw_filing_store, docs_design_technical_design_xbrl_parser, docs_design_technical_design_validation_v1_v11, docs_design_technical_design_latest_value_rule [EXTRACTED 0.95]
- **Nine workflow diagrams** — docs_design_architecture_workflow_results_collection, docs_design_architecture_workflow_daily_prices, docs_design_architecture_workflow_universe_sectors, docs_design_architecture_workflow_reading_results, docs_design_architecture_workflow_quarterly_update, docs_design_architecture_workflow_start_coverage, docs_design_architecture_workflow_template_onboarding, docs_design_architecture_workflow_documents_reports, docs_design_architecture_workflow_events_alerts [EXTRACTED 1.00]
- **Build, scan, deploy and DAST flow** — gitlab_ci_yml_build_image, gitlab_ci_yml_container_scanning, gitlab_ci_yml_deploy_staging, gitlab_ci_yml_dast [EXTRACTED 1.00]
- **Eight non-negotiable rules** — claude_rule1_nse_access, claude_rule2_human_in_loop, claude_rule3_grounded_genai, claude_rule4_decimal_money, claude_rule5_xbrl_wins, claude_rule6_no_raw_files, claude_rule7_no_macros, claude_rule8_no_generated_ratings [EXTRACTED 1.00]
- **Local dev compose stack** — docker_compose_yml_postgres, docker_compose_yml_redis, docker_compose_yml_minio, docker_compose_yml_api, docker_compose_yml_worker, docker_compose_yml_beat, docker_compose_yml_web [EXTRACTED 1.00]
- **Template mapping structure** — mappings_example_quarterly_yaml_period_axis, mappings_example_quarterly_yaml_xbrl_rows, mappings_example_quarterly_yaml_drivers, mappings_example_quarterly_yaml_checks [EXTRACTED 1.00]
- **Trust, approval and NSE-access commitments** — product_principles, claude_rule2_human_in_loop, claude_rule3_grounded_genai, claude_rule1_nse_access [INFERRED 0.75]

## Communities (121 total, 35 thin omitted)

### Community 0 - "CI and Compose Deploy"
Cohesion: 0.06
Nodes (53): CLAUDE.md project guidance, production service api, production service beat, production service migrate (alembic), production service postgres, production service valkey, production service worker, staging service api (+45 more)

### Community 1 - "CompanyPage.tsx"
Cohesion: 0.08
Nodes (50): CompanyDetail, GlanceLine, HistoryLine, WatchlistEntry, COSTS, fmtDate(), QuarterRail(), InfoTip() (+42 more)

### Community 2 - "tasks.py"
Cohesion: 0.08
Nodes (23): get_store(), get_user(), get_settings(), Settings, get_engine(), get_session(), _session_factory(), session_scope() (+15 more)

### Community 3 - "test_builder.py"
Cohesion: 0.10
Nodes (34): assumptions(), decide_assumptions(), discover_models(), finalize(), link_model(), list_models(), _model(), relink_model() (+26 more)

### Community 4 - "Golden Set Runner"
Cohesion: 0.08
Nodes (26): build_sheet(), file_name(), fy_label(), GoldenReport, guess_unit(), import_sheet(), ImportSummary, Mismatch (+18 more)

### Community 5 - "Design Doc Core Components"
Cohesion: 0.05
Nodes (43): Appendices A-H (DDL, mapping, CI, deps, glossary), Backfill (results-backfill, --history, watchdog), NSE daily bhavcopy, Celery beat scheduler in Docker, Company page with results history table, Feed Watcher, NSE financial-results list (history from March 2023), GenAI tools (get_facts, get_kpis, get_model_values, search_filings, get_prices, calc) (+35 more)

### Community 6 - "Analekh CLI"
Cohesion: 0.09
Nodes (27): backfill(), build(), _company(), golden_import(), golden_sheet(), golden_test(), prices(), recompute_latest() (+19 more)

### Community 7 - "Company Page UI"
Cohesion: 0.12
Nodes (35): Suggestion, Icon(), IconName, PATHS, AVATAR_HUES, Badge(), EmptyState(), ErrorNote() (+27 more)

### Community 8 - "ToolExecutor"
Cohesion: 0.08
Nodes (23): qa(), QaRequest, calc(), CalcError, _eval(), check(), collect_values(), _decimals() (+15 more)

### Community 9 - "db/models.py (1)"
Cohesion: 0.11
Nodes (30): activate_template(), confirm(), list_templates(), _template(), test_build(), upload_template(), Template, TemplateTest (+22 more)

### Community 10 - "NSE Integrated Filings"
Cohesion: 0.08
Nodes (26): refused(), _date(), _download_and_ingest(), _error(), _fetch(), fetch_history(), FetchOutcome, _history_row() (+18 more)

### Community 11 - "json"
Cohesion: 0.08
Nodes (13): _add_cuda_dll_dirs(), AudioTranscript, _clock(), _has_cuda(), Segment, transcribe(), evaluate(), lookup() (+5 more)

### Community 12 - "DB Migrations and Admin"
Cohesion: 0.07
Nodes (11): downgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+3 more)

### Community 13 - "API Schemas (1) (1)"
Cohesion: 0.06
Nodes (37): AssumptionDecision, AssumptionDecisions, AssumptionOut, ChangeItemOut, ChangeSetOut, CompanyDetail, CompanyIndexEntry, CompanyOut (+29 more)

### Community 14 - "Validation Rules V1-V11"
Cohesion: 0.10
Nodes (21): _identity(), is_year_end(), _power(), _quarters(), RuleResult, tolerance(), _typical(), v10_kpi_conflict() (+13 more)

### Community 15 - "test_workbook.py (1)"
Cohesion: 0.10
Nodes (20): _api(), apply(), link(), scan(), watch(), hints_for(), iter_workbooks(), scan() (+12 more)

### Community 16 - "Companies API (1) (1)"
Cohesion: 0.10
Nodes (26): company_or_404(), job(), analyse(), company_glance(), company_history(), company_history_xlsx(), company_index(), company_price() (+18 more)

### Community 17 - "reader.py"
Cohesion: 0.11
Nodes (24): Finding, LabelMatch, match_label(), normalise(), Check, Driver, parse_source(), PeriodAxis (+16 more)

### Community 18 - "bhavcopy.py"
Cohesion: 0.11
Nodes (22): Price, BhavRow, _dec(), fetch(), latest_stored(), load_day(), market_cap(), paid_up_capital() (+14 more)

### Community 19 - "Filing (1)"
Cohesion: 0.11
Nodes (25): FeedItem, Filing, fetch_results(), _gone(), pending_feed_items(), process_feed_item(), process_feed_items(), process_pending() (+17 more)

### Community 20 - "test_universe.py (1)"
Cohesion: 0.12
Nodes (27): _date(), _decimal(), ListedCompany, LoadSummary, _norm_header(), parse_equity_list(), refresh_from_nse(), upsert_universe() (+19 more)

### Community 21 - "Office Add-in Task Pane (1) (1)"
Cohesion: 0.06
Nodes (34): AlertChannels, AlertEntry, AlertTest, ApiError, Assumption, BuildOut, Calendar, CalendarEvent (+26 more)

### Community 22 - "XBRL Validation Tests"
Cohesion: 0.23
Nodes (32): KpiValue, validate(), ValidationContext, parse_instance(), main(), by_rule(), _quarter(), test_bank_identities_include_provisions() (+24 more)

### Community 23 - "assumptions.py (1)"
Cohesion: 0.12
Nodes (17): Proposal, propose(), _propose_one(), _q(), _revenue_row(), _series(), fill_history(), FillReport (+9 more)

### Community 24 - "test_ib.py (1) (1)"
Cohesion: 0.12
Nodes (23): book_value(), CompInputs, compute(), four_quarters(), gather(), _pct(), _ratio(), _sum() (+15 more)

### Community 25 - "Results History UI"
Cohesion: 0.15
Nodes (27): Filing, Revision, BOLD, cell(), FilingDetails(), headMark(), OtherFilings(), ResultsHistory() (+19 more)

### Community 26 - "test_ib.py (2)"
Cohesion: 0.14
Nodes (21): _commit(), comps(), comps_table(), create_peer_list(), delete_peer_list(), _list_or_404(), _name(), peer_lists() (+13 more)

### Community 27 - "Object Storage (1)"
Cohesion: 0.09
Nodes (10): LocalStore, pack(), S3Store, unpack(), compress(), main(), store(), test_builtin_template_file_is_rebuilt_when_storage_lost_it() (+2 more)

### Community 28 - "Results Calendar UI"
Cohesion: 0.19
Nodes (29): DayProps, DayStrip(), EventRow(), KIND_LABEL, KIND_TONE, KindChip(), KindFilter, MonthView() (+21 more)

### Community 29 - "db/models.py (2)"
Cohesion: 0.11
Nodes (14): create_report(), get_report(), ReportRequest, Base, ChangeItem, Chunk, Document, JobStatus (+6 more)

### Community 30 - "ResultsDesk.tsx"
Cohesion: 0.20
Nodes (27): Change(), BasisCell(), BasisHeader(), MarketCapCell(), ProfitCell(), ResultColumns(), RevenueCell(), TOP_LINE_TAG (+19 more)

### Community 31 - "io"
Cohesion: 0.12
Nodes (16): quarter_start(), SourceValue, column_letter_shift(), DependencyGraph, expand(), references(), apply_transform(), load_mapping() (+8 more)

### Community 32 - "Results Seasons"
Cohesion: 0.13
Nodes (19): watch_results(), deadline_days(), next_ask(), next_season(), previous_start(), Season, _season(), season_for() (+11 more)

### Community 33 - "Polite HTTP Client (1) (1)"
Cohesion: 0.16
Nodes (22): DisallowedHostError, path_allowed(), PoliteClient, lookup(), classify_announcement(), company(), test_announcement_classifier(), test_client_allows_niftyindices_constituent_lists_only() (+14 more)

### Community 34 - "design_docx.py (1) (1)"
Cohesion: 0.14
Nodes (17): add(), caption(), cell_border(), cells(), code_block(), figure(), heading(), inline() (+9 more)

### Community 35 - "history.py (1)"
Cohesion: 0.13
Nodes (15): files_consolidated(), _day(), glance(), value(), Glance, _latest_revision(), Line, missing_quarter_note() (+7 more)

### Community 36 - "dataclasses (1)"
Cohesion: 0.16
Nodes (14): chunk_pages(), TextChunk, PageScore, score_page(), select_pages(), _ocr(), PageText, read_pages() (+6 more)

### Community 37 - "changeset.py (1)"
Cohesion: 0.14
Nodes (10): detect_axis(), fiscal_label(), _flag(), _month_end(), parse_period(), Period, _year(), test_ai_label_resolver_is_capped_and_memoised() (+2 more)

### Community 38 - "Company (1)"
Cohesion: 0.16
Nodes (23): ingest_results_xbrl(), test_comps_export_shows_each_company_basis(), test_facts_fall_back_to_standalone_when_company_files_no_consolidated(), test_glance_for_a_life_insurer_shows_premium_and_ratios(), quarter(), test_glance_lines_changes_and_derived_ebitda(), quarter(), test_latest_close_on_the_company_page_and_largest_first_on_the_desk() (+15 more)

### Community 39 - "desk.py (1)"
Cohesion: 0.16
Nodes (14): desk(), Desk, DeskRow, _movers(), _quarter_start(), recent_quarters(), SectorProgress, _sectors() (+6 more)

### Community 40 - "Latest Results Paging"
Cohesion: 0.17
Nodes (13): fetch_latest(), company(), list_client(), handler(), row(), test_empty_list_with_zero_total_is_not_truncated(), test_nse_capping_the_page_below_what_we_asked_is_truncation(), test_page_holding_every_row_is_not_truncated() (+5 more)

### Community 41 - "Router and Welcome"
Cohesion: 0.13
Nodes (18): greeting(), hasWelcomed(), markWelcomed(), queryClient, reducedMotion(), Stat(), useCountUp(), Welcome() (+10 more)

### Community 42 - "System Status and Alerts (1)"
Cohesion: 0.13
Nodes (12): raise_alert(), send_email(), send_telegram(), alert_channels(), alerts(), _mask(), test_alert(), AlertChannelsOut (+4 more)

### Community 43 - "test_ingest.py"
Cohesion: 0.13
Nodes (11): FeedWatcher, item_key(), parse_pub_date(), parse_rss(), RssItem, store_items(), test_parse_rss_and_item_key(), test_parse_rss_nse_pub_date() (+3 more)

### Community 44 - "Search and Reports UI"
Cohesion: 0.16
Nodes (17): api, CompanyIndexEntry, INDEX, renderSearch(), CompanySearch(), highlight(), CompanyIndex, escape() (+9 more)

### Community 45 - "ingest/pipeline.py"
Cohesion: 0.14
Nodes (11): Fact, _fact_key(), load_history(), revalidate_company(), rewrite_amounts(), scale_meta(), storage_key(), _jsonable() (+3 more)

### Community 46 - "changeset.py (2)"
Cohesion: 0.24
Nodes (11): build_change_set(), _list_adjacent_hardcodes(), _next_label(), Proposal, _propose_assumption(), _propose_horizon_extension(), ProposedItem, axis_for() (+3 more)

### Community 47 - "V11 Scale Check Tests"
Cohesion: 0.22
Nodes (14): HistoryFact, _company(), history(), quarter_file(), standalone_q2(), test_a_real_jump_reported_on_both_bases_passes(), test_amounts_100_times_too_small_are_corrected_when_both_signals_agree(), test_both_bases_slipped_together_are_corrected() (+6 more)

### Community 48 - "dataclasses (2)"
Cohesion: 0.18
Nodes (11): Embedder, store_chunks(), DocResult, _passing(), process_document(), process_documents(), kpis_for(), QueueRun (+3 more)

### Community 49 - "Layout and Theme"
Cohesion: 0.18
Nodes (17): SegmentThumb(), GROUPS, Item(), Layout(), NavItem, NO_SEARCH_BAR, readCollapsed(), SETTINGS (+9 more)

### Community 50 - "change_sets.py"
Cohesion: 0.22
Nodes (10): apply(), change_set(), _cs(), decide(), ChangeSet, apply_headless(), ApprovedItem, has_macros() (+2 more)

### Community 51 - "test_universe.py (2)"
Cohesion: 0.16
Nodes (10): fetch_index_sectors(), import_sector_worksheet(), load_sector_map(), parse_constituents(), _rank(), save_sector_map(), taxonomy_for_sector(), test_taxonomy_guess() (+2 more)

### Community 52 - "Company (2)"
Cohesion: 0.11
Nodes (8): demo(), test_alert_channels_and_test_messages_never_leak_secrets(), test_calendar_endpoint_scopes_to_the_watchlist(), test_discover_and_link(), test_peer_lists_and_the_comps_table(), test_search_company_page_and_watchlist(), test_template_upload_confirm_test_activate(), test_watchlist_rows_carry_growth_and_price()

### Community 53 - "dataclasses (3)"
Cohesion: 0.21
Nodes (12): batch_params(), build_prompt(), extract(), ExtractedKpi, Extraction, extraction_schema(), map_back(), _norm() (+4 more)

### Community 54 - "Events Schedule"
Cohesion: 0.24
Nodes (9): CalendarEvent, events(), _filed_results(), kind_of(), parse_description(), _item(), test_calendar_reschedule_watchlist_and_window(), test_parse_description() (+1 more)

### Community 55 - "dataclasses (4)"
Cohesion: 0.21
Nodes (7): LlmCall, Claude, ClaudeResult, RefusalError, request_hash(), resolve(), _schema()

### Community 56 - "XBRL Parser"
Cohesion: 0.20
Nodes (9): Context, _dedupe(), dims_hash(), _parse_context(), period_type(), _unit_label(), test_contexts_resolved_from_dates_not_ids(), test_dims_hash_is_order_independent() (+1 more)

### Community 57 - "Settings UI"
Cohesion: 0.31
Nodes (13): Segmented(), Skeleton(), filedAt(), Alerts(), ChannelRow(), Choice(), count(), DataStatus() (+5 more)

### Community 58 - "Polite HTTP Client (1) (2)"
Cohesion: 0.18
Nodes (5): FetchResult, identity_headers(), RateLimiter, _retryable(), test_identity_headers_keep_contact_out_of_user_agent()

### Community 59 - "FastAPI App"
Cohesion: 0.18
Nodes (5): health(), lifespan(), _storage_down(), _warm_up(), test_analyse_fails_fast_when_the_job_queue_is_down()

### Community 60 - "System Status and Alerts (2)"
Cohesion: 0.17
Nodes (12): data_counts(), prices_status(), _run(), _season(), status(), watcher_status(), DataCountsOut, JobRunOut (+4 more)

### Community 61 - "Watchlist Coverage"
Cohesion: 0.32
Nodes (8): add(), entries(), is_watched(), level(), remove(), _user(), Watchlist, test_watchlist_controls_coverage_level()

### Community 62 - "history.py (2)"
Cohesion: 0.24
Nodes (8): change(), _change(), _groups(), LineChange, _quarter_values(), Revision, revisions(), _when()

### Community 63 - "assumptions.py (2)"
Cohesion: 0.28
Nodes (6): build(), _derived_rows(), DriverSpec, _fill(), Line, TemplateSpec

### Community 64 - "Workbook Engine Design"
Cohesion: 0.17
Nodes (12): Change set and change items, Excel bridge (xlwings, Office.js later), Workbook fingerprint, Hidden tag (custom document property), Initiation pack, Roll-forward, Section 13 Model discovery and recognition, Section 14 Template onboarding (+4 more)

### Community 65 - "test_workbook.py (2)"
Cohesion: 0.30
Nodes (4): Company, CompanyIndex, normalise_name(), test_name_matching()

### Community 66 - "API Settings and Health"
Cohesion: 0.22
Nodes (4): jobs_available(), JobsAvailableOut, _probe(), queue_available()

### Community 67 - "Product Rules and Workflows"
Cohesion: 0.20
Nodes (5): Approval gate, Workflow 5 Quarterly model update, Workflow 6 Start coverage, Workflow 7 Template onboarding, Investor presentations via NSE announcements (proposed)

### Community 68 - "Universe and Sector Design"
Cohesion: 0.20
Nodes (9): Coverage levels (universe, numbers, deep), Excel Stocks data type (LSEG industry group), NSE Indices constituent lists, Results format / results_taxonomy (indas, banking, nbfc, insurance, life_insurance), Section 4.2 Sector classification precedence, Section 4 Company universe and coverage levels, Universe Loader, Watchlist (+1 more)

### Community 69 - "Build Plan Phases"
Cohesion: 0.31
Nodes (9): Phase 0 Spike, Phase 1 Data layer, Phase 2 Builder and sync, Phase 3 Document AI, Phase 4 GenAI outputs, Phase 5 Discovery, IB outputs, polish, Section 26 Build plan, Section 2 Requirements (F1-F20, NFRs) (+1 more)

### Community 71 - "testbuild.py (2)"
Cohesion: 0.36
Nodes (3): CheckResult, CheckRun, run_checks()

### Community 72 - "Results Collection Design"
Cohesion: 0.25
Nodes (5): NSE request limit and watchdog, Workflow 1 Results collection, Newest filed value wins (restatements), How it works pipeline (ingest, XBRL, facts, approve, drafts), Status v0.0.5 (data layer on real NSE data)

### Community 73 - "Object Storage (3)"
Cohesion: 0.50
Nodes (5): bse(), main(), nse(), remaining(), _write()

### Community 74 - "design_docx.py (1) (2)"
Cohesion: 0.33
Nodes (3): initiation_docx(), note_docx(), summary_pptx()

### Community 75 - "test_ib.py (1) (2)"
Cohesion: 0.38
Nodes (4): refresh(), sub(), Replacement, test_pitch_placeholders_replaced_and_logged()

### Community 77 - "Example NBFC Mapping"
Cohesion: 0.38
Nodes (7): Example NBFC quarterly template mapping, checks (balance sheet difference expect 0), drivers (loan_yield actual to forecast), kpi:gold_loan_aum row, period_axis (Period header row, A/E flag row), units default_transform div:10000000 (INR to crore), xbrl source rows (RevenueFromOperations, OtherIncome, FinanceCosts, ProfitLossForPeriod)

### Community 78 - "test_ib.py (4)"
Cohesion: 0.33
Nodes (3): peers(), PeerOut, suggest_peers()

### Community 79 - "dataclasses (5)"
Cohesion: 0.53
Nodes (4): as_prompt_text(), parse_turns(), _role(), Turn

### Community 80 - "Grounded GenAI Design"
Cohesion: 0.33
Nodes (5): Claude API usage policy (Claude.create, fallbacks, Batch), Grounding and style check, Workflow 8 Documents, KPIs and reports, Reports set-up (quarterly update, initiating coverage), Section-by-section report runner (proposed)

### Community 81 - "API Schemas (1) (2)"
Cohesion: 0.40
Nodes (4): results_calendar(), CalendarEventOut, CalendarOut, UnscheduledOut

### Community 82 - "Office Add-in Task Pane (1) (2)"
Cohesion: 0.60
Nodes (4): Item, readTag(), select(), TaskPane()

### Community 87 - "Deployment today and planned hosting"
Cohesion: 0.67
Nodes (3): Deployment today and planned hosting, Scheduler in Docker (Celery beat, worker, Redis), Hosting in India blocker

### Community 88 - "Job schedule by results season"
Cohesion: 0.67
Nodes (3): Job schedule by results season, Workflow 9 Events, results calendar and alerts, Results watcher by SEBI season

### Community 91 - "Call recordings transcription (Whisper)"
Cohesion: 0.67
Nodes (3): Call recordings transcription (Whisper), Live earnings-call listener (future scope), Section 11 Document pipeline

### Community 92 - "Section 22.5 Source control, CI/CD and G"
Cohesion: 0.67
Nodes (3): GitHub read-only mirror via mirror_to_github CI job, GitLab Free as source of truth, Section 22.5 Source control, CI/CD and GitHub mirroring

### Community 93 - "Phase tracker tables"
Cohesion: 0.67
Nodes (3): Dev log, What stops the next phases, Phase tracker tables

## Knowledge Gaps
- **89 isolated node(s):** `Analekh (system)`, `Technical Design Document v0.0.5`, `CI job dependency_audit (OSV-Scanner)`, `CI job golden_set`, `Components and data flow diagram` (+84 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 640 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **35 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_month_end()` connect `changeset.py (1)` to `Results Calendar UI`?**
  _High betweenness centrality (0.242) - this node is a cross-community bridge._
- **Are the 62 inferred relationships involving `Company` (e.g. with `suggest_peers()` and `start_coverage()`) actually correct?**
  _`Company` has 62 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Analekh (system)`, `Technical Design Document v0.0.5`, `CI job dependency_audit (OSV-Scanner)` to the rest of the system?**
  _89 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CI and Compose Deploy` be split into smaller, more focused modules?**
  _Cohesion score 0.05764411027568922 - nodes in this community are weakly interconnected._
- **Why does `Company` connect `test_workbook.py (2)` to `tasks.py`, `test_builder.py`, `Golden Set Runner`, `Analekh CLI`, `ToolExecutor`, `db/models.py (1)`, `NSE Integrated Filings`, `Companies API (1) (1)`, `bhavcopy.py`, `Filing (1)`, `test_universe.py (1)`, `test_ib.py (1) (1)`, `test_ib.py (2)`, `db/models.py (2)`, `Polite HTTP Client (1) (1)`, `history.py (1)`, `Company (1)`, `desk.py (1)`, `Latest Results Paging`, `System Status and Alerts (1)`, `test_ingest.py`, `ingest/pipeline.py`, `V11 Scale Check Tests`, `dataclasses (2)`, `test_universe.py (2)`, `Company (2)`, `Events Schedule`, `System Status and Alerts (2)`, `Watchlist Coverage`, `history.py (2)`, `Object Storage (3)`, `test_ib.py (4)`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `Filing` (e.g. with `process_documents()` and `revalidate_company()`) actually correct?**
  _`Filing` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Should `CompanyPage.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.07832080200501253 - nodes in this community are weakly interconnected._