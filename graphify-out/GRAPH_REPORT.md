# Graph Report - Kaushal-Analekh  (2026-10-22)

## Corpus Check
- 275 files · ~200,243 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 10, .example 1, .ini 1)

## Summary
- 2781 nodes · 8300 edges · 129 communities (93 shown, 36 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 683 edges (avg confidence: 0.92)
- Token cost: 406,493 input · 0 output

## Community Hubs (Navigation)
- CompanyPage.tsx (1)
- @tanstack/react-query
- CI and Compose Deploy
- main.py
- changeset.py
- Mapping
- deps.py
- dataclasses (1)
- Filing
- dataclasses (2)
- Golden Set Runner (1) (1)
- analekh/cli.py
- reader.py (1)
- Design Doc Core Components
- NSE Integrated Filings
- test_auth_reset.py (1) (1) (1)
- router.tsx
- login
- create_user
- routers/models.py
- API Schemas (1) (1) (1) (1) (1) (1) (1)
- db/models.py
- test_upload_limit.py
- auth.py
- Polite HTTP Client (1) (1) (1) (1) (1)
- rules.py
- test_public_load.py
- Reports.tsx (2)
- users.py
- tasks.py
- Office Add-in Task Pane (1) (1)
- ToolExecutor (1) (1) (1)
- ib/comps.py (1)
- test_auth_hardening.py
- ib/comps.py (2)
- design_docx.py (1) (1) (1)
- api
- test_api.py
- db/models.py (1)
- diagram_panels.py
- bhavcopy.py
- feeds.py
- test_queues.py
- parse_equity_list
- ValidationContext
- Results Calendar UI
- pytest
- stocks_workbook.py (1)
- sqlalchemy
- io
- statusPanels.tsx
- Results History UI
- Companies API (1) (1) (1) (1)
- Results Seasons (1)
- Latest Results Paging
- test-utils.tsx
- test_auth_api.py
- sectors.py
- system.py
- ToolExecutor
- desk
- ingest/pipeline.py
- FeedItem
- test_scale_check.py
- q2_instance()
- audio.py (1)
- Claude
- Sign-in, roles, upload limit and model locks: design
- Workbook Engine Design
- Review Focus
- test_cors.py
- Watchlist Coverage
- health.py
- Product Rules and Workflows
- Universe and Sector Design
- taskpane.tsx
- status
- stocks_workbook.py (2)
- Build Plan Phases
- datetime
- parser.py
- Results Collection Design
- desk.py
- Example NBFC Mapping
- test_auth_reset.py (1) (1) (2)
- ib/comps.py (3)
- Grounded GenAI Design
- API Schemas (1) (1) (1) (1) (1) (1) (2)
- last_close_day
- Companies API (1) (1) (1) (2)
- stocks_workbook.py (3)
- Companies API (1) (1) (1) (3)
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
1. `Company` - 129 edges
2. `get_settings()` - 117 edges
3. `Filing` - 65 edges
4. `PoliteClient` - 55 edges
5. `ValidationContext` - 53 edges
6. `ingest_results_xbrl()` - 53 edges
7. `parse_instance()` - 52 edges
8. `User` - 49 edges
9. `Mapping` - 41 edges
10. `login()` - 41 edges

## Surprising Connections (you probably didn't know these)
- `get_user()` --references--> `1. Intent`  [INFERRED]
  analekh/api/deps.py → docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md
- `User` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `User` --references--> `Task 4: Auth router, cookie, CSRF, role dependencies, protect every router`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `db()` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  tests/conftest.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `test_request_reply_same_for_unknown_email()` --references--> `Task 5: Mail to any recipient and the reset-code flow`  [INFERRED]
  tests/test_auth_reset.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md

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

## Communities (129 total, 36 thin omitted)

### Community 0 - "CompanyPage.tsx (1)"
Cohesion: 0.09
Nodes (62): CompRow, CompsTable, GlanceLine, PeerList, Change(), COSTS, fmtDate(), QuarterRail() (+54 more)

### Community 1 - "@tanstack/react-query"
Cohesion: 0.08
Nodes (42): Task 10: Sign-in in the web app, AdminLayout(), ITEMS, Me, onSignedOut(), RequireSignIn(), ME_KEY, rememberReturnPath() (+34 more)

### Community 2 - "CI and Compose Deploy"
Cohesion: 0.06
Nodes (53): CLAUDE.md project guidance, production service api, production service beat, production service migrate (alembic), production service postgres, production service valkey, production service worker, staging service api (+45 more)

### Community 3 - "main.py"
Cohesion: 0.07
Nodes (27): auth_is_off(), check_auth_switch(), _database_busy(), lifespan(), _storage_down(), _warm_up(), auth_status(), cache_size() (+19 more)

### Community 4 - "changeset.py"
Cohesion: 0.09
Nodes (27): fill_history(), write_drivers(), write_sources(), Written, build_change_set(), _list_adjacent_hardcodes(), _next_label(), Proposal (+19 more)

### Community 5 - "Mapping"
Cohesion: 0.09
Nodes (27): Proposal, propose(), _propose_one(), _q(), _revenue_row(), _series(), resolve_row(), Resolved (+19 more)

### Community 6 - "deps.py"
Cohesion: 0.08
Nodes (26): _bearer_user(), _dev_user(), get_current(), get_user(), require_admin(), _session_user(), create(), list_tokens() (+18 more)

### Community 7 - "dataclasses (1)"
Cohesion: 0.10
Nodes (26): discover_models(), Candidate, discover(), link(), Matcher, WorkbookHints, _api(), apply() (+18 more)

### Community 8 - "Filing"
Cohesion: 0.08
Nodes (28): watchlist(), Fact, Filing, files_consolidated(), _day(), glance(), value(), Glance (+20 more)

### Community 9 - "dataclasses (2)"
Cohesion: 0.10
Nodes (28): chunk_pages(), TextChunk, PageScore, score_page(), select_pages(), batch_params(), build_prompt(), extract() (+20 more)

### Community 10 - "Golden Set Runner (1) (1)"
Cohesion: 0.08
Nodes (26): build_sheet(), file_name(), fy_label(), GoldenReport, guess_unit(), import_sheet(), ImportSummary, Mismatch (+18 more)

### Community 11 - "analekh/cli.py"
Cohesion: 0.08
Nodes (28): backfill(), build(), _company(), create_admin(), golden_import(), golden_sheet(), golden_test(), prices() (+20 more)

### Community 12 - "reader.py (1)"
Cohesion: 0.08
Nodes (29): label_resolver(), resolve(), _schema(), column_letter_shift(), DependencyGraph, expand(), references(), fingerprint() (+21 more)

### Community 13 - "Design Doc Core Components"
Cohesion: 0.05
Nodes (43): Appendices A-H (DDL, mapping, CI, deps, glossary), Backfill (results-backfill, --history, watchdog), NSE daily bhavcopy, Celery beat scheduler in Docker, Company page with results history table, Feed Watcher, NSE financial-results list (history from March 2023), GenAI tools (get_facts, get_kpis, get_model_values, search_filings, get_prices, calc) (+35 more)

### Community 14 - "NSE Integrated Filings"
Cohesion: 0.08
Nodes (26): refused(), _date(), _download_and_ingest(), _error(), _fetch(), fetch_history(), FetchOutcome, _history_row() (+18 more)

### Community 15 - "test_auth_reset.py (1) (1) (1)"
Cohesion: 0.10
Nodes (26): send_mail(), normalize_email(), confirm_reset(), _hash_code(), request_reset(), _user(), PasswordReset, Task 5: Mail to any recipient and the reset-code flow (+18 more)

### Community 16 - "router.tsx"
Cohesion: 0.13
Nodes (37): Suggestion, Icon(), IconName, PATHS, EventRow(), Avatar(), AVATAR_HUES, Badge() (+29 more)

### Community 17 - "login"
Cohesion: 0.14
Nodes (35): _hash_token(), login(), LoginResult, logout(), _now(), purge_expired_sessions(), revoke_user_sessions(), set_password() (+27 more)

### Community 18 - "create_user"
Cohesion: 0.07
Nodes (29): _by_email(), create_user(), adopt_local(), AuditEntry, Task 6: User administration, template permissions, create-admin CLI, user(), user(), committed_user() (+21 more)

### Community 19 - "routers/models.py"
Cohesion: 0.12
Nodes (27): assumptions(), builds(), decide_assumptions(), download_version(), finalize(), link_model(), list_models(), _model() (+19 more)

### Community 20 - "API Schemas (1) (1) (1) (1) (1) (1) (1)"
Cohesion: 0.06
Nodes (39): AssumptionDecision, AssumptionDecisions, AssumptionOut, BuildOut, ChangeItemOut, ChangeSetOut, CompanyDetail, CompanyOut (+31 more)

### Community 21 - "db/models.py"
Cohesion: 0.09
Nodes (17): Base, ChangeItem, Chunk, Document, JobStatus, Kpi, LlmCall, Embedder (+9 more)

### Community 22 - "test_upload_limit.py"
Cohesion: 0.09
Nodes (22): get_store(), _out(), read_upload_limit(), set_upload_limit(), UploadLimitIn, UploadLimitOut, get_max_upload_bytes(), mb() (+14 more)

### Community 23 - "auth.py"
Cohesion: 0.07
Nodes (25): _cookie_secure(), login(), LoginIn, logout(), logout_everywhere(), me(), MeOut, reset_confirm() (+17 more)

### Community 24 - "Polite HTTP Client (1) (1) (1) (1) (1)"
Cohesion: 0.11
Nodes (25): DisallowedHostError, FetchResult, identity_headers(), path_allowed(), PoliteClient, RateLimiter, _retryable(), lookup() (+17 more)

### Community 25 - "rules.py"
Cohesion: 0.11
Nodes (21): _identity(), is_year_end(), _power(), _quarters(), RuleResult, tolerance(), _typical(), v10_kpi_conflict() (+13 more)

### Community 26 - "test_public_load.py"
Cohesion: 0.07
Nodes (17): get_engine(), _session_factory(), _attempt(), test_login_flood_gets_no_server_errors(), test_parallel_wrong_passwords_cannot_skip_the_pause(), _cal(), calls(), test_a_rejected_range_is_not_cached_and_costs_no_query() (+9 more)

### Community 27 - "Reports.tsx (2)"
Cohesion: 0.09
Nodes (35): ApiTokenCreated, ADMIN, GROUPS, Item(), Layout(), NavItem, NO_SEARCH_BAR, readCollapsed() (+27 more)

### Community 28 - "users.py"
Cohesion: 0.11
Nodes (24): _active_admins(), _audit(), create(), _get(), list_users(), _out(), PasswordIn, reset_password() (+16 more)

### Community 29 - "tasks.py"
Cohesion: 0.10
Nodes (21): session_scope(), BackfillSummary, run_backfill(), classify_announcement(), default_store(), record(), analyse_company(), backfill() (+13 more)

### Community 30 - "Office Add-in Task Pane (1) (1)"
Cohesion: 0.06
Nodes (35): AlertChannels, AlertEntry, ApiError, ApiToken, Assumption, BuildOut, Calendar, call() (+27 more)

### Community 31 - "ToolExecutor (1) (1) (1)"
Cohesion: 0.11
Nodes (19): calc(), CalcError, _eval(), check(), collect_values(), _decimals(), extract_numbers(), GroundingResult (+11 more)

### Community 32 - "ib/comps.py (1)"
Cohesion: 0.11
Nodes (24): book_value(), CompInputs, four_quarters(), gather(), _pct(), _sum(), refresh(), sub() (+16 more)

### Community 33 - "test_auth_hardening.py"
Cohesion: 0.07
Nodes (16): BodySizeLimit, counted_receive(), tracked_send(), max_body_bytes(), _refuse(), too_large_message(), _reply_seconds(), receive() (+8 more)

### Community 34 - "ib/comps.py (2)"
Cohesion: 0.13
Nodes (24): _commit(), comps(), comps_table(), create_peer_list(), delete_peer_list(), _list_or_404(), _name(), peer_lists() (+16 more)

### Community 35 - "design_docx.py (1) (1) (1)"
Cohesion: 0.10
Nodes (20): initiation_docx(), note_docx(), summary_pptx(), add(), caption(), cell_border(), cells(), code_block() (+12 more)

### Community 36 - "api"
Cohesion: 0.09
Nodes (28): api, CompanyDetail, CompanyIndexEntry, HistoryLine, WatchlistEntry, INDEX, renderSearch(), CompanySearch() (+20 more)

### Community 37 - "test_api.py"
Cohesion: 0.10
Nodes (25): health(), Company, ingest_results_xbrl(), store(), client(), demo(), test_alert_channels_and_test_messages_never_leak_secrets(), test_analyse_fails_fast_when_the_job_queue_is_down() (+17 more)

### Community 38 - "db/models.py (1)"
Cohesion: 0.15
Nodes (22): activate_template(), confirm(), list_templates(), _template(), test_build(), upload_template(), Template, TemplateTest (+14 more)

### Community 39 - "diagram_panels.py"
Cohesion: 0.10
Nodes (9): evaluate(), lookup(), _plain(), recalc_file(), main(), _graphify_python(), install_hooks(), main() (+1 more)

### Community 40 - "bhavcopy.py"
Cohesion: 0.13
Nodes (18): Price, BhavRow, _dec(), fetch(), latest_stored(), load_day(), market_cap(), paid_up_capital() (+10 more)

### Community 41 - "feeds.py"
Cohesion: 0.09
Nodes (14): FeedWatcher, item_key(), parse_pub_date(), parse_rss(), RssItem, store_items(), CompanyIndex, normalise_name() (+6 more)

### Community 42 - "test_queues.py"
Cohesion: 0.12
Nodes (22): process_documents(), fetch_results(), _gone(), pending_feed_items(), process_feed_items(), QueueRun, bad_date_instance(), client_for() (+14 more)

### Community 43 - "parse_equity_list"
Cohesion: 0.13
Nodes (24): _date(), _decimal(), ListedCompany, LoadSummary, _norm_header(), parse_equity_list(), refresh_from_nse(), upsert_universe() (+16 more)

### Community 44 - "ValidationContext"
Cohesion: 0.24
Nodes (29): KpiValue, validate(), ValidationContext, parse_instance(), main(), by_rule(), _quarter(), test_bank_identities_include_provisions() (+21 more)

### Community 45 - "Results Calendar UI"
Cohesion: 0.18
Nodes (30): CalendarEvent, CalendarKind, DayProps, DayStrip(), KIND_LABEL, KIND_TONE, KindChip(), KindFilter (+22 more)

### Community 46 - "pytest"
Cohesion: 0.12
Nodes (21): check_pdf(), NotAPdf, store_document(), storage_key(), test_new_user_starts_active_and_unblocked(), test_role_must_be_admin_or_analyst(), test_users_email_unique(), _user() (+13 more)

### Community 47 - "stocks_workbook.py (1)"
Cohesion: 0.10
Nodes (10): LocalStore, pack(), S3Store, sha256(), unpack(), compress(), main(), test_builtin_template_file_is_rebuilt_when_storage_lost_it() (+2 more)

### Community 48 - "sqlalchemy"
Cohesion: 0.10
Nodes (9): downgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+1 more)

