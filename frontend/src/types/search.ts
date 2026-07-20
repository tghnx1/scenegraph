export type SearchEntityType = 'artist' | 'venue' | 'promoter' | 'event'
export type SearchSort = 'relevance' | 'name_asc' | 'name_desc'

export interface SearchResultItem {
  type: SearchEntityType
  id: number
  name: string
  ra_artist_id?: string | null
  event_count?: number | null
  genres?: string[] | null
  biography_normalized?: string | null
  biography_preview?: string | null
  latest_event_title?: string | null
  latest_event_date?: string | null
}

export interface SearchResponse {
  query: string
  results: SearchResultItem[]
}

export type SearchResult = SearchResultItem
