# Graph Report - Kaushal-Analekh  (2026-10-22)

## Corpus Check
- 257 files · ~194,904 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 10, .example 1, .ini 1)

## Summary
- 2727 nodes · 8246 edges · 131 communities (97 shown, 34 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 719 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4e4ff7a1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- CompanyPage.tsx (1)
- @tanstack/react-query
- CI and Compose Deploy
- routers/models.py
- changeset.py
- test_universe.py
- get_settings()
- test_auth_reset.py (1) (1)
- design_docx.py (1) (1) (1)
- Design Doc Core Components
- Mapping
- Reports.tsx (2)
- Polite HTTP Client (1) (1) (1) (1) (1)
- Object Storage (1)
- router.tsx
- API Schemas (1) (1) (1) (1) (1) (1)
- NSE Integrated Filings
- Companies API (1) (1) (1)
- stocks_workbook.py
- desk.py
- Office Add-in Task Pane (1) (1)
- login
- reader.py (1)
- passwords.py (1) (1)
- test_public_load.py
- test_upload_limit.py
- test_api.py (1) (1) (1)
- rules.py
- ib/comps.py
- db/models.py (1)
- sqlalchemy
- ValidationContext
- test_api_tokens.py
- Golden Set Runner (1) (1)
- api
- test_ingest.py
- Results Calendar UI
- changeset.py
- bhavcopy.py
- Results History UI
- test_login_ip_limit.py
- test_docs.py
- test_builder.py (1)
- Latest Results Paging
- io
- analekh/cli.py
- test-utils.tsx
- Results Seasons (1)
- test_users_api.py
- test_queues.py
- db/models.py
- typing
- public.py
- docs/pipeline.py
- test_auth_api.py
- ToolExecutor (1) (1)
- test_ib.py
- system.py
- User
- test_scale_check.py
- statusPanels.tsx
- create_report
- pytest
- parser.py
- auth.py
- routers/comps.py
- sectors.py
- audio.py (1)
- extract.py
- ToolExecutor (1) (2)
- ingest/pipeline.py
- Watchlist Coverage
- test_modelsync.py (1) (1) (2)
- CompanyPage.tsx (2)
- diagram_panels.py
- Workbook Engine Design
- Sign-in, roles, upload limit and model locks: design
- PageText
- Product Rules and Workflows
- Universe and Sector Design
- FeedItem
- Build Plan Phases
- prices.py
- Results Collection Design
- test_ib.py (1) (5)
- revalidate_company
- config.py
- Example NBFC Mapping
- calc.py
- create_user
- transcripts.py
- Grounded GenAI Design
- test_send_mail_uses_smtp_settings_and_never_logs_body
- _Scope
- taskpane.tsx
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
1. `Company` - 131 edges
2. `get_settings()` - 110 edges
3. `Filing` - 70 edges
4. `User` - 57 edges
5. `PoliteClient` - 55 edges
6. `ValidationContext` - 53 edges
7. `ingest_results_xbrl()` - 53 edges
8. `parse_instance()` - 52 edges
9. `get()` - 48 edges
10. `Mapping` - 42 edges

## Surprising Connections (you probably didn't know these)
- `User` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `User` --references--> `Task 4: Auth router, cookie, CSRF, role dependencies, protect every router`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `User` --references--> `11. Constraints and facts from the codebase`  [INFERRED]
  analekh/db/models.py → docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md
- `db()` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  tests/conftest.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `Badge()` --references--> `Task 11: Admin area (own routes and shell), personal settings`  [INFERRED]
  web/src/components/ui.tsx → docs/superpowers/plans/2026-10-22-auth-stage-1.md

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

## Communities (131 total, 34 thin omitted)

### Community 0 - "CompanyPage.tsx (1)"
Cohesion: 0.12
Nodes (46): Change(), COSTS, fmtDate(), QuarterRail(), BasisCell(), BasisHeader(), MarketCapCell(), ProfitCell() (+38 more)

### Community 1 - "@tanstack/react-query"
Cohesion: 0.07
Nodes (43): Task 10: Sign-in in the web app, AdminLayout(), ITEMS, Me, onSignedOut(), RequireSignIn(), ME_KEY, rememberReturnPath() (+35 more)

### Community 2 - "CI and Compose Deploy"
Cohesion: 0.06
Nodes (53): CLAUDE.md project guidance, production service api, production service beat, production service migrate (alembic), production service postgres, production service valkey, production service worker, staging service api (+45 more)

### Community 3 - "routers/models.py"
Cohesion: 0.12
Nodes (31): assumptions(), builds(), decide_assumptions(), discover_models(), download_version(), finalize(), link_model(), list_models() (+23 more)

### Community 4 - "changeset.py"
Cohesion: 0.10
Nodes (17): fill_history(), FillReport, write_drivers(), write_sources(), Written, axis_for(), find_row(), relabel() (+9 more)

### Community 5 - "test_universe.py"
Cohesion: 0.13
Nodes (23): universe_load(), refresh_universe(), _date(), _decimal(), ListedCompany, LoadSummary, _norm_header(), parse_equity_list() (+15 more)

### Community 6 - "get_settings()"
Cohesion: 0.12
Nodes (14): check_auth_switch(), _database_busy(), lifespan(), _storage_down(), _warm_up(), get_settings(), switch(), test_dev_identity_comes_from_settings() (+6 more)

### Community 7 - "test_auth_reset.py (1) (1)"
Cohesion: 0.12
Nodes (22): send_mail(), confirm_reset(), _hash_code(), request_reset(), PasswordReset, Task 5: Mail to any recipient and the reset-code flow, _code(), sent() (+14 more)

### Community 8 - "design_docx.py (1) (1) (1)"
Cohesion: 0.13
Nodes (17): add(), caption(), cell_border(), cells(), code_block(), figure(), heading(), inline() (+9 more)

### Community 9 - "Design Doc Core Components"
Cohesion: 0.05
Nodes (43): Appendices A-H (DDL, mapping, CI, deps, glossary), Backfill (results-backfill, --history, watchdog), NSE daily bhavcopy, Celery beat scheduler in Docker, Company page with results history table, Feed Watcher, NSE financial-results list (history from March 2023), GenAI tools (get_facts, get_kpis, get_model_values, search_filings, get_prices, calc) (+35 more)

### Community 10 - "Mapping"
Cohesion: 0.09
Nodes (28): Proposal, propose(), _propose_one(), _q(), _revenue_row(), _series(), resolve_row(), Resolved (+20 more)

### Community 11 - "Reports.tsx (2)"
Cohesion: 0.08
Nodes (37): Task 11: Admin area (own routes and shell), personal settings, ApiTokenCreated, Segmented(), SegmentThumb(), ADMIN, GROUPS, Item(), Layout() (+29 more)

### Community 12 - "Polite HTTP Client (1) (1) (1) (1) (1)"
Cohesion: 0.10
Nodes (31): DisallowedHostError, FetchResult, identity_headers(), path_allowed(), PoliteClient, RateLimiter, _retryable(), IncompleteXbrl (+23 more)

### Community 13 - "Object Storage (1)"
Cohesion: 0.08
Nodes (14): LocalStore, pack(), S3Store, sha256(), StorageUnavailable, unpack(), compress(), main() (+6 more)

### Community 14 - "router.tsx"
Cohesion: 0.13
Nodes (37): CompanyDetail, WatchlistEntry, Icon(), IconName, PATHS, EventRow(), ResultsHistory(), Avatar() (+29 more)

### Community 15 - "API Schemas (1) (1) (1) (1) (1) (1)"
Cohesion: 0.05
Nodes (44): results_calendar(), jobs_available(), AlertOut, AssumptionDecision, AssumptionDecisions, AssumptionOut, CalendarEventOut, CalendarOut (+36 more)

### Community 16 - "NSE Integrated Filings"
Cohesion: 0.08
Nodes (25): refused(), _date(), _download_and_ingest(), _error(), _fetch(), fetch_history(), fetch_latest(), FetchOutcome (+17 more)

### Community 17 - "Companies API (1) (1) (1)"
Cohesion: 0.09
Nodes (27): company_or_404(), job(), analyse(), company_glance(), company_history(), company_history_xlsx(), company_index(), company_price() (+19 more)

### Community 18 - "stocks_workbook.py"
Cohesion: 0.44
Nodes (5): bse(), main(), nse(), remaining(), _write()

### Community 19 - "desk.py"
Cohesion: 0.19
Nodes (12): desk(), Desk, DeskRow, _movers(), _quarter_start(), recent_quarters(), SectorProgress, _sectors() (+4 more)

### Community 20 - "Office Add-in Task Pane (1) (1)"
Cohesion: 0.05
Nodes (45): AdminUserRow, AlertChannels, AlertEntry, ApiError, ApiToken, Assumption, BuildOut, Calendar (+37 more)

### Community 21 - "login"
Cohesion: 0.16
Nodes (32): _hash_token(), login(), LoginResult, logout(), _now(), revoke_user_sessions(), set_password(), user_for_token() (+24 more)

### Community 22 - "reader.py (1)"
Cohesion: 0.14
Nodes (17): Finding, scan_hygiene(), LabelMatch, match_label(), normalise(), _cell_kind(), CheckInfo, _combine() (+9 more)

### Community 23 - "passwords.py (1) (1)"
Cohesion: 0.16
Nodes (11): hash_password(), normalize_email(), PasswordTooLong, verify_password(), _user(), Task 2: Password hashing and input validation, test_injection_strings_and_junk_are_invalid_emails(), test_none_hash_still_does_work() (+3 more)

### Community 24 - "test_public_load.py"
Cohesion: 0.14
Nodes (11): _cal(), calls(), test_a_rejected_range_is_not_cached_and_costs_no_query(), test_cache_is_bounded(), test_cache_seconds_comes_from_settings(), test_calendar_cache_expires(), test_different_ranges_are_cached_separately(), test_exhausted_pool_answers_503_quickly() (+3 more)

### Community 25 - "test_upload_limit.py"
Cohesion: 0.10
Nodes (21): _out(), read_upload_limit(), set_upload_limit(), UploadLimitIn, UploadLimitOut, get_max_upload_bytes(), mb(), read_limited() (+13 more)

### Community 26 - "test_api.py (1) (1) (1)"
Cohesion: 0.09
Nodes (33): health(), Watchlist, ingest_results_xbrl(), IngestResult, store(), client(), demo(), test_alert_channels_and_test_messages_never_leak_secrets() (+25 more)

### Community 27 - "rules.py"
Cohesion: 0.10
Nodes (23): _identity(), is_year_end(), _power(), _quarters(), rescaled(), RuleResult, scaled_decimals(), tolerance() (+15 more)

### Community 28 - "ib/comps.py"
Cohesion: 0.08
Nodes (26): Fact, files_consolidated(), change(), _day(), glance(), value(), Glance, is_financial() (+18 more)

### Community 29 - "db/models.py (1)"
Cohesion: 0.10
Nodes (26): start(), activate_template(), confirm(), list_templates(), _template(), test_build(), upload_template(), BuildOut (+18 more)

### Community 30 - "sqlalchemy"
Cohesion: 0.10
Nodes (9): downgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+1 more)

