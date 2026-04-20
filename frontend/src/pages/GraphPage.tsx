import ForceGraph2D from 'react-force-graph-2d'
import { useCallback }   from 'react'
import { useApi }        from '../hooks/useApi'
import { fetchGraph }    from '../api/graph'
import { useGraphStore } from '../store/graphStore'
import type { GraphNode } from '../types/graph'

const NODE_COLORS: Record<string, string> = {
  artist:   '#7F77DD',
  venue:    '#1D9E75',
  promoter: '#D85A30',
}

export function GraphPage() {
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
}