# Graph Report - Kaushal-Analekh  (2026-10-22)

## Corpus Check
- 273 files · ~194,904 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 10, .example 1, .ini 1)

## Summary
- 2733 nodes · 8270 edges · 122 communities (88 shown, 34 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 712 edges (avg confidence: 0.92)
- Token cost: 406,493 input · 0 output

## Community Hubs (Navigation)
- extract.py
- CompanyPage.tsx (1)
- get_settings()
- Mapping
- @tanstack/react-query
- io (1)
- Companies API (1) (1) (1)
- ib/comps.py
- changeset.py
- CI and Compose Deploy
- API Schemas (1) (1) (1) (1) (1) (1)
- Golden Set Runner (1) (1)
- ValidationContext
- routers/models.py
- analekh/cli.py
- Design Doc Core Components
- test_universe.py
- NSE Integrated Filings
- test_auth_reset.py (1) (1)
- rules.py
- login
- Polite HTTP Client (1) (1) (1) (1) (1)
- test_api.py
- users.py
- reader.py (1)
- Office Add-in Task Pane (1) (1)
- test_upload_limit.py
- tasks.py
- dataclasses
- Reports.tsx (2)
- User
- db/models.py
- test_api_tokens.py
- bhavcopy.py
- router.tsx
- db/models.py (1)
- sqlalchemy
- io (2)
- api
- routers/comps.py
- Results Seasons (1)
- Results History UI
- Results Calendar UI
- feeds.py
- test-utils.tsx
- Latest Results Paging
- pytest
- test_login_ip_limit.py
- design_docx.py (1) (1) (1)
- test_users_api.py
- test_auth_api.py
- test_queues.py
- ingest/pipeline.py
- FeedItem
- diagram_panels.py
- ToolExecutor (1) (1) (1)
- statusPanels.tsx
- io (3)
- system.py
- auth.py
- stocks_workbook.py
- Watchlist Coverage
- public.py
- parser.py
- CompanyPage.tsx (2)
- Workbook Engine Design
- Sign-in, roles, upload limit and model locks: design
- ToolExecutor (1) (2)
- .text()
- search.py
- audio.py (1)
- LocalStore (1)
- calc.py
- Product Rules and Workflows
- Universe and Sector Design
- Build Plan Phases
- passwords.py (1) (1)
- LocalStore (2)
- Results Collection Design
- desk.py
- Example NBFC Mapping
- docs/pipeline.py
- Grounded GenAI Design
- taskpane.tsx
- ToolExecutor (1) (1) (2)
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
10. `Mapping` - 41 edges

## Surprising Connections (you probably didn't know these)
- `User` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `User` --references--> `Task 4: Auth router, cookie, CSRF, role dependencies, protect every router`  [INFERRED]
  analekh/db/models.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `db()` --references--> `Task 3: Sign-in service (sessions, failure tiers, disable)`  [INFERRED]
  tests/conftest.py → docs/superpowers/plans/2026-10-22-auth-stage-1.md
- `Segmented()` --references--> `Task 11: Admin area (own routes and shell), personal settings`  [INFERRED]
  web/src/components/ui.tsx → docs/superpowers/plans/2026-10-22-auth-stage-1.md
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

## Communities (122 total, 34 thin omitted)

### Community 0 - "extract.py"
Cohesion: 0.05
Nodes (47): LlmCall, chunk_pages(), TextChunk, PageScore, score_page(), select_pages(), Embedder, get_embedder() (+39 more)

### Community 1 - "CompanyPage.tsx (1)"
Cohesion: 0.08
Nodes (67): CompanyDetail, GlanceLine, HistoryLine, WatchlistEntry, Change(), COSTS, fmtDate(), QuarterRail() (+59 more)

### Community 2 - "get_settings()"
Cohesion: 0.05
Nodes (36): check_auth_switch(), _database_busy(), lifespan(), _storage_down(), _warm_up(), cache_size(), get_settings(), Settings (+28 more)

### Community 3 - "Mapping"
Cohesion: 0.07
Nodes (36): Proposal, propose(), _propose_one(), _q(), _revenue_row(), _series(), quarter_start(), resolve_row() (+28 more)

### Community 4 - "@tanstack/react-query"
Cohesion: 0.07
Nodes (45): Task 10: Sign-in in the web app, AdminLayout(), ITEMS, Me, onSignedOut(), RequireSignIn(), ME_KEY, rememberReturnPath() (+37 more)

### Community 5 - "io (1)"
Cohesion: 0.07
Nodes (36): initiation_docx(), note_docx(), summary_pptx(), book_value(), build_table(), clean_symbols(), CompInputs, CompRow (+28 more)

### Community 6 - "Companies API (1) (1) (1)"
Cohesion: 0.07
Nodes (37): company_or_404(), job(), health(), analyse(), company_glance(), company_history(), company_index(), company_price() (+29 more)

### Community 7 - "ib/comps.py"
Cohesion: 0.08
Nodes (32): company_history_xlsx(), desk(), Desk, DeskRow, _movers(), _quarter_start(), recent_quarters(), SectorProgress (+24 more)

### Community 8 - "changeset.py"
Cohesion: 0.08
Nodes (28): fill_history(), FillReport, write_drivers(), write_sources(), Written, sync_model(), build_change_set(), _list_adjacent_hardcodes() (+20 more)

### Community 9 - "CI and Compose Deploy"
Cohesion: 0.06
Nodes (53): CLAUDE.md project guidance, production service api, production service beat, production service migrate (alembic), production service postgres, production service valkey, production service worker, staging service api (+45 more)

### Community 10 - "API Schemas (1) (1) (1) (1) (1) (1)"
Cohesion: 0.05
Nodes (48): results_calendar(), alert_channels(), jobs_available(), _mask(), _season(), test_alert(), AlertChannelsOut, AlertOut (+40 more)

### Community 11 - "Golden Set Runner (1) (1)"
Cohesion: 0.08
Nodes (27): build_sheet(), file_name(), fy_label(), GoldenReport, guess_unit(), import_sheet(), ImportSummary, Mismatch (+19 more)

### Community 12 - "ValidationContext"
Cohesion: 0.16
Nodes (44): HistoryFact, KpiValue, validate(), ValidationContext, parse_instance(), main(), history(), quarter_file() (+36 more)

### Community 13 - "routers/models.py"
Cohesion: 0.12
Nodes (32): assumptions(), decide_assumptions(), discover_models(), finalize(), link_model(), list_models(), _model(), relink_model() (+24 more)

### Community 14 - "analekh/cli.py"
Cohesion: 0.08
Nodes (28): backfill(), build(), _company(), create_admin(), golden_import(), golden_sheet(), golden_test(), prices() (+20 more)

### Community 15 - "Design Doc Core Components"
Cohesion: 0.05
Nodes (43): Appendices A-H (DDL, mapping, CI, deps, glossary), Backfill (results-backfill, --history, watchdog), NSE daily bhavcopy, Celery beat scheduler in Docker, Company page with results history table, Feed Watcher, NSE financial-results list (history from March 2023), GenAI tools (get_facts, get_kpis, get_model_values, search_filings, get_prices, calc) (+35 more)

### Community 16 - "test_universe.py"
Cohesion: 0.11
Nodes (30): Company, _date(), _decimal(), ListedCompany, LoadSummary, _norm_header(), parse_equity_list(), refresh_from_nse() (+22 more)

### Community 17 - "NSE Integrated Filings"
Cohesion: 0.08
Nodes (24): refused(), _date(), _download_and_ingest(), _error(), _fetch(), fetch_history(), FetchOutcome, _history_row() (+16 more)

### Community 18 - "test_auth_reset.py (1) (1)"
Cohesion: 0.09
Nodes (23): send_mail(), confirm_reset(), _hash_code(), request_reset(), PasswordReset, Task 5: Mail to any recipient and the reset-code flow, _code(), sent() (+15 more)

### Community 19 - "rules.py"
Cohesion: 0.10
Nodes (22): _identity(), is_year_end(), _jsonable(), _power(), _quarters(), RuleResult, tolerance(), _typical() (+14 more)

### Community 20 - "login"
Cohesion: 0.15
Nodes (33): verify_password(), _hash_token(), login(), LoginResult, logout(), _now(), revoke_user_sessions(), set_password() (+25 more)

### Community 21 - "Polite HTTP Client (1) (1) (1) (1) (1)"
Cohesion: 0.10
Nodes (26): DisallowedHostError, FetchResult, identity_headers(), path_allowed(), PoliteClient, RateLimiter, _retryable(), lookup() (+18 more)

### Community 22 - "test_api.py"
Cohesion: 0.09
Nodes (29): client(), test_alert_channels_and_test_messages_never_leak_secrets(), test_comps_export_shows_each_company_basis(), test_discover_and_link(), test_facts_fall_back_to_standalone_when_company_files_no_consolidated(), test_glance_for_a_life_insurer_shows_premium_and_ratios(), quarter(), test_glance_lines_changes_and_derived_ebitda() (+21 more)

### Community 23 - "users.py"
Cohesion: 0.11
Nodes (24): _active_admins(), _audit(), create(), _get(), list_users(), _out(), PasswordIn, reset_password() (+16 more)

### Community 24 - "reader.py (1)"
Cohesion: 0.09
Nodes (23): column_letter_shift(), DependencyGraph, expand(), references(), Finding, scan_hygiene(), LabelMatch, match_label() (+15 more)

### Community 25 - "Office Add-in Task Pane (1) (1)"
Cohesion: 0.06
Nodes (36): AlertChannels, AlertEntry, ApiError, ApiToken, Assumption, BuildOut, Calendar, CalendarEvent (+28 more)

### Community 26 - "test_upload_limit.py"
Cohesion: 0.10
Nodes (21): _out(), read_upload_limit(), set_upload_limit(), UploadLimitIn, UploadLimitOut, get_max_upload_bytes(), mb(), read_limited() (+13 more)

### Community 27 - "tasks.py"
Cohesion: 0.09
Nodes (20): session_scope(), _gone(), pending_feed_items(), process_feed_items(), default_store(), analyse_company(), backfill(), background_backfill() (+12 more)

### Community 28 - "dataclasses"
Cohesion: 0.11
Nodes (18): _api(), apply(), link(), scan(), watch(), apply(), apply_openpyxl(), apply_xlwings() (+10 more)

### Community 29 - "Reports.tsx (2)"
Cohesion: 0.10
Nodes (30): ApiTokenCreated, IconName, PATHS, Segmented(), SegmentThumb(), ADMIN, GROUPS, Item() (+22 more)

### Community 30 - "User"
Cohesion: 0.09
Nodes (20): auth_is_off(), _bearer_user(), _dev_user(), get_current(), get_user(), require_admin(), _session_user(), User (+12 more)

### Community 31 - "db/models.py"
Cohesion: 0.10
Nodes (20): create_report(), get_report(), alerts(), data_counts(), prices_status(), _run(), status(), DataCountsOut (+12 more)

### Community 32 - "test_api_tokens.py"
Cohesion: 0.10
Nodes (21): create(), list_tokens(), revoke(), TokenCreated, TokenIn, TokenOut, _by_email(), create_user() (+13 more)

### Community 33 - "bhavcopy.py"
Cohesion: 0.10
Nodes (21): BhavRow, _dec(), fetch(), latest_stored(), load_day(), market_cap(), paid_up_capital(), parse() (+13 more)

### Community 34 - "router.tsx"
Cohesion: 0.17
Nodes (30): AdminUserRow, UserChange, Icon(), AVATAR_HUES, Badge(), EmptyState(), ErrorNote(), Loading() (+22 more)

### Community 35 - "db/models.py (1)"
Cohesion: 0.12
Nodes (24): start(), activate_template(), confirm(), list_templates(), _template(), test_build(), upload_template(), BuildOut (+16 more)

### Community 36 - "sqlalchemy"
Cohesion: 0.10
Nodes (9): downgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+1 more)

