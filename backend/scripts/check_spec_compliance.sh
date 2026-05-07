#!/bin/bash

CONTAINER="scenegraph-db"
USER="postgres"
DB="sg_db"

echo -e "\n>>> 1. EVENTS AND VENUES (RELATIONSHIPS AND RA IDs)"
docker exec -it $CONTAINER psql -U $USER -d $DB -c \
"SELECT e.ra_event_id, LEFT(e.title, 40) as title, v.ra_venue_id, v.name as venue 
FROM events e 
LEFT JOIN venues v ON e.venue_id = v.id 
LIMIT 5;"

echo -e "\n>>> 2. Text Preservation (Lineup and Description)"
docker exec -it $CONTAINER psql -U $USER -d $DB -c \
"SELECT ra_event_id, 
       (lineup_raw IS NOT NULL) as has_lineup, 
       (description_text IS NOT NULL) as has_desc,
       minimum_age, is_ticketed
FROM events 
LIMIT 5;"
s
echo -e "\n>>> 3. Artist Relationships (Normalization)"
docker exec -it $CONTAINER psql -U $USER -d $DB -c \
"SELECT e.title, a.name 
FROM events e 
JOIN event_artists ea ON e.id = ea.event_id 
JOIN artists a ON a.id = ea.artist_id 
LIMIT 5;"


echo -e "\n>>> 4. Geolocation and Addresses of Venues"
docker exec -it $CONTAINER psql -U $USER -d $DB -c \
"SELECT name, latitude, longitude, country_code 
FROM venues 
WHERE latitude IS NOT NULL 
LIMIT 5;"

echo -e "\n>>> 5. Image Metadata"
docker exec -it $CONTAINER psql -U $USER -d $DB -c \
"SELECT event_id, ra_image_id, image_type, LEFT(image_url, 40) as url_short 
FROM event_images 
LIMIT 5;"

echo -e "\n>>> 6. JSON Payload Integrity (FALLBACK)"
docker exec -it $CONTAINER psql -U $USER -d $DB -c \
"SELECT source_event_id, source_name, 
       pg_size_pretty(octet_length(payload::text)::bigint) as payload_size 
FROM event_source_payloads 
LIMIT 5;"