### Community 49 - "io"
Cohesion: 0.14
Nodes (19): apply(), change_set(), _cs(), decide(), Decisions, ChangeSet, quarter_start(), SourceValue (+11 more)

### Community 50 - "statusPanels.tsx"
Cohesion: 0.14
Nodes (27): AdminUserRow, AlertTest, JobRun, Status, UploadLimit, UserChange, Skeleton(), filedAt() (+19 more)

### Community 51 - "Results History UI"
Cohesion: 0.17
Nodes (25): Filing, BOLD, cell(), FilingDetails(), headMark(), OtherFilings(), ResultsHistory(), SourceLinks() (+17 more)

### Community 52 - "Companies API (1) (1) (1) (1)"
Cohesion: 0.11
Nodes (19): company_or_404(), job(), analyse(), company_glance(), company_history(), company_history_xlsx(), company_price(), facts() (+11 more)

### Community 53 - "Results Seasons (1)"
Cohesion: 0.14
Nodes (20): watcher_status(), WatcherStatusOut, deadline_days(), next_ask(), next_season(), previous_start(), Season, _season() (+12 more)

### Community 54 - "Latest Results Paging"
Cohesion: 0.13
Nodes (21): fetch_latest(), is_truncated(), LatestOutcome, next_page_size(), company(), list_client(), handler(), row() (+13 more)

