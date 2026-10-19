"""Last run of each scheduled job, for the data status on the Settings screen."""

from datetime import UTC, datetime
from typing import Any

import structlog

from analekh.db.models import JobStatus
from analekh.db.session import session_scope

log = structlog.get_logger()


def record(name: str, status: str, summary: dict[str, Any]) -> None:
    """Note a run: ok (did its work), skipped (not due, or nothing to fetch) or error. Never
    raises: a job must not fail because its status could not be written."""
    now = datetime.now(UTC)
    try:
        with session_scope() as s:
            row = s.get(JobStatus, name) or JobStatus(name=name)
            row.last_run_at, row.last_status, row.last_summary = now, status, summary
            if status == "ok":
                row.last_ok_at, row.last_ok_summary = now, summary
            s.add(row)
    except Exception as exc:  # noqa: BLE001 - the job's own result matters more
        log.warning("job_status_not_recorded", job=name, error=str(exc))
