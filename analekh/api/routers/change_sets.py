"""Change-set review and apply (design doc 16.4, 20): nothing is written before every item has a
decision, and apply always saves a new model version. Both are the update's own work, so they
hold the model's lock (model-locks stage 2): a colleague working on the model gets 423."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, Store, User
from analekh.db.models import ChangeSet, Model, ModelVersion
from analekh.ingest.storage import sha256
from analekh.locks import holding
from analekh.modelsync.apply import ApprovedItem, apply_headless
from analekh.workbook.fingerprint import fingerprint
from analekh.workbook.reader import excel_kind, load
from analekh.workbook.recalc import RecalcCannotCompute, RecalcUnavailable, recalc_file

log = logging.getLogger(__name__)
router = APIRouter(tags=["change-sets"])


def _cs(db: DB, cs_id: int) -> ChangeSet:
    cs = db.get(ChangeSet, cs_id)
    if cs is None:
        raise HTTPException(404)
    return cs


@router.get("/change-sets/{cs_id}", response_model=schemas.ChangeSetOut)
def change_set(cs_id: int, db: DB) -> ChangeSet:
    return _cs(db, cs_id)


@router.post("/change-sets/{cs_id}/decisions", response_model=schemas.ChangeSetOut)
def decide(cs_id: int, body: schemas.Decisions, db: DB, user: User) -> ChangeSet:
    cs = _cs(db, cs_id)
    with holding(db, model_ids=[cs.model_id], user_id=user, activity="update"):
        db.refresh(cs)  # read before the lock; a colleague may have moved it since
        return _decide(cs, body, db)


def _decide(cs: ChangeSet, body: schemas.Decisions, db: DB) -> ChangeSet:
    if cs.status not in ("proposed", "approved"):
        raise HTTPException(409, f"change set is {cs.status}")
    items = {i.id: i for i in cs.items}
    # Only items still pending when the request came in can be decided: a page showing an item
    # as pending after someone else decided it must not overwrite that decision.
    pending = {i.id for i in cs.items if i.decision == "pending"}
    for kind in body.accept_kinds:
        for i in cs.items:
            if i.kind == kind and i.decision == "pending":
                i.decision, i.final_value = "accepted", i.new_value
    for d in body.decisions:
        item = items.get(d.item_id)
        if item is None:
            raise HTTPException(422, f"item {d.item_id} not in change set")
        if d.item_id not in pending:
            raise HTTPException(409, f"item {d.item_id} is already decided: reload the change set")
        if d.decision == "edited" and d.final_value is None:
            raise HTTPException(422, "edited decisions need final_value")
        item.decision = d.decision
        item.final_value = (
            d.final_value
            if d.decision == "edited"
            else (item.new_value if d.decision == "accepted" else None)
        )
    if all(i.decision != "pending" for i in cs.items):
        cs.status, cs.decided_at = "approved", datetime.now(UTC)
    db.flush()
    return cs


@router.post("/change-sets/{cs_id}/apply")
def apply(cs_id: int, db: DB, store: Store, user: User) -> dict:
    """Headless apply into a new model version, recalculated by the `recalc` service (or a local
    LibreOffice; see analekh.workbook.recalc). 503 `recalc_unavailable` when it cannot be
    recalculated: nothing is saved. The Excel bridge offers the same on the analyst's machine with
    native recalculation."""
    cs = _cs(db, cs_id)
    with holding(db, model_ids=[cs.model_id], user_id=user, activity="update"):
        db.refresh(cs)  # read before the lock; a colleague may have moved it since
        return _apply(cs, db, store)


def _apply(cs: ChangeSet, db: DB, store: Store) -> dict:
    if cs.status != "approved":
        raise HTTPException(409, "decide every item first")
    latest = (
        db.scalar(
            select(ModelVersion.version)
            .where(ModelVersion.model_id == cs.model_id)
            .order_by(ModelVersion.version.desc())
        )
        or 0
    )
    if cs.base_version != latest:
        # Build or other change set saved a newer version since this was drafted. Deriving from old
        # base would drop that work. Block, never rebase: rebase changes what analyst approved
        # (owner's ruling).
        raise HTTPException(
            409,
            {
                "code": "change_set_stale",
                "message": "The model has changed since this change set was drafted. "
                "Draft a new update.",
                "base_version": cs.base_version,
                "latest_version": latest,
            },
        )
    base = db.scalar(
        select(ModelVersion).where(
            ModelVersion.model_id == cs.model_id, ModelVersion.version == cs.base_version
        )
    )
    if base is None:
        raise HTTPException(404, "base version missing")
    approved = [
        ApprovedItem(
            i.kind,
            i.sheet or "",
            i.cell or "",
            i.final_value,
            i.formula_after if i.decision == "accepted" else None,
        )
        for i in cs.items
        if i.decision in ("accepted", "edited")
    ]
    base_bytes = store.get(base.storage_key)
    written = apply_headless(base_bytes, approved)
    try:
        out = recalc_file(written, reference=base_bytes)
    except RecalcCannotCompute as err:
        # LibreOffice cannot run the analyst's own functions (VBA, add-ins), so saving would put
        # #NAME? where their values were. Nothing is saved; the set stays approved.
        log.error("apply of change set %s refused: cannot compute %s", cs.id, err.cells[:10])
        shown = ", ".join(err.cells[:10]) + (" and more" if len(err.cells) > 10 else "")
        raise HTTPException(
            422,
            {
                "code": "recalc_cannot_compute",
                "message": f"Analekh cannot recalculate {len(err.cells)} cell(s) in this model "
                f"({shown}). They use a function it cannot run, such as a custom VBA function. "
                "Apply from Excel with the Analekh bridge instead.",
                "cells": err.cells[:10],
                "total": len(err.cells),
            },
        ) from err
    except RecalcUnavailable as err:
        # Nothing saved without fresh cached values (checks, ModelReader, report tools read them).
        # Lock released when request ends; change set stays approved, so Apply can be clicked again.
        log.error("apply of change set %s refused: %s", cs.id, err)
        raise HTTPException(
            503,
            {
                "code": "recalc_unavailable",
                "message": "Recalculation is unavailable right now. Try Apply again in a few "
                "minutes, or apply from Excel with the Analekh bridge.",
            },
        ) from err
    suffix, content_type = excel_kind(out)  # an .xlsm model stays an .xlsm
    key = f"models/{cs.model_id}/v{latest + 1}-{sha256(out)[:12]}{suffix}"
    store.put(key, out, content_type)
    db.add(
        ModelVersion(
            model_id=cs.model_id,
            version=latest + 1,
            parent_version=cs.base_version,
            storage_key=key,
            created_by="api",
        )
    )
    model = db.get(Model, cs.model_id)
    if model is not None:
        model.fingerprint = fingerprint(load(written))
        model.last_seen = datetime.now(UTC)
    cs.status = "applied"
    db.flush()
    return {"model_id": cs.model_id, "version": latest + 1, "written": len(approved)}
