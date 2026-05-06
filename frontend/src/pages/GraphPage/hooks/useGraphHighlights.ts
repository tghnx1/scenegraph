import { useCallback, useMemo } from 'react'
import type { GraphNode } from '../../../types/graph'

export function useGraphHighlights(selectedNode: GraphNode | null, data: any) {
  //compute (all) connected node IDs using breadth-first search
  const getConnectedNodeIds = useCallback(() => {
    if (!selectedNode || !data) return new Set<string>()
    const visited = new Set<string>([selectedNode.id])
    const queue: string[] = [selectedNode.id]

    while (queue.length > 0) {
      const currentId = queue.shift()!

      //find (all) neighbors of the current node
      data.links?.forEach((link: any) => {
        const source = typeof link.source === 'object' ? link.source.id : link.source
        const target = typeof link.target === 'object' ? link.target.id : link.target
        
        if (source === currentId && !visited.has(target)) {
          visited.add(target)
          queue.push(target)
        }
        if (target === currentId && !visited.has(source)) {
          visited.add(source)
          queue.push(source)
        }
      })
    }

    return visited
  }, [selectedNode, data])

  const connectedNodes = useMemo(() => getConnectedNodeIds(), [getConnectedNodeIds])

  return { connectedNodes }
}
