from contextlib import nullcontext

from app import recommendation_worker


# Drain every currently queued job, then stop immediately after the first empty claim.
def test_drain_queued_jobs_does_not_poll_after_queue_is_empty(monkeypatch):
    jobs = iter([{"id": "job-1"}, {"id": "job-2"}, None])
    claimed: list[object] = []
    processed: list[str] = []

    monkeypatch.setattr(recommendation_worker, "get_connection", lambda: nullcontext(object()))

    def claim(_connection):
        job = next(jobs)
        claimed.append(job)
        return job

    monkeypatch.setattr(recommendation_worker, "claim_next_recommendation_job", claim)
    monkeypatch.setattr(
        recommendation_worker,
        "_run_job",
        lambda job: processed.append(str(job["id"])),
    )

    recommendation_worker._drain_queued_jobs()

    assert processed == ["job-1", "job-2"]
    assert claimed == [{"id": "job-1"}, {"id": "job-2"}, None]
