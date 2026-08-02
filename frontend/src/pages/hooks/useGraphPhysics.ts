import { useEffect, type RefObject } from 'react'
import type { GraphData, GraphNode } from '../../types/graph'
import { forceCollide } from 'd3-force'

const DISCONNECTED_NODE_TARGET_RADIUS = 95
const DISCONNECTED_NODE_FORCE_STRENGTH = 0.24

type GraphLinkLike = {
  source: string | { id: string }
  target: string | { id: string }
}

function getLinkNodeId(endpoint: GraphLinkLike['source'] | GraphLinkLike['target']) {
  return typeof endpoint === 'object' && endpoint !== null ? endpoint.id : endpoint
}

export function getDisconnectedNodeIds(
  nodes: ReadonlyArray<Pick<GraphNode, 'id'>>,
  links: ReadonlyArray<GraphLinkLike>,
  centerNodeId?: string | null,
) {
  if (!centerNodeId || !nodes.some((node) => node.id === centerNodeId)) {
    return new Set<string>()
  }

  const adjacency = new Map<string, Set<string>>()
  for (const node of nodes) {
    adjacency.set(node.id, new Set())
  }

  for (const link of links) {
    const source = getLinkNodeId(link.source)
    const target = getLinkNodeId(link.target)
    adjacency.get(source)?.add(target)
    adjacency.get(target)?.add(source)
  }

  const connectedNodeIds = new Set<string>()
  const queue = [centerNodeId]
  while (queue.length > 0) {
    const nodeId = queue.shift()
    if (!nodeId || connectedNodeIds.has(nodeId)) continue
    connectedNodeIds.add(nodeId)
    adjacency.get(nodeId)?.forEach((neighbor) => {
      if (!connectedNodeIds.has(neighbor)) queue.push(neighbor)
    })
  }

  return new Set(
    nodes
      .map((node) => node.id)
      .filter((nodeId) => !connectedNodeIds.has(nodeId)),
  )
}

export function getDisconnectedNodeTargetRadius(
  nodeId: string | null,
  disconnectedNodeIds: ReadonlySet<string>,
) {
  return nodeId && disconnectedNodeIds.has(nodeId) ? DISCONNECTED_NODE_TARGET_RADIUS : 0
}

function createDisconnectedNodeForce(disconnectedNodeIds: ReadonlySet<string> = new Set()) {
  let nodes: Array<{ id?: string; x?: number; y?: number; vx?: number; vy?: number }> = []
  const force = (alpha: number) => {
    for (const node of nodes) {
      const nodeId = typeof node.id === 'string' ? node.id : null
      const targetRadius = getDisconnectedNodeTargetRadius(nodeId, disconnectedNodeIds)
      if (targetRadius <= 0) continue

      const x = node.x ?? 0
      const y = node.y ?? 0
      const distance = Math.hypot(x, y) || 1
      const delta = (distance - targetRadius) * DISCONNECTED_NODE_FORCE_STRENGTH * alpha
      const scale = delta / distance

      node.vx = (node.vx ?? 0) - x * scale
      node.vy = (node.vy ?? 0) - y * scale
    }
  }
  force.initialize = (nextNodes: typeof nodes) => {
    nodes = nextNodes
  }

  return force
}

export function useGraphPhysics(graphRef: RefObject<any>, data: GraphData | null | undefined) {
  useEffect(() => {
    if (!graphRef.current) return

    const graph = graphRef.current
    const nodeCount = data?.nodes?.length ?? 0
    const chargeStrength = nodeCount > 250 ? -160 : -70
    const linkDistance = nodeCount > 250 ? 80 : 45
    const disconnectedNodeIds = getDisconnectedNodeIds(
      data?.nodes ?? [],
      data?.links ?? [],
      data?.centerNodeId,
    )

    graph.d3Force('charge')?.strength(chargeStrength)
    graph.d3Force('link')?.id((d: GraphNode) => d.id)
    graph.d3Force('link')?.distance(linkDistance)
    graph.d3Force('link')?.strength(0.5)
    graph.d3Force('disconnectedNodes', createDisconnectedNodeForce(disconnectedNodeIds))
    const COLLIDE_RADIUS = 8
    graph.d3Force('collide', forceCollide(COLLIDE_RADIUS).iterations(2))
    graph.d3ReheatSimulation()
  }, [data, graphRef])
}
