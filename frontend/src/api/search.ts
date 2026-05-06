import { getMockSearchResponse } from './mock_data/mock_search'
import type { SearchResponse } from '../types/search'

export const fetchSearch = (query: string): Promise<SearchResponse> => {
  const trimmed = query.trim()

  if (!trimmed) {
    return Promise.resolve({ query: '', results: [] })
  }

  // TODO: swap to the backend once the search endpoint is implemented.
  // return api.get<SearchResponse>(`/search?q=${encodeURIComponent(trimmed)}`)
  return Promise.resolve(getMockSearchResponse(trimmed))
}
