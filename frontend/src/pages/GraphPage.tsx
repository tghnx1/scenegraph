import ForceGraph2D from 'react-force-graph-2d'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useApi }        from '../hooks/useApi'
import { fetchGraph }    from '../api/graph'
import { useGraphStore } from '../store/graphStore'
import type { GraphNode } from '../types/graph'
import { useNavigate }    from 'react-router-dom' //

const NODE_COLORS: Record<string, string> = {
  artist:   '#7F77DD',
  venue:    '#1D9E75',
  promoter: '#eb7751',
  event:    '#9d2b2b'
}

const CENTERING_FORCE_STRENGTH = 0.04
const MIN_GRAPH_HEIGHT = 520

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


/* export function GraphPage() {
  const { activeGenre, selectedNode, setSelected } = useGraphStore()

  // re-fetches automatically when activeGenre changes
  const { data, isLoading, error } = useApi(
    () => fetchGraph({ genre: activeGenre ?? undefined }),
    [activeGenre]
  )

  const handleNodeClick = useCallback((node: object) => {
    setSelected(node as GraphNode)
  }, [setSelected])

  if (isLoading) return <div style={{ padding: 24 }}>Loading graph...</div>
  if (error)     return <div style={{ padding: 24 }}>Error: {error}</div>

  return (
    <div style={{ display: 'flex', height: '100%' }}>

      <ForceGraph2D
        graphData={data ?? { nodes: [], links: [] }}
        nodeColor={(n: object) => NODE_COLORS[(n as GraphNode).type] ?? '#888'}
        nodeLabel="label"
        linkWidth={(l: object) => Math.sqrt((l as { weight: number }).weight ?? 1)}
        onNodeClick={handleNodeClick}
        backgroundColor="transparent"
      />

      {selectedNode && (
        <div style={{ width: 260, padding: 20, borderLeft: '1px solid #eee',
                       overflowY: 'auto' }}>
          <h2 style={{ marginBottom: 8 }}>{selectedNode.label}</h2>
          <p style={{ color: '#888', fontSize: 13 }}>{selectedNode.type}</p>
          <p>{selectedNode.genres.join(', ')}</p>
        </div>
      )}

    </div>
  )
} */

/*   export function GraphPage() {
  const navigate = useNavigate()
  const { activeGenre, setSelected, selectedNode } = useGraphStore()

  const { data, isLoading, error, refetch } = useApi(
    () => fetchGraph({ genre: activeGenre ?? undefined }),
    [activeGenre]
  )

  const handleNodeClick = useCallback((node: object) => {
    const n = node as GraphNode
    setSelected(n)
    // If user clicks an artist node → go to their page
    if (n.type === 'artist') {
      navigate(`/artist/${n.id}`)   // ← add this
    }
  }, [setSelected, navigate])

  if (isLoading) return <p style={{padding:24}}>Loading graph...</p>
  if (error)     return <p style={{padding:24}}>{error} — <button onClick={refetch}>retry</button></p>

  return (
    <ForceGraph2D
      graphData={data ?? { nodes: [], links: [] }}
      nodeColor={(n: any) => NODE_COLORS[n.type as keyof typeof NODE_COLORS] ?? '#888'}
      nodeLabel="label"
      linkWidth={(l: any) => Math.sqrt(l.weight ?? 1)}
      onNodeClick={handleNodeClick}
      backgroundColor="transparent"
    />
  )
} */

export function GraphPage() {
  const graphRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const navigate = useNavigate()
  const { activeGenre, setSelected, selectedNode } = useGraphStore()

  const { data, isLoading, error, refetch } = useApi(
    () => fetchGraph({ genre: activeGenre ?? undefined }),
    [activeGenre]
  )

  // Compute all connected node IDs using breadth-first search
  const getConnectedNodeIds = useCallback(() => {
    if (!selectedNode || !data) return new Set<string>()
    const visited = new Set<string>([selectedNode.id])
    const queue: string[] = [selectedNode.id]
    
    while (queue.length > 0) {
      const currentId = queue.shift()!
      
      // Find all neighbors of the current node
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

  const connectedNodes = getConnectedNodeIds()

  const handleNodeClick = useCallback(
    (node: object) => {
      const n = node as GraphNode
      setSelected(n)
    },
    [setSelected]
  )

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

  useEffect(() => {
    if (!graphRef.current) return

    const graph = graphRef.current

    // Match the Observable-style D3 setup:
    // link force by id, many-body charge, and x/y centering forces.
    graph.d3Force('charge')?.strength(-70)
    graph.d3Force('link')?.id((d: GraphNode) => d.id)
    graph.d3Force('link')?.distance(45)
    graph.d3Force('link')?.strength(0.5)
    graph.d3Force('x', createAxisForce('x'))
    graph.d3Force('y', createAxisForce('y'))

    // Reheat when data changes so the layout settles again.
    graph.d3ReheatSimulation()
  }, [data])

  if (isLoading) return <p style={{ padding: 24 }}>Loading graph...</p>
  if (error) return <p style={{ padding: 24 }}>{error} — <button onClick={refetch}>retry</button></p>

    return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%', minHeight: MIN_GRAPH_HEIGHT }}>
      <ForceGraph2D
        ref={graphRef}
        width={graphSize.width || undefined}
        height={graphSize.height || undefined}
        graphData={data ?? { nodes: [], links: [] }}
        nodeColor={(n: any) => {
          if (selectedNode?.id === n.id) return '#FFD700' // Selected node: gold
          return NODE_COLORS[n.type as keyof typeof NODE_COLORS] ?? '#888'
        }}
        nodeRelSize={5}
        nodeVal={(n: any) => selectedNode?.id === n.id ? 3 : 1} //larger selected node
        nodeLabel={(n: any) => n.label ?? n.id}
        linkWidth={(l: any) => {
          const source = typeof l.source === 'object' ? l.source.id : l.source
          const target = typeof l.target === 'object' ? l.target.id : l.target
          if (connectedNodes.has(source) && connectedNodes.has(target)) {
            return Math.sqrt(l.value ?? l.weight ?? 1) * 2 // Thicker for highlighted links
          }
          return Math.sqrt(l.value ?? l.weight ?? 1)
        }}
        linkColor={(l: any) => {
          const source = typeof l.source === 'object' ? l.source.id : l.source
          const target = typeof l.target === 'object' ? l.target.id : l.target
          if (connectedNodes.has(source) && connectedNodes.has(target)) {
            return 'rgba(255, 215, 0, 0.8)' // Highlighted for connected links
          }
          return 'rgba(153,153,153,0.6)' // Original color for others
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
        warmupTicks={120}
        cooldownTicks={180}
      />

      {selectedNode && (
        <div
          style={{
            position: 'absolute',
            left: 16,
            right: 16,
            bottom: 16,
            background: 'rgba(15, 15, 18, 0.95)',
            border: '1px solid #2b2b35',
            borderRadius: 12,
            padding: 16,
            color: '#f3f3f3',
            boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: '#9aa', textTransform: 'uppercase' }}>
                {selectedNode.type}
              </div>
              <h3 style={{ margin: '4px 0 8px 0' }}>{selectedNode.label}</h3>
              <div style={{ fontSize: 13, color: '#bbb' }}>{selectedNode.eventCount} events</div>
              <div style={{ fontSize: 13, color: '#bbb', marginTop: 4 }}>
                {selectedNode.genres?.slice(0, 4).join(' · ') || 'No genres'}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              {selectedNode.type === 'artist' && (
                <button onClick={() => navigate(`/artist/${selectedNode.id}`)}>
                  View full profile
                </button>
              )}
              <button onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}