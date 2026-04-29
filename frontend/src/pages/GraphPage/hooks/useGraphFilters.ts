import { useCallback, useState } from 'react'
import type { GraphNode } from '../../../types/graph'

export function useGraphFilters(data: any) {
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<string>>(
    new Set(['artist', 'venue', 'promoter', 'event'])
  )

  //filter graph data based on visible node types
  const filteredData = useCallback(() => {
    if (!data) return { nodes: [], links: [] }
    
    const visibleNodeIds = new Set(
      data.nodes
        ?.filter((n: GraphNode) => visibleNodeTypes.has(n.type))
        .map((n: GraphNode) => n.id)
    )

    return {
      nodes: data.nodes?.filter((n: GraphNode) => visibleNodeTypes.has(n.type)) ?? [],
      links: data.links?.filter((l: any) => {
        const source = typeof l.source === 'object' ? l.source.id : l.source
        const target = typeof l.target === 'object' ? l.target.id : l.target
        return visibleNodeIds.has(source) && visibleNodeIds.has(target)
      }) ?? []
    }
  }, [data, visibleNodeTypes])

  const toggleNodeType = (type: string) => {
    const newTypes = new Set(visibleNodeTypes)
    if (newTypes.has(type)) {
      newTypes.delete(type)
    } else {
      newTypes.add(type)
    }
    setVisibleNodeTypes(newTypes)
  }

  return { visibleNodeTypes, filteredData, toggleNodeType }
}
