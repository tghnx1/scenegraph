import { cn } from '@/shared/lib/cn-utils.ts'
import { GRAPH_NODE_TYPE_ITEMS } from './graphNodeTypes.ts'

export function GraphNodeLegend() {
  return (
    <section
      className="absolute right-4 top-4 z-[2] grid gap-2 rounded-[14px] border border-[var(--control-border)] bg-[var(--surface-overlay)] px-3 py-2.5 text-[0.82rem] text-[var(--text-muted)] backdrop-blur-md"
      aria-label="Graph node type legend"
    >
      <span className="text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
        Node types
      </span>
      <div className="grid grid-cols-2 gap-x-3.5 gap-y-2">
        {GRAPH_NODE_TYPE_ITEMS.map((item) => (
          <div
            key={item.type}
            className="inline-flex items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] px-1.5 py-1"
          >
            <span
              className={cn(
                'inline-block size-3 flex-[0_0_12px]',
                item.shapeClass,
              )}
              aria-hidden="true"
            />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
