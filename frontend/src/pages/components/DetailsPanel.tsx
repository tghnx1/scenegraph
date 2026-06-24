import { RenderDetails } from './RenderDetails.tsx'
import { Badge } from '@/shared/ui/badge'
import type { EntityDetail } from '../../types/entityDetail'
import type { GraphNode } from '../../types/graph'
import type { SearchResult } from '../../types/search'

export interface ManualArtistConnectionControl {
  sourceArtistId: number
  connectedArtistIds: ReadonlySet<number>
  isLoading: boolean
  pendingArtistId: number | null
  error: string | null
  onToggle: (artistId: number) => Promise<void>
}

const sidebarContentClass = 'grid min-h-0 min-w-0 gap-3.5 overflow-y-auto max-[900px]:min-h-[clamp(340px,46dvh,500px)]'
const resultTypeClass = 'text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]'
const resultMetaClass = 'mt-1 text-sm text-[var(--text-muted)]'
const emptyStateClass = 'rounded-[18px] border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-5 text-sm text-[var(--text-muted)]'
const errorClass = 'mt-5 text-[var(--event)]'
const tileClass = 'grid gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3'

interface DetailsPanelProps {
  searchQuery: string
  searchResults: SearchResult[]
  isSearchLoading: boolean
  searchError: string | null
  selectedNode: GraphNode | null
  selectedEntityDetail: EntityDetail | null
  manualArtistConnections?: ManualArtistConnectionControl
}

export function DetailsPanel({
  searchQuery,
  searchResults,
  isSearchLoading,
  searchError,
  selectedNode,
  selectedEntityDetail,
  manualArtistConnections,
}: DetailsPanelProps) {
  const activeSearchResult = searchResults[0] ?? null

  if (selectedEntityDetail) {
    return (
      <div className={sidebarContentClass}>
        <RenderDetails
          variant="inline"
          result={selectedEntityDetail}
          manualArtistConnections={manualArtistConnections}
        />
      </div>
    )
  }

  if (selectedNode) {
    return (
      <div className={sidebarContentClass}>
        <div className="rounded-[18px] border border-[var(--surface-border)] bg-[var(--surface-panel)] p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <span className={resultTypeClass}>{selectedNode.type}</span>
              <h2>{selectedNode.name}</h2>
              <p className={resultMetaClass}>
                {selectedNode.genres?.slice(0, 4).join(' · ') || 'No genres available'}
              </p>
            </div>
          </div>

          <section className="mt-5 grid gap-2.5">
            <h3>Details</h3>
            <div className="grid gap-2.5">
              <div className={tileClass}>
                <strong>Type</strong>
                <span>{selectedNode.type}</span>
              </div>
              <div className={tileClass}>
                <strong>Node ID</strong>
                <span>{selectedNode.id}</span>
              </div>
            </div>
          </section>
        </div>

      </div>
    )
  }

  if (searchQuery) {
    return (
      <div className={sidebarContentClass}>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className={resultTypeClass}>Query</p>
            <h2>{searchQuery}</h2>
          </div>
          <Badge>{searchResults.length} matches</Badge>
        </div>

        {isSearchLoading && <p className={emptyStateClass}>Loading search results...</p>}
        {searchError && <p className={errorClass}>{searchError}</p>}
        {!isSearchLoading && !searchError && !activeSearchResult && (
          <div className={emptyStateClass}>
            <h3>No matches found</h3>
            <p>Try a shorter query or search by artist, venue, promoter, or event name.</p>
          </div>
        )}

        {activeSearchResult && (
          <RenderDetails
            variant="inline"
            result={activeSearchResult}
            manualArtistConnections={manualArtistConnections}
          />
        )}
      </div>
    )
  }

  return (
    <div className={sidebarContentClass}>
      <div className={emptyStateClass}>
        {/* <h3>Information</h3> */}
        <p>Search for an artist, venue, promoter, or event on the search field above, or click a node in the graph to view details.</p>
      </div>
    </div>
  )
}
