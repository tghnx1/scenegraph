from __future__ import annotations

import os

from passlib.context import CryptContext
from psycopg import Connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME")
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
BOOTSTRAP_USER_USERNAME = os.getenv("BOOTSTRAP_USER_USERNAME")
BOOTSTRAP_USER_EMAIL = os.getenv("BOOTSTRAP_USER_EMAIL")
BOOTSTRAP_USER_PASSWORD = os.getenv("BOOTSTRAP_USER_PASSWORD")
BOOTSTRAP_USER_ROLE = os.getenv("BOOTSTRAP_USER_ROLE", "artist")
BOOTSTRAP_USER_UPDATE_EXISTING = os.getenv(
    "BOOTSTRAP_USER_UPDATE_EXISTING",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}


def create_bootstrap_admin(connection: Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE role = 'admin'
            LIMIT 1
            """
        )
        admin = cursor.fetchone()
        if admin is not None:
            return
        if (
            not BOOTSTRAP_ADMIN_USERNAME
            or not BOOTSTRAP_ADMIN_EMAIL
            or not BOOTSTRAP_ADMIN_PASSWORD
        ):
            print("Bootstrap admin variables missing")
            return

        hashed_password = pwd_context.hash(BOOTSTRAP_ADMIN_PASSWORD)
        cursor.execute(
            """
            INSERT INTO users
            (
                username,
                email,
                password_hash,
                role,
                status,
                must_change_password
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'admin',
                'approved',
                TRUE
            )
            """,
            (
                BOOTSTRAP_ADMIN_USERNAME,
                BOOTSTRAP_ADMIN_EMAIL,
                hashed_password,
            ),
        )
        connection.commit()


def create_bootstrap_user(connection: Connection) -> None:
    if (
        not BOOTSTRAP_USER_USERNAME
        or not BOOTSTRAP_USER_EMAIL
        or not BOOTSTRAP_USER_PASSWORD
    ):
        return
    if BOOTSTRAP_USER_ROLE not in {"artist", "agent", "admin"}:
        raise RuntimeError("BOOTSTRAP_USER_ROLE must be one of: artist, agent, admin")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (BOOTSTRAP_USER_USERNAME,),
        )
        existing_user = cursor.fetchone()
        password_hash = pwd_context.hash(BOOTSTRAP_USER_PASSWORD)

        if existing_user is not None:
            if not BOOTSTRAP_USER_UPDATE_EXISTING:
                return
            cursor.execute(
                """
                UPDATE users
                SET email = %s,
                    password_hash = %s,
                    role = %s,
                    status = 'approved',
                    must_change_password = FALSE
                WHERE id = %s
                """,
                (
                    BOOTSTRAP_USER_EMAIL,
                    password_hash,
                    BOOTSTRAP_USER_ROLE,
                    existing_user["id"],
                ),
            )
            connection.commit()
            return

        cursor.execute(
            """
            INSERT INTO users (
                username,
                email,
                password_hash,
                role,
                status,
                must_change_password
            )
            VALUES (%s, %s, %s, %s, 'approved', FALSE)
            """,
            (
                BOOTSTRAP_USER_USERNAME,
                BOOTSTRAP_USER_EMAIL,
                password_hash,
                BOOTSTRAP_USER_ROLE,
            ),
        )
    connection.commit()