### Community 37 - "io (2)"
Cohesion: 0.09
Nodes (12): TemplateTest, DbValueSource, ModelReader, run_test_build(), CheckResult, CheckRun, run_checks(), has_macros() (+4 more)

### Community 38 - "api"
Cohesion: 0.10
Nodes (26): api, CompanyIndexEntry, INDEX, renderSearch(), CompanySearch(), highlight(), Suggestion, CompanyIndex (+18 more)

### Community 39 - "routers/comps.py"
Cohesion: 0.10
Nodes (23): _commit(), comps(), comps_table(), create_peer_list(), delete_peer_list(), _list_or_404(), _name(), peer_lists() (+15 more)

### Community 40 - "Results Seasons (1)"
Cohesion: 0.13
Nodes (21): watcher_status(), WatcherStatusOut, watch_results(), deadline_days(), next_ask(), next_season(), previous_start(), Season (+13 more)

### Community 41 - "Results History UI"
Cohesion: 0.16
Nodes (26): Filing, Revision, BOLD, cell(), FilingDetails(), headMark(), OtherFilings(), ResultsHistory() (+18 more)

### Community 42 - "Results Calendar UI"
Cohesion: 0.19
Nodes (29): DayProps, DayStrip(), EventRow(), KIND_LABEL, KIND_TONE, KindChip(), KindFilter, MonthView() (+21 more)

