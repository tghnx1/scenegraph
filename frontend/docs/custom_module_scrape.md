# Custom Major Module: Music Scene Data Ingestion Pipeline

## Module claim

Claim:

 **IV.10 Modules of choice - Major module**.

Module name:

**Automated Music Scene Data Ingestion Pipeline**

## What the module does

This module collects real event and artist data from external music-scene sources and prepares it for the application.

The pipeline is responsible for:

- collects event data
- extracts artists, venues, promoters, genres, and event details
- collects artist biography information
- saves structured JSON output
- imports the data into PostgreSQL
- validates the imported data
- prepares the data for the graph and recommendation features

## Why we chose this module

The project needs real music-scene data to be useful. Manually entering artists, events, venues, and promoters would be slow and unrealistic.

This needs to be done because the application depends on fresh and structured event data. The graph and recommendation features becomes meaningful when the database contains real relationships from the music scene.

## Technical challenges

This module is technically challenging because external event data needs to be cleaned up and prepared.

Main technical challenges:

- collecting data from dynamic web pages
- using browser automation for pages that require a real browser session
- collecting structured event data through GraphQL
- handling past and future events
- extracting artists from event lineups
- scraping artist biographies separately
- avoiding duplicate events, artists, promoters, and genres
- normalizing raw text into clean database fields
- importing nested JSON data into relational database tables
- validating the final database state
- checking for duplicate records and broken relationships

## How it adds value to the project

The scraping and ingestion pipeline gives the project useful real-world data.

It adds value because:

- the graph can show real relationships instead of demo-only data
- recommendations are based on actual artists, events, venues, and promoters
- the dashboard can display meaningful analytics
- admins can refresh or expand the dataset
- the project becomes closer to a real product for exploring a local music scene

## Why it deserves Major module status

This module deserves Major status because it is more than a small script.

It includes:

- multiple scraping approaches
- browser-based scraping
- GraphQL-based event collection
- artist extraction
- biography collection
- data normalization
- database import logic
- integrity validation
- integration with the graph and recommendation system

The module solves a real project problem: how to transform external, inconsistent event listings into clean application data. It combines scraping, parsing, normalization, database import, and validation.

## Main implementation files

- `parsers/run_ra_pipeline.py` - coordinates the scraping and extraction pipeline
- `parsers/playwright_parser/ra_events_scraper.py` - browser-based event scraper
- `parsers/playwright_parser/artists_bio.py` - artist biography scraper
- `parsers/graphql_parser/parse_past_events.py` - GraphQL parser for past events
- `parsers/graphql_parser/parse_today.py` - GraphQL parser for current events
- `future_events/scrape_graphql.py` - future event scraping experiment
- `parsers/extract_artists.py` - extracts artists from event data
- `backend/scripts/import_events.py` - imports scraped event JSON into PostgreSQL
- `backend/scripts/validate_import.py` - validates imported data integrity
- `WEB_SCRAPER.md` - existing scraper notes and usage details

## How to demonstrate it

1. Show the parser and scraper files.
2. Explain that external event data is collected before being imported into the app.
3. Show an example scraped JSON file or generated output.
4. Run or explain the import script that inserts events, artists, venues, promoters, and genres into PostgreSQL.
5. Run or explain the validation script that checks for duplicates and broken relationships.
6. Open the graph or recommendation feature and explain that it uses the imported data.

## Short explanation

This module is chosen because the project needs real music-scene data. The ingestion pipeline collects external event and artist information, normalizes it, imports it into the database, and validates that the graph relationships are usable. It is technically complex because it combines scraping, GraphQL collection, browser automation, parsing, deduplication, database import, and integrity checks. It adds value by powering the graph, dashboard, and recommendation features with real data.
