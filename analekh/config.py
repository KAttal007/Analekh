"""Settings from environment variables (design doc 22.3). Secrets never live in code."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/analekh"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # S3 API: MinIO locally, any S3 service when hosted (Appendix G.9).
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "analekh"
    minio_secure: bool = False

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_small_model: str = "claude-haiku-5-5"

    embeddings_provider: str = "local"
    embedding_dim: int = 1024

    feed_poll_seconds: int = 300
    event_feed_poll_seconds: int = 1800
    universe_refresh_cron: str = "0 6 * * 1"  # weekly, Monday 06:00 IST
    # One request to NSE's latest-results list per run, at 09:00, 10:00 ... 23:00 IST; outside a
    # results season analekh.seasons skips every run but 21:00 (design doc 9.6; every hour from
    # 2026-10-23, every 2 hours from 2026-10-16, once a day before that).
    results_watch_cron: str = "0 9-23 * * *"
    # NSE's daily bhavcopy, after the close on trading days; hourly retries until it is published
    # (a stored day is skipped, so only the first successful run downloads anything).
    prices_cron: str = "0 19-23 * * 1-5"
    backfill_priority: str = "NIFTY500"
    download_rate_per_second: float = 1.0
    user_agent: str = "Analekh/0.1"
    # Sent as the HTTP From header. NSE's CDN stalls requests whose User-Agent holds an email
    # address or a URL (seen 2026-10-14), so the contact never goes in the User-Agent.
    contact_email: str | None = None
    http_timeout_seconds: float = 30.0
    # Tries per request (first try included) before the polite client gives up.
    http_max_attempts: int = 4
    # A listed XBRL file that arrives cut off is fetched this many times in all before it is
    # skipped (seen on Laurus Labs: the XML stops partway through).
    integrated_file_attempts: int = 2
    # The results watcher reads NSE's latest-results list in ONE request per run (rule 1). Busiest
    # day on record: 692 filings, so 1000 covers a day of missed runs. A truncated page makes the
    # next run ask for double, up to the cap; a full one resets it.
    latest_page_size: int = 1000
    latest_max_page_size: int = 4000

    import_dir: Path = Path("./import")
    # The id that pre-sign-in data (watchlist, templates) is keyed by; `analekh create-admin
    # --adopt-local` moves it to the first admin.
    default_user_id: str = "local"

    # Browser origins allowed to call the API with the session cookie, separated by ";": the web
    # app, and the Office add-in once its dev certificate covers 127.0.0.1 (its manifest still says
    # https://localhost:3000, so add that origin here until then).
    cors_origins: str = "http://127.0.0.1:5173;https://127.0.0.1:3000"

    # Sign-in (auth design, stage 1)
    # The one switch: ENV=dev keeps sign-in OFF (every request acts as the built-in admin; the
    # session cookie works over plain http); anything else (ENV=prod) keeps it ON. Defaults to
    # prod so a forgotten setting fails safe; local `.env` files say ENV=dev.
    env: str = "prod"
    # Optional override, dev only: AUTH_ENABLED=true tries the real sign-in while ENV=dev.
    # AUTH_ENABLED=false outside dev is refused at start-up (check_auth_switch).
    auth_enabled: bool | None = None
    session_idle_hours: int = 9
    password_min_length: int = 15
    session_max_hours: int = 24  # hard cap from sign-in, however active (a fresh sign-in each day)
    # Failed sign-ins per account: pause at the Nth, block (until a password reset) at the Mth.
    login_pause_after: int = 3
    login_block_after: int = 5
    # Long enough that guessing pays nothing (owner, 2026-10-22: raised from 5); short enough that
    # a colleague paused by someone else's typos is not shut out for long.
    login_pause_minutes: int = 15
    # Failed sign-ins per client address (any accounts): past the limit, that address gets a 429
    # until its oldest failure leaves the window. Kept in memory, per API process: before hosting
    # with several processes or behind a proxy, move it to Redis and read trusted proxy headers.
    login_ip_max_failures: int = 30
    login_ip_window_minutes: int = 15
    login_ip_max_tracked: int = 10_000
    # The built-in admin used while AUTH_ENABLED=false (development only; it has no password).
    dev_user_email: str = "dev@analekh.local"
    dev_user_name: str = "Local development"
    reset_code_minutes: int = 10
    reset_max_attempts: int = 5
    # One reset mail per account per cooldown: time for it to arrive and the code to be typed.
    reset_request_cooldown_seconds: int = 120
    # Upload size: the default an admin can change in the app, between the floor and the ceiling.
    max_upload_default_bytes: int = 25 * 1024 * 1024
    min_upload_bytes: int = 1024 * 1024
    max_upload_ceiling_bytes: int = 100 * 1024 * 1024
    # Any request body larger than the ceiling plus this (multipart framing) is refused with 413
    # as it arrives, before the framework spools it to disk.
    request_body_overhead_bytes: int = 1024 * 1024
    # Sign-in sessions past their idle or hard limit are deleted by this job (cron, IST).
    session_purge_cron: str = "30 3 * * *"

    # Public (signed-out) endpoints: one cached answer per range, shared by every visitor.
    public_cache_seconds: int = 60
    public_cache_max_entries: int = 64
    public_calendar_max_days: int = 120  # a public request may not scan more than four months
    # Database pool. The API runs requests on `api_thread_limit` worker threads; the pool must be
    # at least that big or waiting threads starve the ones that would free a connection. When it
    # is full a request waits `db_pool_timeout_seconds`, then gets a 503 instead of hanging.
    api_thread_limit: int = 40
    db_pool_size: int = 20
    db_pool_overflow: int = 20
    db_pool_timeout_seconds: float = 5.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_url: str = ""
    # Sender of reset mail; empty means the user name in SMTP_URL.
    smtp_from: str = ""
    alert_email_to: str = ""

    # Excel bridge (runs on the analyst's machine)
    analekh_api: str = "http://127.0.0.1:8000"
    analekh_token: str = ""  # a token made in Settings; sent as `Authorization: Bearer`
    watch_folders: str = "~/Models"
    save_mode: str = "versioned"  # versioned | in_place (with automatic backup)
    excel_bridge_port: int = 8765

    @property
    def sign_in_on(self) -> bool:
        """Sign-in is on unless ENV=dev, where it is off unless AUTH_ENABLED=true."""
        return self.env != "dev" or self.auth_enabled is True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(";") if o.strip()]

    @property
    def watch_folder_paths(self) -> list[Path]:
        return [Path(p).expanduser() for p in self.watch_folders.split(";") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
