import { useCallback, useMemo } from 'react'
import type { GraphData, GraphNode } from '../../types/graph'

type LinkEndpoint = string | { id: string }

function endpointId(endpoint: LinkEndpoint): string {
  return typeof endpoint === 'object' ? endpoint.id : endpoint
}

function linkKey(source: string, target: string): string {
  return [source, target].sort().join('|')
}

export function useGraphHighlights(
  selectedNode: GraphNode | null,
  data: GraphData,
  targetNodeId?: string | string[],
) {
  const adjacency = useMemo(() => {
    const next = new Map<string, Set<string>>()
    data.links.forEach((link) => {
      const source = endpointId(link.source as LinkEndpoint)
      const target = endpointId(link.target as LinkEndpoint)
      if (!next.has(source)) next.set(source, new Set())
      if (!next.has(target)) next.set(target, new Set())
      next.get(source)?.add(target)
      next.get(target)?.add(source)
    })
    return next
  }, [data.links])

  //compute (all) connected node IDs using breadth-first search
  const getConnectedNodeIds = useCallback(() => {
    if (!selectedNode || !data) return new Set<string>()
    const visited = new Set<string>([selectedNode.id])
    const queue: string[] = [selectedNode.id]

    while (queue.length > 0) {
      const currentId = queue.shift()!

      //find (all) neighbors of the current node
      adjacency.get(currentId)?.forEach((neighbor) => {
        if (visited.has(neighbor)) return
        visited.add(neighbor)
        queue.push(neighbor)
      })
    }

    return visited
  }, [adjacency, selectedNode, data])

  const connectedNodes = useMemo(() => getConnectedNodeIds(), [getConnectedNodeIds])

  const pathLinks = useMemo(() => {
    const highlighted = new Set<string>()
    const targetNodeIds = Array.isArray(targetNodeId)
      ? targetNodeId
      : (targetNodeId ? [targetNodeId] : [])
    if (!selectedNode || targetNodeIds.length === 0) return highlighted

    const computeDistances = (startId: string) => {
      const distances = new Map<string, number>([[startId, 0]])
      const queue: string[] = [startId]

      while (queue.length > 0) {
        const currentId = queue.shift()!
        const currentDistance = distances.get(currentId) ?? 0
        adjacency.get(currentId)?.forEach((neighbor) => {
          if (distances.has(neighbor)) return
          distances.set(neighbor, currentDistance + 1)
          queue.push(neighbor)
        })
      }

      return distances
    }

    const sourceDistances = computeDistances(selectedNode.id)
    targetNodeIds.forEach((targetNode) => {
      if (selectedNode.id === targetNode) return

      const targetDistances = computeDistances(targetNode)
      const shortestDistance = sourceDistances.get(targetNode)
      if (shortestDistance === undefined) return

      data.links.forEach((link) => {
        const source = endpointId(link.source as LinkEndpoint)
        const target = endpointId(link.target as LinkEndpoint)
        const sourceFromStart = sourceDistances.get(source)
        const targetFromStart = sourceDistances.get(target)
        const sourceToTarget = targetDistances.get(source)
        const targetToTarget = targetDistances.get(target)

        const isForwardShortest =
          sourceFromStart !== undefined
          && targetToTarget !== undefined
          && sourceFromStart + 1 + targetToTarget === shortestDistance
        const isBackwardShortest =
          targetFromStart !== undefined
          && sourceToTarget !== undefined
          && targetFromStart + 1 + sourceToTarget === shortestDistance

        if (isForwardShortest || isBackwardShortest) {
          highlighted.add(linkKey(source, target))
        }
      })
    })

    return highlighted
  }, [adjacency, data, selectedNode, targetNodeId])

  const pathNodeIds = useMemo(() => {
    const highlightedNodes = new Set<string>()
    const targetNodeIds = Array.isArray(targetNodeId)
      ? targetNodeId
      : (targetNodeId ? [targetNodeId] : [])
    if (!selectedNode || targetNodeIds.length === 0) return highlightedNodes
    if (pathLinks.size === 0) return highlightedNodes

    highlightedNodes.add(selectedNode.id)
    targetNodeIds.forEach((targetId) => highlightedNodes.add(targetId))
    pathLinks.forEach((key) => {
      const [source, target] = key.split('|')
      if (source) highlightedNodes.add(source)
      if (target) highlightedNodes.add(target)
    })
    return highlightedNodes
  }, [pathLinks, selectedNode, targetNodeId])

  return { connectedNodes, pathLinks, pathNodeIds }
}
