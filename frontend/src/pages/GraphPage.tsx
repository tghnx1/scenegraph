import ForceGraph2D from 'react-force-graph-2d'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { fetchGraph } from '../api/graph'
import { useGraphStore } from '../store/graphStore'
import type { GraphNode } from '../types/graph'
import { useGraphHighlights } from './GraphPage/hooks/useGraphHighlights'
//import { useGraphFilters } from './GraphPage/hooks/useGraphFilters'
import { useGraphPhysics } from './GraphPage/hooks/useGraphPhysics'
//import { GraphNodeFilters } from './GraphPage/components/NodeFilter'
import { GraphNodeDetailsPanel } from './GraphPage/components/DetailsPanel'
import { drawNodeShape } from './GraphPage/drawNode.ts'

const MIN_GRAPH_HEIGHT = 520

export function GraphPage() {
  const graphRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const { activeGenre, setSelected, selectedNode } = useGraphStore()

  const { data, isLoading, error, refetch } = useApi(
    () => fetchGraph({ genre: activeGenre ?? undefined }),
    [activeGenre]
  )

  //hooks
  const { connectedNodes } = useGraphHighlights(selectedNode || null, data)
  //const { visibleNodeTypes, filteredData, toggleNodeType } = useGraphFilters(data)
  useGraphPhysics(graphRef, data)

  //setup container resize observer
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateSize = () => {
      const rect = container.getBoundingClientRect()
      setGraphSize({
        width: Math.floor(rect.width),
        height: Math.max(Math.floor(rect.height), MIN_GRAPH_HEIGHT),
      })
    }

    updateSize()

    const resizeObserver = new ResizeObserver(updateSize)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [])

  const handleNodeClick = useCallback(
    (node: object) => {
      const n = node as GraphNode
      setSelected(n)
    },
    [setSelected]
  )

  if (isLoading) return <p style={{ padding: 24 }}>Loading graph...</p>
  if (error) return <p style={{ padding: 24 }}>{error} — <button onClick={refetch}>retry</button></p>

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%', minHeight: MIN_GRAPH_HEIGHT }}>
      {/* <GraphNodeFilters visibleNodeTypes={visibleNodeTypes} onToggle={toggleNodeType} nodeColors={NODE_COLORS} /> */} 

      <ForceGraph2D
        ref={graphRef}
        width={graphSize.width || undefined}
        height={graphSize.height || undefined}
        //graphData={filteredData()} //filter is disabled like in line 73 & 36
        graphData={data || { nodes: [], links: [] }}
        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D) => {
          drawNodeShape(ctx, node.x, node.y, 5, node.type, selectedNode?.id === node.id)
        }}
        //nodeColor={() => 'rgba(0,0,0,0)'}
        nodeColor={() => 'transparent'}
        nodeRelSize={3}
        nodeVal={(n: any) => selectedNode?.id === n.id ? 3 : 1}
        nodeLabel={(n: any) => n.label ?? n.id}
        linkWidth={(l: any) => {
          const source = typeof l.source === 'object' ? l.source.id : l.source
          const target = typeof l.target === 'object' ? l.target.id : l.target
          if (connectedNodes.has(source) && connectedNodes.has(target)) {
            return Math.sqrt(l.value ?? l.weight ?? 1) * 2
          }
          return Math.sqrt(l.value ?? l.weight ?? 1)
        }}
        linkColor={(l: any) => {
          const source = typeof l.source === 'object' ? l.source.id : l.source
          const target = typeof l.target === 'object' ? l.target.id : l.target
          if (connectedNodes.has(source) && connectedNodes.has(target)) {
            return 'rgba(255, 215, 0, 0.8)'
          }
          return 'rgba(153,153,153,0.6)'
        }}
        enableNodeDrag
        onNodeDrag={(node: any) => {
          node.fx = node.x
          node.fy = node.y
        }}
        onNodeDragEnd={(node: any) => {
          node.fx = null
          node.fy = null
        }}
        onNodeClick={handleNodeClick}
        backgroundColor="#0b1220"
        warmupTicks={120} //120
        cooldownTicks={180} //180
      />

      <GraphNodeDetailsPanel selectedNode={selectedNode || null} onClose={() => setSelected(null)} />
    </div>
  )
}
