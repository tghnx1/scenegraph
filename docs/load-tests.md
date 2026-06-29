# Load Test Commands

This file contains copy-paste commands for the simple multi-user/load checks.

## 0. Start The Stack

Run from the repository root:

```bash
cd /Users/tghnx1/code/scenegraph
make upd
```

Check the backend is reachable:

```bash
curl -k https://localhost:8443/health
```


If you changed `DATABASE_POOL_MAX_SIZE` in `.env`, recreate the backend stack before testing:

```bash
make down
make upd
```

## 2. Artist Biography Write Load Test

This test writes to a temporary artist biography through the same internal write logic used by:

```text
PATCH /api/artist/{artist_id}/biography
```

It intentionally disables refresh-job creation during the test, so the test measures concurrent writes without creating hundreds of artist refresh jobs.

The test creates and deletes its own temporary artist row.

### Small Smoke Test

```bash
docker compose exec backend pytest -q -s tests/test_artist_biography_concurrency.py
```


### 10 Rounds Of 100 Writes With 0.5s Pause

This runs `100 * 10 = 1000` total biography writes.

```bash
docker compose exec \
  -e ARTIST_BIO_WRITE_BURST_SIZE=100 \
  -e ARTIST_BIO_WRITE_ROUNDS=2 \
  -e ARTIST_BIO_WRITE_ROUND_PAUSE_SECONDS=0.5 \
  backend pytest -q -s tests/test_artist_biography_concurrency.py
```


Use a fixed id only when you are sure no other test run is using the same id.

### How To Read The Output


`1 passed` means one pytest test function passed. The real write count is shown by `total_writes`.

If the test fails with `PoolTimeout`, that is useful load-test evidence: the current DB pool and row-lock queue did not process that load within the pool checkout timeout.

## 3. Dashboard k6 Load Test

The k6 script tests authenticated dashboard reads. It does not test biography writes.

File:

```text
scripts/load_dashboard_k6.js
```

### Install k6

Check if k6 is installed:

```bash
k6 version
```

On macOS, install with Homebrew if needed:

```bash
brew install k6
```


### Dashboard API Bundle Heavier Test

```bash
cd /Users/tghnx1/code/scenegraph

SG_K6_BASE_URL=https://localhost:8443 \
SG_K6_ENV_FILE=../.env \
SG_K6_MODE=dashboard-api \
SG_K6_VUS=100 \
SG_K6_ITERATIONS=100 \
k6 run scripts/load_dashboard_k6.js
```

### k6 Variables

- `SG_K6_MODE=dashboard-api` requests the admin dashboard API bundle.
- `SG_K6_MODE=page` requests only `/dashboard`.
- `SG_K6_VUS=100` means 100 virtual users.
- `SG_K6_ITERATIONS=100` means 100 total scenario iterations.
- `SG_K6_BASE_URL=https://localhost:8443` points k6 at the local HTTPS gateway.
- `SG_K6_ENV_FILE=../.env` lets k6 read `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD`. The path is relative to `scripts/load_dashboard_k6.js`, not to your shell directory.

## 4. Optional DB Activity Monitor

Open another terminal while a load test is running.

The helper script reads `.env` and chooses the target automatically:

- if `DATABASE_URL` points to Docker host `db`, it monitors the local Docker Postgres container
- otherwise, it uses `psql "$DATABASE_URL"` directly, for example for AWS RDS

```bash
./scripts/watch_db_activity.sh
```

To debug which database URL the monitor actually selected:

```bash
DB_ACTIVITY_DATABASE_URL="postgresql://scenegraph:<PASSWORD>@scenegraph.cpokossgk60u.eu-north-1.rds.amazonaws.com:5432/scenegraph?sslmode=require" \
bash -x ./scripts/watch_db_activity.sh
```

The output should show `target=DB_ACTIVITY_DATABASE_URL`. If it shows `target=DATABASE_URL`, the override variable did not reach the script.

To focus only on biography updates:

```bash
./scripts/watch_db_activity.sh updates
```

Optional refresh interval override:

```bash
WATCH_INTERVAL=0.1 ./scripts/watch_db_activity.sh
```
