import { useEffect, type RefObject } from 'react'
import type { GraphData, GraphNode } from '../../types/graph'
import { forceCollide, type SimulationNodeDatum } from 'd3-force'

const ISOLATED_NODE_TARGET_RADIUS = 30
const ISOLATED_NODE_TARGET_RING_SPACING = 14
const ISOLATED_NODE_TARGET_SLOT_COUNT = 24
const ISOLATED_NODE_FORCE_STRENGTH = 0.10

type GraphLinkLike = {
  source: string | { id: string }
  target: string | { id: string }
}

function getLinkNodeId(endpoint: GraphLinkLike['source'] | GraphLinkLike['target']) {
  return typeof endpoint === 'object' && endpoint !== null ? endpoint.id : endpoint
}

function getSimulationNodeId(node: SimulationNodeDatum) {
  const nextNode = node as SimulationNodeDatum & { id?: string | number }
  return typeof nextNode.id === 'string' ? nextNode.id : null
}

function hashNodeId(nodeId: string) {
  let hash = 0
  for (let index = 0; index < nodeId.length; index += 1) {
    hash = Math.imul(31, hash) + nodeId.charCodeAt(index)
  }
  return hash >>> 0
}

export function getIsolatedNodeIds(
  nodes: ReadonlyArray<Pick<GraphNode, 'id'>>,
  links: ReadonlyArray<GraphLinkLike>,
) {
  if (nodes.length === 0) {
    return new Set<string>()
  }

  const linkedNodeIds = new Set<string>()
  for (const link of links) {
    const source = getLinkNodeId(link.source)
    const target = getLinkNodeId(link.target)
    linkedNodeIds.add(source)
    linkedNodeIds.add(target)
  }

  return new Set(
    nodes
      .map((node) => node.id)
      .filter((nodeId) => !linkedNodeIds.has(nodeId)),
  )
}

export function getIsolatedNodeTargetRadius(
  nodeId: string | null,
  isolatedNodeIds: ReadonlySet<string>,
) {
  return nodeId && isolatedNodeIds.has(nodeId) ? ISOLATED_NODE_TARGET_RADIUS : 0
}

export function getIsolatedNodeTargetPosition(
  nodeId: string | null,
  isolatedNodeIds: ReadonlySet<string>,
) {
  if (!nodeId || !isolatedNodeIds.has(nodeId)) {
    return null
  }

  const hash = hashNodeId(nodeId)
  const angle = (hash % ISOLATED_NODE_TARGET_SLOT_COUNT) / ISOLATED_NODE_TARGET_SLOT_COUNT * Math.PI * 2
  const ringIndex = Math.floor(hash / ISOLATED_NODE_TARGET_SLOT_COUNT) % 3
  const radius = ISOLATED_NODE_TARGET_RADIUS + (ringIndex * ISOLATED_NODE_TARGET_RING_SPACING)

  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  }
}

function createIsolatedNodeForce(isolatedNodeIds: ReadonlySet<string> = new Set()) {
  let nodes: Array<{ id?: string; x?: number; y?: number; vx?: number; vy?: number }> = []
  const force = (alpha: number) => {
    for (const node of nodes) {
      const nodeId = typeof node.id === 'string' ? node.id : null
      const targetPosition = getIsolatedNodeTargetPosition(nodeId, isolatedNodeIds)
      if (!targetPosition) continue

      const x = node.x ?? 0
      const y = node.y ?? 0
      node.vx = (node.vx ?? 0) + (targetPosition.x - x) * ISOLATED_NODE_FORCE_STRENGTH * alpha
      node.vy = (node.vy ?? 0) + (targetPosition.y - y) * ISOLATED_NODE_FORCE_STRENGTH * alpha
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
    const isolatedNodeIds = getIsolatedNodeIds(
      data?.nodes ?? [],
      data?.links ?? [],
    )

    graph.d3Force('charge')?.strength((node: SimulationNodeDatum) => {
      const nodeId = getSimulationNodeId(node)
      return nodeId && isolatedNodeIds.has(nodeId) ? 0 : chargeStrength
    })
    graph.d3Force('link')?.id((d: GraphNode) => d.id)
    graph.d3Force('link')?.distance(linkDistance)
    graph.d3Force('link')?.strength(0.5)
    graph.d3Force('isolatedNodes', createIsolatedNodeForce(isolatedNodeIds))
    const COLLIDE_RADIUS = 8
    graph.d3Force('collide', forceCollide((node: SimulationNodeDatum) => {
      const nodeId = getSimulationNodeId(node)
      return nodeId && isolatedNodeIds.has(nodeId) ? 0 : COLLIDE_RADIUS
    }).iterations(2))
    graph.d3ReheatSimulation()
  }, [data, graphRef])
}
