# Production delivery

Production delivery is gated by `.github/workflows/production-compose-env.yml`.
Pull requests run production Compose validation, the backend suite against an
ephemeral pgvector/PostgreSQL service, and frontend tests, typecheck, and build.
Pushes to `main` run the same checks before the deploy job becomes eligible.

The deploy job connects the ephemeral GitHub runner to the existing private
Tailscale network, queues the Coolify application deployment, and extracts
`deployments[0].deployment_uuid` from the current API response. It polls
`GET /api/v1/deployments/{deployment_uuid}` every eight seconds for up to 15
minutes. Only `finished` is successful; failed or cancelled terminal states fail
the job. A successful deployment is followed by a bounded live health check of
`https://scenematch.dev/health`. The health response must report `status=ok`,
`database=ok`, `schema.status=ok`, and no missing required tables.

The workflow-level `production-deploy` concurrency group prevents two main
workflows from running at once and never cancels an active production run.
GitHub Actions does not guarantee an unbounded FIFO queue: it retains at most one
pending run in a concurrency group, and a newer pending push can replace an
older pending push.

## Daily ingestion

Production Compose includes a private `ingestion-runner` container built from
`tools/Dockerfile.daily`. It has the RA parser, backend import, tag, embedding,
validation, and recommendation scheduler dependencies, but no exposed or
published ports. Biography scraping is always skipped for this job, so the daily
image intentionally does not install Playwright/Chromium. It contains no cron
loop. Coolify Scheduled Tasks require a running target container, so the
container remains idle while the scheduled command itself is one-shot and exits
after each run.

Create the Coolify Scheduled Task on application
`biclmmeszwg9zb6xi3iguo4p` with:

- Name: `daily-production-ingestion`
- Container: `ingestion-runner`
- Command: `python -m app.daily_ingestion`
- Frequency: `0 4 * * *`
- Server timezone: `Europe/Berlin`
- Timeout: choose a bound that exceeds the measured first ingestion duration

The server timezone is authoritative for Coolify Scheduled Tasks. Confirm it is
`Europe/Berlin` in Coolify before enabling the task; do not convert this schedule
to UTC.

`app.daily_ingestion` calculates the previous Berlin calendar date with
`zoneinfo.ZoneInfo("Europe/Berlin")`. It passes that same value as both
`--min-date` and `--max-date` to the existing full pipeline. The pipeline keeps
DB-backed deduplication and `--refresh-existing-events`, skips biography scraping,
and enables normalized text refresh, tags, embeddings, and validation. Existing
`ImportRunLogger` records stage status and available counts.

The recommendation scheduler runs synchronously only after the full pipeline
returns successfully. A failed scrape, import, enrichment, embedding, or
validation command prevents recommendation scheduling and makes the scheduled
command fail.

## First execution

Keep the task disabled initially and set its command temporarily to a controlled
single-day run:

```sh
DAILY_INGEST_DATE=2026-08-25 python -m app.daily_ingestion
```

Use Execute Now and verify the execution reaches a terminal successful state.
Its log must show identical target/min/max dates, refresh-existing enabled,
successful import/enrichment/validation stages, and recommendation scheduling
only at the end. Then restore `python -m app.daily_ingestion`, confirm the server
timezone and `0 4 * * *` schedule, and enable the task.

An invalid or non-canonical `DAILY_INGEST_DATE` fails before ingestion. This
override processes one day only; historical multi-day backfills remain a separate
manual operator workflow.

No AWS credentials, SSH keys, production database credentials, or provider
secrets are stored in GitHub Actions. Coolify continues to provide production
runtime secrets to containers. This delivery setup does not publish Coolify,
change Security Groups, broaden Tailscale access, or alter RDS networking.