### Community 55 - "test-utils.tsx"
Cohesion: 0.10
Nodes (12): LIMIT, quiet, USERS, TOKENS, ADMIN, ANALYST, Call, Handler (+4 more)

### Community 56 - "test_auth_api.py"
Cohesion: 0.13
Nodes (21): Task 4: Auth router, cookie, CSRF, role dependencies, protect every router, _login(), raw(), test_access_log_has_no_secrets(), test_admin_only_dependency_refuses_analyst(), test_cookie_is_secure_outside_dev(), test_disabled_user_session_gets_401(), test_every_non_public_route_requires_session() (+13 more)

### Community 57 - "sectors.py"
Cohesion: 0.14
Nodes (14): universe_sectors(), apply_sectors(), fetch_index_sectors(), import_sector_worksheet(), import_stocks_workbook(), load_sector_map(), parse_constituents(), _rank() (+6 more)

### Community 58 - "system.py"
Cohesion: 0.13
Nodes (14): raise_alert(), send_email(), send_telegram(), alert_channels(), alerts(), _mask(), _season(), test_alert() (+6 more)

### Community 59 - "ToolExecutor"
Cohesion: 0.13
Nodes (9): create_report(), get_report(), qa(), QaRequest, ReportRequest, Report, ModelReader, ToolExecutor (+1 more)

