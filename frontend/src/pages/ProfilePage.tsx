import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchEntityDetail } from '../api/entityDetails'
import { fetchSearch } from '../api/search'
import { useApi } from '../hooks/useApi'
import { useGraphStore } from '../store/graphStore'
import type { EntityDetail } from '../types/entityDetail'
import { graphEntityId, type GraphNode, type NodeType } from '../types/graph'
import type { PromoterRecommendationResponse } from '../types/recommendation'
import type { SearchResponse, SearchResult } from '../types/search'
import { DetailsPanel } from './components/DetailsPanel.tsx'
import { RecommendationLoading } from './components/LoadingScreen.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { SearchQueryForm } from './components/SearchQuery.tsx'
import { useDebouncedValue } from './hooks/useDebouncedValue'

const PROMOTER_RECOMMENDATIONS_API_BASE_URL = 'http://localhost:8080/api/recommendations/artists/2178/promoters'
const RECOMMENDATION_LOADING_MESSAGES = [
  'Finding similar artists',
  'Comparing related events',
  'Building promoter graph',
]
const DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD = 0.25
const DEFAULT_VISIBLE_PROMOTERS_ON_LOAD = 3
type RecommendationGraphMode = 'compact' | 'full'

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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

// Remove empty entries and duplicates while preserving display order.
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

// Detect which reason group a line belongs to so we can map it to details arrays.
function detectReasonListKind(reason: string): ReasonListKind | null {
  if (reason.includes('related promoter events:')) return 'relatedEvents'
  if (reason.includes('similar promoter events:')) return 'similarEvents'
  if (reason.includes('similar artists connected:')) return 'similarArtists'
  if (reason.includes('co-played artists connected:')) return 'coPlayedArtists'
  if (reason.includes('manually added trusted artist links:')) return 'manualArtists'
  return null
}

// Resolve the full item list for a reason using main contract data (or debug fallback).
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

// Return only hidden list items represented by the trailing "+N more" suffix.
function hiddenReasonItems(recommendation: PromoterRecommendationResponse['recommendations'][number], reason: string): string[] {
  const moreMatch = reason.match(/\+(\d+)\s+more/i)
  if (!moreMatch) return []
  const hiddenCount = Number.parseInt(moreMatch[1] ?? '0', 10)
  if (!Number.isFinite(hiddenCount) || hiddenCount <= 0) return []
  const normalizedItems = reasonListItems(recommendation, reason)
  const hiddenStartIndex = Math.max(normalizedItems.length - hiddenCount, 0)
  return normalizedItems.slice(hiddenStartIndex)
}

// Read recommendation score in a tolerant way to support older/newer response shapes.
function recommendationScore(recommendation: PromoterRecommendationResponse['recommendations'][number]): number {
  const directScore = recommendation.score
  if (typeof directScore === 'number' && Number.isFinite(directScore)) {
    return Math.max(0, Math.min(1, directScore))
  }

  const debugTotal = recommendation.debug?.weightedScores?.total
  if (typeof debugTotal === 'number' && Number.isFinite(debugTotal)) {
    return Math.max(0, Math.min(1, debugTotal))
  }

  return 0
}

