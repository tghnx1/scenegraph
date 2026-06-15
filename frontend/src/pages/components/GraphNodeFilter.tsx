import { cn } from '@/shared/lib/cn-utils.ts'
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
    <div className="absolute right-4 top-4 z-[2] grid grid-cols-2 gap-x-3.5 gap-y-2 rounded-[14px] border border-[var(--control-border)] bg-[var(--surface-overlay)] px-3 py-2.5 text-[0.82rem] text-[var(--text-muted)] backdrop-blur-md" aria-label="Filter graph by entity type">
      {NODE_FILTER_ITEMS.map((item) => {
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
                'inline-block size-3 flex-[0_0_12px] bg-[var(--promoter)]',
                item.type === 'artist' && 'bg-[var(--artist)] [clip-path:polygon(25%_6%,75%_6%,100%_50%,75%_94%,25%_94%,0_50%)]',
                item.type === 'venue' && 'bg-[var(--venue)] [clip-path:polygon(50%_0,100%_100%,0_100%)]',
                item.type === 'promoter' && 'bg-[var(--promoter)]',
                item.type === 'event' && 'rounded-full bg-[var(--event)]',
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
