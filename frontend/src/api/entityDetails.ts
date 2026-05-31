import { api } from './client'
import { graphEntityId, type NodeType } from '../types/graph'
import type { SearchResult } from '../types/search'

type DetailNodeType = Exclude<NodeType, 'artist'>

export const fetchEntityDetail = (type: DetailNodeType, id: string): Promise<SearchResult> =>
  api.get<SearchResult>(`/${type}?id=${encodeURIComponent(String(graphEntityId(id, type) ?? id))}`)
