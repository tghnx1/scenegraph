from __future__ import annotations

from psycopg import Connection


AUTO_APPROVE_PENDING_USERS_SETTING = "auto_approve_pending_users"


def get_boolean_setting(connection: Connection, setting_key: str, *, default: bool = False) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT setting_value
            FROM app_settings
            WHERE setting_key = %s
            """,
            (setting_key,),
        )
        row = cursor.fetchone()

    if row is None:
        return default
    return bool(row["setting_value"])


def set_boolean_setting(connection: Connection, setting_key: str, setting_value: bool) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON CONFLICT (setting_key)
            DO UPDATE SET setting_value = EXCLUDED.setting_value
            """,
            (setting_key, setting_value),
        )
