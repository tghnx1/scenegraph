import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import type { EntityDetail } from '../../types/entityDetail'
import type { GraphNode } from '../../types/graph'
import { RenderDetails } from './RenderDetails'
import type { ManualArtistConnectionControl } from './DetailsPanel'

const inspectorClass = 'grid min-h-0 min-w-0 gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 shadow-[0_10px_24px_rgba(0,0,0,0.08)]'
const inspectorHeadingClass = 'text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]'

interface RecommendationDetailsInspectorProps {
  selectedNode: GraphNode
  selectedEntityDetail: EntityDetail | null
  isLoading: boolean
  error: string | null
  onSelectNode: (node: GraphNode | null) => void
  onClose: () => void
  manualArtistConnections?: ManualArtistConnectionControl
  className?: string
}

export function RecommendationDetailsInspector({
  selectedNode,
  selectedEntityDetail,
  isLoading,
  error,
  onSelectNode,
  onClose,
  manualArtistConnections,
  className,
}: RecommendationDetailsInspectorProps) {
  return (
    <aside className={cn(inspectorClass, className)} aria-label="Recommendation details">
      <header className="flex items-start justify-between gap-3 rounded-[18px] border border-[var(--surface-border)] bg-[var(--surface-panel)] px-4 py-3">
        <div className="grid min-w-0 gap-1">
          <span className={inspectorHeadingClass}>Recommendation details</span>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </header>

      <div className="min-h-0 overflow-y-auto pr-1">
        {error ? (
          <div className="rounded-[18px] border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-4 text-sm text-[var(--event)]">
            {error}
          </div>
        ) : isLoading || !selectedEntityDetail ? (
          <div className="rounded-[18px] border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-4 text-sm text-[var(--text-muted)]">
            Loading details…
          </div>
        ) : (
          <RenderDetails
            variant="inline"
            result={selectedEntityDetail}
            linkMode="inspector"
            hideIdentifiers
            manualArtistConnections={manualArtistConnections}
            onSelectRelatedEntity={onSelectNode}
          />
        )}
      </div>
    </aside>
  )
}
