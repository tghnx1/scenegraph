/* import { api } from './client'
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
  api.get<GraphData>(`/graph/artist/${artistId}?depth=${depth}`) */

import { MOCK_GRAPH } from './mock'
import type { GraphData } from '../types/graph'

export interface GraphParams {
  genre?:    string
  dateFrom?: string
  dateTo?:   string
}

export const fetchGraph = (params: GraphParams = {}): Promise<GraphData> => {
  // TODO: replace with real API call when backend is ready:
  // return api.get<GraphData>(`/graph${toQuery(params)}`)

  // Filter mock data by genre if requested
  const filtered = params.genre
    ? {
        ...MOCK_GRAPH,
        nodes: MOCK_GRAPH.nodes.filter(n =>
          n.genres.some(g =>
            g.toLowerCase() === params.genre!.toLowerCase()
          )
        ),
      }
    : MOCK_GRAPH

  return Promise.resolve(filtered) // ← wraps data in a resolved Promise
}                                    // so useApi works identically

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