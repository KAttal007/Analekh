"""Template onboarding endpoints (design doc 14, 20)."""

from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, AdminUser, Store, company_or_404
from analekh.api.uploads import read_limited
from analekh.config import get_settings
from analekh.db.models import Template
from analekh.templates.files import EXCEL, TemplateFileError, check_file
from analekh.templates.onboarding import (
    TemplateError,
    activate,
    confirm_mapping,
    set_enabled,
    upload,
    upload_report_template,
)
from analekh.templates.testbuild import run_test_build

router = APIRouter(tags=["templates"])


def _template(db: DB, template_id: int) -> Template:
    t = db.get(Template, template_id)
    if t is None:
        raise HTTPException(404, "template not found")
    return t


def _excel_template(db: DB, template_id: int) -> Template:
    t = _template(db, template_id)
    if t.kind != EXCEL:
        raise HTTPException(409, "mapping, test build and activation apply to Excel models only")
    return t


@router.get("/templates", response_model=list[schemas.TemplateOut])
def list_templates(db: DB, sector: str | None = None, kind: str | None = None) -> list[Template]:
    rows = list(db.scalars(select(Template).order_by(Template.name, Template.version.desc())))
    return [t for t in rows if (sector is None or sector in t.sectors) and (kind is None or t.kind == kind)]


@router.post("/templates", response_model=schemas.TemplateOut)
def upload_template(
    db: DB,
    store: Store,
    admin: AdminUser,
    workbook: Annotated[UploadFile, File()],
    name: Annotated[str, Form(max_length=120)],
    sectors: Annotated[str, Form(description="comma separated", max_length=1000)],
    from_existing_model: Annotated[bool, Form()] = False,
    kind: Annotated[str, Form()] = EXCEL,
) -> Template:
    data = read_limited(db, workbook)
    try:
        suffix, ftype = check_file(kind, workbook.filename, data)
    except TemplateFileError as exc:
        raise HTTPException(422, str(exc)) from exc
    sector_list = [s.strip() for s in sectors.split(",") if s.strip()]
    if kind != EXCEL:
        return upload_report_template(db, store, data, kind=kind, suffix=suffix, ftype=ftype, name=name, sectors=sector_list, owner=admin.id)
    ai = None
    if get_settings().anthropic_api_key:
        from analekh.genai.client import Claude
        from analekh.genai.labels import label_resolver

        ai = label_resolver(Claude(db))
    try:
        return upload(
            db,
            store,
            data,
            name=name,
            owner=admin.id,
            sectors=sector_list,
            from_existing_model=from_existing_model,
            ai=ai,
        )
    except TemplateError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/templates/{template_id}/mapping", response_model=schemas.TemplateOut)
def confirm(template_id: int, mapping: dict[str, Any], db: DB, _: AdminUser) -> Template:
    t = _excel_template(db, template_id)
    try:
        confirm_mapping(db, t, mapping)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return t


@router.post("/templates/{template_id}/test", response_model=schemas.TemplateTestOut)
def test_build(template_id: int, body: schemas.TemplateTestRequest, db: DB, store: Store, _: AdminUser):
    t = _excel_template(db, template_id)
    return run_test_build(db, store, t, company_or_404(db, body.symbol))


@router.post("/templates/{template_id}/activate", response_model=schemas.TemplateOut)
def activate_template(template_id: int, db: DB, _: AdminUser, make_default: bool = False) -> Template:
    t = _excel_template(db, template_id)
    try:
        return activate(db, t, make_default)
    except TemplateError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/templates/{template_id}/disable", response_model=schemas.TemplateOut)
def disable_template(template_id: int, db: DB, _: AdminUser) -> Template:
    return set_enabled(db, _template(db, template_id), False)


@router.post("/templates/{template_id}/enable", response_model=schemas.TemplateOut)
def enable_template(template_id: int, db: DB, _: AdminUser) -> Template:
    try:
        return set_enabled(db, _template(db, template_id), True)
    except TemplateError as exc:
        raise HTTPException(409, str(exc)) from exc
