"""Per-model locks (model-locks stage 2): who is working on a model, giving a lock back, the
caller's own locks (the sign-in reminder), and for admins the list of every lock and the release
of anyone's."""

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from analekh.api.deps import DB, AdminUser, CurrentUser
from analekh.api.schemas_locks import AdminLockOut, LockOut
from analekh.db.models import Company, Model, ModelLock
from analekh.db.models import User as UserRow
from analekh.locks import force_release, release, status

router = APIRouter(tags=["locks"])


def _model_or_404(db: DB, model_id: int) -> None:
    if db.get(Model, model_id) is None:
        raise HTTPException(404, "model not found")


def _out(lock: ModelLock, holder_name: str, caller_id: str) -> LockOut:
    return LockOut(
        model_id=lock.model_id,
        holder_id=lock.user_id,
        holder_name=holder_name,
        activity=lock.activity,
        taken_at=lock.taken_at,
        mine=lock.user_id == caller_id,
        job_running=lock.job_id is not None,
    )


@router.get("/models/{model_id}/lock", response_model=LockOut | None)
def lock_status(model_id: int, db: DB, current: CurrentUser) -> LockOut | None:
    """The lock on a model, or null when it is free. Any signed-in user may ask."""
    _model_or_404(db, model_id)
    lock = status(db, model_id=model_id)
    if lock is None:
        return None
    holder = db.get(UserRow, lock.user_id)
    return _out(lock, holder.name if holder else "", current.id)


@router.post("/models/{model_id}/lock/release", status_code=204)
def release_lock(model_id: int, db: DB, current: CurrentUser) -> Response:
    """The holder gives the lock back, even one a running job holds (the job's own release is
    then a no-op). Anyone else is refused, admins included: they use the admin route."""
    _model_or_404(db, model_id)
    lock = status(db, model_id=model_id)
    if lock is not None and lock.user_id != current.id:
        raise HTTPException(403, "Only the person working on this model can release it.")
    release(db, model_id=model_id, user_id=current.id)
    return Response(status_code=204)


@router.get("/me/locks", response_model=list[LockOut])
def my_locks(db: DB, current: CurrentUser) -> list[LockOut]:
    """The locks the caller holds, oldest first."""
    locks = db.scalars(select(ModelLock).where(ModelLock.user_id == current.id).order_by(ModelLock.taken_at, ModelLock.model_id))
    return [_out(lock, current.name, current.id) for lock in locks]


@router.get("/admin/locks", response_model=list[AdminLockOut])
def admin_locks(db: DB, admin: AdminUser) -> list[AdminLockOut]:
    """Every current lock, oldest first, with the holder, the model and its company named."""
    rows = db.execute(
        select(ModelLock, UserRow.name, Model.name, Company.nse_symbol, Company.name)
        .join(Model, Model.id == ModelLock.model_id)
        .join(Company, Company.id == Model.company_id)
        .outerjoin(UserRow, UserRow.id == ModelLock.user_id)
        .order_by(ModelLock.taken_at, ModelLock.model_id)
    )
    return [
        AdminLockOut(
            **_out(lock, holder or "", admin.id).model_dump(),
            model_name=model_name,
            company_symbol=symbol,
            company_name=company,
        )
        for lock, holder, model_name, symbol, company in rows
    ]


@router.post("/admin/locks/{model_id}/release", status_code=204)
def admin_release_lock(model_id: int, db: DB, admin: AdminUser) -> Response:
    """An admin frees a model whoever holds it; the audit log names the holder."""
    _model_or_404(db, model_id)
    force_release(db, model_id=model_id, admin_id=admin.id)
    return Response(status_code=204)
