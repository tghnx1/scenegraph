# Canonical Style Tag Operations

Audit existing artist style rows without changing the database:

```bash
docker compose exec backend python scripts/normalize_existing_artist_style_tags.py --dry-run
```

Explicitly replace existing artist style rows with canonical values in one transaction:

```bash
docker compose exec backend python scripts/normalize_existing_artist_style_tags.py --apply
```

Re-extract v2 artist and event tags without saving:

```bash
docker compose exec backend python scripts/extract_artist_tags.py --limit 100 --batch-size 5 --force --dry-run
docker compose exec backend python scripts/extract_event_tags.py --limit 100 --batch-size 5 --force --dry-run
```

Audit all stored artist style values:

```sql
SELECT tag_value, COUNT(*)
FROM artist_extracted_tags
WHERE tag_type = 'style'
GROUP BY tag_value
ORDER BY COUNT(*) DESC, tag_value;
```

Focused drum-and-bass variant audit:

```sql
SELECT tag_value, COUNT(*)
FROM artist_extracted_tags
WHERE tag_type = 'style'
  AND lower(tag_value) IN (
    'drum and bass', 'drum & bass', 'drum n bass',
    'drum ''n'' bass', 'drum n'' bass', 'dnb', 'd&b'
  )
GROUP BY tag_value
ORDER BY COUNT(*) DESC, tag_value;
```
