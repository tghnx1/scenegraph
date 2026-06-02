export type SearchEntityType = 'artist' | 'venue' | 'promoter' | 'event'

export interface SearchResultItem {
  type: SearchEntityType
  id: number
  name: string
}

export interface SearchResponse {
  query: string
  results: SearchResultItem[]
}

export type SearchResult = SearchResultItem
