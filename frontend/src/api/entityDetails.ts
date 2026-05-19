import { api } from './client'
import type { NodeType } from '../types/graph'
import type { SearchResult } from '../types/search'

type DetailNodeType = Exclude<NodeType, 'artist'>

export const fetchEntityDetail = (type: DetailNodeType, id: string): Promise<SearchResult> =>
  api.get<SearchResult>(`/${type}?id=${encodeURIComponent(id)}`)