### Community 31 - "ValidationContext"
Cohesion: 0.22
Nodes (29): KpiValue, validate(), ValidationContext, parse_instance(), main(), by_rule(), _quarter(), test_bank_identities_include_provisions() (+21 more)

### Community 32 - "test_api_tokens.py"
Cohesion: 0.11
Nodes (18): create(), list_tokens(), revoke(), TokenCreated, TokenIn, TokenOut, create_api_token(), _hash() (+10 more)

### Community 33 - "Golden Set Runner (1) (1)"
Cohesion: 0.09
Nodes (26): build_sheet(), file_name(), fy_label(), GoldenReport, guess_unit(), import_sheet(), ImportSummary, Mismatch (+18 more)

### Community 34 - "api"
Cohesion: 0.10
Nodes (27): api, CompanyIndexEntry, INDEX, renderSearch(), CompanySearch(), highlight(), Suggestion, CompanyIndex (+19 more)

### Community 35 - "test_ingest.py"
Cohesion: 0.10
Nodes (15): Company, FeedWatcher, item_key(), parse_pub_date(), parse_rss(), RssItem, store_items(), CompanyIndex (+7 more)

### Community 36 - "Results Calendar UI"
Cohesion: 0.21
Nodes (27): DayProps, DayStrip(), KIND_LABEL, KIND_TONE, KindChip(), KindFilter, MonthView(), reducedMotion() (+19 more)

