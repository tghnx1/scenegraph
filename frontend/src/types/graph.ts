export type NodeType = 'artist' | 'event' | 'venue' | 'promoter'
export type GraphEvidenceType =
  | 'semantic_bridge'
  | 'direct_connection'
  | 'warm_network'
  | 'manual_connection'
  | 'event_similarity'

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
  evidenceType?: GraphEvidenceType | string
  style?: 'solid' | 'dashed' | 'dotted' | string
  strength?: number | null
}

export interface GraphData {
  centerNodeId?: string
  nodes: GraphNode[]
  links: GraphEdge[]
  preferredPathNodeIds?: Record<string, string[]>
  preferredPathLinkKeys?: Record<string, string[]>
  preferredPathPromoterIdsByNodeId?: Record<string, string[]>
  preferredPathPromoterIdsByLinkKey?: Record<string, string[]>
  fallbackPathNodeIds?: Record<string, string[]>
  fallbackPathLinkKeys?: Record<string, string[]>
  fallbackPathPromoterIdsByNodeId?: Record<string, string[]>
  fallbackPathPromoterIdsByLinkKey?: Record<string, string[]>
}

export function graphEntityId(nodeId: string, type?: NodeType): number | null {
  const prefix = type ? `${type}-` : /^[a-z]+-/
  const rawId = nodeId.replace(prefix, '')
  const entityId = Number(rawId)
  return Number.isInteger(entityId) ? entityId : null
}
