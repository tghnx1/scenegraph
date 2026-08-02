import { useEffect, type RefObject } from 'react'
import type { GraphNode } from '../../types/graph'
import { forceCollide } from 'd3-force'

const CENTERING_FORCE_STRENGTH = 0.04
const LEAF_CENTERING_FORCE_STRENGTH = 0.12

export function getNodeCenteringStrength(
  nodeId: string | null,
  lowDegreeNodeIds: ReadonlySet<string>,
) {
  return nodeId && lowDegreeNodeIds.has(nodeId)
    ? LEAF_CENTERING_FORCE_STRENGTH
    : CENTERING_FORCE_STRENGTH
}

function createAxisForce(
  axis: 'x' | 'y',
  target = 0,
  lowDegreeNodeIds: ReadonlySet<string> = new Set(),
) {
  let nodes: Array<{ x?: number; y?: number; vx?: number; vy?: number }> = []
  const force = (alpha: number) => {
    for (const node of nodes) {
      const nodeId = typeof (node as { id?: unknown }).id === 'string'
        ? (node as { id: string }).id
        : null
      const nodeStrength = getNodeCenteringStrength(nodeId, lowDegreeNodeIds)
      if (axis === 'x') {
        node.vx = (node.vx ?? 0) + (target - (node.x ?? 0)) * nodeStrength * alpha
      } else {
        node.vy = (node.vy ?? 0) + (target - (node.y ?? 0)) * nodeStrength * alpha
      }
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
    graph.d3Force('x', createAxisForce('x', 0, lowDegreeNodeIds))
    graph.d3Force('y', createAxisForce('y', 0, lowDegreeNodeIds))
    const COLLIDE_RADIUS = 8
    graph.d3Force('collide', forceCollide(COLLIDE_RADIUS).iterations(2))
    graph.d3ReheatSimulation() //reheat when data changes so the layout settles again.
  }, [data, graphRef, lowDegreeNodeIds])
}
