import type { GraphData }    from '../types/graph'
import type { Artist, SimilarArtist } from '../types/artist'

// Events: UNITY @ KitKatClub (2343582) and Savory @ OST (2398252)

export const MOCK_GRAPH: GraphData = {
  nodes: [
    //venues
    {
      id:         'venue-10546',
      type:       'venue',
      label:      'KitKatClub',
      genres:     ['Techno', 'Trance'],
      eventCount: 1,
      lat:        52.509718,
      lng:        13.416946,
    },
    {
      id:         'venue-141987',
      type:       'venue',
      label:      'OST',
      genres:     ['Techno'],
      eventCount: 1,
      lat:        52.496987,
      lng:        13.465462,
    },

    //artists
    {
      id:         'artist-156016',
      type:       'artist',
      label:      'ELLER',
      genres:     ['Techno', 'Trance'],
      eventCount: 1,
    },
    {
      id:         'artist-111515',
      type:       'artist',
      label:      'DJ Henk',
      genres:     ['Techno', 'Trance'],
      eventCount: 1,
    },
    {
      id:         'artist-170313',
      type:       'artist',
      label:      'e.leptic',
      genres:     ['Techno', 'Trance'],
      eventCount: 1,
    },
    {
      id:         'artist-155300',
      type:       'artist',
      label:      'WAN.1',
      genres:     ['Techno'],
      eventCount: 1,
    },

    //promoters
    {
      id:         'promoter-133471',
      type:       'promoter',
      label:      'UNITYBERLIN',
      genres:     ['Techno', 'Trance'],
      eventCount: 1,
    },
    {
      id:         'promoter-110655',
      type:       'promoter',
      label:      'OST Events',
      genres:     ['Techno'],
      eventCount: 1,
    },
  ],

  links: [
    // UNITY artists → KitKatClub
    { source: 'artist-156016', target: 'venue-10546',    weight: 1 },
    { source: 'artist-111515', target: 'venue-10546',    weight: 1 },
    { source: 'artist-170313', target: 'venue-10546',    weight: 1 },

    // UNITY co-appearances (played same event)
    { source: 'artist-156016', target: 'artist-111515', weight: 1 },
    { source: 'artist-156016', target: 'artist-170313', weight: 1 },
    { source: 'artist-111515', target: 'artist-170313', weight: 1 },

    // WAN.1 → OST
    { source: 'artist-155300', target: 'venue-141987',  weight: 1 },

    // Promoters → Venues
    { source: 'promoter-133471', target: 'venue-10546',  weight: 1 },
    { source: 'promoter-110655', target: 'venue-141987', weight: 1 },
  ],
}

//mock artist profiles

export const MOCK_ARTISTS: Record<string, Artist> = {
  'artist-156016': {
    id: 'artist-156016', raId: '156016', name: 'ELLER',
    genres: [{ id: '5', name: 'Techno', slug: 'techno' },
             { id: '2', name: 'Trance', slug: 'trance' }],
    bio: 'Berlin-based live act. Regular at UNITY.',
    claimed: false, eventCount: 1,
  },
  'artist-111515': {
    id: 'artist-111515', raId: '111515', name: 'DJ Henk',
    genres: [{ id: '5', name: 'Techno', slug: 'techno' },
             { id: '2', name: 'Trance', slug: 'trance' }],
    bio: 'Live act performing at UNITY events.',
    claimed: false, eventCount: 1,
  },
  'artist-170313': {
    id: 'artist-170313', raId: '170313', name: 'e.leptic',
    genres: [{ id: '5', name: 'Techno', slug: 'techno' },
             { id: '2', name: 'Trance', slug: 'trance' }],
    bio: 'Closing act at UNITY nights.',
    claimed: false, eventCount: 1,
  },
  'artist-155300': {
    id: 'artist-155300', raId: '155300', name: 'WAN.1',
    genres: [{ id: '5', name: 'Techno', slug: 'techno' }],
    bio: 'All-night-long set at Club OST.',
    claimed: false, eventCount: 1,
  },
}

//mock similar artists

export const MOCK_SIMILAR: Record<string, SimilarArtist[]> = {
  'artist-156016': [
    {
      artist: MOCK_ARTISTS['artist-111515'],
      sharedEvents: 1,
      sharedGenres: ['Techno', 'Trance'],
    },
    {
      artist: MOCK_ARTISTS['artist-170313'],
      sharedEvents: 1,
      sharedGenres: ['Techno', 'Trance'],
    },
  ],
  'artist-111515': [
    {
      artist: MOCK_ARTISTS['artist-156016'],
      sharedEvents: 1,
      sharedGenres: ['Techno', 'Trance'],
    },
    {
      artist: MOCK_ARTISTS['artist-170313'],
      sharedEvents: 1,
      sharedGenres: ['Techno', 'Trance'],
    },
  ],
  'artist-170313': [
    {
      artist: MOCK_ARTISTS['artist-156016'],
      sharedEvents: 1,
      sharedGenres: ['Techno', 'Trance'],
    },
  ],
  'artist-155300': [], //WAN.1 played alone — no co-appearances yet
}