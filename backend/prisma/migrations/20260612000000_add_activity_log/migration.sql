CREATE TABLE IF NOT EXISTS "activity_log" (
    "id" BIGSERIAL PRIMARY KEY,
    "user_id" BIGINT REFERENCES users(id) ON DELETE SET NULL,
    "username" TEXT,
    "event_type" TEXT NOT NULL,
    "target" TEXT,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
