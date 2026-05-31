import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchEntityDetail } from '../api/entityDetails'
import { fetchSearch } from '../api/search'
import { useApi } from '../hooks/useApi'
import { useGraphStore } from '../store/graphStore'
import type { EntityDetail } from '../types/entityDetail'
import { graphEntityId, type NodeType } from '../types/graph'
import type { PromoterRecommendationResponse } from '../types/recommendation'
import type { SearchResponse, SearchResult } from '../types/search'
import { DetailsPanel } from './components/DetailsPanel.tsx'
import { RecommendationLoading } from './components/LoadingScreen.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { SearchQueryForm } from './components/SearchQuery.tsx'
import { useDebouncedValue } from './hooks/useDebouncedValue'

const PROMOTER_RECOMMENDATIONS_URL = 'http://localhost:8080/api/recommendations/artists/2178/promoters?limit=50'
const RECOMMENDATION_LOADING_MESSAGES = [
  'Finding similar artists',
  'Comparing related events',
  'Building promoter graph',
]

const PROMOTER_SIZE_LABELS: Record<'small' | 'medium' | 'large', string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large',
}

type ReasonListKind =
  | 'relatedEvents'
  | 'similarEvents'
  | 'similarArtists'
  | 'coPlayedArtists'
  | 'manualArtists'

const MORE_SUFFIX_PATTERN = /,?\s*\+\d+\s+more\.?$/i
const REASON_PREFIX_PATTERN = /^(.+?:)\s*/

function uniqueNonEmpty(values: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    const normalized = value.trim()
    if (!normalized) continue
    const key = normalized.toLocaleLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    result.push(normalized)
  }
  return result
}

function detectReasonListKind(reason: string): ReasonListKind | null {
  if (reason.includes('related promoter events:')) return 'relatedEvents'
  if (reason.includes('similar promoter events:')) return 'similarEvents'
  if (reason.includes('similar artists connected:')) return 'similarArtists'
  if (reason.includes('co-played artists connected:')) return 'coPlayedArtists'
  if (reason.includes('manually added trusted artist links:')) return 'manualArtists'
  return null
}

function reasonListItems(recommendation: PromoterRecommendationResponse['recommendations'][number], reason: string): string[] {
  const kind = detectReasonListKind(reason)
  if (kind === null) return []

  const rawSignals = recommendation.debug?.rawSignals
  let items: string[] = []

  if (kind === 'relatedEvents') {
    items = recommendation.reasonDetails?.relatedEventTitles ?? rawSignals?.relatedEventTitles ?? []
  } else if (kind === 'similarEvents') {
    items = recommendation.reasonDetails?.similarPromoterEventTitles ?? rawSignals?.eventSimilarityEventTitles ?? []
  } else if (kind === 'similarArtists') {
    items = recommendation.reasonDetails?.similarArtistNames ?? rawSignals?.matchedArtistNames ?? []
  } else if (kind === 'coPlayedArtists') {
    items = recommendation.reasonDetails?.coPlayedArtistNames
      ?? (rawSignals?.coPlayedConnectionArtists ?? []).map((artist) => artist.name)
  } else if (kind === 'manualArtists') {
    items = recommendation.reasonDetails?.manualArtistNames
      ?? (rawSignals?.manualConnectionArtists ?? []).map((artist) => artist.name)
  }

  return uniqueNonEmpty(items)
}

function hiddenReasonItems(recommendation: PromoterRecommendationResponse['recommendations'][number], reason: string): string[] {
  const moreMatch = reason.match(/\+(\d+)\s+more/i)
  if (!moreMatch) return []
  const hiddenCount = Number.parseInt(moreMatch[1] ?? '0', 10)
  if (!Number.isFinite(hiddenCount) || hiddenCount <= 0) return []
  const normalizedItems = reasonListItems(recommendation, reason)
  const hiddenStartIndex = Math.max(normalizedItems.length - hiddenCount, 0)
  return normalizedItems.slice(hiddenStartIndex)
}
type ProfileWorkspaceTab = 'graph' | 'recommendations'

