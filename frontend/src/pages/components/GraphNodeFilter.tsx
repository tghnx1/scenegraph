import { cn } from '@/shared/lib/cn-utils.ts'
import type { NodeType } from '../../types/graph.ts'
import { GRAPH_NODE_TYPE_ITEMS } from './graphNodeTypes.ts'

export { GRAPH_NODE_TYPES } from './graphNodeTypes.ts'

interface GraphNodeFilterProps {
  visibleNodeTypes: Set<NodeType>
  onToggle: (type: NodeType) => void
  disabled?: boolean
}

export function GraphNodeFilter({ visibleNodeTypes, onToggle, disabled = false }: GraphNodeFilterProps) {
  return (
    <div className="absolute right-4 top-4 z-[2] grid grid-cols-2 gap-x-3.5 gap-y-2 rounded-[14px] border border-[var(--control-border)] bg-[var(--surface-overlay)] px-3 py-2.5 text-[0.82rem] text-[var(--text-muted)] backdrop-blur-md" aria-label="Filter graph by entity type">
      {GRAPH_NODE_TYPE_ITEMS.map((item) => {
        const isDisabled = disabled || item.type === 'event'
        const isActive = !isDisabled && visibleNodeTypes.has(item.type)

        return (
          <button
            type="button"
            className={cn(
              'inline-flex cursor-pointer items-center gap-2 whitespace-nowrap rounded-lg border border-transparent bg-transparent px-1.5 py-1 font-[inherit] text-inherit opacity-50 transition-[background,border-color,opacity]',
              isActive && 'border-[var(--selection-border)] bg-[var(--selection-soft)] opacity-100',
              !isDisabled && 'hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)] hover:opacity-100',
              isDisabled && 'cursor-default',
            )}
            key={item.type}
            onClick={() => !isDisabled && onToggle(item.type)}
            aria-pressed={isDisabled ? undefined : visibleNodeTypes.has(item.type)}
            disabled={isDisabled}
          >
            <span
              className={cn(
                'inline-block size-3 flex-[0_0_12px]',
                item.shapeClass,
              )}
              aria-hidden="true"
            />
            <span>{item.label}</span>
          </button>
        )
      })}
    </div>
  )
}
