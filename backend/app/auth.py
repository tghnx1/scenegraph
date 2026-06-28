from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from time import time

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from psycopg import Connection

from app.db import get_connection
from app.schemas import RegisterRequest

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
PUBLIC_API_KEY = os.getenv("PUBLIC_API_KEY")

if JWT_SECRET_KEY is None:
    raise RuntimeError("JWT_SECRET_KEY not configured")

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
rate_limit_attempts: dict[str, list[float]] = {}


def _user_id_from_jwt(token: str, connection: Connection) -> int:
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


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, role, status, artist_id
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
    return user


def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization")
    # x_user_id: int | None = Header(default=None, alias="X-User-Id", ge=1),
) -> int:
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid token")
        with get_connection() as connection:
            return _user_id_from_jwt(token, connection)
    # if x_user_id is not None:
    #     return x_user_id
    raise HTTPException(status_code=401, detail="authenticated user required")


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin token required")
    return current_user


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 60) -> None:
    now = time()
    attempts = rate_limit_attempts.get(key, [])
    attempts = [attempt for attempt in attempts if now - attempt < window_seconds]
    if len(attempts) >= max_attempts:
        raise HTTPException(status_code=429, detail="Too many attempts. Try later again")
    attempts.append(now)
    rate_limit_attempts[key] = attempts


def validate_registration_input(register_data: RegisterRequest) -> str | None:
    if not USERNAME_RE.match(register_data.username):
        return "Username must be 3-32 characters and contain only letters, numbers, _ or -"
    if "@" not in register_data.email or len(register_data.email) > 254:
        return "Invalid email"
    if len(register_data.password) < 8:
        return "Password must be at least 8 characters"
    if len(register_data.password) > 128:
        return "Password is too long"
    return None


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password is too long"
    return None


def log_activity(
    connection: Connection,
    user_id: int | None,
    username: str | None,
    event_type: str,
    target: str | None = None,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, username, event_type, target)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, username, event_type, target),
        )
    connection.commit()


def require_public_api_key(api_key: str | None = Header(alias="X-API-Key")) -> None:
    if not PUBLIC_API_KEY or api_key != PUBLIC_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
