"""Settings from environment variables (design doc 22.3). Secrets never live in code."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/analekh"
    redis_url: str = "redis://127.0.0.1:6379/0"

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
    # season analekh.seasons skips all but 21:00 (design doc 9.6; hourly from 2026-10-23, every 2
    results_watch_cron: str = "0 9-23 * * *"
    prices_cron: str = "0 19-23 * * 1-5"
    backfill_priority: str = "NIFTY500"
    download_rate_per_second: float = 1.0
    user_agent: str = "Analekh/0.1"
    contact_email: str | None = None
    http_timeout_seconds: float = 30.0
    http_max_attempts: int = 4
    http_max_redirects: int = 5  # each hop is checked against the allow-list
    integrated_file_attempts: int = 2
    # Results watcher reads NSE's latest-results list in ONE request per run (rule 1). Busiest day
    latest_page_size: int = 1000
    latest_max_page_size: int = 4000

    # Recalculation on Apply (design doc 16.5, 22.1). RECALC_URL set: workbooks go to `recalc`
    recalc_url: str = ""
    recalc_token: str = ""
    recalc_timeout_seconds: float = 180.0
    recalc_retries: int = 1
    recalc_retry_delay_seconds: float = 2.0
    recalc_fallback: Literal["fail", "local"] = "fail"

    import_dir: Path = Path("./import")
    default_user_id: str = "local"

    # add-in once its dev certificate covers 127.0.0.1 (manifest still says https://localhost:3000,
    cors_origins: str = "http://127.0.0.1:5173;https://127.0.0.1:3000"

    env: str = "prod"
    auth_enabled: bool | None = None
    session_idle_hours: int = 9
    password_min_length: int = 15
    # Password rules (first-password design, section 5). The max also caps sign-in and every
    password_max_length: int = 30
    password_min_letters: int = 8
    password_min_digits: int = 1
    password_min_specials: int = 1
    password_min_upper: int = 1
    password_min_lower: int = 1
    first_password_hours: int = 24
    first_password_length: int = 20
    session_max_hours: int = 24  # hard cap from sign-in, however active (a fresh sign-in each day)
    session_max_per_user: int = 3  # browsers signed in at once; one more must end one first
    session_choice_minutes: int = 5  # how long that "end which device?" step stays open
    device_cookie_days: int = 365  # a browser is remembered this long after its last sign-in
    device_name_max_length: int = 40
    login_pause_after: int = 3
    login_block_after: int = 5
    login_pause_minutes: int = 15
    login_ip_max_failures: int = 30
    login_ip_window_minutes: int = 15
    login_ip_max_tracked: int = 10_000
    dev_user_email: str = "dev@analekh.local"
    dev_user_name: str = "Local development"
    reset_code_minutes: int = 2
    reset_max_attempts: int = 5
    reset_request_cooldown_seconds: int = 120
    reset_max_failures: int = 20  # wrong codes across codes before reset locks
    reset_lockout_hours: int = 24  # counted from the last code issued
    max_upload_default_bytes: int = 25 * 1024 * 1024
    min_upload_bytes: int = 1024 * 1024
    max_upload_ceiling_bytes: int = 100 * 1024 * 1024
    request_body_overhead_bytes: int = 1024 * 1024
    lock_poll_seconds: int = 20
    idle_reminder_minutes: int = 30
    session_purge_cron: str = "30 3 * * *"
    sebi_watch_cron: str = "30 8 * * *"  # SEBI offer-document lists, once a day (IST)

    public_cache_seconds: int = 60
    public_cache_max_entries: int = 64
    public_calendar_max_days: int = 120  # a public request may not scan more than four months
    api_thread_limit: int = 40
    db_pool_size: int = 20
    db_pool_overflow: int = 20
    db_pool_timeout_seconds: float = 5.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_url: str = ""
    smtp_from: str = ""
    alert_email_to: str = ""
    web_app_url: str = ""

    analekh_api: str = "http://127.0.0.1:8000"
    analekh_token: str = ""  # a token made in Settings; sent as `Authorization: Bearer`
    watch_folders: str = "~/Models"
    save_mode: str = "versioned"  # versioned | in_place (with automatic backup)
    excel_bridge_port: int = 8765

    def check_password_settings(self) -> None:
        """Refuse rule settings no password can meet."""
        needed = self.password_min_letters + self.password_min_digits + self.password_min_specials
        if needed > self.password_max_length:
            raise ValueError("password rules need more characters than password_max_length allows")
        if self.password_min_length > self.password_max_length:
            raise ValueError("password_min_length is above password_max_length")
        if not self.password_min_length <= self.first_password_length <= self.password_max_length:
            raise ValueError("first_password_length must sit between the password min and max")
        if self.password_min_upper + self.password_min_lower > self.password_min_letters:
            raise ValueError("upper plus lower minimums exceed password_min_letters")

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
    settings = Settings()
    settings.check_password_settings()
    return settings
