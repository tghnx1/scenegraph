Generated parser artifacts live here so the scraper scripts stay separate from their output.

You can move all generated data outside the repo by setting:
- `SCENEGRAPH_DATA_DIR=/absolute/path/to/scenegraph-data`

Recommended layout:
- `json/` for scraped and derived JSON files
  The events dataset is best stored in `json/events_by_year/` as yearly shards.
- `backups/` for a single rolling `*.prev.json` backup of expensive datasets
- `logs/` for parser log files
- `debug/` for screenshots and HTML dumps used during scraper debugging
- `runtime/` for long-lived local browser profiles and other restart-safe runtime state