### Community 60 - "desk"
Cohesion: 0.16
Nodes (14): results_desk(), desk(), Desk, DeskRow, _movers(), _quarter_start(), recent_quarters(), SectorProgress (+6 more)

### Community 61 - "ingest/pipeline.py"
Cohesion: 0.13
Nodes (10): _fact_key(), load_history(), revalidate_company(), rewrite_amounts(), scale_meta(), _jsonable(), rescaled(), scaled_decimals() (+2 more)

### Community 62 - "FeedItem"
Cohesion: 0.21
Nodes (12): FeedItem, Watchlist, CalendarEvent, events(), _filed_results(), kind_of(), parse_description(), test_calendar_endpoint_scopes_to_the_watchlist() (+4 more)

### Community 63 - "test_scale_check.py"
Cohesion: 0.22
Nodes (14): HistoryFact, _company(), history(), quarter_file(), standalone_q2(), test_a_real_jump_reported_on_both_bases_passes(), test_amounts_100_times_too_small_are_corrected_when_both_signals_agree(), test_both_bases_slipped_together_are_corrected() (+6 more)

### Community 64 - "q2_instance()"
Cohesion: 0.19
Nodes (16): dims_hash(), test_backfill_from_import_folder(), test_ingest_dedupes_and_handles_restatement(), test_v8_year_end_deadline_is_60_days(), test_contexts_resolved_from_dates_not_ids(), test_dims_hash_is_order_independent(), test_instants_and_meta(), test_period_type_buckets() (+8 more)

