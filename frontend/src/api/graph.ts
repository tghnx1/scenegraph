import { api } from './client'
import type { GraphData } from '../types/graph'

export interface GraphParams {
  genre?:    string
  dateFrom?: string
  dateTo?:   string
}

function toQuery(params: GraphParams): string {
  const q = new URLSearchParams()
  if (params.genre)    q.set('genre',    params.genre)
  if (params.dateFrom) q.set('dateFrom', params.dateFrom)
  if (params.dateTo)   q.set('dateTo',   params.dateTo)
  return q.toString() ? `?${q}` : ''
}

export const fetchGraph = (params: GraphParams = {}) =>
  api.get<GraphData>(`/graph${toQuery(params)}`)

export const fetchArtistEgoGraph = (artistId: string, depth = 2) =>
  api.get<GraphData>(`/graph/artist/${artistId}?depth=${depth}`)