# Graph Report - Kaushal-Analekh  (2026-10-22)

## Corpus Check
- 273 files · ~194,904 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 10, .example 1, .ini 1)

## Summary
- 2726 nodes · 8245 edges · 137 communities (100 shown, 37 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 719 edges (avg confidence: 0.92)
- Token cost: 406,493 input · 0 output

## Community Hubs (Navigation)
- CompanyPage.tsx (1)
- @tanstack/react-query
- CI and Compose Deploy
- routers/models.py
- changeset.py
- Company
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
- tasks.py
- Filing
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
- db/models.py
- bhavcopy.py
- Results History UI
- test_login_ip_limit.py
- test_docs.py
- test_builder.py (1)
- Latest Results Paging
- test_modelsync.py (1) (1) (1)
- analekh/cli.py (1) (1) (1) (1)
- test-utils.tsx
- Results Seasons (1)
- test_users_api.py
- test_queues.py
- main.py
- Claude
- public.py
- docs/pipeline.py
- test_auth_api.py
- ToolExecutor (1) (1)
- test_ib.py (1) (1)
- test_auth_reset.py (1) (2) (1) (1) (1)
- ParsedFiling
- test_scale_check.py
- statusPanels.tsx
- checks.py
- pytest
- parser.py
- auth.py
- test_ib.py (1) (2)
- test_ib.py (1) (3)
- audio.py (1)
- extract.py
- ToolExecutor (1) (2)
- ingest/pipeline.py
- Watchlist Coverage
- test_modelsync.py (1) (1) (2)
- CompanyPage.tsx (2)
- test_ib.py (1) (4)
- Workbook Engine Design
- Sign-in, roles, upload limit and model locks: design
- Review Focus
- Product Rules and Workflows
- Universe and Sector Design
- FeedItem
- Build Plan Phases
- test_auth_reset.py (1) (2) (1) (1) (2)
- Results Collection Design
- test_ib.py (1) (5)
- ValidationReport
- Example NBFC Mapping
- test_ib.py (1) (6)
- analekh/cli.py (1) (1) (1) (2)
- recompute_latest()
- Grounded GenAI Design
- API Schemas (1) (1) (1) (1) (1) (2)
- last_close_day
- taskpane.tsx
- test_api.py (1) (1) (2)
- API Schemas (1) (1) (1) (1) (1) (3)
- analekh/cli.py (1) (1) (1) (3)
- Rule 8 Ratings and target prices from th
- Deployment today and planned hosting
- Job schedule by results season
- Only latest day's prices kept
- Workflow 4 Opening Analekh and reading r
- Call recordings transcription (Whisper)
- Section 22.5 Source control, CI/CD and G
- Phase tracker tables
- API Schemas (1) (1) (1) (1) (1) (4)
- analekh/cli.py (1) (1) (1) (4)
- analekh/cli.py (1) (1) (1) (5)
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
- `AuditEntry` --references--> `Task 6: User administration, template permissions, create-admin CLI`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `User` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `User` --references--> `Task 4: Auth router, cookie, CSRF, role dependencies, protect every router`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
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

## Communities (137 total, 37 thin omitted)

### Community 0 - "CompanyPage.tsx (1)"
Cohesion: 0.10
Nodes (55): CompanyDetail, HistoryLine, WatchlistEntry, Change(), COSTS, fmtDate(), QuarterRail(), BasisCell() (+47 more)

### Community 1 - "@tanstack/react-query"
Cohesion: 0.07
Nodes (43): Task 10: Sign-in in the web app, AdminLayout(), ITEMS, Me, onSignedOut(), RequireSignIn(), ME_KEY, rememberReturnPath() (+35 more)

### Community 2 - "CI and Compose Deploy"
Cohesion: 0.06
Nodes (53): CLAUDE.md project guidance, production service api, production service beat, production service migrate (alembic), production service postgres, production service valkey, production service worker, staging service api (+45 more)

### Community 3 - "routers/models.py"
Cohesion: 0.10
Nodes (35): assumptions(), builds(), decide_assumptions(), discover_models(), download_version(), finalize(), link_model(), list_models() (+27 more)

### Community 4 - "changeset.py"
Cohesion: 0.08
Nodes (29): fill_history(), FillReport, write_drivers(), write_sources(), Written, ChangeItem, sync_model(), build_change_set() (+21 more)

### Community 5 - "Company"
Cohesion: 0.09
Nodes (37): Company, _date(), _decimal(), ListedCompany, LoadSummary, _norm_header(), parse_equity_list(), upsert_universe() (+29 more)

### Community 6 - "get_settings()"
Cohesion: 0.06
Nodes (26): check_auth_switch(), _database_busy(), lifespan(), _storage_down(), _warm_up(), get_settings(), Settings, _api() (+18 more)

### Community 7 - "test_auth_reset.py (1) (1)"
Cohesion: 0.08
Nodes (24): send_mail(), confirm_reset(), _hash_code(), request_reset(), _user(), PasswordReset, Task 5: Mail to any recipient and the reset-code flow, _code() (+16 more)

### Community 8 - "design_docx.py (1) (1) (1)"
Cohesion: 0.07
Nodes (22): add(), caption(), cell_border(), cells(), code_block(), figure(), heading(), inline() (+14 more)

### Community 9 - "Design Doc Core Components"
Cohesion: 0.05
Nodes (43): Appendices A-H (DDL, mapping, CI, deps, glossary), Backfill (results-backfill, --history, watchdog), NSE daily bhavcopy, Celery beat scheduler in Docker, Company page with results history table, Feed Watcher, NSE financial-results list (history from March 2023), GenAI tools (get_facts, get_kpis, get_model_values, search_filings, get_prices, calc) (+35 more)

### Community 10 - "Mapping"
Cohesion: 0.10
Nodes (25): Proposal, propose(), _propose_one(), _q(), _revenue_row(), _series(), resolve_row(), Resolved (+17 more)

### Community 11 - "Reports.tsx (2)"
Cohesion: 0.07
Nodes (42): Task 11: Admin area (own routes and shell), personal settings, ApiTokenCreated, Segmented(), SegmentThumb(), ADMIN, GROUPS, Item(), Layout() (+34 more)

### Community 12 - "Polite HTTP Client (1) (1) (1) (1) (1)"
Cohesion: 0.10
Nodes (27): DisallowedHostError, FetchResult, identity_headers(), path_allowed(), PoliteClient, RateLimiter, _retryable(), fetch_results() (+19 more)

### Community 13 - "Object Storage (1)"
Cohesion: 0.08
Nodes (15): LocalStore, pack(), S3Store, StorageUnavailable, unpack(), compress(), main(), main() (+7 more)

### Community 14 - "router.tsx"
Cohesion: 0.14
Nodes (32): AdminUserRow, UserChange, Icon(), IconName, PATHS, AVATAR_HUES, Badge(), EmptyState() (+24 more)

### Community 15 - "API Schemas (1) (1) (1) (1) (1) (1)"
Cohesion: 0.06
Nodes (41): AlertOut, AssumptionDecision, AssumptionDecisions, AssumptionOut, BuildOut, ChangeItemOut, ChangeSetOut, CompanyDetail (+33 more)

### Community 16 - "NSE Integrated Filings"
Cohesion: 0.09
Nodes (24): refused(), _date(), _download_and_ingest(), _error(), _fetch(), fetch_history(), FetchOutcome, _history_row() (+16 more)

### Community 17 - "Companies API (1) (1) (1)"
Cohesion: 0.09
Nodes (26): company_or_404(), job(), analyse(), company_glance(), company_history(), company_index(), company_price(), facts() (+18 more)

### Community 18 - "tasks.py"
Cohesion: 0.09
Nodes (23): get_store(), session_scope(), default_store(), ObjectStore, record(), analyse_company(), backfill(), background_backfill() (+15 more)

### Community 19 - "Filing"
Cohesion: 0.10
Nodes (24): Filing, desk(), Desk, DeskRow, _movers(), _quarter_start(), recent_quarters(), SectorProgress (+16 more)

### Community 20 - "Office Add-in Task Pane (1) (1)"
Cohesion: 0.06
Nodes (38): AlertChannels, AlertEntry, ApiError, ApiToken, Assumption, BuildOut, Calendar, CalendarEvent (+30 more)

### Community 21 - "login"
Cohesion: 0.16
Nodes (32): _hash_token(), login(), LoginResult, logout(), _now(), revoke_user_sessions(), set_password(), user_for_token() (+24 more)

### Community 22 - "reader.py (1)"
Cohesion: 0.09
Nodes (20): column_letter_shift(), DependencyGraph, expand(), references(), Finding, scan_hygiene(), LabelMatch, match_label() (+12 more)

### Community 23 - "passwords.py (1) (1)"
Cohesion: 0.11
Nodes (25): _active_admins(), _audit(), create(), _get(), list_users(), _out(), PasswordIn, reset_password() (+17 more)

### Community 24 - "test_public_load.py"
Cohesion: 0.08
Nodes (19): cache_size(), get_engine(), _session_factory(), _attempt(), committed_user(), test_login_flood_gets_no_server_errors(), test_parallel_wrong_passwords_cannot_skip_the_pause(), _cal() (+11 more)

### Community 25 - "test_upload_limit.py"
Cohesion: 0.10
Nodes (21): _out(), read_upload_limit(), set_upload_limit(), UploadLimitIn, UploadLimitOut, get_max_upload_bytes(), mb(), read_limited() (+13 more)

### Community 26 - "test_api.py (1) (1) (1)"
Cohesion: 0.11
Nodes (27): ingest_results_xbrl(), store(), client(), test_comps_export_shows_each_company_basis(), test_discover_and_link(), test_facts_fall_back_to_standalone_when_company_files_no_consolidated(), test_glance_for_a_life_insurer_shows_premium_and_ratios(), quarter() (+19 more)

### Community 27 - "rules.py"
Cohesion: 0.11
Nodes (20): _identity(), is_year_end(), _power(), _quarters(), RuleResult, tolerance(), _typical(), v10_kpi_conflict() (+12 more)

### Community 28 - "ib/comps.py"
Cohesion: 0.10
Nodes (18): company_history_xlsx(), files_consolidated(), _day(), glance(), value(), Glance, is_financial(), _latest_revision() (+10 more)

### Community 29 - "db/models.py (1)"
Cohesion: 0.14
Nodes (24): activate_template(), confirm(), list_templates(), _template(), test_build(), upload_template(), Template, TemplateTest (+16 more)

### Community 30 - "sqlalchemy"
Cohesion: 0.10
Nodes (9): downgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+1 more)