### Community 37 - "changeset.py"
Cohesion: 0.09
Nodes (26): ChangeItem, quarter_start(), SourceValue, build_change_set(), _list_adjacent_hardcodes(), _next_label(), Proposal, _propose_assumption() (+18 more)

### Community 38 - "bhavcopy.py"
Cohesion: 0.11
Nodes (22): Price, BhavRow, _dec(), fetch(), latest_stored(), load_day(), market_cap(), paid_up_capital() (+14 more)

### Community 39 - "Results History UI"
Cohesion: 0.15
Nodes (26): Filing, History, HistoryLine, Revision, BOLD, cell(), FilingDetails(), headMark() (+18 more)

### Community 40 - "test_login_ip_limit.py"
Cohesion: 0.13
Nodes (16): clear(), _prune(), record_failure(), retry_after(), tracked(), watch(), _fresh(), _login() (+8 more)

### Community 41 - "test_docs.py"
Cohesion: 0.25
Nodes (7): chunk_pages(), TextChunk, _ocr(), read_pages(), subset(), test_chunks_keep_page_numbers(), test_read_and_subset_pdf()

### Community 42 - "test_builder.py (1)"
Cohesion: 0.12
Nodes (19): _api(), apply(), link(), scan(), hints_for(), iter_workbooks(), scan(), apply() (+11 more)

