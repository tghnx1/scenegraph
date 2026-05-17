import { getMockSearchResponse } from './mock_data/mock_search'
import { MOCK_SEARCH_RESPONSES } from './mock_data/mock_search'
import type { SearchEntityType, SearchResponse, SearchResult } from '../types/search'

export const fetchSearch = (query: string): Promise<SearchResponse> => {
  const trimmed = query.trim()

  if (!trimmed) {
    return Promise.resolve({ query: '', results: [] })
  }

  // TODO: swap to the backend once the search endpoint is implemented.
  // return api.get<SearchResponse>(`/search?q=${encodeURIComponent(trimmed)}`)
  return Promise.resolve(getMockSearchResponse(trimmed))
}

export const fetchSearchResultById = (
  type: SearchEntityType,
  id: string,
  query = ''
): Promise<SearchResult | null> => {
  // TODO: swap to a backend detail endpoint, for example:
  // return api.get<SearchResult>(`/entities/${type}/${encodeURIComponent(id)}`)
  const queryMatch = getMockSearchResponse(query).results.find((result) => result.type === type && result.id === id)

  if (queryMatch) {
    return Promise.resolve(queryMatch)
  }

  const result = Object.values(MOCK_SEARCH_RESPONSES)
    .flatMap((response) => response.results)
    .find((entry) => entry.type === type && entry.id === id)

  return Promise.resolve(result ?? null)
}
