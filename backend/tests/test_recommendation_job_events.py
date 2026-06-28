import asyncio

from app.recommendations.job_events import (
    RecommendationJobSocketHub,
    _parse_job_update,
)


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_json(self, message: dict[str, object]) -> None:
        self.messages.append(message)


# Verify that internal ownership data is used for routing but not exposed to browsers.
def test_parse_job_update_routes_by_user_and_strips_user_id():
    parsed = _parse_job_update(
        '{"type":"recommendation.job.updated","jobId":"job-1","userId":42,"status":"completed"}'
    )

    assert parsed == (
        42,
        {
            "type": "recommendation.job.updated",
            "jobId": "job-1",
            "status": "completed",
        },
    )


# Reject malformed database notifications instead of forwarding untrusted payloads.
def test_parse_job_update_rejects_invalid_status():
    assert _parse_job_update(
        '{"jobId":"job-1","userId":42,"status":"unknown"}'
    ) is None


# Route updates only to sockets registered for the owning authenticated user.
def test_socket_hub_sends_updates_only_to_owner():
    async def scenario() -> None:
        hub = RecommendationJobSocketHub()
        owner_socket = FakeWebSocket()
        other_socket = FakeWebSocket()
        await hub.add(1, owner_socket)  # type: ignore[arg-type]
        await hub.add(2, other_socket)  # type: ignore[arg-type]

        message = {
            "type": "recommendation.job.updated",
            "jobId": "job-1",
            "status": "completed",
        }
        await hub.send_to_user(1, message)

        assert owner_socket.messages == [message]
        assert other_socket.messages == []

    asyncio.run(scenario())


# Ask all connected sessions to recover state after the PostgreSQL listener reconnects.
def test_socket_hub_requests_resync_for_all_users():
    async def scenario() -> None:
        hub = RecommendationJobSocketHub()
        first_socket = FakeWebSocket()
        second_socket = FakeWebSocket()
        await hub.add(1, first_socket)  # type: ignore[arg-type]
        await hub.add(2, second_socket)  # type: ignore[arg-type]

        await hub.request_resync()

        expected = [{"type": "recommendation.jobs.resync"}]
        assert first_socket.messages == expected
        assert second_socket.messages == expected

    asyncio.run(scenario())
