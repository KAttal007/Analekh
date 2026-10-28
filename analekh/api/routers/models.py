"""Coverage Builder, assumptions, model discovery and linking, sync and versions (design doc 13,
15, 16, 20)."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, Store, User, company_or_404, job
from analekh.builder.coverage import (
    BuildNotReadyError,
    NoHistoryError,
    finalize_build,
    start_coverage,
)
from analekh.db.models import Assumption, Company, Model, ModelBuild, ModelVersion, Template
from analekh.discovery import WorkbookHints, discover, link
from analekh.locks import acquire, attach_job, holding, release_for_job
from analekh.templates.onboarding import default_for, ensure_builtin_templates
from analekh.workbook.reader import excel_kind

router = APIRouter(tags=["models"])


def _model(db: DB, model_id: int) -> Model:
    m = db.get(Model, model_id)
    if m is None:
        raise HTTPException(404, "model not found")
    return m


@router.post("/coverage", response_model=schemas.BuildOut)
def start(body: schemas.CoverageRequest, db: DB, store: Store, user: User) -> schemas.BuildOut:
    """Start coverage: build a model from a template with sourced history (section 15).

    The company's existing models are locked while the build runs, so it does not start under a
    colleague's update or report. The new model needs no lock: nobody else can see it before
    this request commits, and its inline build ends with the request."""
    company = company_or_404(db, body.symbol)
    existing = db.scalars(select(Model.id).where(Model.company_id == company.id))
    with holding(db, model_ids=list(existing), user_id=user, activity="build"):
        return _start(body, db, store, company)


def _start(body: schemas.CoverageRequest, db: DB, store: Store, company: Company) -> schemas.BuildOut:
    ensure_builtin_templates(db, store)
    template = db.get(Template, body.template_id) if body.template_id else default_for(db, company.industry or company.sector)
    template = template or default_for(db, None)
    if template is None or template.status != "active":
        raise HTTPException(409, "no active template for this sector; upload and test one")
    try:
        res = start_coverage(db, store, company, template)
    except NoHistoryError as exc:
        raise HTTPException(409, f"{exc}; run POST /companies/{company.nse_symbol}/analyse to backfill first") from exc
    return schemas.BuildOut(
        model=schemas.ModelOut.model_validate(res.model),
        build_status=res.build.status,
        filled_cells=len(res.fill.written),
        blank_rows=res.fill.blank_rows,
        assumptions=[schemas.AssumptionOut.model_validate(a) for a in db.scalars(select(Assumption).where(Assumption.model_id == res.model.id))],
    )


@router.get("/models/{model_id}/assumptions", response_model=list[schemas.AssumptionOut])
def assumptions(model_id: int, db: DB) -> list[Assumption]:
    return list(db.scalars(select(Assumption).where(Assumption.model_id == _model(db, model_id).id).order_by(Assumption.id)))


@router.post("/models/{model_id}/assumptions/decisions", response_model=list[schemas.AssumptionOut])
def decide_assumptions(model_id: int, body: schemas.AssumptionDecisions, db: DB, user: User) -> list[Assumption]:
    """Accept, edit or reject proposed assumptions: part of the build, so it holds the lock."""
    _model(db, model_id)
    with holding(db, model_ids=[model_id], user_id=user, activity="build"):
        return _decide(model_id, body, db)


def _decide(model_id: int, body: schemas.AssumptionDecisions, db: DB) -> list[Assumption]:
    rows = {a.id: a for a in assumptions(model_id, db)}
    pending = {a.id for a in rows.values() if a.decision == "pending"}
    if body.accept_all:
        for a in rows.values():
            if a.decision == "pending":
                a.decision, a.final_value = "accepted", a.proposed_value
    for d in body.decisions:
        item = rows.get(d.id)
        if item is None:
            raise HTTPException(422, f"assumption {d.id} not on model {model_id}")
        if d.id not in pending:
            raise HTTPException(409, f"assumption {d.id} is already decided: reload the page")
        if d.decision == "edited" and d.final_value is None:
            raise HTTPException(422, "edited decisions need final_value")
        item.decision = d.decision
        item.final_value = d.final_value if d.decision == "edited" else (item.proposed_value if d.decision == "accepted" else None)
    db.flush()
    return list(rows.values())


@router.post("/models/{model_id}/finalize")
def finalize(model_id: int, db: DB, store: Store, user: User) -> dict:
    """Write accepted assumptions, run Checks, tag and save version 1 of a built model."""
    model = _model(db, model_id)
    with holding(db, model_ids=[model_id], user_id=user, activity="build"):
        try:
            res = finalize_build(db, store, model, created_by="api")
        except BuildNotReadyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {
            "status": res.build.status,
            "checks": res.checks.as_dict(),
            "version": res.version.version if res.version else None,
        }


@router.post("/models/discover")
def discover_models(body: schemas.DiscoverRequest, db: DB) -> dict:
    hints = [WorkbookHints(**w.model_dump()) for w in body.workbooks]
    return {"candidates": [c.as_dict() for c in discover(db, hints)]}


@router.post("/models/link", response_model=schemas.ModelOut)
def link_model(body: schemas.LinkRequest, db: DB) -> Model:
    """Confirm a discovered workbook belongs to a company; the bridge then writes the tag."""
    model = link(db, company_or_404(db, body.symbol), WorkbookHints(**body.workbook.model_dump()))
    if body.mapping:
        model.mapping = body.mapping
    model.last_seen = datetime.now(UTC)
    db.flush()
    return model


@router.post("/models/{model_id}/link", response_model=schemas.ModelOut)
def relink_model(model_id: int, body: schemas.LinkRequest, db: DB) -> Model:
    model = _model(db, model_id)
    model.company_id = company_or_404(db, body.symbol).id
    model.file_path = body.workbook.path
    db.flush()
    return model


@router.get("/models", response_model=list[schemas.ModelOut])
def list_models(db: DB) -> list[Model]:
    return list(db.scalars(select(Model).order_by(Model.id.desc())))


@router.get("/models/{model_id}/builds")
def builds(model_id: int, db: DB) -> list[dict]:
    return [
        {
            "id": b.id,
            "status": b.status,
            "history_from": b.history_from,
            "history_to": b.history_to,
            "created_at": b.created_at,
        }
        for b in db.scalars(select(ModelBuild).where(ModelBuild.model_id == model_id))
    ]


@router.post("/models/{model_id}/sync", response_model=schemas.JobOut)
def sync(model_id: int, body: schemas.SyncRequest, db: DB, user: User) -> schemas.JobOut:
    """Queue a quarterly update. The lock is taken for the job and committed before it is
    queued, under the job's own id, so the job can give it back however quickly it ends."""
    from analekh.jobs.tasks import sync_model

    _model(db, model_id)
    job_id = str(uuid4())
    acquire(db, model_id=model_id, user_id=user, activity="update", job_id=job_id)
    attach_job(db, model_id=model_id, user_id=user, job_id=job_id, activity="update")
    db.commit()
    try:
        return job(sync_model, model_id, body.filing_id, task_id=job_id)
    except BaseException:
        release_for_job(db, model_id=model_id, job_id=job_id)
        db.commit()
        raise


@router.get("/models/{model_id}/versions/{version}")
def download_version(model_id: int, version: int, db: DB, store: Store) -> Response:
    mv = db.scalar(select(ModelVersion).where(ModelVersion.model_id == model_id, ModelVersion.version == version))
    if mv is None:
        raise HTTPException(404)
    data = store.get(mv.storage_key)
    return Response(data, media_type=excel_kind(data)[1])
