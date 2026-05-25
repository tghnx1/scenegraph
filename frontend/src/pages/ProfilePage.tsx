import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchEntityDetail } from '../api/entityDetails'
import { fetchArtist } from '../api/artists'
import { fetchSearch } from '../api/search'
import { useApi } from '../hooks/useApi'
import { useGraphStore } from '../store/graphStore'
import type { Artist } from '../types/artist'
import type { EntityDetail } from '../types/entityDetail'
import { graphEntityId, type GraphNode, type NodeType } from '../types/graph'
import type { PromoterRecommendationResponse } from '../types/recommendation'
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
type ProfileWorkspaceTab = 'graph' | 'recommendations'

export function ProfilePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<ProfileWorkspaceTab>('graph')
  const [recommendationsData, setRecommendationsData] = useState<PromoterRecommendationResponse | null>(null)
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false)
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null)
  const submittedQuery = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedIdParam = searchParams.get('selectedId')
  const selectedArtistNodeId = selectedNode?.type === 'artist'
    ? selectedNode.id
    : selectedTypeParam === 'artist'
      ? selectedIdParam
      : null
  const selectedArtistId = selectedArtistNodeId
    ? String(graphEntityId(selectedArtistNodeId, 'artist') ?? selectedArtistNodeId)
    : null
  const selectedDetailType = selectedNode && selectedNode.type !== 'artist'
    ? selectedNode.type
    : selectedTypeParam && selectedTypeParam !== 'artist'
      ? selectedTypeParam
      : null
  const selectedDetailNodeId = selectedNode && selectedNode.type !== 'artist' ? selectedNode.id : selectedIdParam
  const selectedDetailId = selectedDetailType && selectedDetailNodeId
    ? String(graphEntityId(selectedDetailNodeId, selectedDetailType as NodeType) ?? selectedDetailNodeId)
    : null

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

  const { data: selectedEntityDetail, isLoading: isSelectedEntityDetailLoading } = useApi<EntityDetail | null>(
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

      setRecommendationsData(await response.json() as PromoterRecommendationResponse)
    } catch (error) {
      setRecommendationsData(null)
      setRecommendationsError(error instanceof Error ? error.message : 'Failed to load recommendations')
    } finally {
      setIsRecommendationsLoading(false)
    }
  }, [])

  const handleSelectRecommendation = useCallback((recommendationId: number) => {
    const recommendationNode = recommendationsData?.graph.nodes.find((node) => (
      node.type === 'promoter' && node.entityId === recommendationId
    ))

    if (recommendationNode) {
      setSelected(recommendationNode)
    }
  }, [recommendationsData, setSelected])

  const searchResults = searchData?.results ?? []
  const trimmedSearchValue = searchValue.trim()
  const trimmedSubmittedQuery = submittedQuery.trim()
  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const shouldFetchDropdownSearch =
    debouncedSearchValue.length >= 2 &&
    debouncedSearchValue === trimmedSearchValue &&
    debouncedSearchValue !== trimmedSubmittedQuery
  const dropdownSearchResults = shouldFetchDropdownSearch ? dropdownSearchData?.results ?? [] : []
  const detailsSearchError = searchError
  const isDetailsSearchLoading = isSearchLoading || isSelectedEntityDetailLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const activeSelectedArtist = selectedArtistId ? selectedArtist : null
  const selectedArtistNode: GraphNode | null = activeSelectedArtist
    ? {
        id: activeSelectedArtist.id,
        entityId: graphEntityId(activeSelectedArtist.id, 'artist') ?? 0,
        type: 'artist',
        name: activeSelectedArtist.name,
        genres: activeSelectedArtist.genres,
        eventCount: activeSelectedArtist.eventCount,
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
            searchResults={searchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={detailsSelectedNode}
            selectedArtist={activeSelectedArtist}
            selectedEntityDetail={selectedEntityDetail}
          />
        </article>

        <section className="graph-workspace" aria-label="Profile graph workspace">
          <article className="profile-card graph-panel">
            <div className="profile-workspace-tabs" role="tablist" aria-label="Profile graph views">
              <button
                type="button"
                id="profile-workspace-tab-graph"
                className={`profile-workspace-tab${activeWorkspaceTab === 'graph' ? ' active' : ''}`}
                role="tab"
                aria-selected={activeWorkspaceTab === 'graph'}
                aria-controls="profile-workspace-panel-graph"
                onClick={() => setActiveWorkspaceTab('graph')}
              >
                Graph
              </button>
              <button
                type="button"
                id="profile-workspace-tab-recommendations"
                className={`profile-workspace-tab${activeWorkspaceTab === 'recommendations' ? ' active' : ''}`}
                role="tab"
                aria-selected={activeWorkspaceTab === 'recommendations'}
                aria-controls="profile-workspace-panel-recommendations"
                onClick={() => setActiveWorkspaceTab('recommendations')}
              >
                Recommendations
              </button>
            </div>
            {activeWorkspaceTab === 'graph' && (
              <section
                id="profile-workspace-panel-graph"
                className="profile-workspace-content"
                role="tabpanel"
                aria-labelledby="profile-workspace-tab-graph"
              >
                <ScenegraphMapPanel />
              </section>
            )}
            {activeWorkspaceTab === 'recommendations' && (
              <section
                id="profile-workspace-panel-recommendations"
                className="profile-workspace-content recommendations-panel"
                role="tabpanel"
                aria-labelledby="profile-workspace-tab-recommendations"
              >
                <div className="panel-heading">
                  <span className="search-query-label">Promoter Recommendations</span>
                  {recommendationsData === null && (
                    <button
                      type="button"
                      onClick={() => void handleLoadRecommendations()}
                      disabled={isRecommendationsLoading}
                    >
                      {isRecommendationsLoading
                        ? 'Loading. Dont do anything, dont even breathe.'
                        : recommendationsError
                          ? 'Retry'
                          : 'The button'}
                    </button>
                  )}
                </div>
                {recommendationsData === null && !recommendationsError && !isRecommendationsLoading && (
                  <p className="recommendations-help">
                    Click the button to load recommendations. Load time may be quite long. Let the wizard does its magic.
                  </p>
                )}
                {recommendationsError && <p className="error">{recommendationsError}</p>}
                {recommendationsData !== null && (
                  <div className="recommendations-content">
                    <section className="recommendation-list" aria-label="Recommended promoters">
                      {recommendationsData.recommendations.map((recommendation) => (
                        <article className="recommendation-item" key={recommendation.id}>
                          <button
                            type="button"
                            className="recommendation-name"
                            aria-pressed={selectedNode?.id === `promoter-${recommendation.id}`}
                            onClick={() => handleSelectRecommendation(recommendation.id)}
                          >
                            {recommendation.name}
                          </button>
                          <ul className="recommendation-reasons">
                            {recommendation.reasons.map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        </article>
                      ))}
                    </section>
                    <section className="recommendation-graph-map" aria-label="Recommendation evidence graph">
                      <ScenegraphMapPanel
                        providedData={recommendationsData.graph}
                        showFilters={false}
                        highlightPathToNodeId={`artist-${recommendationsData.entityId}`}
                      />
                    </section>
                  </div>
                )}
              </section>
            )}
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