export function ProfilePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<ProfileWorkspaceTab>('graph')
  const [recommendationsData, setRecommendationsData] = useState<PromoterRecommendationResponse | null>(null)
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false)
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null)
  const [recommendationLoadingMessageIndex, setRecommendationLoadingMessageIndex] = useState(0)
  const [expandedRecommendationId, setExpandedRecommendationId] = useState<number | null>(null)
  const [expandedReasonItems, setExpandedReasonItems] = useState<Record<string, boolean>>({})
  const submittedQuery = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedIdParam = searchParams.get('selectedId')
  const selectedDetailType = selectedNode
    ? selectedNode.type
    : selectedTypeParam
      ? selectedTypeParam
      : null
  const selectedDetailNodeId = selectedNode ? selectedNode.id : selectedIdParam
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
        ? fetchEntityDetail(selectedDetailType as NodeType, selectedDetailId)
        : Promise.resolve(null)
    ),
    [selectedDetailType, selectedDetailId]
  )

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

  useEffect(() => {
    if (!isRecommendationsLoading) {
      setRecommendationLoadingMessageIndex(0)
      return
    }

    const messageInterval = window.setInterval(() => {
      setRecommendationLoadingMessageIndex((currentIndex) => (
        (currentIndex + 1) % RECOMMENDATION_LOADING_MESSAGES.length
      ))
    }, 1800)

    return () => window.clearInterval(messageInterval)
  }, [isRecommendationsLoading])

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
    setExpandedRecommendationId(null)
    setExpandedReasonItems({})

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

  const handleToggleRecommendation = useCallback((recommendationId: number) => {
    setExpandedRecommendationId((currentId) => (
      currentId === recommendationId ? null : recommendationId
    ))
    handleSelectRecommendation(recommendationId)
  }, [handleSelectRecommendation])

  const handleToggleReasonItems = useCallback((key: string) => {
    setExpandedReasonItems((current) => ({ ...current, [key]: !current[key] }))
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
  const detailsSearchError = searchError
  const isDetailsSearchLoading = isSearchLoading || isSelectedEntityDetailLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const detailsSelectedNode = selectedEntityDetail ? null : selectedNode

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
          <DetailsPanel
            searchQuery={submittedQuery}
            searchResults={searchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={detailsSelectedNode}
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
            <section
              id="profile-workspace-panel-graph"
              className="profile-workspace-content"
              role="tabpanel"
              aria-labelledby="profile-workspace-tab-graph"
              hidden={activeWorkspaceTab !== 'graph'}
            >
              <ScenegraphMapPanel />
            </section>
            <section
              id="profile-workspace-panel-recommendations"
              className="profile-workspace-content recommendations-panel"
              role="tabpanel"
              aria-labelledby="profile-workspace-tab-recommendations"
              hidden={activeWorkspaceTab !== 'recommendations'}
            >
                <div className="panel-heading">
                  <span className="search-query-label">Promoter Recommendations</span>
                </div>
                {recommendationsData === null && !isRecommendationsLoading && (
                  <div className="recommendations-start">
                    <p className={recommendationsError ? 'error' : 'recommendations-help'}>
                      {recommendationsError
                        ?? 'Click the button to load recommendations. Load time may be quite long. Let the wizard does its magic.'}
                    </p>
                    <button
                      type="button"
                      className="recommendations-load-button"
                      onClick={() => void handleLoadRecommendations()}
                    >
                      {recommendationsError ? 'Retry' : 'The button'}
                    </button>
                  </div>
                )}
                {isRecommendationsLoading && (
                  <RecommendationLoading activity={RECOMMENDATION_LOADING_MESSAGES[recommendationLoadingMessageIndex]} />
                )}
                {recommendationsData !== null && (
                  <div className="recommendations-content">
                    <section className="recommendation-list" aria-label="Recommended promoters">
                      {recommendationsData.recommendations.map((recommendation) => (
                        <article className="recommendation-item" key={recommendation.id}>
                          <button
                            type="button"
                            className="recommendation-name"
                            aria-pressed={selectedNode?.id === `promoter-${recommendation.id}`}
                            aria-expanded={expandedRecommendationId === recommendation.id}
                            aria-controls={`recommendation-reasons-${recommendation.id}`}
                            onClick={() => handleToggleRecommendation(recommendation.id)}
                          >
                            <span className="recommendation-name-label">{recommendation.name}</span>
                            <span
                              className={`recommendation-size-badge recommendation-size-${recommendation.promoterSizeSegment}`}
                            >
                              {PROMOTER_SIZE_LABELS[recommendation.promoterSizeSegment]}
                            </span>
                          </button>
                          {expandedRecommendationId === recommendation.id && (
                            <ul
                              id={`recommendation-reasons-${recommendation.id}`}
                              className="recommendation-reasons"
                            >
                              {recommendation.reasons.map((reason, index) => {
                                const reasonKey = `${recommendation.id}-${index}`
                                const hiddenItems = hiddenReasonItems(recommendation, reason)
                                const canExpand = hiddenItems.length > 0
                                const isExpanded = Boolean(expandedReasonItems[reasonKey])
                                const cleanReason = reason.replace(MORE_SUFFIX_PATTERN, '')
                                const prefixMatch = cleanReason.match(REASON_PREFIX_PATTERN)
                                const reasonPrefix = prefixMatch ? prefixMatch[1] : cleanReason
                                const allItems = reasonListItems(recommendation, reason)
                                const visibleItems = canExpand
                                  ? allItems.slice(0, Math.max(allItems.length - hiddenItems.length, 0))
                                  : allItems

                                return (
                                  <li key={reasonKey}>
                                    {(allItems.length > 0 && prefixMatch) ? (
                                      <>
                                        <span>{reasonPrefix}</span>
                                        <ul className="recommendation-reasons-inline-list">
                                          {visibleItems.map((item) => (
                                            <li key={`${reasonKey}-visible-${item}`}>{item}</li>
                                          ))}
                                        </ul>
                                      </>
                                    ) : (
                                      <span>{cleanReason}</span>
                                    )}
                                    {canExpand && (
                                      <>
                                        {!isExpanded && (
                                          <button
                                            type="button"
                                            className="recommendation-reasons-more-button"
                                            aria-expanded={false}
                                            onClick={() => handleToggleReasonItems(reasonKey)}
                                          >
                                            {`+${hiddenItems.length} more`}
                                          </button>
                                        )}
                                        {isExpanded && (
                                          <>
                                            <ul className="recommendation-reasons-more-list">
                                              {hiddenItems.map((item) => (
                                                <li key={`${reasonKey}-${item}`}>{item}</li>
                                              ))}
                                            </ul>
                                            <button
                                              type="button"
                                              className="recommendation-reasons-more-button"
                                              aria-expanded
                                              onClick={() => handleToggleReasonItems(reasonKey)}
                                            >
                                              Hide
                                            </button>
                                          </>
                                        )}
                                      </>
                                    )}
                                  </li>
                                )
                              })}
                            </ul>
                          )}
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
