"""Replies of the lock routes (model-locks stage 2). A holder is named, never emailed."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LockOut(BaseModel):
    """Who is working on a model, doing what, since when; `mine` is true for the caller, and
    `job_running` while a background job (a quarterly update) holds the lock."""

    model_config = ConfigDict(from_attributes=True)

    model_id: int
    holder_id: str
    holder_name: str
    activity: str
    taken_at: datetime
    mine: bool
    job_running: bool


class AdminLockOut(LockOut):
    """A lock in the admin's list: the model and its company named, so the admin knows which
    workbook a release frees."""

    model_name: str
    company_symbol: str
    company_name: str
