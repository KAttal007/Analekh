"""Data status and alerts, for the Settings screen (design doc 19.1)."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter
from sqlalchemy import func, inspect, select, text

from analekh import __version__, seasons
from analekh.alerts.notify import send_email, send_telegram
from analekh.api import schemas
from analekh.api.deps import DB
from analekh.config import get_settings
from analekh.db.models import Alert, Company, Filing, JobStatus, Price
from analekh.glance import quarter_label

router = APIRouter(tags=["system"])
log = structlog.get_logger()

# A start counts as missed when nothing was recorded this long after it (runs take seconds to a
# few minutes; NSE retries included).
GRACE = timedelta(minutes=20)
PRICES_DUE_AFTER = timedelta(hours=5, minutes=30)


def _run(db: DB, name: str) -> schemas.JobRunOut:
    # Before `alembic upgrade head` the table doesn't exist yet: say "not recorded", don't fail.
    if not inspect(db.get_bind()).has_table(JobStatus.__tablename__):
        return schemas.JobRunOut()
    row = db.get(JobStatus, name)
    if row is None:
        return schemas.JobRunOut()
    return schemas.JobRunOut(
        last_run_at=row.last_run_at,
        last_status=row.last_status,
        last_summary=row.last_summary or {},
        last_ok_at=row.last_ok_at,
        last_ok_summary=row.last_ok_summary,
    )


def _season(s: seasons.Season | None) -> schemas.SeasonOut | None:
    if s is None:
        return None
    return schemas.SeasonOut(
        quarter_end=s.quarter_end,
        quarter_label=quarter_label(s.quarter_end),
        opens=s.opens,
        closes=s.closes,
    )


def watcher_status(db: DB, now: datetime) -> schemas.WatcherStatusOut:
    run = _run(db, "results_watch")
    today = now.astimezone(seasons.IST).date()
    season = seasons.season_for(today)
    started = seasons.previous_start(now)
    # Only once something was recorded: a fresh install has no runs yet, which isn't a miss.
    missed = None
    if run.last_run_at is not None and now - started > GRACE and run.last_run_at < started:
        missed = started
    return schemas.WatcherStatusOut(
        run=run,
        in_season=season is not None,
        season=_season(season),
        next_season=None if season else _season(seasons.next_season(today)),
        schedule=(
            "Every 2 hours, 09:00 to 23:00 IST"
            if season
            else "Once a day at 21:00 IST, until the season opens"
        ),
        next_ask_at=seasons.next_ask(now),
        missed_start_at=missed,
    )


def prices_status(db: DB, now: datetime) -> schemas.PricesStatusOut:
    from analekh.jobs.tasks import last_close_day

    latest = db.scalar(select(func.max(Price.trade_date)))
    counts = db.execute(
        select(func.count(), func.count(Price.market_cap)).where(Price.trade_date == latest)
    ).one()
    return schemas.PricesStatusOut(
        run=_run(db, "prices"),
        latest_day=latest,
        # The job tries hourly from 19:00 to 23:00 IST, so a day's close is only overdue from
        # 23:30: shifting the clock back 5.5 hours moves last_close_day's 18:00 cut-off there.
        expected_day=last_close_day(now - PRICES_DUE_AFTER),
        priced=counts[0] if latest else 0,
        with_market_cap=counts[1] if latest else 0,
    )


def data_counts(db: DB) -> schemas.DataCountsOut:
    active = Company.is_active.is_(True)
    companies, with_sector = db.execute(
        select(func.count(), func.count(Company.sector)).where(active)
    ).one()
    filings, with_results, latest = db.execute(
        select(
            func.count(), func.count(func.distinct(Filing.company_id)), func.max(Filing.filed_at)
        )
    ).one()
    # The planner's estimate: an exact count of ten million rows takes seconds.
    values = db.scalar(text("SELECT reltuples::bigint FROM pg_class WHERE relname = 'facts'"))
    size = db.scalar(text("SELECT pg_database_size(current_database())"))
    return schemas.DataCountsOut(
        companies=companies,
        with_sector=with_sector,
        with_results=with_results,
        filings=filings,
        values_estimate=max(int(values or 0), 0),
        latest_filed_at=latest,
        database_bytes=int(size) if size is not None else None,
    )


@router.get("/status")
def status(db: DB) -> schemas.StatusOut:
    """What the scheduled jobs last did and what is stored. Reads only; never contacts NSE."""
    now = datetime.now(UTC)
    return schemas.StatusOut(
        version=__version__,
        checked_at=now,
        watcher=watcher_status(db, now),
        prices=prices_status(db, now),
        data=data_counts(db),
        ai_configured=bool(get_settings().anthropic_api_key),
    )


@router.get("/system/jobs")
def jobs_available() -> schemas.JobsAvailableOut:
    """Whether background jobs (Analyse, Refresh) can be queued; answers in under half a second."""
    from analekh.jobs.health import NOT_RUNNING, queue_available

    ok = queue_available()
    return schemas.JobsAvailableOut(available=ok, detail=None if ok else NOT_RUNNING)


def _mask(email: str) -> str:
    user, _, domain = email.partition("@")
    return f"{user[:1]}•••@{domain}" if domain else "•••"


@router.get("/alerts/channels")
def alert_channels() -> schemas.AlertChannelsOut:
    """Which alert channels are set up in the environment (never the secrets)."""
    s = get_settings()
    email = bool(s.smtp_url and s.alert_email_to)
    return schemas.AlertChannelsOut(
        telegram=bool(s.telegram_bot_token and s.telegram_chat_id),
        email=email,
        email_to=_mask(s.alert_email_to) if email else None,
    )


@router.post("/alerts/test")
def test_alert(body: schemas.AlertTestIn) -> schemas.AlertTestOut:
    """Send one test message on a channel. Errors are summarised, never echoed: a failed
    Telegram request's message holds the bot token in its URL."""
    text_ = "Analekh test alert: this channel works."
    channels = alert_channels()
    if body.channel == "telegram":
        if not channels.telegram:
            return schemas.AlertTestOut(
                ok=False, detail="Not set up: add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env"
            )
        try:
            ok = send_telegram(text_)
        except Exception as exc:  # noqa: BLE001 - reported to the user without details
            log.warning("test_alert_failed", channel="telegram", error=type(exc).__name__)
            ok = False
        detail = (
            "Sent: check Telegram" if ok else "Telegram refused it: check the token and chat id"
        )
        return schemas.AlertTestOut(ok=ok, detail=detail)
    if not channels.email:
        return schemas.AlertTestOut(
            ok=False, detail="Not set up: add SMTP_URL and ALERT_EMAIL_TO to .env"
        )
    try:
        send_email("Analekh test alert", text_)
    except Exception as exc:  # noqa: BLE001 - reported to the user without details
        log.warning("test_alert_failed", channel="email", error=type(exc).__name__)
        return schemas.AlertTestOut(
            ok=False, detail=f"The mail server refused it ({type(exc).__name__}): check SMTP_URL"
        )
    return schemas.AlertTestOut(ok=True, detail=f"Sent to {channels.email_to}")


@router.get("/alerts")
def alerts(db: DB, limit: int = 50) -> list[schemas.AlertOut]:
    rows = db.execute(
        select(Alert, Company.nse_symbol)
        .outerjoin(Company, Company.id == Alert.company_id)
        .order_by(Alert.id.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return [
        schemas.AlertOut(
            id=a.id,
            kind=a.kind,
            symbol=symbol,
            text=(a.payload or {}).get("text"),
            channel=a.channel,
            sent_at=a.sent_at,
        )
        for a, symbol in rows
    ]
