/* import { api } from './client' //brings the api.get() and api.post() functions from client.ts
import type { GraphData } from '../types/graph' //"import type" is only for TypeScript checking

export interface GraphParams { //GraphParams interface defines the filters that can be passed to fetchGraph. ? -> optional
  genre?:    string
  dateFrom?: string
  dateTo?:   string
}

function toQuery(params: GraphParams): string { //helper, converts params object into URL query string
  const q = new URLSearchParams()
  if (params.genre)    q.set('genre',    params.genre)
  if (params.dateFrom) q.set('dateFrom', params.dateFrom)
  if (params.dateTo)   q.set('dateTo',   params.dateTo)
  return q.toString() ? `?${q}` : '' //if no params, return an empty string so the URL is /graph, not /graph?
}

export const fetchGraph = (params: GraphParams = {}) => //the function components actually call, builds the URL and delegates to api.get. TypeScript knows the return type is Promise<GraphData>.
  api.get<GraphData>(`/graph${toQuery(params)}`)

export const fetchArtistEgoGraph = (artistId: string, depth = 2) => //fetches the subgraph around one artist. used when a user clicks a node(depth=2 -> artist + their connections + those connections' connections)
  api.get<GraphData>(`/graph/artist/${artistId}?depth=${depth}`) */

import { MOCK_GRAPH } from './mock_data/mock'
import type { GraphData, GraphNode, GraphEdge } from '../types/graph'

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
        nodes: MOCK_GRAPH.nodes.filter((n: GraphNode) =>
          n.genres?.some(g =>
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
    (l: GraphEdge) => l.source === artistId || l.target === artistId
  )
  const connectedIds = new Set([
    artistId,
    ...connectedLinks.map((l: GraphEdge) => l.source as string),
    ...connectedLinks.map((l: GraphEdge) => l.target as string),
  ])
  return Promise.resolve({
    nodes: MOCK_GRAPH.nodes.filter((n: GraphNode) => connectedIds.has(n.id)),
    links: connectedLinks,
  })
}