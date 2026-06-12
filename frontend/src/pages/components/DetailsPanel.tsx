import { RenderDetails } from './RenderDetails.tsx'
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
      <div className="graph-sidebar-content">
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
      <div className="graph-sidebar-content">
        <div className="search-result-card search-result-card--inline graph-node-detail">
          <div className="result-header">
            <div>
              <span className="result-type">{selectedNode.type}</span>
              <h2>{selectedNode.name}</h2>
              <p className="result-meta">
                {selectedNode.genres?.slice(0, 4).join(' · ') || 'No genres available'}
              </p>
            </div>
          </div>

          <section className="result-section">
            <h3>Details</h3>
            <div className="result-list">
              <div className="result-tile">
                <strong>Type</strong>
                <span>{selectedNode.type}</span>
              </div>
              <div className="result-tile">
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
      <div className="graph-sidebar-content">
        <div className="search-summary compact">
          <div>
            <p className="result-type">Query</p>
            <h2>{searchQuery}</h2>
          </div>
          <span className="result-badge">{searchResults.length} matches</span>
        </div>

        {isSearchLoading && <p className="empty-state">Loading search results...</p>}
        {searchError && <p className="error">{searchError}</p>}
        {!isSearchLoading && !searchError && !activeSearchResult && (
          <div className="empty-state">
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
    <div className="graph-sidebar-content">
      <div className="empty-state">
        {/* <h3>Information</h3> */}
        <p>Search for an artist, venue, promoter, or event on the search field above, or click a node in the graph to view details.</p>
      </div>
    </div>
  )
}
