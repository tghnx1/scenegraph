export type NodeType = 'artist' | 'event' | 'venue' | 'promoter'

export interface GraphNode {
  id: string
  entityId: number
  type: NodeType
  name: string
  genres: string[]
  eventCount?: number | null
  date?: string | null
  startDate?: string | null
  endDate?: string | null
  district?: string | null
  sceneFocus?: string | null
}

export interface GraphEdge {
  source: string
  target: string
  relationship: string
  weight: number
}

export interface GraphData {
  centerNodeId?: string
  nodes: GraphNode[]
  links: GraphEdge[]
}

export function graphEntityId(nodeId: string, type?: NodeType): number | null {
  const prefix = type ? `${type}-` : /^[a-z]+-/
  const rawId = nodeId.replace(prefix, '')
  const entityId = Number(rawId)
  return Number.isInteger(entityId) ? entityId : null
}
