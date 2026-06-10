export type SearchEntityType = 'artist' | 'venue' | 'promoter' | 'event'
export type SearchSort = 'relevance' | 'name_asc' | 'name_desc' | 'id_asc' | 'id_desc'

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
