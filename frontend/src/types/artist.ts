import type { SearchArtistConnection, SearchEventSummary } from './search'

export interface Genre { //separate interface if genres are their own entities in the db
  id:   string
  name: string
  slug: string //URL-safe name used for filtering (like techno or dub-techno).
}

export interface Artist { //matches the rich artist detail response from GET /api/artist?<artist-node-id>
  type?:          'artist'
  id:             string
  raId?:          string //ra's id maybe unnecessary
  name:           string
  genres:         Array<string | Genre>
  bio?:           string
  claimed?:       boolean //if profile is claimed to be used later to show an "Edit profile" to real artist
  eventCount?:    number
  events?:        SearchEventSummary[]
  connectedArtists?: SearchArtistConnection[]
}

export interface SimilarArtist { //used by GET /artists/:id/similar
  artist:       Artist
  sharedEvents: number
  sharedGenres: string[]
}