### Community 31 - "ValidationContext"
Cohesion: 0.23
Nodes (33): KpiValue, validate(), ValidationContext, parse_instance(), handler(), handler(), by_rule(), _quarter() (+25 more)

### Community 32 - "test_api_tokens.py"
Cohesion: 0.12
Nodes (16): create(), list_tokens(), revoke(), TokenCreated, TokenIn, TokenOut, create_api_token(), _hash() (+8 more)

### Community 33 - "Golden Set Runner (1) (1)"
Cohesion: 0.13
Nodes (21): build_sheet(), file_name(), fy_label(), GoldenReport, guess_unit(), import_sheet(), ImportSummary, Mismatch (+13 more)

### Community 34 - "api"
Cohesion: 0.10
Nodes (26): api, CompanyIndexEntry, INDEX, renderSearch(), CompanySearch(), highlight(), Suggestion, CompanyIndex (+18 more)

### Community 35 - "test_ingest.py"
Cohesion: 0.10
Nodes (15): FeedItem, FeedWatcher, item_key(), parse_pub_date(), parse_rss(), RssItem, store_items(), CompanyIndex (+7 more)

### Community 36 - "Results Calendar UI"
Cohesion: 0.19
Nodes (29): DayProps, DayStrip(), EventRow(), KIND_LABEL, KIND_TONE, KindChip(), KindFilter, MonthView() (+21 more)