### Community 43 - "feeds.py"
Cohesion: 0.10
Nodes (14): FeedWatcher, item_key(), parse_pub_date(), parse_rss(), RssItem, store_items(), CompanyIndex, normalise_name() (+6 more)

### Community 44 - "test-utils.tsx"
Cohesion: 0.11
Nodes (12): LIMIT, quiet, USERS, TOKENS, ADMIN, ANALYST, Call, Handler (+4 more)

### Community 45 - "Latest Results Paging"
Cohesion: 0.13
Nodes (21): fetch_latest(), is_truncated(), LatestOutcome, next_page_size(), company(), list_client(), handler(), row() (+13 more)

### Community 46 - "pytest"
Cohesion: 0.13
Nodes (19): BackfillSummary, run_backfill(), check_pdf(), classify_announcement(), NotAPdf, store_document(), make_pdf(), test_announcement_classifier() (+11 more)

### Community 47 - "test_login_ip_limit.py"
Cohesion: 0.11
Nodes (18): clear_cache(), clear(), _prune(), record_failure(), retry_after(), tracked(), _fresh_in_memory_state(), _fresh() (+10 more)

### Community 48 - "design_docx.py (1) (1) (1)"
Cohesion: 0.14
Nodes (16): add(), caption(), cell_border(), code_block(), figure(), heading(), inline(), list_item() (+8 more)

