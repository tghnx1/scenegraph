import { api } from './client'
import type { GraphData, NodeType } from '../types/graph'

export interface GraphParams {
  genre?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
}

export interface EgoGraphParams {
  type: NodeType
  id: string
  depth?: number
  limit?: number
}

function toQuery(params: GraphParams): string {
  const q = new URLSearchParams()
  if (params.genre) q.set('genre', params.genre)
  if (params.dateFrom) q.set('dateFrom', params.dateFrom)
  if (params.dateTo) q.set('dateTo', params.dateTo)
  if (params.limit !== undefined) q.set('limit', String(params.limit))
  return q.toString() ? `?${q.toString()}` : ''
}

export const fetchGraph = (params: GraphParams = {}): Promise<GraphData> =>
  api.get<GraphData>(`/graph${toQuery(params)}`)

export const fetchEgoGraph = ({
  type,
  id,
  depth = 1,
  limit = 100,
}: EgoGraphParams): Promise<GraphData> => {
  const q = new URLSearchParams()
  q.set('type', type)
  q.set('id', id)
  q.set('depth', String(depth))
  q.set('limit', String(limit))

  return api.get<GraphData>(`/graph/ego?${q.toString()}`)
}