### Community 65 - "audio.py (1)"
Cohesion: 0.16
Nodes (10): _add_cuda_dll_dirs(), AudioTranscript, _clock(), _has_cuda(), Segment, transcribe(), 5. Security requirements (hard rules), engine() (+2 more)

### Community 66 - "Claude"
Cohesion: 0.22
Nodes (5): Claude, ClaudeResult, pdf_block(), RefusalError, request_hash()

### Community 67 - "Sign-in, roles, upload limit and model locks: design"
Cohesion: 0.14
Nodes (13): 10. Other screens still to be mocked, 12. Left to the builder, 13. Open decisions for the owner, 1. Intent, 2. Goals, 3. Non-goals and anti-goals, 4. Roles, 6. The sign-in screen (chosen mockup) (+5 more)

### Community 68 - "Workbook Engine Design"
Cohesion: 0.17
Nodes (12): Change set and change items, Excel bridge (xlwings, Office.js later), Workbook fingerprint, Hidden tag (custom document property), Initiation pack, Roll-forward, Section 13 Model discovery and recognition, Section 14 Template onboarding (+4 more)

### Community 69 - "Review Focus"
Cohesion: 0.15
Nodes (12): Global Constraints, Review Focus, Self-review notes, Sign-in, Roles and Upload Limit (Stage 1) Implementation Plan, Task 11: Admin area (own routes and shell), personal settings, Task 12: Records and end-to-end check, Task 1: Tables, config and dependency, Task 7: Upload limit (+4 more)

