from contextlib import nullcontext

from app.recommendations import worker as recommendation_worker


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


def test_run_job_dispatches_artist_bio_refresh_jobs(monkeypatch):
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(recommendation_worker, "get_connection", lambda: nullcontext(object()))
    monkeypatch.setattr(
        recommendation_worker,
        "refresh_artist_derived_data",
        lambda connection, *, artist_id: calls.append(("refresh", artist_id)) or {
            "artistId": artist_id,
            "artistName": "Artist",
            "tagsRefreshed": True,
            "embeddingsRefreshed": True,
        },
    )
    monkeypatch.setattr(
        recommendation_worker,
        "complete_recommendation_job",
        lambda connection, **kwargs: calls.append(("complete", kwargs["job_id"])),
    )

    recommendation_worker._run_job(
        {
            "id": "job-1",
            "job_type": "artist_bio_refresh",
            "artist_id": 2178,
            "user_id": 1,
            "params_json": {},
        }
    )

    assert calls == [("refresh", 2178), ("complete", "job-1")]
