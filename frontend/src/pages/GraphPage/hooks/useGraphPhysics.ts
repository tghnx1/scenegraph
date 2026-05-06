import { useEffect } from 'react'
import type { GraphNode } from '../../../types/graph'
import { forceCollide } from 'd3-force'

const CENTERING_FORCE_STRENGTH = 0.04

function createAxisForce(axis: 'x' | 'y', target = 0, strength = CENTERING_FORCE_STRENGTH) {
  let nodes: Array<{ x?: number; y?: number; vx?: number; vy?: number }> = []
  const force = (alpha: number) => {
    for (const node of nodes) {
      if (axis === 'x') {
        node.vx = (node.vx ?? 0) + (target - (node.x ?? 0)) * strength * alpha
      } else {
        node.vy = (node.vy ?? 0) + (target - (node.y ?? 0)) * strength * alpha
      }
    }
  }
  force.initialize = (nextNodes: typeof nodes) => {
    nodes = nextNodes
  }

  return force
}

export function useGraphPhysics(graphRef: React.RefObject<any>, data: any) {
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
    graph.d3Force('x', createAxisForce('x'))
    graph.d3Force('y', createAxisForce('y'))
    const COLLIDE_RADIUS = 8
    graph.d3Force('collide', forceCollide(COLLIDE_RADIUS).iterations(2))
    graph.d3ReheatSimulation() //reheat when data changes so the layout settles again.
  }, [data, graphRef])
}