### Community 43 - "Latest Results Paging"
Cohesion: 0.16
Nodes (18): next_page_size(), company(), list_client(), handler(), row(), test_a_damaged_summary_falls_back_to_the_default(), test_a_full_run_goes_back_to_the_default(), test_a_truncated_run_doubles_the_size_for_the_next() (+10 more)

### Community 44 - "io"
Cohesion: 0.11
Nodes (21): apply(), change_set(), _cs(), decide(), Decisions, ChangeSet, TemplateTest, apply_headless() (+13 more)

### Community 45 - "analekh/cli.py"
Cohesion: 0.07
Nodes (34): backfill(), build(), _company(), create_admin(), golden_import(), golden_sheet(), golden_test(), prices() (+26 more)

### Community 46 - "test-utils.tsx"
Cohesion: 0.10
Nodes (12): LIMIT, quiet, USERS, TOKENS, ADMIN, ANALYST, Call, Handler (+4 more)

### Community 47 - "Results Seasons (1)"
Cohesion: 0.14
Nodes (18): deadline_days(), next_ask(), next_season(), previous_start(), Season, _season(), season_for(), _seasons_around() (+10 more)

### Community 48 - "test_users_api.py"
Cohesion: 0.15
Nodes (14): get_store(), adopt_local(), AuditEntry, Base, Task 6: User administration, template permissions, create-admin CLI, admin(), analyst(), _sign_in() (+6 more)

### Community 49 - "test_queues.py"
Cohesion: 0.15
Nodes (19): Filing, fetch_results(), bulk_fetch_results(), bad_date_instance(), client_for(), company(), feed_item(), row() (+11 more)

### Community 50 - "db/models.py"
Cohesion: 0.08
Nodes (15): auth_is_off(), _bearer_user(), _dev_user(), get_current(), require_admin(), get_report(), LlmCall, Report (+7 more)

### Community 51 - "typing"
Cohesion: 0.20
Nodes (4): ClaudeResult, RefusalError, request_hash(), to_json()

### Community 52 - "public.py"
Cohesion: 0.11
Nodes (17): auth_status(), cache_size(), _cached(), calendar(), build(), clear_cache(), PublicCalendarOut, PublicEventOut (+9 more)

