"""RBAC ownership-scoping helpers used by every router.

Two rules across the app:

    1. Regular user: list endpoints return only rows where owner_id == user.id;
       get/patch/delete on someone else's row returns 404 (not 403 — we don't
       leak existence).
    2. Super-admin: sees everything by default; can pass `?owner_id=<uuid>` on
       list endpoints to view one specific user's data ("act as" view).

The helpers are router-level on purpose — services may be called from the Gmail
poller / LangGraph workflow with no `current_user`, so they must stay neutral.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.models.user import User


def scope_query(
    query: Query,
    user: User,
    owner_col,
    requested_owner: Optional[UUID] = None,
) -> Query:
    """Apply the ownership filter to a list query.

    - Regular user → filter to their own rows (requested_owner is ignored).
    - Super-admin  → no filter, OR if requested_owner is provided, filter to that user.
    """
    if user.is_superuser:
        if requested_owner is not None:
            return query.filter(owner_col == requested_owner)
        return query
    return query.filter(owner_col == user.id)


def assert_can_access(entity, user: User, owner_attr: str = "owner_id") -> None:
    """Raise 404 if `user` cannot access `entity`. No-op for super-admin.

    Use immediately after fetching an entity by id but before returning / mutating.
    Returns nothing on success — raises HTTPException(404) otherwise.
    The 404 is deliberate: we don't leak that the entity exists.
    """
    if user.is_superuser:
        return
    owner = getattr(entity, owner_attr, None)
    if owner != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def visible_owner_ids(user: User) -> Optional[set[UUID]]:
    """For raw-SQL or aggregate queries that can't use the helpers above.

    Returns the set of owner_ids this user is allowed to see, or None for
    super-admin (meaning "all"). Callers should treat None as "no filter".
    """
    if user.is_superuser:
        return None
    return {user.id}
