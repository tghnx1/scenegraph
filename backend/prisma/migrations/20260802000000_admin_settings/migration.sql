CREATE TABLE IF NOT EXISTS app_settings (
  setting_key TEXT PRIMARY KEY,
  setting_value BOOLEAN NOT NULL DEFAULT FALSE
);
