import { MOCK_ARTISTS } from './mock'
import type {
  SearchResponse,
  SearchArtistResult,
  SearchVenueResult,
  SearchPromoterResult,
  SearchEventResult,
  SearchEventSummary,
} from '../../types/search'

function getMockArtist(artistId: string, defaultLabel: string) {
  const artist = MOCK_ARTISTS[artistId]

  if (!artist) {
    return {
      id: artistId,
      name: defaultLabel,
      genres: [],
      bio: '',
      eventCount: 0,
    }
  }

  return artist
}

const ellerArtist = getMockArtist('artist-156016', 'ELLER')
const connectedArtist1 = getMockArtist('artist-111515', 'artist-111515')
const connectedArtist2 = getMockArtist('artist-170313', 'artist-170313')
const unityEventArtist3 = getMockArtist('artist-155300', 'artist-155300')

const unityEventSummary: SearchEventSummary = {
  id: 'event-unity-2025-01-18',
  label: 'UNITY',
  date: '2025-01-18',
  venueName: 'KitKatClub',
  artists: ['ELLER', 'DJ Henk', 'e.leptic', 'WAN.1'],
  promoters: ['UNITYBERLIN'],
}

const savoryEventSummary: SearchEventSummary = {
  id: 'event-savory-2025-01-25',
  label: 'Savory',
  date: '2025-01-25',
  venueName: 'OST',
  artists: ['WAN.1'],
  promoters: ['OST Events'],
}

const ellerResult: SearchArtistResult = {
  type: 'artist',
  id: ellerArtist.id,
  label: ellerArtist.name,
  genres: ellerArtist.genres.map((genre) => typeof genre === 'string' ? genre : genre.name),
  bio: ellerArtist.bio,
  eventCount: ellerArtist.eventCount ?? 1,
  events: [unityEventSummary],
  connectedArtists: [
    {
      id: connectedArtist1.id,
      label: connectedArtist1.name,
      sharedEvents: 1,
    },
    {
      id: connectedArtist2.id,
      label: connectedArtist2.name,
      sharedEvents: 1,
    },
  ],
}

const kitkatResult: SearchVenueResult = {
  type: 'venue',
  id: 'venue-10546',
  label: 'KitKatClub',
  address: 'Kohlfurter Str. 16, 10999 Berlin',
  district: 'Kreuzberg',
  eventCount: 1,
  events: [unityEventSummary],
}

const unityPromoterResult: SearchPromoterResult = {
  type: 'promoter',
  id: 'promoter-133471',
  label: 'UNITYBERLIN',
  eventCount: 1,
  events: [unityEventSummary],
}

const unityEventResult: SearchEventResult = {
  type: 'event',
  id: unityEventSummary.id,
  label: unityEventSummary.label,
  date: unityEventSummary.date,
  venue: {
    id: 'venue-10546',
    label: 'KitKatClub',
  },
  artists: [
    {
      id: ellerArtist.id,
      label: ellerArtist.name,
    },
    {
      id: connectedArtist1.id,
      label: connectedArtist1.name,
    },
    {
      id: connectedArtist2.id,
      label: connectedArtist2.name,
    },
    {
      id: unityEventArtist3.id,
      label: unityEventArtist3.name,
    },
  ],
  promoters: [
    {
      id: 'promoter-133471',
      label: 'UNITYBERLIN',
    },
  ],
}

const savoryEventResult: SearchEventResult = {
  type: 'event',
  id: savoryEventSummary.id,
  label: savoryEventSummary.label,
  date: savoryEventSummary.date,
  venue: {
    id: 'venue-141987',
    label: 'OST',
  },
  artists: [
    {
      id: unityEventArtist3.id,
      label: unityEventArtist3.name,
    },
  ],
  promoters: [
    {
      id: 'promoter-110655',
      label: 'OST Events',
    },
  ],
}

const oriolmaniaEventSummary: SearchEventSummary = {
  id: 'event-2314765-27',
  label: 'ORIOLMANIA',
  date: '2025-12-02',
  venueName: 'Orangerie Neukölln',
  artists: ['ORIOL //'],
  promoters: ['1991'],
}

const aroundTheKornerEventSummary: SearchEventSummary = {
  id: 'event-2313891-32',
  label: 'Around The Körner #55 with Oriol //',
  date: '2025-12-02',
  venueName: 'Orangerie Neukölln',
  artists: ['Oriol'],
  promoters: ['Orangerie Neukölln'],
}

