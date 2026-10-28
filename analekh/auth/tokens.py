"""Bearer tokens for Excel bridge and add-in (auth design, section 5).

Long random string, user creates it and sees it once; only SHA-256 stored. Sent in
`Authorization: Bearer` header, never in a URL; carries user's role.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from analekh.db.models import ApiToken, User

PREFIX = "ak_"  # recognisable in a leaked paste or secret scan


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_api_token(db: Session, user: User, name: str) -> tuple[ApiToken, str]:
    """A new token for `user`. The plain token is returned once and never stored."""
    token = PREFIX + secrets.token_urlsafe(32)
    row = ApiToken(user_id=user.id, name=name.strip(), token_hash=_hash(token))
    db.add(row)
    db.flush()
    return row, token


def user_for_api_token(db: Session, token: str) -> User | None:
    """The active user behind a live token, else None."""
    if not token.startswith(PREFIX):
        return None
    row = db.scalar(select(ApiToken).where(ApiToken.token_hash == _hash(token)))
    if row is None or row.revoked_at is not None:
        return None
    user = db.get(User, row.user_id)
    return user if user is not None and user.is_active else None


def list_api_tokens(db: Session, user: User) -> list[ApiToken]:
    return list(db.scalars(select(ApiToken).where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None)).order_by(ApiToken.created_at)))


def revoke_api_token(db: Session, user: User, token_id: int) -> bool:
    """Revoke one of the user's own tokens. False when it is not theirs or already revoked."""
    row = db.get(ApiToken, token_id)
    if row is None or row.user_id != user.id or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    db.flush()
    return True


def revoke_all_api_tokens(db: Session, user_id: str) -> int:
    """Revoke every live token of one user (sign out everywhere). Returns how many."""
    result = db.execute(update(ApiToken).where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    db.flush()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
