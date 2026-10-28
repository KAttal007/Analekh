"""Reports, initiation drafts and Q&A (design doc 17, 20). Comps and alerts have their own
routers (comps.py, system.py)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, Store, User, company_or_404
from analekh.db.models import Company, Model, Report
from analekh.locks import holding

router = APIRouter(tags=["outputs"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/reports")
def create_report(body: schemas.ReportRequest, db: DB, store: Store, user: User) -> dict:
    """Flash, note, slides, digest or initiation. Ungrounded output is returned blocked.
    PHASE 4: move to a Celery job; runs inline for now.

    The model the report reads (the one named, else the company's models) is locked while the
    report runs; a company without a model takes no lock."""
    c = company_or_404(db, body.symbol)
    if body.kind == "initiation" and body.model_id is None:
        raise HTTPException(422, "an initiation draft needs the built model (model_id)")
    if body.model_id is not None:
        model = db.get(Model, body.model_id)
        if model is None or model.company_id != c.id:
            raise HTTPException(404, "model not found for this company")
        model_ids = [body.model_id]
    else:
        model_ids = list(db.scalars(select(Model.id).where(Model.company_id == c.id)))
    with holding(db, model_ids=model_ids, user_id=user, activity="report"):
        return _run_report(body, db, store, c)


def _run_report(body: schemas.ReportRequest, db: DB, store: Store, c: Company) -> dict:
    from analekh.genai.client import Claude
    from analekh.genai.reports import run_report
    from analekh.genai.tools import ModelReader, ToolExecutor

    claude = Claude(db)
    run = run_report(
        claude,
        ToolExecutor(db, ModelReader(db, store)),
        body.kind,
        company=c.nse_symbol,
        period_end=body.period_end.isoformat(),
        model_id=body.model_id,
    )
    report = Report(
        company_id=c.id,
        model_id=body.model_id,
        kind=body.kind,
        model_used=claude.model,
        citations={"tool_calls": run.tool_calls, "grounding": run.grounding.__dict__},
    )
    db.add(report)
    db.flush()
    return {
        "report_id": report.id,
        "blocked": run.blocked,
        "unmatched_numbers": run.grounding.unmatched,
        "text": run.text,
    }


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: DB) -> dict:
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(404)
    return {
        "id": r.id,
        "kind": r.kind,
        "model_id": r.model_id,
        "storage_key": r.storage_key,
        "citations": r.citations,
        "created_at": r.created_at,
    }


@router.post("/qa")
def qa(body: schemas.QaRequest, db: DB) -> dict:
    from analekh.genai.client import Claude
    from analekh.genai.reports import run_report
    from analekh.genai.tools import ToolExecutor

    c = company_or_404(db, body.symbol)
    run = run_report(Claude(db), ToolExecutor(db), "qa", company=c.nse_symbol, question=body.question)
    return {
        "answer": run.text,
        "blocked": run.blocked,
        "unmatched_numbers": run.grounding.unmatched,
    }
