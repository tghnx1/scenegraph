export type NodeType = 'artist' | 'event' | 'venue' | 'promoter'

export interface GraphNode {
  id: string
  type: NodeType
  name: string
  genres: string[]
  eventCount?: number
  entityId?: number
  date?: string
  startDate?: string
  endDate?: string
  district?: string
  lat?: number
  lng?: number
}

export interface GraphEdge {
  source: string
  target: string
  weight: number
  relationship?: string
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphEdge[]
}
