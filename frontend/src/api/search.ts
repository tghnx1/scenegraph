import { api } from './client'
import type { SearchEntityType, SearchResponse } from '../types/search'

export const SEARCH_RESULT_LIMIT = 10
export const SEARCH_RESULT_MAX_LIMIT = 100

export const fetchSearch = async (query: string, limit = SEARCH_RESULT_LIMIT, type?: SearchEntityType): Promise<SearchResponse> => {
  const trimmed = query.trim()

  if (!trimmed) {
    return { query: '', results: [] }
  }

  const safeLimit = Math.min(limit, SEARCH_RESULT_MAX_LIMIT)
  const params = new URLSearchParams({
    q: trimmed,
    limit: String(safeLimit),
  })

  if (type) {
    params.set('type', type)
  }

  return api.get<SearchResponse>(`/search?${params.toString()}`)
}