### Community 49 - "test_users_api.py"
Cohesion: 0.11
Nodes (15): get_store(), adopt_local(), AuditEntry, Task 6: User administration, template permissions, create-admin CLI, admin(), analyst(), _Scope, _sign_in() (+7 more)

### Community 50 - "test_auth_api.py"
Cohesion: 0.15
Nodes (20): Task 4: Auth router, cookie, CSRF, role dependencies, protect every router, _login(), raw(), test_access_log_has_no_secrets(), test_admin_only_dependency_refuses_analyst(), test_cookie_is_secure_outside_dev(), test_disabled_user_session_gets_401(), test_every_non_public_route_requires_session() (+12 more)

### Community 51 - "test_queues.py"
Cohesion: 0.17
Nodes (17): fetch_results(), bad_date_instance(), client_for(), company(), feed_item(), row(), stored_doc(), test_a_failed_item_retries_after_fresh_ones() (+9 more)

### Community 52 - "ingest/pipeline.py"
Cohesion: 0.13
Nodes (14): _fact_key(), IncompleteXbrl, ingest_results_xbrl(), load_history(), revalidate_company(), rewrite_amounts(), scale_meta(), storage_key() (+6 more)

### Community 53 - "FeedItem"
Cohesion: 0.15
Nodes (11): FeedItem, process_feed_item(), CalendarEvent, events(), _filed_results(), kind_of(), parse_description(), _item() (+3 more)

### Community 54 - "diagram_panels.py"
Cohesion: 0.13
Nodes (5): main(), _graphify_python(), install_hooks(), main(), _triggered_by_rebuild()

### Community 55 - "ToolExecutor (1) (1) (1)"
Cohesion: 0.19
Nodes (13): check(), collect_values(), _decimals(), extract_numbers(), GroundingResult, matches(), ReportRun, run_report() (+5 more)

### Community 56 - "statusPanels.tsx"
Cohesion: 0.22
Nodes (18): AlertTest, JobRun, Status, UploadLimit, Skeleton(), filedAt(), AdminSettings(), mb() (+10 more)

### Community 57 - "io (3)"
Cohesion: 0.19
Nodes (12): apply(), change_set(), _cs(), decide(), Decisions, ChangeSet, sha256(), apply_headless() (+4 more)

