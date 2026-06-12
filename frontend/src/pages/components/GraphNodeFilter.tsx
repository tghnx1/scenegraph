import type { NodeType } from '../../types/graph.ts'

export const GRAPH_NODE_TYPES: NodeType[] = ['venue', 'artist', 'promoter', 'event']

const NODE_FILTER_ITEMS = [
  { type: 'venue', label: 'Venue' },
  { type: 'artist', label: 'Artist' },
  { type: 'promoter', label: 'Promoter' },
  { type: 'event', label: 'Event' },
] satisfies Array<{ type: NodeType; label: string }>

interface GraphNodeFilterProps {
  visibleNodeTypes: Set<NodeType>
  onToggle: (type: NodeType) => void
  disabled?: boolean
}

export function GraphNodeFilter({ visibleNodeTypes, onToggle, disabled = false }: GraphNodeFilterProps) {
  return (
    <div className="graph-legend" aria-label="Filter graph by entity type">
      {NODE_FILTER_ITEMS.map((item) => {
        const isDisabled = disabled || item.type === 'event'

        return (
          <button
            type="button"
            className={`graph-legend-item${!isDisabled && visibleNodeTypes.has(item.type) ? ' active' : ''}`}
            key={item.type}
            onClick={() => !isDisabled && onToggle(item.type)}
            aria-pressed={isDisabled ? undefined : visibleNodeTypes.has(item.type)}
            disabled={isDisabled}
          >
            <span className={`graph-legend-marker graph-legend-marker--${item.type}`} aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        )
      })}
    </div>
  )
}
