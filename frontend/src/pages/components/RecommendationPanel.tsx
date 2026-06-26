import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import { api } from '@/api/client'
import {
  deletePromoterFeedback,
  getPromoterFeedback,
  setPromoterFeedback,
  type PromoterFeedbackValue,
} from '@/api/recommendationFeedback'
import { graphEntityId, type GraphNode } from '../../types/graph'
import type { PromoterRecommendationResponse } from '../../types/recommendation'
import { RecommendationLoading } from './LoadingScreen'
import { ScenegraphMapPanel } from './GraphPanel'
import { RecommendationExportMenu } from './ExportRecommendation'

const PROMOTER_RECOMMENDATIONS_API_PATH = '/recommendations/artists'
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

const labelClass = 'text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]'
const panelHeadingClass = 'flex items-center justify-between gap-3 max-[900px]:flex-wrap'
const mutedTextClass = 'text-sm text-[var(--text-muted)]'

type ReasonListKind =
  | 'sharedExtractedGenres'
  | 'sharedThemes'
  | 'sharedMoods'
  | 'similarArtists'
  | 'coPlayedArtists'
  | 'manualArtists'

type SharedGenreSource = {
  eventId: number
  raEventId?: string | null
  title: string
  eventDate?: string | null
  sourceType: 'event_genres' | 'event_extracted_tags'
}

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
  artistId: number | null
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
  if (reason.includes('shared extracted genres:')) return 'sharedExtractedGenres'
  if (reason.includes('shared themes:')) return 'sharedThemes'
  if (reason.includes('shared moods:')) return 'sharedMoods'
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

  if (kind === 'sharedExtractedGenres') {
    items = recommendation.reasonDetails?.sharedExtractedGenres ?? rawSignals?.sharedExtractedGenres ?? []
  } else if (kind === 'sharedThemes') {
    items = recommendation.reasonDetails?.sharedThemes ?? rawSignals?.sharedThemes ?? []
  } else if (kind === 'sharedMoods') {
    items = recommendation.reasonDetails?.sharedMoods ?? rawSignals?.sharedMoods ?? []
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

function sharedGenreSourceGroups(
  recommendation: PromoterRecommendationResponse['recommendations'][number],
): Array<{ genre: string; sources: SharedGenreSource[] }> {
  const sourceMap = recommendation.reasonDetails?.sharedExtractedGenreSources ?? {}
  return Object.entries(sourceMap)
    .map(([genre, sources]) => ({
      genre,
      sources: Array.isArray(sources)
        ? sources.filter((source): source is SharedGenreSource => Boolean(source && source.title))
        : [],
    }))
    .filter((entry) => entry.sources.length > 0)
    .sort((left, right) => left.genre.localeCompare(right.genre))
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
  artistId,
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
  const [pendingFeedbackPromoterId, setPendingFeedbackPromoterId] = useState<number | null>(null)
  const [localFeedbackByPromoterId, setLocalFeedbackByPromoterId] = useState<
    Record<number, PromoterFeedbackValue | null>
  >({})
  const [localFeedbackIdByPromoterId, setLocalFeedbackIdByPromoterId] = useState<Record<number, number>>({})
  const recommendationThresholdInitializedRef = useRef(false)
  const recommendationListRef = useRef<HTMLElement | null>(null)
  const recommendationRequestIdRef = useRef(0)
  const recommendationArtistId = targetControls
    ? targetControls.artistId
    : artistId

  useEffect(() => {
    recommendationRequestIdRef.current += 1
    setRecommendationsData(null)
    setRecommendationsError(null)
    setIsRecommendationsLoading(false)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setPendingFeedbackPromoterId(null)
    setLocalFeedbackByPromoterId({})
    setLocalFeedbackIdByPromoterId({})
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
      setRecommendationsError(targetControls?.emptyMessage ?? 'Claiming an artist is required to load recommendations.')
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
      const recommendationResponse = await api.get<PromoterRecommendationResponse>(
        `${PROMOTER_RECOMMENDATIONS_API_PATH}/${recommendationArtistId}/promoters?limit=50`,
      )
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

  const handleResetRecommendations = useCallback(() => {
    recommendationRequestIdRef.current += 1
    recommendationThresholdInitializedRef.current = false
    setRecommendationsData(null)
    setRecommendationsError(null)
    setIsRecommendationsLoading(false)
    setRecommendationStrengthThreshold(DEFAULT_RECOMMENDATION_STRENGTH_THRESHOLD)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setPendingFeedbackPromoterId(null)
    setLocalFeedbackByPromoterId({})
    setLocalFeedbackIdByPromoterId({})
    setRecommendationGraphMode('compact')
    onSelectNode(null)
  }, [onSelectNode])

  const handlePromoterFeedback = useCallback(async (
    promoterId: number,
    feedback: PromoterFeedbackValue,
  ) => {
    if (recommendationArtistId === null) {
      setRecommendationsError(targetControls?.emptyMessage ?? 'Claiming an artist is required to load recommendations.')
      return
    }

    setPendingFeedbackPromoterId(promoterId)
    setRecommendationsError(null)

    const hasLocalFeedback = Object.prototype.hasOwnProperty.call(localFeedbackByPromoterId, promoterId)
    const previousFeedback = hasLocalFeedback
      ? localFeedbackByPromoterId[promoterId]
      : recommendationsData?.recommendations.find((item) => item.id === promoterId)?.feedbackState
    const isRemovingFeedback = previousFeedback === feedback

    setLocalFeedbackByPromoterId((current) => ({
      ...current,
      [promoterId]: isRemovingFeedback ? null : feedback,
    }))

    try {
      if (isRemovingFeedback) {
        let feedbackId = localFeedbackIdByPromoterId[promoterId]
        if (!feedbackId) {
          const response = await getPromoterFeedback(recommendationArtistId, promoterId)
          feedbackId = response.feedback[0]?.id
        }
        if (feedbackId) {
          await deletePromoterFeedback(feedbackId)
        }
        setLocalFeedbackIdByPromoterId((current) => {
          const next = { ...current }
          delete next[promoterId]
          return next
        })
      } else {
        const savedFeedback = await setPromoterFeedback(recommendationArtistId, promoterId, feedback)
        setLocalFeedbackIdByPromoterId((current) => ({
          ...current,
          [promoterId]: savedFeedback.id,
        }))
      }
    } catch (error) {
      setLocalFeedbackByPromoterId((current) => ({ ...current, [promoterId]: previousFeedback ?? null }))
      setRecommendationsError(error instanceof Error ? error.message : 'Failed to save feedback')
    } finally {
      setPendingFeedbackPromoterId(null)
    }
  }, [localFeedbackByPromoterId, localFeedbackIdByPromoterId, recommendationArtistId, recommendationsData, targetControls?.emptyMessage])

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

  const effectiveFeedbackForPromoter = useCallback((promoterId: number) => (
    Object.prototype.hasOwnProperty.call(localFeedbackByPromoterId, promoterId)
      ? localFeedbackByPromoterId[promoterId]
      : recommendationsData?.recommendations.find((item) => item.id === promoterId)?.feedbackState ?? null
  ), [localFeedbackByPromoterId, recommendationsData])

  useEffect(() => {
    if (expandedRecommendationId === null) return
    const list = recommendationListRef.current
    const card = document.getElementById(`recommendation-card-${expandedRecommendationId}`)
    const header = card?.querySelector<HTMLElement>('[data-recommendation-name]')
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
      className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] gap-4"
      role="tabpanel"
      aria-labelledby="profile-workspace-tab-recommendations"
      hidden={!isActive}
    >
      <div className={panelHeadingClass}>
        <span className={labelClass}>Promoter Recommendations</span>
        {(targetControls || recommendationsData) && (
          <div className="flex min-w-0 flex-nowrap items-center justify-end gap-2 max-[900px]:w-full max-[900px]:flex-wrap">
            {targetControls?.controls}
            <Button
              type="button"
              size="sm"
              className="shrink-0"
              onClick={() => {
                if (recommendationsData) {
                  handleResetRecommendations()
                } else {
                  void handleLoadRecommendations()
                }
              }}
              disabled={isRecommendationsLoading || recommendationArtistId === null}
            >
              {recommendationsData ? 'Reset' : (targetControls?.getButtonLabel ?? 'Get rec')}
            </Button>
          </div>
        )}
      </div>
      {recommendationsData === null && !isRecommendationsLoading && (
        <div className="grid min-h-0 place-items-center gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-6 text-center">
          <p className={recommendationsError ? 'm-0 text-[var(--event)]' : cn('m-0', mutedTextClass)}>
            {recommendationsError
              ?? (targetControls?.emptyMessage
                ?? (recommendationArtistId === null
                  ? 'Claiming an artist is required to load recommendations.'
                  : 'Click "Get Rec" to load recommendations. Loading time may be quite long. Let the wizard does its magic.'))}
          </p>
          {!targetControls && (
            <Button
              type="button"
              onClick={() => void handleLoadRecommendations()}
            >
              {recommendationsError ? 'Retry' : 'Get Rec'}
            </Button>
          )}
        </div>
      )}
      {isRecommendationsLoading && (
        <RecommendationLoading activity={RECOMMENDATION_LOADING_MESSAGES[recommendationLoadingMessageIndex]} />
      )}
      {recommendationsData !== null && (
        <div className="grid min-h-0 min-w-0 grid-cols-[minmax(220px,0.72fr)_minmax(0,1.28fr)] gap-3 overflow-hidden max-[1180px]:grid-cols-1">
          <div className="col-span-full grid grid-cols-[auto_minmax(160px,1fr)_auto] items-center gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 text-sm text-[var(--text-muted)] max-[700px]:grid-cols-1" aria-label="Recommendation strength control">
            <label className="font-semibold text-[var(--text)]" htmlFor="recommendation-strength-threshold">
              Strength: {Math.round(recommendationStrengthThreshold * 100)}%
            </label>
            <input
              className="h-2 w-full accent-[var(--selection)]"
              id="recommendation-strength-threshold"
              type="range"
              min={recommendationScoreBounds.min}
              max={recommendationScoreBounds.max}
              step={recommendationStrengthStep}
              value={recommendationStrengthThreshold}
              onChange={(event) => handleRecommendationStrengthChange(Number(event.target.value))}
            />
            <p className="m-0">{filteredRecommendations.length} / {sortedRecommendations.length} promoters shown</p>
          </div>
          <section
            ref={recommendationListRef}
            className="grid min-h-0 min-w-0 content-start gap-2 overflow-y-auto overflow-x-hidden pr-1"
            aria-label="Recommended promoters"
          >
            {filteredRecommendations.length === 0 && (
              <p className="m-0 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4 text-sm text-[var(--text-muted)]">
                No promoters at this threshold. Lower the slider to include more matches.
              </p>
            )}
            {filteredRecommendations.map((recommendation) => (
              <article
                className="min-w-0 rounded-2xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_38%,transparent)] p-2 backdrop-blur-sm"
                key={recommendation.id}
                id={`recommendation-card-${recommendation.id}`}
              >
                <button
                  type="button"
                  data-recommendation-name
                  className="flex w-full min-w-0 cursor-pointer flex-wrap items-center justify-between gap-2 rounded-xl border border-transparent bg-transparent p-2 text-left text-[var(--text)] transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]"
                  aria-pressed={focusedRecommendationPromoterIds?.includes(recommendation.id) ?? false}
                  aria-expanded={expandedRecommendationId === recommendation.id}
                  aria-controls={`recommendation-reasons-${recommendation.id}`}
                  onClick={() => handleToggleRecommendation(recommendation.id)}
                >
                  <span className="min-w-0 flex-1 overflow-hidden text-sm font-semibold leading-snug [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">{recommendation.name}</span>
                  <span className={cn(
                    'shrink-0 rounded-full border px-2 py-0.5 text-[0.68rem] font-semibold',
                    recommendation.promoterSizeSegment === 'small' && 'border-[var(--promoter-border)] bg-[var(--promoter-soft)]',
                    recommendation.promoterSizeSegment === 'medium' && 'border-[var(--info-border)] bg-[var(--info-soft)]',
                    recommendation.promoterSizeSegment === 'large' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]',
                  )}>
                    {PROMOTER_SIZE_LABELS[recommendation.promoterSizeSegment]}
                  </span>
                </button>
                <div className="flex flex-wrap gap-2 px-3 pb-2" aria-label={`Feedback for ${recommendation.name}`}>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className={cn(
                      'min-w-[7.5rem]',
                      effectiveFeedbackForPromoter(recommendation.id) === 'positive'
                        ? 'border-[var(--selection-border)] bg-[var(--selection-soft)]'
                        : '',
                    )}
                    aria-pressed={effectiveFeedbackForPromoter(recommendation.id) === 'positive'}
                    disabled={pendingFeedbackPromoterId === recommendation.id}
                    onClick={() => void handlePromoterFeedback(recommendation.id, 'positive')}
                  >
                    Interested
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className={cn(
                      'min-w-[7.5rem]',
                      effectiveFeedbackForPromoter(recommendation.id) === 'negative'
                        ? 'border-[color-mix(in_srgb,var(--event)_50%,transparent)] bg-[color-mix(in_srgb,var(--event)_12%,transparent)]'
                        : '',
                    )}
                    aria-pressed={effectiveFeedbackForPromoter(recommendation.id) === 'negative'}
                    disabled={pendingFeedbackPromoterId === recommendation.id}
                    onClick={() => void handlePromoterFeedback(recommendation.id, 'negative')}
                  >
                    Not relevant
                  </Button>
                </div>
                {expandedRecommendationId === recommendation.id && (
                  <>
                    <ul
                      id={`recommendation-reasons-${recommendation.id}`}
                      className="m-0 mt-2 grid min-w-0 gap-2 pl-4 text-sm text-[var(--text-muted)]"
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
                          <li className="min-w-0 overflow-hidden" key={reasonKey}>
                            {(allItems.length > 0 && prefixMatch) ? (
                              <>
                                <span className="break-words">{reasonPrefix}</span>
                                <ul className="mt-1 flex flex-wrap gap-1.5 p-0">
                                  {visibleItems.map((item) => (
                                    <li className="list-none rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2 py-0.5 text-xs" key={`${reasonKey}-visible-${item}`}>{item}</li>
                                  ))}
                                </ul>
                              </>
                            ) : (
                              <span className="break-words">{cleanReason}</span>
                            )}
                            {canExpand && (
                              <>
                                {!isExpanded && (
                                  <button
                                    type="button"
                                    className="ml-2 cursor-pointer rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2 py-0.5 text-xs font-semibold text-[var(--text)]"
                                    aria-expanded={false}
                                    onClick={() => handleToggleReasonItems(reasonKey)}
                                  >
                                    {`+${hiddenItems.length} more`}
                                  </button>
                                )}
                                {isExpanded && (
                                  <>
                                    <ul className="mt-1 flex flex-wrap gap-1.5 p-0">
                                      {hiddenItems.map((item) => (
                                        <li className="list-none rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2 py-0.5 text-xs" key={`${reasonKey}-${item}`}>{item}</li>
                                      ))}
                                    </ul>
                                    <button
                                      type="button"
                                      className="mt-1 cursor-pointer rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2 py-0.5 text-xs font-semibold text-[var(--text)]"
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
                    {sharedGenreSourceGroups(recommendation).length > 0 && (
                      <div className="mt-3 grid min-w-0 gap-2">
                        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                          Genre sources
                        </span>
                        {sharedGenreSourceGroups(recommendation).map(({ genre, sources }) => (
                          <div className="grid min-w-0 gap-1" key={`${recommendation.id}-${genre}`}>
                            <span className="text-sm font-semibold text-[var(--text)]">{genre}</span>
                            <ul className="m-0 flex flex-wrap gap-1.5 p-0">
                              {sources.map((source) => (
                                <li
                                  className="list-none rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2 py-0.5 text-xs text-[var(--text-muted)]"
                                  key={`${recommendation.id}-${genre}-${source.eventId}-${source.sourceType}`}
                                  title={[
                                    source.sourceType,
                                    source.eventDate ? `event ${source.eventDate}` : null,
                                    source.raEventId ? `RA ${source.raEventId}` : null,
                                  ].filter(Boolean).join(' • ')}
                                >
                                  {source.title}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </article>
            ))}
          </section>
          <section className="grid min-h-[420px] min-w-0 overflow-hidden grid-rows-[auto_minmax(0,1fr)] gap-3" aria-label="Recommendation evidence graph">
            <div className={panelHeadingClass}>
              <span className={labelClass}>
                {recommendationGraphMode === 'compact' ? 'Artist-only path' : 'Full analytics graph'}
              </span>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <RecommendationExportMenu
                  recommendationsData={recommendationsData}
                  filteredRecommendations={filteredRecommendations}
                  recommendationStrengthThreshold={recommendationStrengthThreshold}
                  recommendationGraphMode={recommendationGraphMode}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleToggleRecommendationGraphMode}
                  disabled={isRecommendationsLoading}
                >
                  {recommendationGraphMode === 'compact'
                    ? 'Show analytics graph'
                    : 'Show compact path'}
                </Button>
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
