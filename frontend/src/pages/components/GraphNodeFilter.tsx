import type { NodeType } from '../../types/graph.ts'

export const GRAPH_NODE_TYPES: NodeType[] = ['artist', 'venue', 'promoter', 'event']

const NODE_FILTER_ITEMS = [
  { type: 'artist', label: 'Artist' },
  { type: 'venue', label: 'Venue' },
  { type: 'promoter', label: 'Promoter' },
  { type: 'event', label: 'Event' },
] satisfies Array<{ type: NodeType; label: string }>

interface GraphNodeFilterProps {
  visibleNodeTypes: Set<NodeType>
  onToggle: (type: NodeType) => void
}

export function GraphNodeFilter({ visibleNodeTypes, onToggle }: GraphNodeFilterProps) {
  return (
    <div className="graph-legend" aria-label="Filter graph by entity type">
      {NODE_FILTER_ITEMS.map((item) => (
        <button
          type="button"
          className={`graph-legend-item${visibleNodeTypes.has(item.type) ? ' active' : ''}`}
          key={item.type}
          onClick={() => onToggle(item.type)}
          aria-pressed={visibleNodeTypes.has(item.type)}
        >
          <span className={`graph-legend-marker graph-legend-marker--${item.type}`} aria-hidden="true" />
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  )
}
