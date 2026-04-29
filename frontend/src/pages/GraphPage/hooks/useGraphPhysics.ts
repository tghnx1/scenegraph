import { useEffect } from 'react'
import type { GraphNode } from '../../../types/graph'

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

    //similar to the observable D3 setup:
    // link force by id, many-body charge, and x/y centering forces.
    graph.d3Force('charge')?.strength(-70)
    graph.d3Force('link')?.id((d: GraphNode) => d.id)
    graph.d3Force('link')?.distance(45)
    graph.d3Force('link')?.strength(0.5)
    graph.d3Force('x', createAxisForce('x'))
    graph.d3Force('y', createAxisForce('y'))

    //reheat when data changes so the layout settles again.
    graph.d3ReheatSimulation()
  }, [data, graphRef])
}
