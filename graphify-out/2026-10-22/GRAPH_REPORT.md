# Graph Report - Kaushal-Analekh  (2026-10-22)

## Corpus Check
- 259 files · ~200,243 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 10, .example 1, .ini 1)

## Summary
- 3248 nodes · 9411 edges · 163 communities (113 shown, 50 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 742 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bdb19020`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_docs.py
- CompanyPage.tsx (1)
- get_settings()
- Mapping
- @tanstack/react-query
- test_ib.py
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
- sectors.py
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
- main.py
- db/models.py
- test_api_tokens.py
- bhavcopy.py
- router.tsx
- db/models.py (1)
- sqlalchemy
- checks.py
- api
- ib/comps.py
- Results Seasons (1)
- Results History UI
- Results Calendar UI
- feeds.py
- test-utils.tsx
- Latest Results Paging
- pytest
- io
- design_docx.py (1) (1) (1)
- create_user
- test_auth_api.py
- test_queues.py
- ingest/pipeline.py
- FeedItem
- diagram_panels.py
- ToolExecutor (1) (1) (1)
- statusPanels.tsx
- apply
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
- docs/pipeline.py
- search.py
- audio.py (1)
- LocalStore (1)
- calc.py
- Product Rules and Workflows
- Universe and Sector Design
- Build Plan Phases
- test_upload_limit.py
- test_auth_hardening.py
- Results Collection Design
- jobs/app.py
- desk.py
- Example NBFC Mapping
- Filing
- Grounded GenAI Design
- taskpane.tsx
- web/package.json
- office-addin/package.json
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
- extract.py
- parse_equity_list
- Company
- test_scale_check.py
- devDependencies
- compilerOptions
- ParsedFiling
- package.json
- .__call__
- Claude
- compilerOptions
- dependencies
- search.py
- recalc.py
- stocks_workbook.py
- FetchOutcome
- create_report
- last_close_day
- scripts
- transcripts.py
- schema.d.ts
- IncompleteXbrl
- SourceViewer.tsx
- eslint.config.js
- engines
- .prettierrc.json
- analekh

## God Nodes (most connected - your core abstractions)
1. `Company` - 131 edges
2. `get_settings()` - 117 edges
3. `Filing` - 70 edges
4. `User` - 58 edges
5. `PoliteClient` - 55 edges
6. `ingest_results_xbrl()` - 55 edges
7. `ValidationContext` - 53 edges
8. `parse_instance()` - 52 edges
9. `login()` - 44 edges
10. `Mapping` - 43 edges

## Surprising Connections (you probably didn't know these)
- `1. Intent` --references--> `get_user()`  [INFERRED]
  docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md → analekh/api/deps.py
- `Task 5: Mail to any recipient and the reset-code flow` --references--> `send_email()`  [INFERRED]
  docs/superpowers/plans/2026-10-22-auth-stage-1.md → analekh/alerts/notify.py
- `Task 4: Auth router, cookie, CSRF, role dependencies, protect every router` --references--> `get_current()`  [INFERRED]
  docs/superpowers/plans/2026-10-22-auth-stage-1.md → analekh/api/deps.py
- `Sign-in, Roles and Upload Limit (Stage 1) Implementation Plan` --references--> `get_user()`  [INFERRED]
  docs/superpowers/plans/2026-10-22-auth-stage-1.md → analekh/api/deps.py
- `Task 4: Auth router, cookie, CSRF, role dependencies, protect every router` --references--> `get_user()`  [INFERRED]
  docs/superpowers/plans/2026-10-22-auth-stage-1.md → analekh/api/deps.py

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

## Communities (163 total, 50 thin omitted)

### Community 0 - "test_docs.py"
Cohesion: 0.17
Nodes (13): chunk_pages(), PageScore, score_page(), select_pages(), _ocr(), PageText, read_pages(), subset() (+5 more)

### Community 1 - "CompanyPage.tsx (1)"
Cohesion: 0.12
Nodes (48): vitest, GlanceLine, Change(), COSTS, fmtDate(), QuarterRail(), BasisCell(), BasisHeader() (+40 more)

### Community 2 - "get_settings()"
Cohesion: 0.04
Nodes (39): BodySizeLimit, max_body_bytes(), too_large_message(), check_auth_switch(), get_settings(), Settings, get_engine(), get_session() (+31 more)

### Community 3 - "Mapping"
Cohesion: 0.09
Nodes (24): Proposal, propose(), _propose_one(), _q(), _revenue_row(), _series(), build(), _derived_rows() (+16 more)

### Community 4 - "@tanstack/react-query"
Cohesion: 0.08
Nodes (36): Task 10: Sign-in in the web app, @fontsource-variable/inter, react-router-dom, @tanstack/react-query, AdminLayout(), ITEMS, Me, onSignedOut() (+28 more)

### Community 5 - "test_ib.py"
Cohesion: 0.15
Nodes (20): CompInputs, compute(), refresh(), sub(), Replacement, build(), ProfileData, comp() (+12 more)

### Community 6 - "Companies API (1) (1) (1)"
Cohesion: 0.10
Nodes (22): company_or_404(), job(), analyse(), company_glance(), company_history(), company_history_xlsx(), company_index(), company_price() (+14 more)

### Community 7 - "ib/comps.py"
Cohesion: 0.07
Nodes (31): desk(), Desk, DeskRow, _movers(), _quarter_start(), recent_quarters(), SectorProgress, _sectors() (+23 more)

### Community 8 - "changeset.py"
Cohesion: 0.07
Nodes (26): fill_history(), write_drivers(), write_sources(), Written, build_change_set(), _list_adjacent_hardcodes(), _next_label(), Proposal (+18 more)

### Community 9 - "CI and Compose Deploy"
Cohesion: 0.06
Nodes (53): CLAUDE.md project guidance, production service api, production service beat, production service migrate (alembic), production service postgres, production service valkey, production service worker, staging service api (+45 more)

### Community 10 - "API Schemas (1) (1) (1) (1) (1) (1)"
Cohesion: 0.06
Nodes (60): AlertChannelsOut, AlertOut, AlertTestIn, AlertTestOut, AssumptionDecision, AssumptionDecisions, AssumptionOut, BuildOut (+52 more)

### Community 11 - "Golden Set Runner (1) (1)"
Cohesion: 0.11
Nodes (22): build_sheet(), file_name(), fy_label(), GoldenReport, guess_unit(), import_sheet(), ImportSummary, Mismatch (+14 more)

### Community 12 - "ValidationContext"
Cohesion: 0.21
Nodes (33): KpiValue, validate(), ValidationContext, parse_instance(), main(), by_rule(), _quarter(), test_bank_identities_include_provisions() (+25 more)

### Community 13 - "routers/models.py"
Cohesion: 0.07
Nodes (40): assumptions(), builds(), decide_assumptions(), discover_models(), download_version(), finalize(), link_model(), list_models() (+32 more)

### Community 14 - "analekh/cli.py"
Cohesion: 0.11
Nodes (27): backfill(), build(), _company(), create_admin(), golden_import(), golden_sheet(), golden_test(), prices() (+19 more)

### Community 15 - "Design Doc Core Components"
Cohesion: 0.05
Nodes (43): Appendices A-H (DDL, mapping, CI, deps, glossary), Backfill (results-backfill, --history, watchdog), NSE daily bhavcopy, Celery beat scheduler in Docker, Company page with results history table, Feed Watcher, NSE financial-results list (history from March 2023), GenAI tools (get_facts, get_kpis, get_model_values, search_filings, get_prices, calc) (+35 more)

### Community 16 - "sectors.py"
Cohesion: 0.14
Nodes (14): apply_sectors(), fetch_index_sectors(), import_sector_worksheet(), import_stocks_workbook(), load_sector_map(), parse_constituents(), _rank(), refresh_sectors() (+6 more)

### Community 17 - "NSE Integrated Filings"
Cohesion: 0.11
Nodes (18): _date(), _download_and_ingest(), _error(), _fetch(), fetch_history(), _history_row(), IntegratedFiling, _ist() (+10 more)

### Community 18 - "test_auth_reset.py (1) (1)"
Cohesion: 0.07
Nodes (28): send_mail(), normalize_email(), confirm_reset(), _hash_code(), request_reset(), _user(), PasswordReset, Task 5: Mail to any recipient and the reset-code flow (+20 more)

### Community 19 - "rules.py"
Cohesion: 0.10
Nodes (23): _identity(), is_year_end(), _power(), _quarters(), rescaled(), RuleResult, scaled_decimals(), tolerance() (+15 more)

### Community 20 - "login"
Cohesion: 0.13
Nodes (37): _by_email(), _hash_token(), last_seen(), login(), LoginResult, logout(), _now(), purge_expired_sessions() (+29 more)

### Community 21 - "Polite HTTP Client (1) (1) (1) (1) (1)"
Cohesion: 0.10
Nodes (24): DisallowedHostError, FetchResult, identity_headers(), path_allowed(), PoliteClient, RateLimiter, refused(), _retryable() (+16 more)

### Community 22 - "test_api.py"
Cohesion: 0.07
Nodes (38): health(), FeedItem, Watchlist, ingest_results_xbrl(), save_proposal(), client(), demo(), test_alert_channels_and_test_messages_never_leak_secrets() (+30 more)

### Community 23 - "users.py"
Cohesion: 0.10
Nodes (24): _active_admins(), _audit(), create(), _get(), list_users(), _out(), PasswordIn, reset_password() (+16 more)

### Community 24 - "reader.py (1)"
Cohesion: 0.07
Nodes (22): DependencyGraph, expand(), references(), Finding, scan_hygiene(), LabelMatch, match_label(), normalise() (+14 more)

### Community 25 - "Office Add-in Task Pane (1) (1)"
Cohesion: 0.06
Nodes (36): AlertChannels, AlertEntry, ApiError, ApiToken, Assumption, BuildOut, Calendar, CalendarEvent (+28 more)

### Community 26 - "test_upload_limit.py"
Cohesion: 0.11
Nodes (14): _out(), read_upload_limit(), set_upload_limit(), UploadLimitIn, UploadLimitOut, get_max_upload_bytes(), mb(), read_limited() (+6 more)

### Community 27 - "tasks.py"
Cohesion: 0.12
Nodes (18): session_scope(), pending_feed_items(), default_store(), record(), analyse_company(), backfill(), background_backfill(), bulk_fetch_results() (+10 more)

### Community 28 - "dataclasses"
Cohesion: 0.09
Nodes (21): _api(), apply(), link(), scan(), watch(), hints_for(), iter_workbooks(), scan() (+13 more)

### Community 29 - "Reports.tsx (2)"
Cohesion: 0.07
Nodes (45): ApiTokenCreated, CompanyDetail, HistoryLine, WatchlistEntry, ADMIN, GROUPS, Item(), Layout() (+37 more)

### Community 30 - "main.py"
Cohesion: 0.07
Nodes (17): auth_is_off(), _bearer_user(), _dev_user(), get_current(), get_user(), require_admin(), _session_user(), _database_busy() (+9 more)

### Community 31 - "db/models.py"
Cohesion: 0.11
Nodes (10): Base, ChangeItem, Chunk, Document, Fact, JobStatus, Kpi, LlmCall (+2 more)

### Community 32 - "test_api_tokens.py"
Cohesion: 0.09
Nodes (20): create(), list_tokens(), revoke(), TokenCreated, TokenIn, TokenOut, create_api_token(), _hash() (+12 more)

### Community 33 - "bhavcopy.py"
Cohesion: 0.14
Nodes (17): Price, BhavRow, _dec(), fetch(), latest_stored(), load_day(), market_cap(), paid_up_capital() (+9 more)

### Community 34 - "router.tsx"
Cohesion: 0.11
Nodes (44): Icon(), IconName, PATHS, RequireSignIn(), EventRow(), Avatar(), AVATAR_HUES, Badge() (+36 more)

### Community 35 - "db/models.py (1)"
Cohesion: 0.09
Nodes (21): activate_template(), confirm(), list_templates(), _template(), test_build(), upload_template(), Template, TemplateTest (+13 more)

### Community 36 - "sqlalchemy"
Cohesion: 0.09
Nodes (9): downgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+1 more)

### Community 37 - "checks.py"
Cohesion: 0.29
Nodes (4): CheckResult, CheckRun, run_checks(), lookup()

### Community 38 - "api"
Cohesion: 0.15
Nodes (18): api, CompanyIndexEntry, INDEX, renderSearch(), CompanySearch(), highlight(), Suggestion, CompanyIndex (+10 more)

### Community 39 - "ib/comps.py"
Cohesion: 0.08
Nodes (28): _commit(), comps(), comps_table(), create_peer_list(), delete_peer_list(), _list_or_404(), _name(), peer_lists() (+20 more)

### Community 40 - "Results Seasons (1)"
Cohesion: 0.14
Nodes (18): deadline_days(), next_ask(), next_season(), previous_start(), Season, _season(), season_for(), _seasons_around() (+10 more)

### Community 41 - "Results History UI"
Cohesion: 0.16
Nodes (26): Filing, Revision, BOLD, cell(), FilingDetails(), headMark(), OtherFilings(), ResultsHistory() (+18 more)

### Community 42 - "Results Calendar UI"
Cohesion: 0.18
Nodes (30): Task 11: Admin area (own routes and shell), personal settings, DayProps, DayStrip(), KIND_LABEL, KIND_TONE, KindChip(), KindFilter, MonthView() (+22 more)

### Community 43 - "feeds.py"
Cohesion: 0.11
Nodes (11): FeedWatcher, item_key(), parse_pub_date(), parse_rss(), RssItem, store_items(), test_parse_rss_and_item_key(), test_parse_rss_nse_pub_date() (+3 more)

### Community 44 - "test-utils.tsx"
Cohesion: 0.11
Nodes (13): @testing-library/react, LIMIT, quiet, USERS, TOKENS, ADMIN, ANALYST, Call (+5 more)

### Community 45 - "Latest Results Paging"
Cohesion: 0.12
Nodes (21): fetch_latest(), is_truncated(), LatestOutcome, next_page_size(), company(), list_client(), handler(), row() (+13 more)

### Community 46 - "pytest"
Cohesion: 0.14
Nodes (15): _gone(), NotAPdf, process_feed_items(), make_pdf(), company(), count(), store_it(), test_a_feed_item_with_an_error_page_is_given_up_at_once_and_the_queue_goes_on() (+7 more)

### Community 47 - "io"
Cohesion: 0.10
Nodes (17): quarter_start(), resolve_row(), Resolved, SourceValue, ValueSource, apply_headless(), ApprovedItem, apply_transform() (+9 more)

### Community 48 - "design_docx.py (1) (1) (1)"
Cohesion: 0.10
Nodes (20): initiation_docx(), note_docx(), summary_pptx(), add(), caption(), cell_border(), cells(), code_block() (+12 more)

### Community 49 - "create_user"
Cohesion: 0.07
Nodes (33): clear(), _prune(), record_failure(), retry_after(), tracked(), create_user(), adopt_local(), AuditEntry (+25 more)

### Community 50 - "test_auth_api.py"
Cohesion: 0.13
Nodes (22): Task 4: Auth router, cookie, CSRF, role dependencies, protect every router, _login(), raw(), test_access_log_has_no_secrets(), test_admin_only_dependency_refuses_analyst(), test_cookie_is_secure_outside_dev(), test_disabled_user_session_gets_401(), test_every_non_public_route_requires_session() (+14 more)

### Community 51 - "test_queues.py"
Cohesion: 0.15
Nodes (17): fetch_results(), bad_date_instance(), client_for(), company(), feed_item(), row(), stored_doc(), test_a_failed_item_retries_after_fresh_ones() (+9 more)

### Community 52 - "ingest/pipeline.py"
Cohesion: 0.13
Nodes (9): _fact_key(), IngestResult, load_history(), revalidate_company(), rewrite_amounts(), scale_meta(), _jsonable(), ValidationReport (+1 more)

### Community 53 - "FeedItem"
Cohesion: 0.22
Nodes (8): CalendarEvent, events(), _filed_results(), kind_of(), parse_description(), _item(), test_calendar_reschedule_watchlist_and_window(), test_parse_description()

### Community 54 - "diagram_panels.py"
Cohesion: 0.14
Nodes (5): main(), _graphify_python(), install_hooks(), main(), _triggered_by_rebuild()

### Community 55 - "ToolExecutor (1) (1) (1)"
Cohesion: 0.12
Nodes (16): check(), collect_values(), _decimals(), extract_numbers(), GroundingResult, matches(), ReportRun, run_report() (+8 more)

### Community 56 - "statusPanels.tsx"
Cohesion: 0.14
Nodes (27): AdminUserRow, AlertTest, JobRun, Status, UploadLimit, UserChange, Skeleton(), filedAt() (+19 more)

### Community 57 - "apply"
Cohesion: 0.33
Nodes (5): apply(), change_set(), _cs(), decide(), ChangeSet

### Community 58 - "system.py"
Cohesion: 0.10
Nodes (17): raise_alert(), send_email(), send_telegram(), alert_channels(), alerts(), data_counts(), jobs_available(), _mask() (+9 more)

### Community 59 - "auth.py"
Cohesion: 0.12
Nodes (13): _cookie_secure(), login(), LoginIn, logout(), logout_everywhere(), me(), MeOut, reset_confirm() (+5 more)

### Community 60 - "stocks_workbook.py"
Cohesion: 0.09
Nodes (10): pack(), S3Store, StorageUnavailable, unpack(), compress(), main(), test_storage_down_is_a_fast_503(), down() (+2 more)

### Community 61 - "Watchlist Coverage"
Cohesion: 0.27
Nodes (7): add(), entries(), is_watched(), level(), remove(), _user(), test_watchlist_controls_coverage_level()

### Community 62 - "public.py"
Cohesion: 0.08
Nodes (18): auth_status(), cache_size(), _cached(), calendar(), build(), clear_cache(), PublicCalendarOut, PublicEventOut (+10 more)

### Community 63 - "parser.py"
Cohesion: 0.18
Nodes (10): Context, _dedupe(), dims_hash(), _parse_context(), period_type(), _unit_label(), test_contexts_resolved_from_dates_not_ids(), test_dims_hash_is_order_independent() (+2 more)

### Community 64 - "CompanyPage.tsx (2)"
Cohesion: 0.19
Nodes (16): CompRow, CompsTable, PeerList, AS_FLAG, BASES, Basis, Blank(), Comps() (+8 more)

### Community 65 - "Workbook Engine Design"
Cohesion: 0.17
Nodes (12): Change set and change items, Excel bridge (xlwings, Office.js later), Workbook fingerprint, Hidden tag (custom document property), Initiation pack, Roll-forward, Section 13 Model discovery and recognition, Section 14 Template onboarding (+4 more)

### Community 66 - "Sign-in, roles, upload limit and model locks: design"
Cohesion: 0.13
Nodes (14): 10. Other screens still to be mocked, 11. Constraints and facts from the codebase, 12. Left to the builder, 13. Open decisions for the owner, 1. Intent, 2. Goals, 3. Non-goals and anti-goals, 4. Roles (+6 more)

### Community 67 - "ToolExecutor (1) (2)"
Cohesion: 0.17
Nodes (4): ModelReader, _tool(), ToolExecutor, test_tool_executor_looks_companies_up_like_everywhere_else()

### Community 68 - "docs/pipeline.py"
Cohesion: 0.12
Nodes (11): TextChunk, Embedder, get_embedder(), LocalEmbedder, store_chunks(), DocResult, _passing(), process_document() (+3 more)

### Community 69 - "search.py"
Cohesion: 0.20
Nodes (11): _run(), search(), SearchHit, test_parse_equity_list_handles_both_header_styles(), test_rights_entitlements_are_not_companies(), test_search_matches_words_in_any_order(), symbols(), test_search_narrows_with_each_keystroke() (+3 more)

### Community 70 - "audio.py (1)"
Cohesion: 0.15
Nodes (10): _add_cuda_dll_dirs(), AudioTranscript, _clock(), _has_cuda(), Segment, transcribe(), 5. Security requirements (hard rules), engine() (+2 more)

### Community 71 - "LocalStore (1)"
Cohesion: 0.36
Nodes (3): LocalStore, test_builtin_template_file_is_rebuilt_when_storage_lost_it(), test_store_gzips_xml_and_returns_the_original_bytes()

### Community 72 - "calc.py"
Cohesion: 0.31
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

### Community 76 - "test_upload_limit.py"
Cohesion: 0.08
Nodes (20): get_store(), Global Constraints, Review Focus, Self-review notes, Sign-in, Roles and Upload Limit (Stage 1) Implementation Plan, Task 12: Records and end-to-end check, Task 1: Tables, config and dependency, Task 7: Upload limit (+12 more)

### Community 77 - "test_auth_hardening.py"
Cohesion: 0.10
Nodes (10): raw(), sent(), _signed_in(), small_cap(), test_reset_request_timing_known_vs_unknown(), test_sign_out_everywhere_ends_every_session_and_token(), test_sign_out_everywhere_needs_the_anti_forgery_header(), test_streamed_oversized_body_is_cut_off() (+2 more)

### Community 78 - "Results Collection Design"
Cohesion: 0.25
Nodes (5): NSE request limit and watchdog, Workflow 1 Results collection, Newest filed value wins (restatements), How it works pipeline (ingest, XBRL, facts, approve, drafts), Status v0.0.5 (data layer on real NSE data)

### Community 80 - "desk.py"
Cohesion: 0.39
Nodes (4): _change(), LastClose, latest_price(), latest_prices()

### Community 81 - "Example NBFC Mapping"
Cohesion: 0.38
Nodes (7): Example NBFC quarterly template mapping, checks (balance sheet difference expect 0), drivers (loan_yield actual to forecast), kpi:gold_loan_aum row, period_axis (Period header row, A/E flag row), units default_transform div:10000000 (INR to crore), xbrl source rows (RevenueFromOperations, OtherIncome, FinanceCosts, ProfitLossForPeriod)

### Community 82 - "Filing"
Cohesion: 0.16
Nodes (11): Filing, process_feed_item(), _change(), _groups(), infer_revision_flags(), LineChange, _quarter_values(), Revision (+3 more)

### Community 83 - "Grounded GenAI Design"
Cohesion: 0.33
Nodes (5): Claude API usage policy (Claude.create, fallbacks, Batch), Grounding and style check, Workflow 8 Documents, KPIs and reports, Reports set-up (quarterly update, initiating coverage), Section-by-section report runner (proposed)

### Community 84 - "taskpane.tsx"
Cohesion: 0.36
Nodes (9): get(), Item, readTag(), readToken(), select(), SignedOut, TaskPane(), TokenForm() (+1 more)

### Community 85 - "web/package.json"
Cohesion: 0.09
Nodes (21): ag-grid-community, ag-grid-react, echarts, echarts-for-react, eslint, jsdom, openapi-typescript, prettier (+13 more)

### Community 86 - "office-addin/package.json"
Cohesion: 0.05
Nodes (35): dependencies, react, react-dom, devDependencies, office-addin-debugging, office-addin-dev-certs, office-addin-manifest, @types/office-js (+27 more)

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

### Community 122 - "extract.py"
Cohesion: 0.19
Nodes (12): batch_params(), build_prompt(), extract(), ExtractedKpi, Extraction, extraction_schema(), map_back(), _norm() (+4 more)

### Community 123 - "parse_equity_list"
Cohesion: 0.19
Nodes (12): _date(), _decimal(), ListedCompany, LoadSummary, _norm_header(), parse_equity_list(), refresh_from_nse(), upsert_universe() (+4 more)

### Community 124 - "Company"
Cohesion: 0.18
Nodes (6): Company, CompanyIndex, normalise_name(), test_name_matching(), _company(), test_ingest_stores_corrected_amounts_and_revalidating_never_doubles_them()

### Community 125 - "test_scale_check.py"
Cohesion: 0.27
Nodes (12): HistoryFact, history(), quarter_file(), standalone_q2(), test_a_real_jump_reported_on_both_bases_passes(), test_amounts_100_times_too_small_are_corrected_when_both_signals_agree(), test_both_bases_slipped_together_are_corrected(), test_one_signal_alone_is_a_suspect_never_a_correction() (+4 more)

### Community 126 - "devDependencies"
Cohesion: 0.12
Nodes (16): devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks, jsdom, openapi-typescript, prettier, @testing-library/dom (+8 more)

### Community 127 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 128 - "ParsedFiling"
Cohesion: 0.23
Nodes (4): sheet_lines(), SheetLine, _date_or_none(), ParsedFiling

### Community 129 - "package.json"
Cohesion: 0.15
Nodes (12): description, engines, node, name, packageManager, private, scripts, api-types (+4 more)

### Community 130 - ".__call__"
Cohesion: 0.26
Nodes (7): counted_receive(), tracked_send(), _refuse(), _reply_seconds(), receive(), run(), send()

### Community 131 - "Claude"
Cohesion: 0.24
Nodes (4): Claude, ClaudeResult, RefusalError, request_hash()

### Community 132 - "compilerOptions"
Cohesion: 0.17
Nodes (11): compilerOptions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck, strict (+3 more)

### Community 133 - "dependencies"
Cohesion: 0.17
Nodes (12): dependencies, ag-grid-community, ag-grid-react, echarts, echarts-for-react, @fontsource-variable/inter, pdfjs-dist, react (+4 more)

### Community 134 - "search.py"
Cohesion: 0.25
Nodes (5): BackfillSummary, run_backfill(), classify_announcement(), get(), test_announcement_classifier()

### Community 135 - "recalc.py"
Cohesion: 0.29
Nodes (3): evaluate(), _plain(), recalc_file()

### Community 136 - "stocks_workbook.py"
Cohesion: 0.42
Nodes (5): bse(), main(), nse(), remaining(), _write()

### Community 137 - "FetchOutcome"
Cohesion: 0.28
Nodes (4): FetchOutcome, record_gap(), handler(), test_no_filings_list_records_reason_and_drops_resolved()

### Community 138 - "create_report"
Cohesion: 0.29
Nodes (3): create_report(), get_report(), qa()

### Community 139 - "last_close_day"
Cohesion: 0.33
Nodes (4): last_close_day(), test_prices_are_overdue_only_after_the_evening_window(), expected(), test_latest_close_day_waits_for_the_evening_and_skips_weekends()

### Community 140 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, api-types, build, dev, format, lint, test

### Community 141 - "transcripts.py"
Cohesion: 0.53
Nodes (4): as_prompt_text(), parse_turns(), _role(), Turn

### Community 142 - "schema.d.ts"
Cohesion: 0.33
Nodes (5): components, $defs, operations, paths, webhooks

### Community 145 - "eslint.config.js"
Cohesion: 0.50
Nodes (3): @eslint/js, eslint-plugin-react-hooks, typescript-eslint

## Knowledge Gaps
- **116 isolated node(s):** `react`, `react-dom`, `@types/office-js`, `@types/react`, `@types/react-dom` (+111 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1067 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **50 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_month_end()` connect `changeset.py` to `Results Calendar UI`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `Company` (e.g. with `company_or_404()` and `company_index()`) actually correct?**
  _`Company` has 67 INFERRED edges - model-reasoned connections that need verification._
- **What connects `react`, `react-dom`, `@types/office-js` to the rest of the system?**
  _116 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CompanyPage.tsx (1)` be split into smaller, more focused modules?**
  _Cohesion score 0.1191919191919192 - nodes in this community are weakly interconnected._
- **Why does `Task 10: Sign-in in the web app` connect `@tanstack/react-query` to `auth.py`, `test_upload_limit.py`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `Filing` (e.g. with `filings()` and `watchlist()`) actually correct?**
  _`Filing` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Should `get_settings()` be split into smaller, more focused modules?**
  _Cohesion score 0.044622044622044624 - nodes in this community are weakly interconnected._