# SceneGraph — RA Event Scraper

## Overview

This scraper collects structured event data from Resident Advisor (RA) using a real browser session.

It extracts:

* event metadata (title, date, venue, promoters)
* artists (from JSON-LD + lineup block)
* raw lineup text (for further processing)
* engagement metrics (`interested`)

The scraper is designed as an **ingestion layer** for a graph-based music scene analysis system.

---

## Key Design Principles

### 1. Real browser session (anti-bot safe)

The scraper connects to an existing Chrome instance via CDP instead of launching a headless browser.

This allows:

* reuse of cookies/session
* reduced bot detection
* manual control if needed

---

### 2. Two-layer architecture

#### Layer 1 — Scraping

Collects:

* structured data (JSON-LD, links)
* raw data (`lineup_block_text_raw`)

#### Layer 2 — Normalization (future)

* resolves missing artists (e.g. plain text like "USH")
* filters noise (e.g. "Human Installations")
* enriches graph

---

### 3. Minimal assumptions

The scraper avoids over-parsing:

* does NOT try to fully interpret lineup
* preserves raw data for downstream processing

---

## Data Output

Example:

```json
{
  "url": "https://ra.co/events/2356313",
  "title": "HIVE Easter RAVE",
  "date": {
    "start": "2026-04-03T23:00:00.000",
    "end": "2026-04-04T08:00:00.000"
  },
  "venue": "DSTRKT Club Berlin",
  "promoter": ["DSTRKT", "HIVE Festival"],
  "artists": [
    {
      "name": "Ben Techy",
      "ra_url": "https://ra.co/dj/bentechy",
      "has_ra_profile": true
    }
  ],
  "lineup_block_text_raw": "Ben Techy DIØR ... USH ...",
  "description": "Tickets are now on sale!",
  "interested": 1500
}
```

---

## How It Works

### Step 1 — Connect to browser

The script connects to a running Chrome instance:

```bash
chrome --remote-debugging-port=9222
```

---

### Step 2 — Use existing RA tab

You must manually open:

```
https://ra.co/events/de/berlin
```

The script attaches to this tab.

---

### Step 3 — Collect event links

* scrolls page
* extracts `/events/...` links
* filters valid event URLs

---

### Step 4 — Parse each event

For each event page:

* extract JSON-LD (`MusicEvent`)
* extract lineup block (raw + linked artists)
* extract `interested` count
* merge structured data

---

### Step 5 — Save results

Outputs JSON file:

```bash
ra_berlin_events.json
```

---

## Anti-Bot Strategy

The scraper reduces detection risk by:

* using a real browser session (CDP)
* avoiding headless mode
* adding random delays
* simulating scrolling
* limiting request rate
* detecting block pages (captcha / restricted)

It does NOT bypass captchas or protections.

---

## Running the scraper

```bash
python ra_events_scraper.py --max-events 10
```

Options:

* `--max-events` — number of events to parse
* `--out` — output file
* `--cdp-url` — Chrome debugging URL

---

## Limitations

* relies on current RA DOM structure
* may miss plain-text artists (handled later)
* does not solve captcha challenges
* `interested` parsing depends on layout consistency

---

## Roadmap

* normalization layer (artist extraction from raw lineup)
* graph database integration
* recommendation engine
* multi-source ingestion (beyond RA)

---

## Disclaimer

This project is for research and development purposes.

Respect the target website's terms of service and avoid excessive scraping.
