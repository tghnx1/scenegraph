from __future__ import annotations

from fastapi import Header, HTTPException


def get_current_user_id(
    x_user_id: int | None = Header(default=None, alias="X-User-Id", ge=1),
) -> int:
    """Temporary feedback-only seam until the real auth dependency is merged."""
    # TODO: switch this to the real authenticated user identity once auth lands.
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="authenticated user required")
    return x_user_id
