"""Celery wrappers for report thread jobs. The work is in analekh/reports/jobs.py."""

from analekh.config import get_settings
from analekh.db.session import session_scope
from analekh.ingest.storage import default_store
from analekh.jobs.app import app
from analekh.reports.chat import Selection
from analekh.reports.jobs import do_chat_turn, do_first_draft

_LIMIT = get_settings().chat_turn_timeout_s


def _tools(db):  # type: ignore[no-untyped-def]
    from analekh.genai.client import Claude
    from analekh.genai.tools import ModelReader, ToolExecutor

    store = default_store()
    return store, Claude(db), ToolExecutor(db, ModelReader(db, store))


@app.task(bind=True, soft_time_limit=_LIMIT, time_limit=_LIMIT + 30)
def generate_first_draft(self, thread_id: int, user_id: str) -> None:  # type: ignore[no-untyped-def]
    with session_scope() as db:
        store, claude, executor = _tools(db)
        do_first_draft(db, store, claude, executor, thread_id=thread_id, user_id=user_id, job_id=self.request.id)


@app.task(bind=True, soft_time_limit=_LIMIT, time_limit=_LIMIT + 30)
def run_chat_turn(self, thread_id: int, message: str, selection: dict | None, user_id: str) -> None:  # type: ignore[no-untyped-def]
    with session_scope() as db:
        store, claude, executor = _tools(db)
        picked = Selection(unit=selection["unit"], block=selection.get("block")) if selection else None
        do_chat_turn(db, store, claude, executor, thread_id=thread_id, message=message, selection=picked, user_id=user_id, job_id=self.request.id)


@app.task(soft_time_limit=_LIMIT, time_limit=_LIMIT + 30)
def learn_from_publish(published_id: int) -> int:
    """Propose lessons from a published report; returns how many were added or strengthened."""
    from analekh.genai.client import Claude
    from analekh.reports.lessons import learn_from_published

    with session_scope() as db:
        return len(learn_from_published(db, default_store(), Claude(db), published_id))


@app.task(bind=True, soft_time_limit=_LIMIT, time_limit=_LIMIT + 30)
def run_qa_turn(self, qa_id: int, question: str, user_id: str) -> None:  # type: ignore[no-untyped-def]
    from analekh.genai.qa_chat import do_qa_turn

    with session_scope() as db:
        _, claude, executor = _tools(db)
        do_qa_turn(db, claude, executor, qa_id=qa_id, question=question, user_id=user_id, job_id=self.request.id)
