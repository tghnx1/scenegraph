import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchEntityDetail } from '../api/entityDetails'
import { fetchArtist } from '../api/artists'
import { fetchSearch } from '../api/search'
import { useApi } from '../hooks/useApi'
import { useGraphStore } from '../store/graphStore'
import type { Artist } from '../types/artist'
import { graphEntityId, type GraphNode, type NodeType } from '../types/graph'
import type { SearchResponse, SearchResult } from '../types/search'
import { GraphSidebarDetails } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/ScenegraphMapPanel.tsx'
import { SearchQueryForm } from './components/SearchQueryForm.tsx'
import { useDebouncedValue } from './hooks/useDebouncedValue'

const stats = [
  { label: 'Connected nodes', value: '0' },
  { label: 'Shared events', value: '0' },
  { label: 'Recommendations', value: '0' },
]

const PROMOTER_RECOMMENDATIONS_URL = 'http://localhost:8080/api/recommendations/artists/2178/promoters?limit=10'

export function ProfilePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const [recommendationsJson, setRecommendationsJson] = useState<unknown>(null)
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false)
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null)
  const submittedQuery = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedIdParam = searchParams.get('selectedId')
  const selectedArtistId = selectedNode?.type === 'artist'
    ? selectedNode.id
    : selectedTypeParam === 'artist'
      ? selectedIdParam
      : null
  const selectedDetailType = selectedNode && selectedNode.type !== 'artist'
    ? selectedNode.type
    : selectedTypeParam && selectedTypeParam !== 'artist'
      ? selectedTypeParam
      : null
  const selectedDetailId = selectedNode && selectedNode.type !== 'artist' ? selectedNode.id : selectedIdParam

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

  const { data: dropdownSearchData, isLoading: isDropdownSearchLoading } = useApi<SearchResponse>(
    () => (
      debouncedSearchValue.length >= 2 &&
        debouncedSearchValue === searchValue.trim() &&
        debouncedSearchValue !== submittedQuery.trim()
        ? fetchSearch(debouncedSearchValue)
        : Promise.resolve({ query: '', results: [] })
    ),
    [debouncedSearchValue, searchValue, submittedQuery]
  )

  const { data: selectedEntityDetail, isLoading: isSelectedEntityDetailLoading } = useApi(
    () => (
      selectedDetailType && selectedDetailId
        ? fetchEntityDetail(selectedDetailType as Exclude<NodeType, 'artist'>, selectedDetailId)
        : Promise.resolve(null)
    ),
    [selectedDetailType, selectedDetailId]
  )

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

  const handleSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const nextQuery = searchValue.trim()
      if (!nextQuery) return
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', nextQuery)
      nextParams.delete('artist')
      nextParams.delete('selectedType')
      nextParams.delete('selectedId')
      setSelected(null)
      setSearchParams(nextParams, { replace: true })
    },
    [searchParams, searchValue, setSearchParams, setSelected]
  )

  const handleClearSearch = useCallback(() => {
    setSearchValue('')
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('q')
    nextParams.delete('artist')
    nextParams.delete('selectedType')
    nextParams.delete('selectedId')
    setSearchParams(nextParams, { replace: true })
    setSelected(null)
  }, [searchParams, setSearchParams, setSelected])

  const handleSearchValueChange = useCallback((nextValue: string) => {
    setSearchValue(nextValue)
  }, [])

  const handleSelectSearchResult = useCallback(
    (result: SearchResult) => {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', result.name)
      nextParams.set('selectedType', result.type)
      nextParams.set('selectedId', result.id)
      nextParams.delete('artist')
      setSearchValue(result.name)
      setSelected(null)
      setSearchParams(nextParams, { replace: false })
    },
    [searchParams, setSearchParams, setSelected]
  )

  const handleLoadRecommendations = useCallback(async () => {
    setIsRecommendationsLoading(true)
    setRecommendationsError(null)

    try {
      const response = await fetch(PROMOTER_RECOMMENDATIONS_URL)

      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }

      setRecommendationsJson(await response.json())
    } catch (error) {
      setRecommendationsJson(null)
      setRecommendationsError(error instanceof Error ? error.message : 'Failed to load recommendations')
    } finally {
      setIsRecommendationsLoading(false)
    }
  }, [])

  const searchResults = searchData?.results ?? []
  const trimmedSearchValue = searchValue.trim()
  const trimmedSubmittedQuery = submittedQuery.trim()
  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const shouldFetchDropdownSearch =
    debouncedSearchValue.length >= 2 &&
    debouncedSearchValue === trimmedSearchValue &&
    debouncedSearchValue !== trimmedSubmittedQuery
  const dropdownSearchResults = shouldFetchDropdownSearch ? dropdownSearchData?.results ?? [] : []
  const detailSearchResults = selectedEntityDetail ? [selectedEntityDetail] : searchResults
  const detailsSearchError = searchError
  const isDetailsSearchLoading = isSearchLoading || isSelectedEntityDetailLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const selectedArtistNode: GraphNode | null = selectedArtist
    ? {
        id: selectedArtist.id,
        entityId: graphEntityId(selectedArtist.id, 'artist') ?? 0,
        type: 'artist',
        name: selectedArtist.name,
        genres: selectedArtist.genres,
        eventCount: selectedArtist.eventCount,
      }
    : null
  const detailsSelectedNode = selectedEntityDetail ? null : selectedNode ?? selectedArtistNode

  return (
    <div className="profile-page">
      <div className="profile-actions" aria-label="Profile actions">
        <button type="button">Export to PDF</button>
      </div>

      <section className="profile-grid" aria-label="Profile overview">
        <article className="profile-card context-panel">
          <SearchQueryForm
            inputId="profile-details-search-query-input"
            label="Search database"
            value={searchValue}
            onChange={handleSearchValueChange}
            onSubmit={handleSearchSubmit}
            onClear={handleClearSearch}
            showClear={hasActiveSearchState}
            results={dropdownSearchResults}
            isLoading={isDropdownWaiting || isDropdownSearchLoading}
            onSelectResult={handleSelectSearchResult}
          />

          {/* <div className="panel-heading">
            <span className="search-query-label">Node details</span>
          </div> */}
          <GraphSidebarDetails
            searchQuery={submittedQuery}
            searchResults={detailSearchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={detailsSelectedNode}
            selectedArtist={selectedArtist}
          />
        </article>

        <section className="graph-workspace" aria-label="Profile graph workspace">
          <article className="profile-card graph-panel">
            <ScenegraphMapPanel /* title="Scenegraph Database" */ />
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

        <article className="profile-card recommendations-panel">
          <div className="panel-heading">
            <span className="search-query-label">Recommendations</span>
            <button
              type="button"
              onClick={handleLoadRecommendations}
              disabled={isRecommendationsLoading}
            >
              {isRecommendationsLoading ? 'Loading...' : 'The button'}
            </button>
          </div>
          {recommendationsError && <p className="error">{recommendationsError}</p>}
          {recommendationsJson !== null && (
            <pre className="recommendations-json">
              {JSON.stringify(recommendationsJson, null, 2)}
            </pre>
          )}
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