### Community 37 - "db/models.py"
Cohesion: 0.12
Nodes (8): Base, Chunk, Fact, Kpi, hybrid_search(), engine(), _ensure_database(), _no_real_claude()

### Community 38 - "bhavcopy.py"
Cohesion: 0.14
Nodes (17): Price, BhavRow, _dec(), fetch(), latest_stored(), load_day(), market_cap(), paid_up_capital() (+9 more)

### Community 39 - "Results History UI"
Cohesion: 0.17
Nodes (25): Filing, BOLD, cell(), FilingDetails(), headMark(), OtherFilings(), ResultsHistory(), SourceLinks() (+17 more)

### Community 40 - "test_login_ip_limit.py"
Cohesion: 0.10
Nodes (17): clear(), _prune(), record_failure(), retry_after(), tracked(), _probe(), queue_available(), _fresh() (+9 more)

### Community 41 - "test_docs.py"
Cohesion: 0.15
Nodes (16): PageScore, score_page(), select_pages(), _ocr(), PageText, read_pages(), subset(), as_prompt_text() (+8 more)

### Community 42 - "test_builder.py (1)"
Cohesion: 0.14
Nodes (17): link(), apply(), apply_openpyxl(), apply_xlwings(), link_tag(), target_path(), Write, coerce() (+9 more)

