import { api } from './client'
// import { getMockSearchResponse } from './mock_data/mock_search'
// import { MOCK_SEARCH_RESPONSES } from './mock_data/mock_search'
import type { SearchEntityType, SearchResponse, SearchResult } from '../types/search'

interface SearchApiResult {
  type: SearchEntityType
  id: string
  name: string
}

interface SearchApiResponse {
  query: string
  results: SearchApiResult[]
}

function toSearchResult(result: SearchApiResult): SearchResult {
  if (result.type === 'artist') {
    return {
      type: 'artist',
      id: result.id,
      label: result.name,
      genres: [],
      eventCount: 0,
      events: [],
      connectedArtists: [],
    }
  }

  if (result.type === 'venue') {
    return {
      type: 'venue',
      id: result.id,
      label: result.name,
      eventCount: 0,
      events: [],
    }
  }

  if (result.type === 'promoter') {
    return {
      type: 'promoter',
      id: result.id,
      label: result.name,
      eventCount: 0,
      events: [],
    }
  }

  return {
    type: 'event',
    id: result.id,
    label: result.name,
    date: '',
    venue: {
      id: '',
      label: '',
    },
    artists: [],
    promoters: [],
  }
}

export const fetchSearch = async (query: string, limit = 8): Promise<SearchResponse> => {
  const trimmed = query.trim()

  if (!trimmed) {
    return { query: '', results: [] }
  }

  const response = await api.get<SearchApiResponse>(`/search?q=${encodeURIComponent(trimmed)}&limit=${limit}`)
  return {
    query: response.query,
    results: response.results.map(toSearchResult),
  }
}
