import { api } from './client'
import { MOCK_GRAPH } from './mock'
import type { GraphData } from '../types/graph'

export interface GraphParams {
  genre?:    string
  dateFrom?: string
  dateTo?:   string
  limit?:    number
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

export const fetchArtistEgoGraph = (artistId: string): Promise<GraphData> => {
  // Return only nodes and links connected to this artist
  const connectedLinks = MOCK_GRAPH.links.filter(
    l => l.source === artistId || l.target === artistId
  )
  const connectedIds = new Set([
    artistId,
    ...connectedLinks.map(l => l.source as string),
    ...connectedLinks.map(l => l.target as string),
  ])
  return Promise.resolve({
    nodes: MOCK_GRAPH.nodes.filter(n => connectedIds.has(n.id)),
    links: connectedLinks,
  })
}