### Community 53 - "docs/pipeline.py"
Cohesion: 0.14
Nodes (13): Chunk, Document, Embedder, get_embedder(), LocalEmbedder, store_chunks(), DocResult, _passing() (+5 more)

### Community 54 - "test_auth_api.py"
Cohesion: 0.14
Nodes (21): Task 4: Auth router, cookie, CSRF, role dependencies, protect every router, _login(), raw(), test_access_log_has_no_secrets(), test_admin_only_dependency_refuses_analyst(), test_cookie_is_secure_outside_dev(), test_disabled_user_session_gets_401(), test_every_non_public_route_requires_session() (+13 more)

### Community 55 - "ToolExecutor (1) (1)"
Cohesion: 0.16
Nodes (14): check(), collect_values(), _decimals(), extract_numbers(), GroundingResult, matches(), ReportRun, run_report() (+6 more)

### Community 56 - "test_ib.py"
Cohesion: 0.09
Nodes (32): book_value(), build_table(), CompInputs, CompRow, compute(), four_quarters(), gather(), _metric() (+24 more)

### Community 57 - "system.py"
Cohesion: 0.08
Nodes (20): raise_alert(), send_email(), send_telegram(), alert_channels(), alerts(), data_counts(), _mask(), prices_status() (+12 more)

### Community 58 - "User"
Cohesion: 0.16
Nodes (20): _session_user(), _active_admins(), _audit(), create(), _get(), list_users(), _out(), PasswordIn (+12 more)

### Community 59 - "test_scale_check.py"
Cohesion: 0.22
Nodes (14): HistoryFact, _company(), history(), quarter_file(), standalone_q2(), test_a_real_jump_reported_on_both_bases_passes(), test_amounts_100_times_too_small_are_corrected_when_both_signals_agree(), test_both_bases_slipped_together_are_corrected() (+6 more)

### Community 60 - "statusPanels.tsx"
Cohesion: 0.22
Nodes (18): AlertTest, JobRun, Status, UploadLimit, Skeleton(), filedAt(), AdminSettings(), mb() (+10 more)

### Community 61 - "create_report"
Cohesion: 0.29
Nodes (3): create_report(), ReportRequest, ModelReader

### Community 62 - "pytest"
Cohesion: 0.22
Nodes (13): NotAPdf, make_pdf(), company(), count(), store_it(), test_a_feed_item_with_an_error_page_is_given_up_at_once_and_the_queue_goes_on(), handler(), test_a_file_that_is_not_a_pdf_is_refused_and_nothing_is_stored() (+5 more)

### Community 63 - "parser.py"
Cohesion: 0.15
Nodes (12): Context, _dedupe(), dims_hash(), _parse_context(), period_type(), _unit_label(), test_contexts_resolved_from_dates_not_ids(), test_dims_hash_is_order_independent() (+4 more)

### Community 64 - "auth.py"
Cohesion: 0.17
Nodes (10): _cookie_secure(), login(), LoginIn, logout(), me(), MeOut, reset_confirm(), reset_request() (+2 more)

### Community 65 - "routers/comps.py"
Cohesion: 0.11
Nodes (22): _commit(), comps(), comps_table(), create_peer_list(), delete_peer_list(), _list_or_404(), _name(), peer_lists() (+14 more)

### Community 66 - "sectors.py"
Cohesion: 0.13
Nodes (15): universe_sectors(), apply_sectors(), fetch_index_sectors(), import_sector_worksheet(), import_stocks_workbook(), load_sector_map(), _rank(), refresh_sectors() (+7 more)

### Community 67 - "audio.py (1)"
Cohesion: 0.21
Nodes (8): _add_cuda_dll_dirs(), AudioTranscript, _clock(), _has_cuda(), Segment, transcribe(), 5. Security requirements (hard rules), test_audio_transcript_text_carries_timestamps()

### Community 68 - "extract.py"
Cohesion: 0.20
Nodes (13): Kpi, batch_params(), build_prompt(), extract(), ExtractedKpi, Extraction, extraction_schema(), map_back() (+5 more)