// Choose a high default threshold that keeps at least a few top promoters visible.
function initialStrengthThreshold(recommendations: PromoterRecommendationResponse['recommendations']): number {
  if (recommendations.length === 0) return DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD

  const sortedScores = recommendations
    .map((recommendation) => recommendationScore(recommendation))
    .sort((left, right) => right - left)

  const targetIndex = Math.min(DEFAULT_VISIBLE_PROMOTERS_ON_LOAD - 1, sortedScores.length - 1)
  const threshold = sortedScores[targetIndex] ?? DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD
  return Math.max(0, Math.min(1, threshold))
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
  const [recommendationGraphMode, setRecommendationGraphMode] = useState<RecommendationGraphMode>('compact')
  const [recommendationStrengthThreshold, setRecommendationStrengthThreshold] = useState(
    DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD,
  )
  const [expandedRecommendationId, setExpandedRecommendationId] = useState<number | null>(null)
  const [focusedRecommendationPromoterIds, setFocusedRecommendationPromoterIds] = useState<number[] | null>(null)
  const [expandedReasonItems, setExpandedReasonItems] = useState<Record<string, boolean>>({})
  const recommendationThresholdInitializedRef = useRef(false)
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

  useEffect(() => {
    if (!recommendationsData) {
      recommendationThresholdInitializedRef.current = false
      return
    }
    if (recommendationThresholdInitializedRef.current) return
    setRecommendationStrengthThreshold(initialStrengthThreshold(recommendationsData.recommendations))
    recommendationThresholdInitializedRef.current = true
  }, [recommendationsData])

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
    recommendationThresholdInitializedRef.current = false
    setIsRecommendationsLoading(true)
    setRecommendationsError(null)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setRecommendationGraphMode('compact')

    try {
      const requestUrl = new URL(PROMOTER_RECOMMENDATIONS_API_BASE_URL)
      requestUrl.searchParams.set('limit', '50')
      const response = await fetch(requestUrl.toString())

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
      setFocusedRecommendationPromoterIds([recommendationId])
    }
  }, [recommendationsData, setSelected])

  // Toggle recommendation card focus; collapsing clears selected promoter and resets graph focus.
  const handleToggleRecommendation = useCallback((recommendationId: number) => {
    const isCollapsingCurrent = expandedRecommendationId === recommendationId

    if (isCollapsingCurrent) {
      setExpandedRecommendationId(null)
      setFocusedRecommendationPromoterIds(null)
      setSelected(null)
      return
    }

    setExpandedRecommendationId(recommendationId)
    handleSelectRecommendation(recommendationId)
  }, [expandedRecommendationId, handleSelectRecommendation, setSelected])

  const handleToggleReasonItems = useCallback((key: string) => {
    setExpandedReasonItems((current) => ({ ...current, [key]: !current[key] }))
  }, [])

  const handleToggleRecommendationGraphMode = useCallback(() => {
    setRecommendationGraphMode((current) => (current === 'compact' ? 'full' : 'compact'))
  }, [])

  // Slider change resets focused promoter so graph returns to threshold-based baseline paths.
  const handleRecommendationStrengthChange = useCallback((nextThreshold: number) => {
    setRecommendationStrengthThreshold(nextThreshold)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setSelected(null)
  }, [setSelected])

  // Handle recommendation graph clicks: update details + list card, and focus the clicked promoter path(s).
  const handleRecommendationGraphNodeClick = useCallback((node: GraphNode, promoterNodeIds: string[] | null) => {
    setSelected(node)

    if (!promoterNodeIds || promoterNodeIds.length === 0) {
      setExpandedRecommendationId(null)
      setFocusedRecommendationPromoterIds(null)
      return
    }

    const promoterIds = promoterNodeIds
      .map((promoterNodeId) => graphEntityId(promoterNodeId, 'promoter'))
      .filter((promoterId): promoterId is number => promoterId !== null)

    if (promoterIds.length === 1) {
      setExpandedRecommendationId(promoterIds[0])
      setFocusedRecommendationPromoterIds(promoterIds)
      return
    }

    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(promoterIds)
  }, [setSelected])

  const handleRecommendationGraphPaneClick = useCallback(() => {
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setSelected(null)
  }, [setSelected])

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
  const sortedRecommendations = useMemo(() => {
    if (!recommendationsData) return []

    return [...recommendationsData.recommendations].sort((left, right) => {
      const scoreDelta = recommendationScore(right) - recommendationScore(left)
      if (Math.abs(scoreDelta) > 1e-9) return scoreDelta
      return left.name.localeCompare(right.name)
    })
  }, [recommendationsData])
  const recommendationScoreBounds = useMemo(() => {
    if (sortedRecommendations.length === 0) {
      return { min: 0, max: 1 }
    }

    const scores = sortedRecommendations.map((recommendation) => recommendationScore(recommendation))
    const min = Math.min(...scores)
    const max = Math.max(...scores)
    return {
      min,
      max,
    }
  }, [sortedRecommendations])

  useEffect(() => {
    setRecommendationStrengthThreshold((current) => {
      const bounded = clamp(current, recommendationScoreBounds.min, recommendationScoreBounds.max)
      return Math.abs(current - bounded) < 1e-9 ? current : bounded
    })
  }, [recommendationScoreBounds.max, recommendationScoreBounds.min])

  const recommendationStrengthStep = useMemo(() => {
    const range = recommendationScoreBounds.max - recommendationScoreBounds.min
    if (range <= 0) return 0.001
    return Math.max(range / 500, 0.0005)
  }, [recommendationScoreBounds.max, recommendationScoreBounds.min])

  const filteredRecommendations = useMemo(
    () => sortedRecommendations.filter((recommendation) => (
      recommendationScore(recommendation) >= recommendationStrengthThreshold
    )),
    [recommendationStrengthThreshold, sortedRecommendations],
  )
  const filteredRecommendationPromoterNodeIds = useMemo(
    () => filteredRecommendations.map((recommendation) => `promoter-${recommendation.id}`),
    [filteredRecommendations],
  )
  const currentRecommendationGraph = useMemo(
    () => {
      if (!recommendationsData) return null
      return recommendationGraphMode === 'full'
        ? (recommendationsData.analyticsGraph ?? recommendationsData.graph)
        : recommendationsData.graph
    },
    [recommendationGraphMode, recommendationsData],
  )
  useEffect(() => {
    if (expandedRecommendationId === null) return
    const isStillVisible = filteredRecommendations.some((recommendation) => (
      recommendation.id === expandedRecommendationId
    ))
    if (!isStillVisible) {
      setExpandedRecommendationId(null)
      setFocusedRecommendationPromoterIds(null)
    }
  }, [expandedRecommendationId, filteredRecommendations])

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
                    <div className="recommendation-threshold-control" aria-label="Recommendation strength control">
                      <label htmlFor="recommendation-strength-threshold">
                        Strength: {Math.round(recommendationStrengthThreshold * 100)}%
                      </label>
                      <input
                        id="recommendation-strength-threshold"
                        type="range"
                        min={recommendationScoreBounds.min}
                        max={recommendationScoreBounds.max}
                        step={recommendationStrengthStep}
                        value={recommendationStrengthThreshold}
                        onChange={(event) => handleRecommendationStrengthChange(Number(event.target.value))}
                      />
                      <p>{filteredRecommendations.length} / {sortedRecommendations.length} promoters shown</p>
                    </div>
                    <section className="recommendation-list" aria-label="Recommended promoters">
                      {filteredRecommendations.length === 0 && (
                        <p className="recommendation-list-empty">
                          No promoters at this threshold. Lower the slider to include more matches.
                        </p>
                      )}
                      {filteredRecommendations.map((recommendation) => (
                        <article
                          className="recommendation-item"
                          key={recommendation.id}
                          id={`recommendation-card-${recommendation.id}`}
                        >
                          <button
                            type="button"
                            className="recommendation-name"
                            aria-pressed={focusedRecommendationPromoterIds?.includes(recommendation.id) ?? false}
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
                      <div className="panel-heading">
                        <span className="search-query-label">
                          {recommendationGraphMode === 'compact' ? 'Artist-only path' : 'Full analytics graph'}
                        </span>
                        <button
                          type="button"
                          onClick={handleToggleRecommendationGraphMode}
                          disabled={isRecommendationsLoading}
                        >
                          {recommendationGraphMode === 'compact'
                            ? 'Show analytics graph'
                            : 'Show compact path'}
                        </button>
                      </div>
                      {currentRecommendationGraph && (
                        <ScenegraphMapPanel
                          key={recommendationGraphMode}
                          providedData={currentRecommendationGraph}
                          showFilters={false}
                          showNodeTypeFilter={false}
                          highlightPathToNodeId={`artist-${recommendationsData.entityId}`}
                          visibleRecommendationPromoterNodeIds={filteredRecommendationPromoterNodeIds}
                          focusedRecommendationPromoterNodeIds={focusedRecommendationPromoterIds?.map((promoterId) => `promoter-${promoterId}`) ?? null}
                          onRecommendationGraphNodeClick={handleRecommendationGraphNodeClick}
                          onRecommendationGraphPaneClick={handleRecommendationGraphPaneClick}
                        />
                      )}
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