### Community 70 - "test_cors.py"
Cohesion: 0.24
Nodes (7): Settings, _preflight(), test_a_foreign_origin_is_not_allowed(), test_defaults_name_127_0_0_1_not_localhost(), test_localhost_is_no_longer_allowed_by_default(), test_origins_come_from_the_environment(), test_the_web_app_origin_is_allowed_with_credentials()

### Community 71 - "Watchlist Coverage"
Cohesion: 0.33
Nodes (7): add(), entries(), is_watched(), level(), remove(), _user(), test_watchlist_controls_coverage_level()

### Community 72 - "health.py"
Cohesion: 0.22
Nodes (4): jobs_available(), JobsAvailableOut, _probe(), queue_available()

### Community 73 - "Product Rules and Workflows"
Cohesion: 0.20
Nodes (5): Approval gate, Workflow 5 Quarterly model update, Workflow 6 Start coverage, Workflow 7 Template onboarding, Investor presentations via NSE announcements (proposed)

### Community 74 - "Universe and Sector Design"
Cohesion: 0.20
Nodes (9): Coverage levels (universe, numbers, deep), Excel Stocks data type (LSEG industry group), NSE Indices constituent lists, Results format / results_taxonomy (indas, banking, nbfc, insurance, life_insurance), Section 4.2 Sector classification precedence, Section 4 Company universe and coverage levels, Universe Loader, Watchlist (+1 more)

### Community 75 - "taskpane.tsx"
Cohesion: 0.36
Nodes (9): get(), Item, readTag(), readToken(), select(), SignedOut, TaskPane(), TokenForm() (+1 more)

### Community 76 - "status"
Cohesion: 0.22
Nodes (8): data_counts(), prices_status(), _run(), status(), DataCountsOut, JobRunOut, PricesStatusOut, StatusOut

### Community 77 - "stocks_workbook.py (2)"
Cohesion: 0.42
Nodes (5): bse(), main(), nse(), remaining(), _write()

### Community 78 - "Build Plan Phases"
Cohesion: 0.31
Nodes (9): Phase 0 Spike, Phase 1 Data layer, Phase 2 Builder and sync, Phase 3 Document AI, Phase 4 GenAI outputs, Phase 5 Discovery, IB outputs, polish, Section 26 Build plan, Section 2 Requirements (F1-F20, NFRs) (+1 more)

### Community 80 - "parser.py"
Cohesion: 0.29
Nodes (4): Context, _dedupe(), _parse_context(), _unit_label()

### Community 81 - "Results Collection Design"
Cohesion: 0.25
Nodes (5): NSE request limit and watchdog, Workflow 1 Results collection, Newest filed value wins (restatements), How it works pipeline (ingest, XBRL, facts, approve, drafts), Status v0.0.5 (data layer on real NSE data)