### Community 43 - "Latest Results Paging"
Cohesion: 0.13
Nodes (21): fetch_latest(), is_truncated(), LatestOutcome, next_page_size(), company(), list_client(), handler(), row() (+13 more)

### Community 44 - "test_modelsync.py (1) (1) (1)"
Cohesion: 0.14
Nodes (19): apply(), change_set(), _cs(), decide(), ChangeSet, quarter_start(), apply_headless(), ApprovedItem (+11 more)

### Community 45 - "analekh/cli.py (1) (1) (1) (1)"
Cohesion: 0.16
Nodes (18): build(), _company(), create_admin(), golden_sheet(), prices(), results_backfill(), results_watch(), revalidate() (+10 more)

### Community 46 - "test-utils.tsx"
Cohesion: 0.10
Nodes (12): LIMIT, quiet, USERS, TOKENS, ADMIN, ANALYST, Call, Handler (+4 more)

### Community 47 - "Results Seasons (1)"
Cohesion: 0.15
Nodes (18): watcher_status(), WatcherStatusOut, deadline_days(), next_ask(), next_season(), previous_start(), Season, _season() (+10 more)

### Community 48 - "test_users_api.py"
Cohesion: 0.11
Nodes (19): _by_email(), create_user(), adopt_local(), Task 6: User administration, template permissions, create-admin CLI, user(), user(), user(), test_create_user_validates_role_and_email() (+11 more)

### Community 49 - "test_queues.py"
Cohesion: 0.14
Nodes (20): pending_feed_items(), process_feed_items(), test_backfill_from_import_folder(), bad_date_instance(), client_for(), company(), feed_item(), row() (+12 more)

### Community 50 - "main.py"
Cohesion: 0.14
Nodes (15): auth_is_off(), _bearer_user(), _dev_user(), get_current(), get_user(), require_admin(), _session_user(), User (+7 more)

### Community 51 - "Claude"
Cohesion: 0.13
Nodes (13): create_report(), get_report(), qa(), LlmCall, Report, Claude, ClaudeResult, RefusalError (+5 more)

### Community 52 - "public.py"
Cohesion: 0.12
Nodes (16): auth_status(), _cached(), calendar(), build(), clear_cache(), PublicCalendarOut, PublicEventOut, welcome() (+8 more)

### Community 53 - "docs/pipeline.py"
Cohesion: 0.15
Nodes (13): Document, chunk_pages(), TextChunk, Embedder, get_embedder(), LocalEmbedder, store_chunks(), DocResult (+5 more)

### Community 54 - "test_auth_api.py"
Cohesion: 0.15
Nodes (20): Task 4: Auth router, cookie, CSRF, role dependencies, protect every router, _login(), raw(), test_access_log_has_no_secrets(), test_admin_only_dependency_refuses_analyst(), test_cookie_is_secure_outside_dev(), test_disabled_user_session_gets_401(), test_every_non_public_route_requires_session() (+12 more)

