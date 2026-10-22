"""Create, list and revoke bearer tokens for the Excel bridge and add-in (plan task 8)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from analekh.api.deps import DB, CurrentUser
from analekh.auth import tokens

router = APIRouter(prefix="/auth/tokens", tags=["auth"])

MAX_NAME = 80  # a label, for example "Office laptop"


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME)


class TokenOut(BaseModel):
    id: int
    name: str
    created_at: datetime


class TokenCreated(TokenOut):
    token: str  # shown once


@router.post("", response_model=TokenCreated, status_code=201)
def create(body: TokenIn, db: DB, current: CurrentUser) -> TokenCreated:
    row, token = tokens.create_api_token(db, current, body.name)
    db.commit()
    return TokenCreated(id=row.id, name=row.name, created_at=row.created_at, token=token)


@router.get("", response_model=list[TokenOut])
def list_tokens(db: DB, current: CurrentUser) -> list[TokenOut]:
    return [
        TokenOut(id=t.id, name=t.name, created_at=t.created_at)
        for t in tokens.list_api_tokens(db, current)
    ]


@router.delete("/{token_id}", status_code=204)
def revoke(token_id: int, db: DB, current: CurrentUser) -> Response:
    if not tokens.revoke_api_token(db, current, token_id):
        raise HTTPException(404, "Token not found.")
    db.commit()
    return Response(status_code=204)
