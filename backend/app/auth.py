from __future__ import annotations

import os

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from psycopg import Connection

from app.db import get_db

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def _user_id_from_jwt(token: str, connection: Connection) -> int:
    if JWT_SECRET_KEY is None:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY not configured")

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, status
            FROM users
            WHERE id = %s
            """,
            (int(user_id),),
        )
        user = cursor.fetchone()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if user["status"] != "approved":
        raise HTTPException(status_code=403, detail="Account is not approved")
    return int(user["id"])


def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: int | None = Header(default=None, alias="X-User-Id", ge=1),
    connection: Connection = Depends(get_db),
) -> int:
    """Resolve the current user from JWT auth, with a legacy header fallback for tests."""
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return _user_id_from_jwt(token, connection)
    if x_user_id is not None:
        return x_user_id
    raise HTTPException(status_code=401, detail="authenticated user required")