### Community 69 - "ToolExecutor (1) (2)"
Cohesion: 0.24
Nodes (4): qa(), QaRequest, ToolExecutor, test_tool_executor_looks_companies_up_like_everywhere_else()

### Community 70 - "ingest/pipeline.py"
Cohesion: 0.12
Nodes (18): FeedItem, BackfillSummary, run_backfill(), check_pdf(), classify_announcement(), _gone(), pending_feed_items(), process_feed_item() (+10 more)

### Community 71 - "Watchlist Coverage"
Cohesion: 0.32
Nodes (6): add(), is_watched(), level(), remove(), _user(), test_watchlist_controls_coverage_level()

### Community 73 - "CompanyPage.tsx (2)"
Cohesion: 0.19
Nodes (16): CompRow, CompsTable, PeerList, AS_FLAG, BASES, Basis, Blank(), Comps() (+8 more)

### Community 74 - "diagram_panels.py"
Cohesion: 0.13
Nodes (5): main(), _graphify_python(), install_hooks(), main(), _triggered_by_rebuild()

### Community 75 - "Workbook Engine Design"
Cohesion: 0.17
Nodes (12): Change set and change items, Excel bridge (xlwings, Office.js later), Workbook fingerprint, Hidden tag (custom document property), Initiation pack, Roll-forward, Section 13 Model discovery and recognition, Section 14 Template onboarding (+4 more)

### Community 76 - "Sign-in, roles, upload limit and model locks: design"
Cohesion: 0.07
Nodes (26): get_user(), Global Constraints, Review Focus, Self-review notes, Sign-in, Roles and Upload Limit (Stage 1) Implementation Plan, Task 12: Records and end-to-end check, Task 1: Tables, config and dependency, Task 7: Upload limit (+18 more)

### Community 77 - "PageText"
Cohesion: 0.31
Nodes (6): PageScore, score_page(), select_pages(), PageText, test_classifier_selects_kpi_and_statement_pages(), test_map_back_translates_pages_and_checks_quotes()

### Community 78 - "Product Rules and Workflows"
Cohesion: 0.20
Nodes (5): Approval gate, Workflow 5 Quarterly model update, Workflow 6 Start coverage, Workflow 7 Template onboarding, Investor presentations via NSE announcements (proposed)

### Community 79 - "Universe and Sector Design"
Cohesion: 0.20
Nodes (9): Coverage levels (universe, numbers, deep), Excel Stocks data type (LSEG industry group), NSE Indices constituent lists, Results format / results_taxonomy (indas, banking, nbfc, insurance, life_insurance), Section 4.2 Sector classification precedence, Section 4 Company universe and coverage levels, Universe Loader, Watchlist (+1 more)

### Community 80 - "FeedItem"
Cohesion: 0.24
Nodes (9): CalendarEvent, events(), _filed_results(), kind_of(), parse_description(), _item(), test_calendar_reschedule_watchlist_and_window(), test_parse_description() (+1 more)

### Community 81 - "Build Plan Phases"
Cohesion: 0.31
Nodes (9): Phase 0 Spike, Phase 1 Data layer, Phase 2 Builder and sync, Phase 3 Document AI, Phase 4 GenAI outputs, Phase 5 Discovery, IB outputs, polish, Section 26 Build plan, Section 2 Requirements (F1-F20, NFRs) (+1 more)

### Community 82 - "prices.py"
Cohesion: 0.29
Nodes (7): watchlist(), WatchlistEntryOut, entries(), _change(), LastClose, latest_price(), latest_prices()

### Community 83 - "Results Collection Design"
Cohesion: 0.25
Nodes (5): NSE request limit and watchdog, Workflow 1 Results collection, Newest filed value wins (restatements), How it works pipeline (ingest, XBRL, facts, approve, drafts), Status v0.0.5 (data layer on real NSE data)

### Community 84 - "test_ib.py (1) (5)"
Cohesion: 0.33
Nodes (3): initiation_docx(), note_docx(), summary_pptx()

### Community 85 - "revalidate_company"
Cohesion: 0.12
Nodes (8): _fact_key(), load_history(), revalidate_company(), rewrite_amounts(), scale_meta(), _jsonable(), ValidationReport, detect_taxonomy()

