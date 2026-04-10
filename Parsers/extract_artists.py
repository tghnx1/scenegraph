import json

input_path = '/Users/tghnx1/Desktop/42/scenegraph/Parsers/ra_berlin_past_events.json'
output_path = 'artists.json'

with open(input_path, 'r', encoding='utf-8') as infile:
    events = json.load(infile)

unique_artists = {}

for event in events:
    artists = event.get('artists', [])
    for artist in artists:
        artist_id = artist.get('id')
        content_url = artist.get('contentUrl')

        if artist_id and content_url and artist_id not in unique_artists:
            unique_artists[artist_id] = {
                'id': artist_id,
                'url': f"https://ra.co{content_url}/biography"
            }

with open(output_path, 'w', encoding='utf-8') as outfile:
    json.dump(list(unique_artists.values()), outfile, indent=4)