import { useCallback, useMemo } from 'react'
import type { GraphData, GraphNode } from '../../types/graph'

type LinkEndpoint = string | { id: string }

function endpointId(endpoint: LinkEndpoint): string {
  return typeof endpoint === 'object' ? endpoint.id : endpoint
}

function linkKey(source: string, target: string): string {
  return [source, target].sort().join('|')
}

export function useGraphHighlights(selectedNode: GraphNode | null, data: GraphData, targetNodeId?: string) {
  //compute (all) connected node IDs using breadth-first search
  const getConnectedNodeIds = useCallback(() => {
    if (!selectedNode || !data) return new Set<string>()
    const visited = new Set<string>([selectedNode.id])
    const queue: string[] = [selectedNode.id]

    while (queue.length > 0) {
      const currentId = queue.shift()!

      //find (all) neighbors of the current node
      data.links.forEach((link) => {
        const source = endpointId(link.source as LinkEndpoint)
        const target = endpointId(link.target as LinkEndpoint)
        
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

  const pathLinks = useMemo(() => {
    const highlighted = new Set<string>()
    if (!selectedNode || !targetNodeId || selectedNode.id === targetNodeId) return highlighted

    const queue: string[] = [selectedNode.id]
    const visited = new Set<string>(queue)
    const previous = new Map<string, string>()

    while (queue.length > 0 && !visited.has(targetNodeId)) {
      const currentId = queue.shift()!

      data.links.forEach((link) => {
        const source = endpointId(link.source as LinkEndpoint)
        const target = endpointId(link.target as LinkEndpoint)
        const neighbor = source === currentId ? target : target === currentId ? source : null

        if (!neighbor || visited.has(neighbor)) return
        visited.add(neighbor)
        previous.set(neighbor, currentId)
        queue.push(neighbor)
      })
    }

    if (!visited.has(targetNodeId)) return highlighted

    let currentId = targetNodeId
    while (currentId !== selectedNode.id) {
      const priorId = previous.get(currentId)
      if (!priorId) return new Set<string>()
      highlighted.add(linkKey(priorId, currentId))
      currentId = priorId
    }

    return highlighted
  }, [data, selectedNode, targetNodeId])

  return { connectedNodes, pathLinks }
}
