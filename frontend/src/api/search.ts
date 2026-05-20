import { api } from './client'
import type { SearchResponse } from '../types/search'

export const fetchSearch = async (query: string, limit = 8): Promise<SearchResponse> => {
  const trimmed = query.trim()

  if (!trimmed) {
    return { query: '', results: [] }
  }

  return api.get<SearchResponse>(`/search?q=${encodeURIComponent(trimmed)}&limit=${limit}`)
}
