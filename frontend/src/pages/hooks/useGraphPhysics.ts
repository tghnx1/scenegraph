import { useEffect, type RefObject } from 'react'
import type { GraphNode } from '../../types/graph'
import { forceCollide } from 'd3-force'

const LEAF_RADIAL_TARGET_RADIUS = 150
const LEAF_RADIAL_STRENGTH = 0.25

export function getLeafRadialTargetRadius(nodeId: string | null, lowDegreeNodeIds: ReadonlySet<string>) {
  return nodeId && lowDegreeNodeIds.has(nodeId) ? LEAF_RADIAL_TARGET_RADIUS : 0
}

function createLeafRadialForce(lowDegreeNodeIds: ReadonlySet<string> = new Set()) {
  let nodes: Array<{ id?: string; x?: number; y?: number; vx?: number; vy?: number }> = []
  const force = (alpha: number) => {
    for (const node of nodes) {
      const nodeId = typeof (node as { id?: unknown }).id === 'string'
        ? (node as { id: string }).id
        : null
      const targetRadius = getLeafRadialTargetRadius(nodeId, lowDegreeNodeIds)
      if (targetRadius <= 0) continue

      const x = node.x ?? 0
      const y = node.y ?? 0
      const distance = Math.hypot(x, y) || 1
      const delta = (targetRadius - distance) * LEAF_RADIAL_STRENGTH * alpha
      const scale = delta / distance

      node.vx = (node.vx ?? 0) + x * scale
      node.vy = (node.vy ?? 0) + y * scale
    }
  }
  force.initialize = (nextNodes: typeof nodes) => {
    nodes = nextNodes
  }

  return force
}

export function useGraphPhysics(
  graphRef: RefObject<any>,
  data: any,
  lowDegreeNodeIds: ReadonlySet<string> = new Set(),
) {
  useEffect(() => {
    if (!graphRef.current) return

    const graph = graphRef.current
    const nodeCount = data?.nodes?.length ?? 0
    const chargeStrength = nodeCount > 250 ? -160 : -70
    const linkDistance = nodeCount > 250 ? 80 : 45

    graph.d3Force('charge')?.strength(chargeStrength)
    graph.d3Force('link')?.id((d: GraphNode) => d.id)
    graph.d3Force('link')?.distance(linkDistance)
    graph.d3Force('link')?.strength(0.5)
    graph.d3Force('leafRadial', createLeafRadialForce(lowDegreeNodeIds))
    const COLLIDE_RADIUS = 8
    graph.d3Force('collide', forceCollide(COLLIDE_RADIUS).iterations(2))
    graph.d3ReheatSimulation() //reheat when data changes so the layout settles again.
  }, [data, graphRef, lowDegreeNodeIds])
}