### Community 55 - "ToolExecutor (1) (1)"
Cohesion: 0.14
Nodes (14): check(), collect_values(), _decimals(), extract_numbers(), GroundingResult, matches(), ReportRun, to_json() (+6 more)

### Community 56 - "test_ib.py (1) (1)"
Cohesion: 0.18
Nodes (19): CompInputs, compute(), four_quarters(), gather(), _pct(), _ratio(), _sum(), comp() (+11 more)

### Community 57 - "test_auth_reset.py (1) (2) (1) (1) (1)"
Cohesion: 0.13
Nodes (13): raise_alert(), send_email(), send_telegram(), alerts(), data_counts(), jobs_available(), prices_status(), _run() (+5 more)

### Community 58 - "ParsedFiling"
Cohesion: 0.12
Nodes (10): resolve(), sheet_lines(), SheetLine, _fact_key(), rewrite_amounts(), rescaled(), scaled_decimals(), _date_or_none() (+2 more)

### Community 59 - "test_scale_check.py"
Cohesion: 0.19
Nodes (16): load_history(), revalidate_company(), HistoryFact, _company(), history(), quarter_file(), standalone_q2(), test_a_real_jump_reported_on_both_bases_passes() (+8 more)

### Community 60 - "statusPanels.tsx"
Cohesion: 0.22
Nodes (18): AlertTest, JobRun, Status, UploadLimit, Skeleton(), filedAt(), AdminSettings(), mb() (+10 more)

### Community 61 - "checks.py"
Cohesion: 0.18
Nodes (7): CheckResult, CheckRun, run_checks(), evaluate(), lookup(), _plain(), recalc_file()

### Community 62 - "pytest"
Cohesion: 0.22
Nodes (13): NotAPdf, make_pdf(), company(), count(), store_it(), test_a_feed_item_with_an_error_page_is_given_up_at_once_and_the_queue_goes_on(), handler(), test_a_file_that_is_not_a_pdf_is_refused_and_nothing_is_stored() (+5 more)

### Community 63 - "parser.py"
Cohesion: 0.13
Nodes (10): detect_taxonomy(), Context, _dedupe(), dims_hash(), _parse_context(), _unit_label(), test_contexts_resolved_from_dates_not_ids(), test_dims_hash_is_order_independent() (+2 more)

### Community 64 - "auth.py"
Cohesion: 0.17
Nodes (10): _cookie_secure(), login(), LoginIn, logout(), me(), MeOut, reset_confirm(), reset_request() (+2 more)

### Community 65 - "test_ib.py (1) (2)"
Cohesion: 0.22
Nodes (12): _commit(), create_peer_list(), delete_peer_list(), _list_or_404(), _name(), peer_lists(), _symbols(), update_peer_list() (+4 more)

### Community 66 - "test_ib.py (1) (3)"
Cohesion: 0.18
Nodes (14): comps(), comps_table(), _requested(), _row_out(), CompRowOut, CompsRequest, CompsTableOut, CompStatOut (+6 more)

### Community 67 - "audio.py (1)"
Cohesion: 0.18
Nodes (9): transcribe_audio(), _add_cuda_dll_dirs(), AudioTranscript, _clock(), _has_cuda(), Segment, transcribe(), 5. Security requirements (hard rules) (+1 more)

### Community 68 - "extract.py"
Cohesion: 0.21
Nodes (12): batch_params(), build_prompt(), extract(), ExtractedKpi, Extraction, extraction_schema(), map_back(), _norm() (+4 more)

### Community 69 - "ToolExecutor (1) (2)"
Cohesion: 0.18
Nodes (5): calc(), CalcError, _eval(), ToolExecutor, test_calc_is_exact_and_safe()

### Community 70 - "ingest/pipeline.py"
Cohesion: 0.18
Nodes (9): BackfillSummary, run_backfill(), check_pdf(), classify_announcement(), _gone(), process_feed_item(), store_document(), storage_key() (+1 more)