### Community 83 - "desk.py"
Cohesion: 0.48
Nodes (4): _change(), LastClose, latest_price(), latest_prices()

### Community 84 - "Example NBFC Mapping"
Cohesion: 0.38
Nodes (7): Example NBFC quarterly template mapping, checks (balance sheet difference expect 0), drivers (loan_yield actual to forecast), kpi:gold_loan_aum row, period_axis (Period header row, A/E flag row), units default_transform div:10000000 (INR to crore), xbrl source rows (RevenueFromOperations, OtherIncome, FinanceCosts, ProfitLossForPeriod)

### Community 86 - "ib/comps.py (3)"
Cohesion: 0.33
Nodes (3): peers(), PeerOut, suggest_peers()

### Community 87 - "Grounded GenAI Design"
Cohesion: 0.33
Nodes (5): Claude API usage policy (Claude.create, fallbacks, Batch), Grounding and style check, Workflow 8 Documents, KPIs and reports, Reports set-up (quarterly update, initiating coverage), Section-by-section report runner (proposed)

### Community 88 - "API Schemas (1) (1) (1) (1) (1) (1) (2)"
Cohesion: 0.40
Nodes (4): results_calendar(), CalendarEventOut, CalendarOut, UnscheduledOut

### Community 89 - "last_close_day"
Cohesion: 0.50
Nodes (4): last_close_day(), test_prices_are_overdue_only_after_the_evening_window(), expected(), test_latest_close_day_waits_for_the_evening_and_skips_weekends()

### Community 91 - "stocks_workbook.py (3)"
Cohesion: 0.67
Nodes (3): StorageUnavailable, test_storage_down_is_a_fast_503(), down()

### Community 94 - "Deployment today and planned hosting"
Cohesion: 0.67
Nodes (3): Deployment today and planned hosting, Scheduler in Docker (Celery beat, worker, Redis), Hosting in India blocker

### Community 95 - "Job schedule by results season"
Cohesion: 0.67
Nodes (3): Job schedule by results season, Workflow 9 Events, results calendar and alerts, Results watcher by SEBI season

### Community 98 - "Call recordings transcription (Whisper)"
Cohesion: 0.67
Nodes (3): Call recordings transcription (Whisper), Live earnings-call listener (future scope), Section 11 Document pipeline

### Community 99 - "Section 22.5 Source control, CI/CD and G"
Cohesion: 0.67
Nodes (3): GitHub read-only mirror via mirror_to_github CI job, GitLab Free as source of truth, Section 22.5 Source control, CI/CD and GitHub mirroring

### Community 101 - "Phase tracker tables"
Cohesion: 0.67
Nodes (3): Dev log, What stops the next phases, Phase tracker tables

## Knowledge Gaps
- **89 isolated node(s):** `Analekh (system)`, `Technical Design Document v0.0.5`, `Comps (peer lists, TTM, multiples)`, `Section 18 IB Output Engine`, `Decisions waiting on the owner` (+84 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 829 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_month_end()` connect `changeset.py` to `Results Calendar UI`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 65 inferred relationships involving `Company` (e.g. with `suggest_peers()` and `start_coverage()`) actually correct?**
  _`Company` has 65 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Analekh (system)`, `Technical Design Document v0.0.5`, `Comps (peer lists, TTM, multiples)` to the rest of the system?**
  _89 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CompanyPage.tsx (1)` be split into smaller, more focused modules?**
  _Cohesion score 0.08651911468812877 - nodes in this community are weakly interconnected._
- **Why does `Review Focus` connect `Review Focus` to `@tanstack/react-query`, `test_auth_reset.py (1) (1) (1)`, `login`, `create_user`, `test_auth_api.py`, `users.py`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `Filing` (e.g. with `process_documents()` and `revalidate_company()`) actually correct?**
  _`Filing` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Should `@tanstack/react-query` be split into smaller, more focused modules?**
  _Cohesion score 0.07518796992481203 - nodes in this community are weakly interconnected._