const orangerieVenueResult: SearchVenueResult = {
  type: 'venue',
  id: 'venue-208328',
  label: 'Orangerie Neukölln',
  address: 'Neukölln, Berlin',
  district: 'Neukölln',
  eventCount: 2,
  events: [oriolmaniaEventSummary, aroundTheKornerEventSummary],
}

const oriolArtistResult: SearchArtistResult = {
  type: 'artist',
  id: 'artist-173747',
  label: 'ORIOL //',
  genres: ['Disco', 'Italo Disco'],
  bio: 'Active in Berlin electronic music scene.',
  eventCount: 1,
  events: [oriolmaniaEventSummary],
  connectedArtists: [
    {
      id: 'artist-16472',
      label: 'Oriol',
      sharedEvents: 1,
    },
  ],
}

const oriolArtistResult2: SearchArtistResult = {
  type: 'artist',
  id: 'artist-16472',
  label: 'Oriol',
  genres: ['Funk / Soul', 'Italo Disco'],
  bio: 'Active in Berlin electronic music scene.',
  eventCount: 1,
  events: [aroundTheKornerEventSummary],
  connectedArtists: [
    {
      id: 'artist-173747',
      label: 'ORIOL //',
      sharedEvents: 1,
    },
  ],
}

const promoter1991Result: SearchPromoterResult = {
  type: 'promoter',
  id: 'promoter-177031',
  label: '1991',
  eventCount: 1,
  events: [oriolmaniaEventSummary],
}

const orangeriePromoterResult: SearchPromoterResult = {
  type: 'promoter',
  id: 'promoter-174901',
  label: 'Orangerie Neukölln',
  eventCount: 1,
  events: [aroundTheKornerEventSummary],
}

const oriolmaniaEventResult: SearchEventResult = {
  type: 'event',
  id: oriolmaniaEventSummary.id,
  label: oriolmaniaEventSummary.label,
  date: oriolmaniaEventSummary.date,
  venue: {
    id: 'venue-208328',
    label: 'Orangerie Neukölln',
  },
  artists: [
    {
      id: 'artist-173747',
      label: 'ORIOL //',
    },
  ],
  promoters: [
    {
      id: 'promoter-177031',
      label: '1991',
    },
  ],
}

const aroundTheKornerEventResult: SearchEventResult = {
  type: 'event',
  id: aroundTheKornerEventSummary.id,
  label: aroundTheKornerEventSummary.label,
  date: aroundTheKornerEventSummary.date,
  venue: {
    id: 'venue-208328',
    label: 'Orangerie Neukölln',
  },
  artists: [
    {
      id: 'artist-16472',
      label: 'Oriol',
    },
  ],
  promoters: [
    {
      id: 'promoter-174901',
      label: 'Orangerie Neukölln',
    },
  ],
}

const searchResponses: Record<string, SearchResponse> = {
  eller: {
    query: 'eller',
    results: [ellerResult, unityEventResult],
  },
  kitkatclub: {
    query: 'kitkatclub',
    results: [kitkatResult, unityEventResult],
  },
  unityberlin: {
    query: 'unityberlin',
    results: [unityPromoterResult, unityEventResult, kitkatResult],
  },
  unity: {
    query: 'unity',
    results: [unityEventResult, ellerResult, kitkatResult, unityPromoterResult],
  },
  savory: {
    query: 'savory',
    results: [savoryEventResult],
  },
  orangerie: {
    query: 'orangerie',
    results: [
      orangerieVenueResult,
      oriolmaniaEventResult,
      aroundTheKornerEventResult,
      oriolArtistResult,
      oriolArtistResult2,
      promoter1991Result,
      orangeriePromoterResult,
    ],
  },
  'orangerie neukölln': {
    query: 'orangerie neukölln',
    results: [
      orangerieVenueResult,
      oriolmaniaEventResult,
      aroundTheKornerEventResult,
      oriolArtistResult,
      oriolArtistResult2,
      promoter1991Result,
      orangeriePromoterResult,
    ],
  },
}

export function getMockSearchResponse(query: string): SearchResponse {
  const normalized = query.trim().toLowerCase()

  if (!normalized) {
    return { query: '', results: [] }
  }

  return searchResponses[normalized] ?? {
    query,
    results: [],
  }
}

export const MOCK_SEARCH_RESPONSES = searchResponses