### Community 71 - "Watchlist Coverage"
Cohesion: 0.26
Nodes (9): add(), entries(), is_watched(), level(), remove(), _user(), Watchlist, test_calendar_endpoint_scopes_to_the_watchlist() (+1 more)

### Community 72 - "test_modelsync.py (1) (1) (2)"
Cohesion: 0.16
Nodes (3): DbValueSource, SourceValue, FakeSource

### Community 73 - "CompanyPage.tsx (2)"
Cohesion: 0.19
Nodes (14): CompRow, CompsTable, PeerList, AS_FLAG, BASES, Basis, Blank(), CompsGrid() (+6 more)

### Community 74 - "test_ib.py (1) (4)"
Cohesion: 0.19
Nodes (7): refresh(), sub(), Replacement, build(), ProfileData, test_pitch_placeholders_replaced_and_logged(), test_profile_slide_builds()

### Community 75 - "Workbook Engine Design"
Cohesion: 0.17
Nodes (12): Change set and change items, Excel bridge (xlwings, Office.js later), Workbook fingerprint, Hidden tag (custom document property), Initiation pack, Roll-forward, Section 13 Model discovery and recognition, Section 14 Template onboarding (+4 more)

### Community 76 - "Sign-in, roles, upload limit and model locks: design"
Cohesion: 0.15
Nodes (12): 10. Other screens still to be mocked, 12. Left to the builder, 13. Open decisions for the owner, 2. Goals, 3. Non-goals and anti-goals, 4. Roles, 6. The sign-in screen (chosen mockup), 7. Upload limit (+4 more)

### Community 77 - "Review Focus"
Cohesion: 0.17
Nodes (11): Global Constraints, Review Focus, Self-review notes, Sign-in, Roles and Upload Limit (Stage 1) Implementation Plan, Task 12: Records and end-to-end check, Task 1: Tables, config and dependency, Task 7: Upload limit, Task 8: Bridge and add-in tokens (+3 more)

### Community 78 - "Product Rules and Workflows"
Cohesion: 0.20
Nodes (5): Approval gate, Workflow 5 Quarterly model update, Workflow 6 Start coverage, Workflow 7 Template onboarding, Investor presentations via NSE announcements (proposed)

### Community 79 - "Universe and Sector Design"
Cohesion: 0.20
Nodes (9): Coverage levels (universe, numbers, deep), Excel Stocks data type (LSEG industry group), NSE Indices constituent lists, Results format / results_taxonomy (indas, banking, nbfc, insurance, life_insurance), Section 4.2 Sector classification precedence, Section 4 Company universe and coverage levels, Universe Loader, Watchlist (+1 more)

### Community 80 - "FeedItem"
Cohesion: 0.33
Nodes (6): kind_of(), parse_description(), _item(), test_calendar_reschedule_watchlist_and_window(), test_parse_description(), test_past_days_show_results_filed_and_replace_the_announcement()

### Community 81 - "Build Plan Phases"
Cohesion: 0.31
Nodes (9): Phase 0 Spike, Phase 1 Data layer, Phase 2 Builder and sync, Phase 3 Document AI, Phase 4 GenAI outputs, Phase 5 Discovery, IB outputs, polish, Section 26 Build plan, Section 2 Requirements (F1-F20, NFRs) (+1 more)

### Community 82 - "test_auth_reset.py (1) (2) (1) (1) (2)"
Cohesion: 0.25
Nodes (6): alert_channels(), _mask(), test_alert(), AlertChannelsOut, AlertTestIn, AlertTestOut

### Community 83 - "Results Collection Design"
Cohesion: 0.25
Nodes (5): NSE request limit and watchdog, Workflow 1 Results collection, Newest filed value wins (restatements), How it works pipeline (ingest, XBRL, facts, approve, drafts), Status v0.0.5 (data layer on real NSE data)

### Community 84 - "test_ib.py (1) (5)"
Cohesion: 0.33
Nodes (3): initiation_docx(), note_docx(), summary_pptx()

