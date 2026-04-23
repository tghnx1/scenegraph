import ForceGraph2D from 'react-force-graph-2d'
import { useCallback, useEffect, useRef } from 'react'
import { useApi }        from '../hooks/useApi'
import { fetchGraph }    from '../api/graph'
import { useGraphStore } from '../store/graphStore'
import type { GraphNode } from '../types/graph'
import { useNavigate }    from 'react-router-dom' //

const NODE_COLORS: Record<string, string> = {
  artist:   '#7F77DD',
  venue:    '#1D9E75',
  promoter: '#D85A30',
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
  const navigate = useNavigate()
  const { activeGenre, setSelected, selectedNode } = useGraphStore()

  const { data, isLoading, error, refetch } = useApi(
    () => fetchGraph({ genre: activeGenre ?? undefined }),
    [activeGenre]
  )

  const handleNodeClick = useCallback(
    (node: object) => {
      const n = node as GraphNode
      setSelected(n)
    },
    [setSelected]
  )

  useEffect(() => {
    if (!graphRef.current) return

    //adjust forces
    graphRef.current.d3Force('charge')?.strength(-12)
    graphRef.current.d3Force('link')?.distance(45)
    graphRef.current.d3Force('link')?.strength(0.2)
  }, [data])

  if (isLoading) return <p style={{ padding: 24 }}>Loading graph...</p>
  if (error) return <p style={{ padding: 24 }}>{error} — <button onClick={refetch}>retry</button></p>

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <ForceGraph2D
        ref={graphRef}
        graphData={data ?? { nodes: [], links: [] }}
        nodeColor={(n: any) => NODE_COLORS[n.type as keyof typeof NODE_COLORS] ?? '#888'}
        nodeLabel="label"
        linkWidth={(l: any) => Math.sqrt(l.weight ?? 1)}
        onNodeClick={handleNodeClick}
        backgroundColor="transparent"
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