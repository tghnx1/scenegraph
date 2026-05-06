import { useNavigate } from 'react-router-dom'
import type { GraphNode } from '../../../types/graph'
import { BACKGROUND, GRADIENT_MID, TEXT, TEXT_MUTED, hexToRgba } from '../../../styles/colors'

interface GraphNodeDetailsPanelProps {
  selectedNode: GraphNode | null
  onClose: () => void
}

export function GraphNodeDetailsPanel({ selectedNode, onClose }: GraphNodeDetailsPanelProps) {
  const navigate = useNavigate()

  if (!selectedNode) return null

  return (
    <div
      style={{
        position: 'absolute',
        left: 16,
        right: 16,
        bottom: 16,
        background: hexToRgba(BACKGROUND, 0.95),
        border: `1px solid ${hexToRgba(GRADIENT_MID, 0.6)}`,
        borderRadius: 12,
        padding: 16,
        color: TEXT,
        boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ fontSize: 12, color: TEXT_MUTED, textTransform: 'uppercase' }}>
            {selectedNode.type}
          </div>
          <h3 style={{ margin: '4px 0 8px 0' }}>{selectedNode.label}</h3>
          <div style={{ fontSize: 13, color: TEXT_MUTED }}>{selectedNode.eventCount} events</div>
          <div style={{ fontSize: 13, color: TEXT_MUTED, marginTop: 4 }}>
            {selectedNode.genres?.slice(0, 4).join(' · ') || 'No genres'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          {selectedNode.type === 'artist' && (
            <button onClick={() => navigate(`/artist/${selectedNode.id}`)}>
              View full profile
            </button>
          )}
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