### Community 85 - "ValidationReport"
Cohesion: 0.33
Nodes (3): scale_meta(), _jsonable(), ValidationReport

### Community 87 - "Example NBFC Mapping"
Cohesion: 0.38
Nodes (7): Example NBFC quarterly template mapping, checks (balance sheet difference expect 0), drivers (loan_yield actual to forecast), kpi:gold_loan_aum row, period_axis (Period header row, A/E flag row), units default_transform div:10000000 (INR to crore), xbrl source rows (RevenueFromOperations, OtherIncome, FinanceCosts, ProfitLossForPeriod)

### Community 88 - "test_ib.py (1) (6)"
Cohesion: 0.33
Nodes (3): peers(), PeerOut, suggest_peers()

### Community 89 - "analekh/cli.py (1) (1) (1) (2)"
Cohesion: 0.20
Nodes (3): golden_import(), golden_test(), refresh()

### Community 90 - "recompute_latest()"
Cohesion: 0.33
Nodes (3): recompute_latest(), refresh_latest(), infer_revision_flags()

### Community 91 - "Grounded GenAI Design"
Cohesion: 0.33
Nodes (5): Claude API usage policy (Claude.create, fallbacks, Batch), Grounding and style check, Workflow 8 Documents, KPIs and reports, Reports set-up (quarterly update, initiating coverage), Section-by-section report runner (proposed)

### Community 92 - "API Schemas (1) (1) (1) (1) (1) (2)"
Cohesion: 0.40
Nodes (4): results_calendar(), CalendarEventOut, CalendarOut, UnscheduledOut

### Community 93 - "last_close_day"
Cohesion: 0.50
Nodes (4): last_close_day(), test_prices_are_overdue_only_after_the_evening_window(), expected(), test_latest_close_day_waits_for_the_evening_and_skips_weekends()

### Community 94 - "taskpane.tsx"
Cohesion: 0.60
Nodes (4): Item, readTag(), select(), TaskPane()

### Community 95 - "test_api.py (1) (1) (2)"
Cohesion: 0.33
Nodes (3): health(), test_alert_channels_and_test_messages_never_leak_secrets(), test_analyse_fails_fast_when_the_job_queue_is_down()

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
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 804 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **37 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Task 10: Sign-in in the web app` connect `@tanstack/react-query` to `auth.py`, `Review Focus`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `Company` (e.g. with `suggest_peers()` and `start_coverage()`) actually correct?**
  _`Company` has 67 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Analekh (system)`, `Technical Design Document v0.0.5`, `Scheduler in Docker (Celery beat, worker, Redis)` to the rest of the system?**
  _89 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CompanyPage.tsx (1)` be split into smaller, more focused modules?**
  _Cohesion score 0.10189452124935997 - nodes in this community are weakly interconnected._
- **Why does `Company` connect `Company` to `routers/models.py`, `Polite HTTP Client (1) (1) (1) (1) (1)`, `NSE Integrated Filings`, `Companies API (1) (1) (1)`, `tasks.py`, `Filing`, `test_api.py (1) (1) (1)`, `ib/comps.py`, `db/models.py (1)`, `Golden Set Runner (1) (1)`, `test_ingest.py`, `db/models.py`, `bhavcopy.py`, `Latest Results Paging`, `analekh/cli.py (1) (1) (1) (1)`, `test_queues.py`, `main.py`, `public.py`, `docs/pipeline.py`, `test_auth_api.py`, `test_ib.py (1) (1)`, `test_auth_reset.py (1) (2) (1) (1) (1)`, `test_scale_check.py`, `pytest`, `audio.py (1)`, `ToolExecutor (1) (2)`, `ingest/pipeline.py`, `Watchlist Coverage`, `FeedItem`, `test_ib.py (1) (6)`, `recompute_latest()`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `Filing` (e.g. with `process_documents()` and `revalidate_company()`) actually correct?**
  _`Filing` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Should `@tanstack/react-query` be split into smaller, more focused modules?**
  _Cohesion score 0.07130333138515488 - nodes in this community are weakly interconnected._