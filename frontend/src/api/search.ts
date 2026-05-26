import { api } from './client'
import type { SearchResponse } from '../types/search'

export const SEARCH_RESULT_LIMIT = 16

export const fetchSearch = async (query: string, limit = SEARCH_RESULT_LIMIT): Promise<SearchResponse> => {
  const trimmed = query.trim()

  if (!trimmed) {
    return { query: '', results: [] }
  }

  return api.get<SearchResponse>(`/search?q=${encodeURIComponent(trimmed)}&limit=${limit}`)
}
