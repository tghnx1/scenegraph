import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { graphEntityId, type GraphNode } from '../../types/graph'
import type { PromoterRecommendationResponse } from '../../types/recommendation'
import { RecommendationLoading } from './LoadingScreen'
import { ScenegraphMapPanel } from './GraphPanel'
import { RecommendationExportMenu } from './ExportRecommendation'

const DEFAULT_PROFILE_RECOMMENDATION_ARTIST_ID = 2178
const PROMOTER_RECOMMENDATIONS_API_PATH = '/api/recommendations/artists'
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

export interface RecommendationTargetControls {
  artistId: number | null
  controls: ReactNode
  emptyMessage: string
  getButtonLabel?: string
}

interface PromoterRecommendationsPanelProps {
  isActive: boolean
  targetControls?: RecommendationTargetControls
  onSelectNode: (node: GraphNode | null) => void
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

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

function initialStrengthThreshold(recommendations: PromoterRecommendationResponse['recommendations']): number {
  if (recommendations.length === 0) return DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD

  const sortedScores = recommendations
    .map((recommendation) => recommendationScore(recommendation))
    .sort((left, right) => right - left)

  const targetIndex = Math.min(DEFAULT_VISIBLE_PROMOTERS_ON_LOAD - 1, sortedScores.length - 1)
  const threshold = sortedScores[targetIndex] ?? DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD
  return Math.max(0, Math.min(1, threshold))
}

export function PromoterRecommendationsPanel({
  isActive,
  targetControls,
  onSelectNode,
}: PromoterRecommendationsPanelProps) {
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
  const recommendationListRef = useRef<HTMLElement | null>(null)
  const recommendationRequestIdRef = useRef(0)
  const recommendationArtistId = targetControls
    ? targetControls.artistId
    : DEFAULT_PROFILE_RECOMMENDATION_ARTIST_ID

  useEffect(() => {
    recommendationRequestIdRef.current += 1
    setRecommendationsData(null)
    setRecommendationsError(null)
    setIsRecommendationsLoading(false)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setRecommendationGraphMode('compact')
    recommendationThresholdInitializedRef.current = false
  }, [recommendationArtistId])

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

  const handleLoadRecommendations = useCallback(async () => {
    if (recommendationArtistId === null) {
      setRecommendationsError(targetControls?.emptyMessage ?? 'Select an artist to load recommendations.')
      return
    }

    recommendationThresholdInitializedRef.current = false
    const requestId = recommendationRequestIdRef.current + 1
    recommendationRequestIdRef.current = requestId
    setIsRecommendationsLoading(true)
    setRecommendationsError(null)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setRecommendationGraphMode('compact')

    try {
      const requestUrl = new URL(
        `${PROMOTER_RECOMMENDATIONS_API_PATH}/${recommendationArtistId}/promoters`,
        window.location.origin,
      )
      requestUrl.searchParams.set('limit', '50')
      const response = await fetch(requestUrl.toString())

      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }

      const recommendationResponse = await response.json() as PromoterRecommendationResponse
      if (recommendationRequestIdRef.current !== requestId) return
      setRecommendationsData(recommendationResponse)
    } catch (error) {
      if (recommendationRequestIdRef.current !== requestId) return
      setRecommendationsData(null)
      setRecommendationsError(error instanceof Error ? error.message : 'Failed to load recommendations')
    } finally {
      if (recommendationRequestIdRef.current === requestId) {
        setIsRecommendationsLoading(false)
      }
    }
  }, [recommendationArtistId, targetControls?.emptyMessage])

  const handleSelectRecommendation = useCallback((recommendationId: number) => {
    const recommendationNode = recommendationsData?.graph.nodes.find((node) => (
      node.type === 'promoter' && node.entityId === recommendationId
    ))

    if (recommendationNode) {
      onSelectNode(recommendationNode)
      setFocusedRecommendationPromoterIds([recommendationId])
    }
  }, [onSelectNode, recommendationsData])