### Community 58 - "system.py"
Cohesion: 0.15
Nodes (5): raise_alert(), send_email(), send_telegram(), _probe(), queue_available()

### Community 59 - "auth.py"
Cohesion: 0.16
Nodes (10): _cookie_secure(), login(), LoginIn, logout(), me(), MeOut, reset_confirm(), reset_request() (+2 more)

### Community 60 - "stocks_workbook.py"
Cohesion: 0.18
Nodes (4): S3Store, compress(), main(), test_s3_store_write_marks_gzip_and_overwrites()

### Community 61 - "Watchlist Coverage"
Cohesion: 0.23
Nodes (10): unwatch(), add(), entries(), is_watched(), level(), remove(), _user(), Watchlist (+2 more)

### Community 62 - "public.py"
Cohesion: 0.22
Nodes (9): auth_status(), _cached(), calendar(), build(), PublicCalendarOut, PublicEventOut, welcome(), build() (+1 more)

### Community 63 - "parser.py"
Cohesion: 0.20
Nodes (9): Context, _dedupe(), dims_hash(), _parse_context(), period_type(), _unit_label(), test_contexts_resolved_from_dates_not_ids(), test_dims_hash_is_order_independent() (+1 more)

### Community 64 - "CompanyPage.tsx (2)"
Cohesion: 0.19
Nodes (14): CompRow, CompsTable, PeerList, AS_FLAG, BASES, Basis, Blank(), CompsGrid() (+6 more)

### Community 65 - "Workbook Engine Design"
Cohesion: 0.17
Nodes (12): Change set and change items, Excel bridge (xlwings, Office.js later), Workbook fingerprint, Hidden tag (custom document property), Initiation pack, Roll-forward, Section 13 Model discovery and recognition, Section 14 Template onboarding (+4 more)

### Community 66 - "Sign-in, roles, upload limit and model locks: design"
Cohesion: 0.15
Nodes (12): 10. Other screens still to be mocked, 12. Left to the builder, 13. Open decisions for the owner, 2. Goals, 3. Non-goals and anti-goals, 4. Roles, 6. The sign-in screen (chosen mockup), 7. Upload limit (+4 more)

### Community 67 - "ToolExecutor (1) (2)"
Cohesion: 0.24
Nodes (4): qa(), QaRequest, ToolExecutor, test_tool_executor_looks_companies_up_like_everywhere_else()

### Community 68 - ".text()"
Cohesion: 0.18
Nodes (7): _clock(), Global Constraints, Self-review notes, Sign-in, Roles and Upload Limit (Stage 1) Implementation Plan, 5. Security requirements (hard rules), engine(), _ensure_database()

### Community 69 - "search.py"
Cohesion: 0.26
Nodes (9): _run(), search(), SearchHit, db(), test_search_matches_words_in_any_order(), symbols(), test_search_narrows_with_each_keystroke(), symbols() (+1 more)

### Community 70 - "audio.py (1)"
Cohesion: 0.29
Nodes (6): _add_cuda_dll_dirs(), AudioTranscript, _has_cuda(), Segment, transcribe(), test_audio_transcript_text_carries_timestamps()

### Community 71 - "LocalStore (1)"
Cohesion: 0.25
Nodes (5): LocalStore, _no_real_claude(), store(), test_builtin_template_file_is_rebuilt_when_storage_lost_it(), test_store_gzips_xml_and_returns_the_original_bytes()

### Community 72 - "calc.py"
Cohesion: 0.33
Nodes (4): calc(), CalcError, _eval(), test_calc_is_exact_and_safe()

### Community 73 - "Product Rules and Workflows"
Cohesion: 0.20
Nodes (5): Approval gate, Workflow 5 Quarterly model update, Workflow 6 Start coverage, Workflow 7 Template onboarding, Investor presentations via NSE announcements (proposed)

### Community 74 - "Universe and Sector Design"
Cohesion: 0.20
Nodes (9): Coverage levels (universe, numbers, deep), Excel Stocks data type (LSEG industry group), NSE Indices constituent lists, Results format / results_taxonomy (indas, banking, nbfc, insurance, life_insurance), Section 4.2 Sector classification precedence, Section 4 Company universe and coverage levels, Universe Loader, Watchlist (+1 more)

