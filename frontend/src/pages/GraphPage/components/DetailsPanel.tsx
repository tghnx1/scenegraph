import { SearchResultCard } from '../../../components/SearchResultCard.tsx'
import type { Artist, SimilarArtist } from '../../../types/artist.ts'
import type { GraphNode } from '../../../types/graph.ts'
import type { SearchArtistResult, SearchResult } from '../../../types/search.ts'

interface GraphSidebarDetailsProps {
  searchQuery: string
  searchResults: SearchResult[]
  isSearchLoading: boolean
  searchError: string | null
  selectedNode: GraphNode | null
  selectedArtist: Artist | null
  isArtistLoading: boolean
  artistError: string | null
  similarArtists: SimilarArtist[]
  onClearSelection: () => void
}

function toSelectedArtistResult(
  selectedNode: GraphNode | null,
  selectedArtist: Artist | null,
  similarArtists: SimilarArtist[]
): SearchArtistResult | null {
  if (!selectedNode || selectedNode.type !== 'artist' || !selectedArtist) {
    return null
  }

  return {
    type: 'artist',
    id: selectedArtist.id,
    label: selectedArtist.name,
    genres: selectedArtist.genres.map((genre) => genre.name),
    bio: selectedArtist.bio,
    eventCount: selectedArtist.eventCount ?? selectedNode.eventCount ?? 0,
    events: [],
    connectedArtists: similarArtists.map((entry) => ({
      id: entry.artist.id,
      label: entry.artist.name,
      sharedEvents: entry.sharedEvents,
    })),
  }
}

export function GraphSidebarDetails({
  searchQuery,
  searchResults,
  isSearchLoading,
  searchError,
  selectedNode,
  selectedArtist,
  isArtistLoading,
  artistError,
  similarArtists,
  onClearSelection,
}: GraphSidebarDetailsProps) {
  const activeSearchResult = searchResults[0] ?? null
  const selectedArtistResult = toSelectedArtistResult(selectedNode, selectedArtist, similarArtists)

  if (selectedNode) {
    if (selectedNode.type === 'artist' && isArtistLoading) {
      return (
        <div className="graph-sidebar-content">
          <div className="empty-state">
            <h3>Loading biography...</h3>
            <p>Fetching the selected artist details.</p>
          </div>
          <button className="graph-sidebar-close" onClick={onClearSelection}>
            Clear selection
          </button>
        </div>
      )
    }

    if (selectedNode.type === 'artist' && artistError) {
      return (
        <div className="graph-sidebar-content">
          <div className="empty-state">
            <h3>Could not load biography</h3>
            <p className="error">{artistError}</p>
          </div>
          <button className="graph-sidebar-close" onClick={onClearSelection}>
            Clear selection
          </button>
        </div>
      )
    }

    if (selectedNode.type === 'artist' && selectedArtistResult) {
      return (
        <div className="graph-sidebar-content">
          <SearchResultCard variant="inline" result={selectedArtistResult} />
          <button className="graph-sidebar-close" onClick={onClearSelection}>
            Clear selection
          </button>
        </div>
      )
    }

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
            <span className="result-badge">{selectedNode.eventCount ?? 0} events</span>
          </div>

          <section className="result-section">
            <h3>Overview</h3>
            <p className="result-description">
              Click an artist node to open biography and linked entities. Search results stay in the same panel above.
            </p>
          </section>

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

        <button className="graph-sidebar-close" onClick={onClearSelection}>
          Clear selection
        </button>
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

        {activeSearchResult && <SearchResultCard variant="inline" result={activeSearchResult} />}
      </div>
    )
  }

  return (
    <div className="graph-sidebar-content">
      <div className="empty-state">
        <h3>No node selected</h3>
        <p>Search for an artist, venue, or event above, or click a node in the graph to view details.</p>
      </div>
    </div>
  )
}