  const handleToggleRecommendation = useCallback((recommendationId: number) => {
    const isCollapsingCurrent = expandedRecommendationId === recommendationId

    if (isCollapsingCurrent) {
      setExpandedRecommendationId(null)
      setFocusedRecommendationPromoterIds(null)
      onSelectNode(null)
      return
    }

    setExpandedRecommendationId(recommendationId)
    handleSelectRecommendation(recommendationId)
  }, [expandedRecommendationId, handleSelectRecommendation, onSelectNode])

  const handleToggleReasonItems = useCallback((key: string) => {
    setExpandedReasonItems((current) => ({ ...current, [key]: !current[key] }))
  }, [])

  const handleToggleRecommendationGraphMode = useCallback(() => {
    setRecommendationGraphMode((current) => (current === 'compact' ? 'full' : 'compact'))
  }, [])

  const handleRecommendationStrengthChange = useCallback((nextThreshold: number) => {
    setRecommendationStrengthThreshold(nextThreshold)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    onSelectNode(null)
  }, [onSelectNode])

  const handleRecommendationGraphNodeClick = useCallback((node: GraphNode, promoterNodeIds: string[] | null) => {
    onSelectNode(node)

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
  }, [onSelectNode])

  const handleRecommendationGraphPaneClick = useCallback(() => {
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    onSelectNode(null)
  }, [onSelectNode])

  useEffect(() => {
    if (expandedRecommendationId === null) return
    const list = recommendationListRef.current
    const card = document.getElementById(`recommendation-card-${expandedRecommendationId}`)
    const header = card?.querySelector<HTMLElement>('.recommendation-name')
    if (!list || !card || !header) return

    const animationFrame = window.requestAnimationFrame(() => {
      const listRect = list.getBoundingClientRect()
      const headerRect = header.getBoundingClientRect()
      const nextScrollTop = Math.max(list.scrollTop + (headerRect.top - listRect.top) - 12, 0)
      list.scrollTo({ top: nextScrollTop, behavior: 'smooth' })
    })

    return () => window.cancelAnimationFrame(animationFrame)
  }, [expandedRecommendationId])

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
    return {
      min: Math.min(...scores),
      max: Math.max(...scores),
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
    <section
      id="profile-workspace-panel-recommendations"
      className="profile-workspace-content recommendations-panel"
      role="tabpanel"
      aria-labelledby="profile-workspace-tab-recommendations"
      hidden={!isActive}
    >
      <div className="panel-heading recommendations-panel-heading">
        <span className="search-query-label">Promoter Recommendations</span>
        {targetControls && (
          <div className="recommendation-target-actions">
            {targetControls.controls}
            <button
              type="button"
              onClick={() => void handleLoadRecommendations()}
              disabled={isRecommendationsLoading || recommendationArtistId === null}
            >
              {targetControls.getButtonLabel ?? 'Get rec'}
            </button>
          </div>
        )}
      </div>
      {recommendationsData === null && !isRecommendationsLoading && (
        <div className="recommendations-start">
          <p className={recommendationsError ? 'error' : 'recommendations-help'}>
            {recommendationsError
              ?? (targetControls?.emptyMessage
                ?? 'Click "Get Rec" to load recommendations. Loading time may be quite long. Let the wizard does its magic.')}
          </p>
          {!targetControls && (
            <button
              type="button"
              className="recommendations-load-button"
              onClick={() => void handleLoadRecommendations()}
            >
              {recommendationsError ? 'Retry' : 'Get Rec'}
            </button>
          )}
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
          <section
            ref={recommendationListRef}
            className="recommendation-list"
            aria-label="Recommended promoters"
          >
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
                  <span className={`recommendation-size-badge recommendation-size-${recommendation.promoterSizeSegment}`}>
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
              <div className="panel-heading-actions">
                <RecommendationExportMenu
                  recommendationsData={recommendationsData}
                  filteredRecommendations={filteredRecommendations}
                  recommendationStrengthThreshold={recommendationStrengthThreshold}
                  recommendationGraphMode={recommendationGraphMode}
                />
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
  )
}