### Community 75 - "Build Plan Phases"
Cohesion: 0.31
Nodes (9): Phase 0 Spike, Phase 1 Data layer, Phase 2 Builder and sync, Phase 3 Document AI, Phase 4 GenAI outputs, Phase 5 Discovery, IB outputs, polish, Section 26 Build plan, Section 2 Requirements (F1-F20, NFRs) (+1 more)

### Community 76 - "passwords.py (1) (1)"
Cohesion: 0.22
Nodes (9): Review Focus, Task 11: Admin area (own routes and shell), personal settings, Task 12: Records and end-to-end check, Task 1: Tables, config and dependency, Task 7: Upload limit, Task 8: Bridge and add-in tokens, Task 9: Mock-ups gate (owner decision), test_bearer_token_authenticates_and_carries_role() (+1 more)

### Community 78 - "Results Collection Design"
Cohesion: 0.25
Nodes (5): NSE request limit and watchdog, Workflow 1 Results collection, Newest filed value wins (restatements), How it works pipeline (ingest, XBRL, facts, approve, drafts), Status v0.0.5 (data layer on real NSE data)

### Community 80 - "desk.py"
Cohesion: 0.48
Nodes (4): _change(), LastClose, latest_price(), latest_prices()

### Community 81 - "Example NBFC Mapping"
Cohesion: 0.38
Nodes (7): Example NBFC quarterly template mapping, checks (balance sheet difference expect 0), drivers (loan_yield actual to forecast), kpi:gold_loan_aum row, period_axis (Period header row, A/E flag row), units default_transform div:10000000 (INR to crore), xbrl source rows (RevenueFromOperations, OtherIncome, FinanceCosts, ProfitLossForPeriod)

### Community 82 - "docs/pipeline.py"
Cohesion: 0.40
Nodes (4): StorageUnavailable, test_storage_down_is_a_fast_503(), down(), test_s3_store_unreachable_raises_storage_unavailable()

### Community 83 - "Grounded GenAI Design"
Cohesion: 0.33
Nodes (5): Claude API usage policy (Claude.create, fallbacks, Batch), Grounding and style check, Workflow 8 Documents, KPIs and reports, Reports set-up (quarterly update, initiating coverage), Section-by-section report runner (proposed)

### Community 84 - "taskpane.tsx"
Cohesion: 0.47
Nodes (4): Item, readTag(), select(), TaskPane()

### Community 88 - "Deployment today and planned hosting"
Cohesion: 0.67
Nodes (3): Deployment today and planned hosting, Scheduler in Docker (Celery beat, worker, Redis), Hosting in India blocker

### Community 89 - "Job schedule by results season"
Cohesion: 0.67
Nodes (3): Job schedule by results season, Workflow 9 Events, results calendar and alerts, Results watcher by SEBI season

### Community 92 - "Call recordings transcription (Whisper)"
Cohesion: 0.67
Nodes (3): Call recordings transcription (Whisper), Live earnings-call listener (future scope), Section 11 Document pipeline

### Community 93 - "Section 22.5 Source control, CI/CD and G"
Cohesion: 0.67
Nodes (3): GitHub read-only mirror via mirror_to_github CI job, GitLab Free as source of truth, Section 22.5 Source control, CI/CD and GitHub mirroring

### Community 94 - "Phase tracker tables"
Cohesion: 0.67
Nodes (3): Dev log, What stops the next phases, Phase tracker tables

## Knowledge Gaps
- **89 isolated node(s):** `Analekh (system)`, `Technical Design Document v0.0.5`, `Scheduler in Docker (Celery beat, worker, Redis)`, `Hosting in India blocker`, `Workflow 9 Events, results calendar and alerts` (+84 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 808 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Task 10: Sign-in in the web app` connect `@tanstack/react-query` to `auth.py`, `passwords.py (1) (1)`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `Company` (e.g. with `suggest_peers()` and `start_coverage()`) actually correct?**
  _`Company` has 67 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Analekh (system)`, `Technical Design Document v0.0.5`, `Scheduler in Docker (Celery beat, worker, Redis)` to the rest of the system?**
  _89 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `extract.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05417236662106703 - nodes in this community are weakly interconnected._
- **Why does `_month_end()` connect `changeset.py` to `Results Calendar UI`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `Filing` (e.g. with `process_documents()` and `revalidate_company()`) actually correct?**
  _`Filing` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Should `CompanyPage.tsx (1)` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._