### Community 86 - "config.py"
Cohesion: 0.12
Nodes (7): Settings, _preflight(), test_a_foreign_origin_is_not_allowed(), test_defaults_name_127_0_0_1_not_localhost(), test_localhost_is_no_longer_allowed_by_default(), test_origins_come_from_the_environment(), test_the_web_app_origin_is_allowed_with_credentials()

### Community 87 - "Example NBFC Mapping"
Cohesion: 0.38
Nodes (7): Example NBFC quarterly template mapping, checks (balance sheet difference expect 0), drivers (loan_yield actual to forecast), kpi:gold_loan_aum row, period_axis (Period header row, A/E flag row), units default_transform div:10000000 (INR to crore), xbrl source rows (RevenueFromOperations, OtherIncome, FinanceCosts, ProfitLossForPeriod)

### Community 88 - "calc.py"
Cohesion: 0.39
Nodes (4): calc(), CalcError, _eval(), test_calc_is_exact_and_safe()

### Community 89 - "create_user"
Cohesion: 0.29
Nodes (6): _by_email(), create_user(), user(), committed_user(), user(), test_create_user_validates_role_and_email()

### Community 90 - "transcripts.py"
Cohesion: 0.43
Nodes (5): as_prompt_text(), parse_turns(), _role(), Turn, test_transcript_roles()

### Community 91 - "Grounded GenAI Design"
Cohesion: 0.33
Nodes (5): Claude API usage policy (Claude.create, fallbacks, Batch), Grounding and style check, Workflow 8 Documents, KPIs and reports, Reports set-up (quarterly update, initiating coverage), Section-by-section report runner (proposed)

### Community 94 - "taskpane.tsx"
Cohesion: 0.47
Nodes (4): Item, readTag(), select(), TaskPane()

### Community 100 - "Deployment today and planned hosting"
Cohesion: 0.67
Nodes (3): Deployment today and planned hosting, Scheduler in Docker (Celery beat, worker, Redis), Hosting in India blocker

### Community 101 - "Job schedule by results season"
Cohesion: 0.67
Nodes (3): Job schedule by results season, Workflow 9 Events, results calendar and alerts, Results watcher by SEBI season

### Community 104 - "Call recordings transcription (Whisper)"
Cohesion: 0.67
Nodes (3): Call recordings transcription (Whisper), Live earnings-call listener (future scope), Section 11 Document pipeline

### Community 105 - "Section 22.5 Source control, CI/CD and G"
Cohesion: 0.67
Nodes (3): GitHub read-only mirror via mirror_to_github CI job, GitLab Free as source of truth, Section 22.5 Source control, CI/CD and GitHub mirroring

### Community 106 - "Phase tracker tables"
Cohesion: 0.67
Nodes (3): Dev log, What stops the next phases, Phase tracker tables

## Knowledge Gaps
- **89 isolated node(s):** `Analekh (system)`, `Technical Design Document v0.0.5`, `Scheduler in Docker (Celery beat, worker, Redis)`, `Hosting in India blocker`, `Workflow 9 Events, results calendar and alerts` (+84 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 805 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Task 10: Sign-in in the web app` connect `@tanstack/react-query` to `auth.py`, `Sign-in, roles, upload limit and model locks: design`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `Company` (e.g. with `company_or_404()` and `company_index()`) actually correct?**
  _`Company` has 67 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Analekh (system)`, `Technical Design Document v0.0.5`, `Scheduler in Docker (Celery beat, worker, Redis)` to the rest of the system?**
  _89 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CompanyPage.tsx (1)` be split into smaller, more focused modules?**
  _Cohesion score 0.12299091544374563 - nodes in this community are weakly interconnected._
- **Why does `_month_end()` connect `changeset.py` to `Results Calendar UI`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `Filing` (e.g. with `filings()` and `watchlist()`) actually correct?**
  _`Filing` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Should `@tanstack/react-query` be split into smaller, more focused modules?**
  _Cohesion score 0.07320024198427103 - nodes in this community are weakly interconnected._