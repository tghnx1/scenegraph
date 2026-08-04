from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


ADMIN_USER_ID = 98_101
ADMIN_USERNAME = f"ui-settings-admin-{ADMIN_USER_ID}"

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def cleanup() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM app_settings WHERE setting_key = 'show_graph_tab'")
            cursor.execute("DELETE FROM users WHERE id = %s", (ADMIN_USER_ID,))
            connection.commit()


def seed_admin() -> None:
    cleanup()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, status)
                VALUES (%s, %s, %s, 'test-password-hash', 'admin', 'approved')
                """,
                (
                    ADMIN_USER_ID,
                    ADMIN_USERNAME,
                    f"{ADMIN_USERNAME}@example.com",
                ),
            )
            connection.commit()


def test_ui_settings_can_hide_and_restore_graph_tab() -> None:
    seed_admin()
    try:
        public_response = client.get('/api/settings/ui')
        assert public_response.status_code == 200
        assert public_response.json()['show_graph_tab'] is True

        update_response = client.put(
            '/api/admin/settings/ui',
            headers=admin_headers(),
            json={'show_graph_tab': False},
        )
        assert update_response.status_code == 200
        assert update_response.json()['show_graph_tab'] is False

        hidden_response = client.get('/api/settings/ui')
        assert hidden_response.status_code == 200
        assert hidden_response.json()['show_graph_tab'] is False

        restore_response = client.put(
            '/api/admin/settings/ui',
            headers=admin_headers(),
            json={'show_graph_tab': True},
        )
        assert restore_response.status_code == 200
        assert restore_response.json()['show_graph_tab'] is True
    finally:
        cleanup()
