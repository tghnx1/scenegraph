import { useSearchParams } from 'react-router-dom'
import { fetchArtist, fetchSimilarArtists } from '../api/artists.ts'
import { fetchSearch } from '../api/search.ts'
import { useApi } from '../hooks/useApi.ts'
import { useGraphStore } from '../store/graphStore.ts'
import type { Artist, SimilarArtist } from '../types/artist.ts'
import type { SearchResponse } from '../types/search.ts'
import { GraphSidebarDetails } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/ScenegraphMapPanel.tsx'

const stats = [
  { label: 'Connected nodes', value: '0' },
  { label: 'Shared events', value: '0' },
  { label: 'Recommendations', value: '0' },
]

export function ProfilePage({ themeName }: { themeName?: string } = {}) {
  const [searchParams] = useSearchParams()
  const { selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const selectedArtistId = selectedNode?.type === 'artist' ? selectedNode.id : null

  const {
    data: searchData,
    isLoading: isSearchLoading,
    error: searchError,
  } = useApi<SearchResponse>(
    () => (submittedQuery ? fetchSearch(submittedQuery) : Promise.resolve({ query: '', results: [] })),
    [submittedQuery]
  )

  const { data: selectedArtist } = useApi<Artist | null>(
    () => (selectedArtistId ? fetchArtist(selectedArtistId) : Promise.resolve(null)),
    [selectedArtistId]
  )

  const { data: similarArtists } = useApi<SimilarArtist[]>(
    () => (selectedArtistId ? fetchSimilarArtists(selectedArtistId) : Promise.resolve([] as SimilarArtist[])),
    [selectedArtistId]
  )

  const searchResults = searchData?.results ?? []
  const detailSearchResults = searchResults
  const detailsSearchError = searchError
  const isDetailsSearchLoading = isSearchLoading

  return (
    <div className="profile-page">
      <section className="profile-grid" aria-label="Profile overview">
        <article className="profile-card context-panel">
          <div className="panel-heading">
            <span className="search-query-label">Node details</span>
          </div>
          <GraphSidebarDetails
            searchQuery={submittedQuery}
            searchResults={detailSearchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={selectedNode}
            selectedArtist={selectedArtist}
            similarArtists={similarArtists ?? []}
          />
        </article>

        <section className="graph-workspace" aria-label="Profile graph workspace">
          <article className="profile-card graph-panel">
            <ScenegraphMapPanel title="Scenegraph Database" themeName={themeName} />
          </article>
        </section>

        <article className="profile-card profile-summary-panel">
          <div className="panel-heading">
            <span className="search-query-label">Profile</span>
            <button type="button">Edit</button>
          </div>
          <h2>Artist biography</h2>
          <p>Self biography and claimed profile fields appear here.</p>
          <div className="profile-fields">
            <span>Name</span>
            <span>Genres</span>
            <span>Location</span>
          </div>
        </article>

        <article className="profile-card stats-panel">
          <div className="panel-heading">
            <span className="search-query-label">Statistics</span>
            {/* <span className="panel-status">Overview</span> */}
          </div>
          <div className="stat-grid">
            {stats.map((item) => (
              <div key={item.label} className="stat-tile">
                <strong>{item.value}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div className="chart-placeholder" aria-label="Chart placeholder" />
        </article>

        <article className="profile-card side-panel recommendations-panel">
          <div className="panel-heading">
            <span className="search-query-label">Recommendations</span>
            {/* <span className="panel-status">Draft</span> */}
          </div>
          <div className="placeholder-list">
            <span>Recommended names</span>
            <span>A list of names/connections.</span>
          </div>
        </article>

        <article className="profile-card side-panel communications-panel">
          <div className="panel-heading">
            <span className="search-query-label">Communications</span>
            {/* <span className="panel-status">Inbox</span> */}
          </div>
          <div className="placeholder-list">
            <span>Clickable contact names</span>
            <span>Open a chat</span>
          </div>
        </article>
      </section>
    </div>
  )
}
