Generated parser artifacts live here so the scraper scripts stay separate from their output.

Recommended layout:
- `json/` for scraped and derived JSON files
- `backups/` for a single rolling `*.prev.json` backup of expensive datasets
- `logs/` for parser log files
- `debug/` for screenshots and HTML dumps used during scraper debugging
- `runtime/` for long-lived local browser profiles and other restart-safe runtime state
