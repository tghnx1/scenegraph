interface GraphNodeFiltersProps {
  visibleNodeTypes: Set<string>
  onToggle: (type: string) => void
  nodeColors: Record<string, string>
}

export function GraphNodeFilters({ visibleNodeTypes, onToggle, nodeColors }: GraphNodeFiltersProps) {
  return (
    <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 10, display: 'flex', gap: 8 }}>
      {Object.keys(nodeColors).map((type) => (
        <button
          key={type}
          onClick={() => onToggle(type)}
          style={{
            padding: '6px 12px',
            backgroundColor: visibleNodeTypes.has(type) ? nodeColors[type as keyof typeof nodeColors] : '#444',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
            opacity: visibleNodeTypes.has(type) ? 1 : 0.5,
            textTransform: 'capitalize'
          }}
        >
          {type}
        </button>
      ))}
    </div>
  )
}
