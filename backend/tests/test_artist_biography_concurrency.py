from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db import get_connection
from app.routers import artists as artists_router
from app.text_profiles import normalize_biography_text


TEST_USER_ID = 991_217_802
WRITE_BURST_SIZE = int(os.getenv("ARTIST_BIO_WRITE_BURST_SIZE", "10"))
WRITE_ROUNDS = int(os.getenv("ARTIST_BIO_WRITE_ROUNDS", "1"))
WRITE_ROUND_PAUSE_SECONDS = float(os.getenv("ARTIST_BIO_WRITE_ROUND_PAUSE_SECONDS", "0"))
WRITE_COUNT = WRITE_BURST_SIZE * WRITE_ROUNDS


def _test_artist_id() -> int:
    explicit = os.getenv("ARTIST_BIO_TEST_ARTIST_ID")
    if explicit:
        return int(explicit)
    return 991_000_000 + (time.time_ns() % 1_000_000)


def _reset_test_artist(artist_id: int) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE artist_id = %s",
                (artist_id,),
            )
            cursor.execute("DELETE FROM artists WHERE id = %s", (artist_id,))
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name, biography, biography_normalized, biography_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    artist_id,
                    f"test-concurrent-bio-{artist_id}",
                    "Concurrent Bio Test Artist",
                    "Original biography.",
                    "Original biography.",
                    "imported",
                ),
            )


def _cleanup_test_artist(artist_id: int) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE artist_id = %s",
                (artist_id,),
            )
            cursor.execute("DELETE FROM artists WHERE id = %s", (artist_id,))


def _write_biography(artist_id: int, index: int) -> dict:
    biography = f"  Concurrent biography write {index}\\nwith normalized spacing.  "
    with get_connection() as connection:
        return artists_router._update_artist_biography_row(
            connection,
            artist_id=artist_id,
            biography=biography,
            user_id=TEST_USER_ID,
            enqueue_refresh_job=False,
        )


def _run_write_burst(artist_id: int, start_index: int, size: int, *, round_number: int) -> list[dict]:
    started_at = time.perf_counter()
    print(
        f"[artist-bio-load] round={round_number} starting "
        f"burst_size={size} index_range={start_index}-{start_index + size - 1}",
        flush=True,
    )
    results: list[dict] = []
    progress_every = max(1, min(10, size // 5 or 1))

    with ThreadPoolExecutor(max_workers=size) as executor:
        futures = [
            executor.submit(_write_biography, artist_id, index)
            for index in range(start_index, start_index + size)
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if completed == size or completed % progress_every == 0:
                elapsed = time.perf_counter() - started_at
                print(
                    f"[artist-bio-load] round={round_number} completed={completed}/{size} "
                    f"elapsed={elapsed:.2f}s",
                    flush=True,
                )

    elapsed = time.perf_counter() - started_at
    print(
        f"[artist-bio-load] round={round_number} finished "
        f"completed={len(results)}/{size} elapsed={elapsed:.2f}s",
        flush=True,
    )
    return results


def test_concurrent_artist_biography_writes_are_valid_without_refresh_jobs():
    expected_biographies = {
        f"Concurrent biography write {index}\\nwith normalized spacing."
        for index in range(WRITE_COUNT)
    }

    artist_id = _test_artist_id()
    print(
        f"[artist-bio-load] setup artist_id={artist_id} "
        f"burst_size={WRITE_BURST_SIZE} rounds={WRITE_ROUNDS} "
        f"round_pause_seconds={WRITE_ROUND_PAUSE_SECONDS} total_writes={WRITE_COUNT}",
        flush=True,
    )
    _reset_test_artist(artist_id)
    try:
        results = []
        for round_index in range(WRITE_ROUNDS):
            results.extend(
                _run_write_burst(
                    artist_id,
                    round_index * WRITE_BURST_SIZE,
                    WRITE_BURST_SIZE,
                    round_number=round_index + 1,
                )
            )
            if round_index < WRITE_ROUNDS - 1 and WRITE_ROUND_PAUSE_SECONDS > 0:
                print(
                    f"[artist-bio-load] sleeping {WRITE_ROUND_PAUSE_SECONDS:.2f}s before next round",
                    flush=True,
                )
                time.sleep(WRITE_ROUND_PAUSE_SECONDS)

        assert len(results) == WRITE_COUNT
        assert {result["id"] for result in results} == {artist_id}
        assert {result["name"] for result in results} == {"Concurrent Bio Test Artist"}
        assert {result["biography"] for result in results}.issubset(expected_biographies)

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT biography, biography_normalized, biography_status
                    FROM artists
                    WHERE id = %s
                    """,
                    (artist_id,),
                )
                artist = cursor.fetchone()
                cursor.execute(
                    "SELECT COUNT(*) AS count FROM recommendation_jobs WHERE artist_id = %s",
                    (artist_id,),
                )
                job_count = cursor.fetchone()["count"]

        assert artist is not None
        assert artist["biography"] in expected_biographies
        assert artist["biography_normalized"] == normalize_biography_text(artist["biography"])
        assert artist["biography_status"] == "manually_edited"
        assert job_count == 0
        print(
            f"[artist-bio-load] verified total_writes={len(results)} "
            f"final_bio={artist['biography']!r} refresh_jobs={job_count}",
            flush=True,
        )
    finally:
        _cleanup_test_artist(artist_id)
        print(f"[artist-bio-load] cleanup artist_id={artist_id}", flush=True)
