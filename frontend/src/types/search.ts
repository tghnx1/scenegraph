export type SearchEntityType = 'artist' | 'venue' | 'promoter' | 'event'

export interface SearchEventSummary {
  id: string
  label: string
  date: string
  venueName: string
  artists: string[]
  promoters: string[]
}

export interface SearchArtistConnection {
  id: string
  label: string
  sharedEvents: number
}

export interface SearchArtistResult {
  type: 'artist'
  id: string
  label: string
  genres: string[]
  bio?: string
  eventCount: number
  events: SearchEventSummary[]
  connectedArtists: SearchArtistConnection[]
}

export interface SearchVenueResult {
  type: 'venue'
  id: string
  label: string
  address?: string
  district?: string
  eventCount: number
  events: SearchEventSummary[]
}

export interface SearchPromoterResult {
  type: 'promoter'
  id: string
  label: string
  eventCount: number
  events: SearchEventSummary[]
}

export interface SearchEventResult {
  type: 'event'
  id: string
  label: string
  date: string
  venue: {
    id: string
    label: string
  }
  artists: {
    id: string
    label: string
  }[]
  promoters: {
    id: string
    label: string
  }[]
}

export type SearchResult =
  | SearchArtistResult
  | SearchVenueResult
  | SearchPromoterResult
  | SearchEventResult

export interface SearchResponse {
  query: string
  results: SearchResult[]
}
