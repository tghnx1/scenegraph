import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Check, ChevronRight, Circle } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import { api } from '@/api/client'
import { fetchEntityDetail } from '@/api/entityDetails'
import { useApi } from '@/api/useApi'
import {
  deletePromoterFeedback,
  getPromoterFeedback,
  setPromoterFeedback,
  type PromoterFeedbackValue,
} from '@/api/recommendationFeedback'
import { graphEntityId, type GraphNode } from '../../types/graph'
import type { EntityDetail } from '../../types/entityDetail'
import type {
  PromoterRecommendationResponse,
  RecommendationJobCreatedResponse,
  RecommendationJobResponse,
} from '../../types/recommendation'
import { useRecommendationJobUpdates } from '../hooks/useRecommendationJobUpdates'
import { RecommendationLoading } from './LoadingScreen'
import { ScenegraphMapPanel } from './GraphPanel'
import { RecommendationExportMenu } from './ExportRecommendation'
import { RecommendationDetailsInspector } from './RecommendationDetailsInspector'
import {
  isArtistProfileReady,
  type ArtistProfileReadiness,
} from '../profileReadiness'

const PROMOTER_RECOMMENDATIONS_API_PATH = '/recommendations/artists'
const RECOMMENDATION_LOADING_MESSAGES = [
  'Finding similar artists',
  'Comparing related events',
  'Building promoter graph',
]
const INITIAL_VISIBLE_PROMOTERS = 20
const PROMOTER_PAGE_SIZE = 20

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
  artistName?: string | null
  controls: ReactNode
  emptyMessage: string
  getButtonLabel?: string
}

interface PromoterRecommendationsPanelProps {
  isActive: boolean
  artistId: number | null
  artistName?: string | null
  targetControls?: RecommendationTargetControls
  autoLoad?: boolean
  profileReadiness?: ArtistProfileReadiness
  onNavigateToSection?: (section: 'biography' | 'manual_artists') => void
  profileChangedSinceRecommendations?: boolean
  onRecommendationsSynced?: () => void
  emptyStateMessage?: string
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

function isProfileSetupRecommendationError(error: string | null): boolean {
  if (!error) return false
  const normalizedError = error.toLocaleLowerCase()
  return normalizedError.includes('embedding found for artist') || normalizedError.includes('no text-embedding')
}

function ProfileSetupStatusRow({
  label,
  isComplete,
  statusText,
  onClick,
}: {
  label: string
  isComplete: boolean
  statusText: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className="group grid w-full grid-cols-[auto_minmax(0,1fr)_auto_auto] items-center gap-3 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] px-3 py-2.5 text-left transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)] focus-visible:border-[var(--selection-border)] focus-visible:bg-[var(--selection-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-border)] focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
      aria-label={`${label}: ${statusText}`}
      onClick={onClick}
    >
      <span className={cn(
        'inline-flex size-7 items-center justify-center rounded-full border text-sm',
        isComplete
          ? 'border-[var(--selection-border)] bg-[var(--selection-soft)] text-[var(--text)]'
          : 'border-[var(--surface-border)] bg-[var(--surface-soft)] text-[var(--text-muted)]',
      )} aria-hidden="true">
        {isComplete ? <Check className="size-4" /> : <Circle className="size-4" />}
      </span>
      <span className="font-medium text-[var(--text)]">{label}</span>
      <span className="text-right text-sm text-[var(--text-muted)]">{statusText}</span>
      <ChevronRight className="size-4 text-[var(--text-muted)] transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden="true" />
    </button>
  )
}

type ProfileSetupSection = 'biography' | 'manual_artists'

function ProfileSetupCard({
  readiness,
  message,
  onNavigateToSection,
  footerAction,
}: {
  readiness: ArtistProfileReadiness
  message: string
  onNavigateToSection: (section: ProfileSetupSection) => void
  footerAction?: {
    label: string
    onClick: () => void
  }
}) {
  const biographyComplete = readiness.hasBiography === true
  const manualCount = Math.max(0, readiness.manualArtistCount)
  const requiredManualCount = Math.max(0, readiness.requiredManualArtistCount)
  const manualComplete = manualCount >= requiredManualCount
  const biographyStatusText = readiness.hasBiography === true
    ? 'Added'
    : readiness.hasBiography === false
      ? 'Missing'
      : 'Unknown'

  return (
    <div className="grid w-full max-w-[36rem] gap-4 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-5 text-left shadow-[0_10px_24px_rgba(0,0,0,0.1)] max-[700px]:max-w-full">
      <div className="grid gap-2">
        <span className={labelClass}>Profile setup</span>
        <h3 className="m-0 text-xl font-semibold text-[var(--text)]">
          Complete your profile to generate recommendations
        </h3>
        <p className="m-0 text-sm leading-6 text-[var(--text-muted)]">
          {message}
        </p>
      </div>
      <div className="grid gap-2">
        <ProfileSetupStatusRow
          label="Biography"
          isComplete={biographyComplete}
          statusText={biographyStatusText}
          onClick={() => onNavigateToSection('biography')}
        />
        <ProfileSetupStatusRow
          label="Artists you know"
          isComplete={manualComplete}
          statusText={`${Math.min(manualCount, requiredManualCount)} of ${requiredManualCount} added`}
          onClick={() => onNavigateToSection('manual_artists')}
        />
      </div>
      {footerAction ? (
        <div className="pt-1">
          <Button type="button" className="w-fit" onClick={footerAction.onClick}>
            {footerAction.label}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function ProfileReadinessLoadingState() {
  return (
    <div className="grid min-h-[320px] place-items-center rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-6 text-center">
      <p className="m-0 text-sm font-medium text-[var(--text-muted)]">
        Checking your artist profile…
      </p>
    </div>
  )
}

function formatMatchCount(count: number): string {
  return `${count} match${count === 1 ? '' : 'es'}`
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

export function PromoterRecommendationsPanel({
  isActive,
  artistId,
  artistName,
  targetControls,
  autoLoad = false,
  profileReadiness,
  onNavigateToSection,
  profileChangedSinceRecommendations = false,
  onRecommendationsSynced,
  emptyStateMessage,
}: PromoterRecommendationsPanelProps) {
  const [recommendationsData, setRecommendationsData] = useState<PromoterRecommendationResponse | null>(null)
  const [activeRecommendationJobId, setActiveRecommendationJobId] = useState<string | null>(null)
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false)
  const [isRecommendationsRefreshing, setIsRecommendationsRefreshing] = useState(false)
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null)
  const [recommendationLoadingMessageIndex, setRecommendationLoadingMessageIndex] = useState(0)
  const [recommendationGraphMode, setRecommendationGraphMode] = useState<RecommendationGraphMode>('full')
  const [visiblePromoterCount, setVisiblePromoterCount] = useState(INITIAL_VISIBLE_PROMOTERS)
  const [expandedRecommendationId, setExpandedRecommendationId] = useState<number | null>(null)
  const [focusedRecommendationPromoterIds, setFocusedRecommendationPromoterIds] = useState<number[] | null>(null)
  const [expandedReasonItems, setExpandedReasonItems] = useState<Record<string, boolean>>({})
  const [pendingFeedbackPromoterId, setPendingFeedbackPromoterId] = useState<number | null>(null)
  const [localFeedbackByPromoterId, setLocalFeedbackByPromoterId] = useState<
    Record<number, PromoterFeedbackValue | null>
  >({})
  const [localFeedbackIdByPromoterId, setLocalFeedbackIdByPromoterId] = useState<Record<number, number>>({})
  const [selectedRecommendationNode, setSelectedRecommendationNode] = useState<GraphNode | null>(null)
  const recommendationListRef = useRef<HTMLElement | null>(null)
  const lastRecommendationFocusRef = useRef<HTMLElement | null>(null)
  const recommendationRequestIdRef = useRef(0)
  const activeRecommendationJobRef = useRef<{ jobId: string; requestId: number; isRefresh: boolean } | null>(null)
  const autoLoadTriggeredArtistIdRef = useRef<number | null>(null)
  const recommendationArtistId = targetControls
    ? targetControls.artistId
    : artistId
  const recommendationTargetName = (
    artistName
    ?? targetControls?.artistName
    ?? null
  )?.trim() || null
  const recommendationTargetLabel = recommendationTargetName
    ?? (recommendationArtistId !== null ? `artist #${recommendationArtistId}` : null)
  const recommendationHeaderLabel = recommendationTargetLabel
    ? `Promoter Recommendations for ${recommendationTargetLabel}`
    : 'Promoter Recommendations'
  const recommendationReadyMessage = 'Recommendations are ready to generate.'
  const recommendationPrimaryButtonLabel = targetControls?.getButtonLabel ?? 'Get recommendations'
  const shouldGateByProfileReadiness = autoLoad && profileReadiness !== undefined
  const profileSetupReady = isArtistProfileReady(profileReadiness)
  const isProfileSetupLoading = Boolean(profileReadiness?.isLoading)

  useEffect(() => {
    recommendationRequestIdRef.current += 1
    autoLoadTriggeredArtistIdRef.current = null
    setRecommendationsData(null)
    setActiveRecommendationJobId(null)
    activeRecommendationJobRef.current = null
    setRecommendationsError(null)
    setIsRecommendationsLoading(false)
    setIsRecommendationsRefreshing(false)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setPendingFeedbackPromoterId(null)
    setLocalFeedbackByPromoterId({})
    setLocalFeedbackIdByPromoterId({})
    setRecommendationGraphMode('full')
    setVisiblePromoterCount(INITIAL_VISIBLE_PROMOTERS)
    setSelectedRecommendationNode(null)
  }, [recommendationArtistId])

  useEffect(() => {
    if (!shouldGateByProfileReadiness) return
    if (profileReadiness === undefined) return
    if (profileReadiness.isLoading || !profileSetupReady) {
      autoLoadTriggeredArtistIdRef.current = null
    }
  }, [profileReadiness, profileSetupReady, shouldGateByProfileReadiness])

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
    setVisiblePromoterCount((current) => {
      const nextVisibleCount = recommendationsData
        ? Math.min(INITIAL_VISIBLE_PROMOTERS, recommendationsData.recommendations.length)
        : INITIAL_VISIBLE_PROMOTERS

      return current === nextVisibleCount ? current : nextVisibleCount
    })
  }, [recommendationsData])

  useEffect(() => {
    if (selectedRecommendationNode === null) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setSelectedRecommendationNode(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedRecommendationNode])

  useEffect(() => {
    if (selectedRecommendationNode !== null) return

    window.setTimeout(() => {
      const element = lastRecommendationFocusRef.current
      if (element instanceof HTMLElement && document.contains(element)) {
        element.focus({ preventScroll: true })
      }
      lastRecommendationFocusRef.current = null
    }, 0)
  }, [selectedRecommendationNode])

  const selectedRecommendationDetailPath = useMemo(() => (
    selectedRecommendationNode
      ? `${selectedRecommendationNode.type}-${selectedRecommendationNode.entityId}`
      : null
  ), [selectedRecommendationNode])

  const {
    data: selectedRecommendationEntityDetail,
    isLoading: isSelectedRecommendationEntityDetailLoading,
    error: selectedRecommendationEntityDetailError,
  } = useApi<EntityDetail | null>(
    () => (
      selectedRecommendationNode
        ? fetchEntityDetail(selectedRecommendationNode.type, String(selectedRecommendationNode.entityId))
        : Promise.resolve(null)
    ),
    [selectedRecommendationDetailPath],
  )

  // Read durable job state once after a WebSocket signal or reconnect.
  const refreshRecommendationJob = useCallback(async (jobId: string) => {
    const activeJob = activeRecommendationJobRef.current
    if (activeJob === null || activeJob.jobId !== jobId) return

    try {
      const job = await api.get<RecommendationJobResponse>(`/recommendations/jobs/${jobId}`)
      const currentJob = activeRecommendationJobRef.current
      if (currentJob === null || currentJob.jobId !== jobId || currentJob.requestId !== activeJob.requestId) return

      if (job.status === 'completed') {
        if (!job.result) throw new Error('Recommendation job completed without a result')
        setRecommendationsData(job.result)
        setRecommendationsError(null)
        setIsRecommendationsLoading(false)
        setIsRecommendationsRefreshing(false)
        setActiveRecommendationJobId(null)
        activeRecommendationJobRef.current = null
        onRecommendationsSynced?.()
      } else if (job.status === 'failed') {
        if (!activeJob.isRefresh) {
          setRecommendationsData(null)
        }
        setRecommendationsError(job.errorMessage ?? 'Recommendation job failed')
        setIsRecommendationsLoading(false)
        setIsRecommendationsRefreshing(false)
        setActiveRecommendationJobId(null)
        activeRecommendationJobRef.current = null
      }
    } catch (error) {
      const currentJob = activeRecommendationJobRef.current
      if (currentJob === null || currentJob.jobId !== jobId) return
      setRecommendationsError(error instanceof Error ? error.message : 'Failed to read recommendation job')
      setIsRecommendationsLoading(false)
      setIsRecommendationsRefreshing(false)
      setActiveRecommendationJobId(null)
      activeRecommendationJobRef.current = null
    }
  }, [onRecommendationsSynced])

  // Ignore status signals for stale jobs created by earlier UI requests.
  const handleRecommendationJobUpdate = useCallback((message: { jobId: string }) => {
    if (message.jobId === activeRecommendationJobRef.current?.jobId) {
      void refreshRecommendationJob(message.jobId)
    }
  }, [refreshRecommendationJob])

  // Recover a result that completed while the browser socket was disconnected.
  const handleRecommendationSocketConnected = useCallback(() => {
    const jobId = activeRecommendationJobRef.current?.jobId
    if (jobId) void refreshRecommendationJob(jobId)
  }, [refreshRecommendationJob])

  useRecommendationJobUpdates(
    activeRecommendationJobId !== null,
    handleRecommendationJobUpdate,
    handleRecommendationSocketConnected,
  )

  const createRecommendationJob = useCallback(async (refreshing: boolean) => {
    if (recommendationArtistId === null) {
      setRecommendationsError(
        targetControls?.emptyMessage
          ?? emptyStateMessage
          ?? 'Select an artist to load recommendations.',
      )
      return
    }

    const requestId = recommendationRequestIdRef.current + 1
    recommendationRequestIdRef.current = requestId
    setRecommendationsError(null)
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    setExpandedReasonItems({})
    setSelectedRecommendationNode(null)
    if (refreshing) {
      setIsRecommendationsRefreshing(true)
    } else {
      setIsRecommendationsLoading(true)
      setRecommendationsData(null)
      setRecommendationGraphMode('full')
    }

    try {
      const createdJob = await api.post<RecommendationJobCreatedResponse>(
        `${PROMOTER_RECOMMENDATIONS_API_PATH}/${recommendationArtistId}/promoters/jobs`,
        { limit: 50, debug: false },
      )
      if (recommendationRequestIdRef.current !== requestId) return
      activeRecommendationJobRef.current = { jobId: createdJob.jobId, requestId, isRefresh: refreshing }
      setActiveRecommendationJobId(createdJob.jobId)
      await refreshRecommendationJob(createdJob.jobId)
    } catch (error) {
      if (recommendationRequestIdRef.current !== requestId) return
      if (!refreshing) {
        setRecommendationsData(null)
      }
      setRecommendationsError(error instanceof Error ? error.message : 'Failed to load recommendations')
      setIsRecommendationsLoading(false)
      setIsRecommendationsRefreshing(false)
      setActiveRecommendationJobId(null)
      activeRecommendationJobRef.current = null
    }
  }, [emptyStateMessage, recommendationArtistId, refreshRecommendationJob, targetControls?.emptyMessage])

  const handleLoadRecommendations = useCallback(() => {
    void createRecommendationJob(false)
  }, [createRecommendationJob])

  const handleUpdateRecommendations = useCallback(() => {
    void createRecommendationJob(true)
  }, [createRecommendationJob])

  useEffect(() => {
    if (!autoLoad) return
    if (!isActive) return
    if (recommendationArtistId === null) return
    if (recommendationsData !== null || isRecommendationsLoading) return

    if (shouldGateByProfileReadiness) {
      if (isProfileSetupLoading) return
      if (!profileSetupReady) return
    }

    if (autoLoadTriggeredArtistIdRef.current === recommendationArtistId) return

    autoLoadTriggeredArtistIdRef.current = recommendationArtistId
    void handleLoadRecommendations()
  }, [
    autoLoad,
    handleLoadRecommendations,
    isActive,
    isProfileSetupLoading,
    isRecommendationsLoading,
    profileSetupReady,
    recommendationArtistId,
    recommendationsData,
    shouldGateByProfileReadiness,
  ])

  const isProfileSetupError = isProfileSetupRecommendationError(recommendationsError)

  const handlePromoterFeedback = useCallback(async (
    promoterId: number,
    feedback: PromoterFeedbackValue,
  ) => {
    if (recommendationArtistId === null) {
      setRecommendationsError(
        targetControls?.emptyMessage
          ?? emptyStateMessage
          ?? 'Select an artist to load recommendations.',
      )
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
  }, [emptyStateMessage, localFeedbackByPromoterId, localFeedbackIdByPromoterId, recommendationArtistId, recommendationsData, targetControls?.emptyMessage])

  const handleSelectRecommendationNode = useCallback((node: GraphNode | null) => {
    if (node) {
      const activeElement = document.activeElement
      lastRecommendationFocusRef.current = activeElement instanceof HTMLElement ? activeElement : null
    }
    setSelectedRecommendationNode(node)
  }, [])

  const handleSelectRecommendation = useCallback((recommendationId: number) => {
    const recommendationNode = recommendationsData?.graph.nodes.find((node) => (
      node.type === 'promoter' && node.entityId === recommendationId
    )) ?? {
      id: `promoter-${recommendationId}`,
      entityId: recommendationId,
      type: 'promoter',
      name: recommendationsData?.recommendations.find((recommendation) => recommendation.id === recommendationId)?.name ?? `Promoter ${recommendationId}`,
      genres: [],
    }

    handleSelectRecommendationNode(recommendationNode)
    setFocusedRecommendationPromoterIds([recommendationId])
  }, [handleSelectRecommendationNode, recommendationsData])

  const handleToggleRecommendation = useCallback((recommendationId: number) => {
    const isCollapsingCurrent = expandedRecommendationId === recommendationId

    if (isCollapsingCurrent) {
      setExpandedRecommendationId(null)
      setFocusedRecommendationPromoterIds(null)
      handleSelectRecommendationNode(null)
      return
    }

    setExpandedRecommendationId(recommendationId)
    handleSelectRecommendation(recommendationId)
  }, [expandedRecommendationId, handleSelectRecommendation, handleSelectRecommendationNode])

  const handleToggleReasonItems = useCallback((key: string) => {
    setExpandedReasonItems((current) => ({ ...current, [key]: !current[key] }))
  }, [])

  const handleToggleRecommendationGraphMode = useCallback(() => {
    setRecommendationGraphMode((current) => (current === 'compact' ? 'full' : 'compact'))
  }, [])

  const handleRecommendationGraphNodeClick = useCallback((node: GraphNode, promoterNodeIds: string[] | null) => {
    handleSelectRecommendationNode(node)

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
  }, [handleSelectRecommendationNode])

  const handleRecommendationGraphPaneClick = useCallback(() => {
    setExpandedRecommendationId(null)
    setFocusedRecommendationPromoterIds(null)
    handleSelectRecommendationNode(null)
  }, [handleSelectRecommendationNode])

  const effectiveFeedbackForPromoter = useCallback((promoterId: number) => (
    Object.prototype.hasOwnProperty.call(localFeedbackByPromoterId, promoterId)
      ? localFeedbackByPromoterId[promoterId]
      : recommendationsData?.recommendations.find((item) => item.id === promoterId)?.feedbackState ?? null
  ), [localFeedbackByPromoterId, recommendationsData])
  const sortedRecommendations = useMemo(() => {
    if (!recommendationsData) return []

    return [...recommendationsData.recommendations].sort((left, right) => {
      const scoreDelta = recommendationScore(right) - recommendationScore(left)
      if (Math.abs(scoreDelta) > 1e-9) return scoreDelta
      return left.name.localeCompare(right.name)
    })
  }, [recommendationsData])

  const displayedRecommendations = useMemo(
    () => sortedRecommendations.slice(0, visiblePromoterCount),
    [sortedRecommendations, visiblePromoterCount],
  )
  const displayedRecommendationPromoterNodeIds = useMemo(
    () => displayedRecommendations.map((recommendation) => `promoter-${recommendation.id}`),
    [displayedRecommendations],
  )
  const hasMoreRecommendations = visiblePromoterCount < sortedRecommendations.length

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
    const isStillVisible = sortedRecommendations.some((recommendation) => (
      recommendation.id === expandedRecommendationId
    ))
    if (!isStillVisible) {
      setExpandedRecommendationId(null)
      setFocusedRecommendationPromoterIds(null)
    }
  }, [expandedRecommendationId, sortedRecommendations])

  const handleShowMorePromoters = useCallback(() => {
    setVisiblePromoterCount((current) => Math.min(current + PROMOTER_PAGE_SIZE, sortedRecommendations.length))
  }, [sortedRecommendations.length])

  return (
    <section
      id="profile-workspace-panel-recommendations"
      className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] gap-4"
      role="tabpanel"
      aria-labelledby="profile-workspace-tab-recommendations"
      hidden={!isActive}
    >
      <div className={panelHeadingClass}>
        <span className={labelClass}>{recommendationHeaderLabel}</span>
        {targetControls?.controls && (
          <div className="flex min-w-0 flex-nowrap items-center justify-end gap-2 max-[900px]:w-full max-[900px]:flex-wrap">
            {targetControls.controls}
          </div>
        )}
      </div>

      {recommendationsData === null && !isRecommendationsLoading && !isRecommendationsRefreshing && (
        isProfileSetupLoading ? (
          <ProfileReadinessLoadingState />
        ) : profileReadiness !== undefined && !profileSetupReady ? (
          <div className="grid min-h-0 place-items-center rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-6">
            <ProfileSetupCard
              readiness={profileReadiness}
              message="Complete these steps and recommendations will start automatically."
              onNavigateToSection={onNavigateToSection ?? (() => {})}
            />
          </div>
        ) : profileReadiness !== undefined && profileSetupReady && isProfileSetupError ? (
          <div className="grid min-h-0 place-items-center rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-6">
            <ProfileSetupCard
              readiness={profileReadiness}
              message="Your profile was updated, but recommendations are not ready yet."
              onNavigateToSection={onNavigateToSection ?? (() => {})}
              footerAction={{
                label: 'Try again',
                onClick: () => void handleLoadRecommendations(),
              }}
            />
          </div>
        ) : (
          <div className="grid min-h-0 place-items-center gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-6 text-center">
            <p className={recommendationsError ? 'm-0 text-[var(--event)]' : cn('m-0', mutedTextClass)}>
              {recommendationsError
                ?? (targetControls?.emptyMessage
                  ?? (profileReadiness !== undefined && profileSetupReady
                    ? recommendationReadyMessage
                    : emptyStateMessage)
                  ?? (recommendationTargetLabel
                    ? `Click "${recommendationPrimaryButtonLabel}" to load recommendations for ${recommendationTargetLabel}. Loading time may be quite long. Let the wizard does its magic.`
                    : `Click "${recommendationPrimaryButtonLabel}" to load recommendations. Loading time may be quite long. Let the wizard does its magic.`))}
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <Button
                type="button"
                size="sm"
                onClick={() => void handleLoadRecommendations()}
                disabled={isRecommendationsLoading || isRecommendationsRefreshing || recommendationArtistId === null}
              >
                {recommendationsError ? 'Retry' : recommendationPrimaryButtonLabel}
              </Button>
            </div>
          </div>
        )
      )}

      {isRecommendationsLoading && (
        <RecommendationLoading activity={RECOMMENDATION_LOADING_MESSAGES[recommendationLoadingMessageIndex]} />
      )}

      {recommendationsData !== null && (
        <div className={cn(
          'grid min-h-0 min-w-0 gap-3 overflow-hidden',
          selectedRecommendationNode
            ? 'min-[1400px]:grid-cols-[minmax(240px,0.76fr)_minmax(0,1.24fr)_minmax(320px,0.9fr)] max-[1399px]:grid-cols-[minmax(240px,0.84fr)_minmax(0,1.16fr)] max-[980px]:grid-cols-1'
            : 'grid-cols-[minmax(240px,0.84fr)_minmax(0,1.16fr)] max-[980px]:grid-cols-1',
        )}>
          {recommendationsError && !isRecommendationsLoading && (
            <div className="col-span-full flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color-mix(in_srgb,var(--event)_30%,transparent)] bg-[color-mix(in_srgb,var(--event)_10%,transparent)] p-3 text-sm text-[var(--text)]">
              <p className="m-0">
                Couldn’t update recommendations. Your previous results are still shown.
              </p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleUpdateRecommendations}
                disabled={isRecommendationsRefreshing || recommendationArtistId === null}
              >
                Retry
              </Button>
            </div>
          )}

          {profileChangedSinceRecommendations && (
            <div className="col-span-full flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--info-border)] bg-[var(--info-soft)] p-3 text-sm text-[var(--text)]">
              <p className="m-0">
                Your profile changed. Update recommendations to use the latest information.
              </p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleUpdateRecommendations}
                disabled={isRecommendationsLoading || isRecommendationsRefreshing || recommendationArtistId === null}
              >
                Update recommendations
              </Button>
            </div>
          )}

          <section
            ref={recommendationListRef}
            className="grid min-h-0 min-w-0 content-start gap-3 overflow-y-auto overflow-x-hidden pr-1"
            aria-label="Recommended promoters"
          >
            <header className="grid gap-2 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="inline-flex size-5 shrink-0 rounded-[0.2rem] bg-[var(--promoter)] shadow-[0_0_0_1px_color-mix(in_srgb,var(--text)_10%,transparent)]"
                  />
                  <h3 className="m-0 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--text)]">
                    Recommended promoters
                  </h3>
                </div>
                <p className="m-0 shrink-0 text-sm font-medium text-[var(--text-muted)]">
                  {formatMatchCount(sortedRecommendations.length)}
                </p>
              </div>
              <p className="m-0 text-sm leading-6 text-[var(--text-muted)]">
                Promoters matched to your profile, network and scene activity.
              </p>
            </header>

            {sortedRecommendations.length === 0 && (
              <p className="m-0 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4 text-sm text-[var(--text-muted)]">
                No promoters matched this recommendation run.
              </p>
            )}

            {displayedRecommendations.map((recommendation) => (
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
                  <span
                    className={cn(
                      'shrink-0 rounded-full border px-2 py-0.5 text-[0.68rem] font-semibold',
                      recommendation.promoterSizeSegment === 'small' && 'border-[var(--promoter-border)] bg-[var(--promoter-soft)]',
                      recommendation.promoterSizeSegment === 'medium' && 'border-[var(--info-border)] bg-[var(--info-soft)]',
                      recommendation.promoterSizeSegment === 'large' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]',
                    )}
                    title={`Promoter size: ${PROMOTER_SIZE_LABELS[recommendation.promoterSizeSegment]}`}
                    aria-label={`Promoter size: ${PROMOTER_SIZE_LABELS[recommendation.promoterSizeSegment]}`}
                  >
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

            {hasMoreRecommendations && (
              <div className="flex justify-center pt-1">
                <Button type="button" variant="outline" onClick={handleShowMorePromoters}>
                  Show more promoters
                </Button>
              </div>
            )}
          </section>

          <section className="grid min-h-[420px] min-w-0 overflow-hidden grid-rows-[auto_minmax(0,1fr)] gap-3" aria-label="Recommendation evidence graph">
            <div className={panelHeadingClass}>
              <span className={labelClass}>
                {recommendationGraphMode === 'compact' ? 'Artist-only path' : 'Full analytics graph'}
              </span>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <RecommendationExportMenu
                  recommendationsData={recommendationsData}
                  recommendationGraphMode={recommendationGraphMode}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleToggleRecommendationGraphMode}
                  disabled={isRecommendationsLoading || isRecommendationsRefreshing}
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
                showNodeTypeLegend
                highlightPathToNodeId={`artist-${recommendationsData.entityId}`}
                visibleRecommendationPromoterNodeIds={displayedRecommendationPromoterNodeIds}
                focusedRecommendationPromoterNodeIds={focusedRecommendationPromoterIds?.map((promoterId) => `promoter-${promoterId}`) ?? null}
                onRecommendationGraphNodeClick={handleRecommendationGraphNodeClick}
                onRecommendationGraphPaneClick={handleRecommendationGraphPaneClick}
              />
            )}
          </section>

          {selectedRecommendationNode && (
            <RecommendationDetailsInspector
              className="max-[1399px]:col-span-full"
              selectedNode={selectedRecommendationNode}
              selectedEntityDetail={selectedRecommendationEntityDetail}
              isLoading={isSelectedRecommendationEntityDetailLoading}
              error={selectedRecommendationEntityDetailError}
              onSelectNode={handleSelectRecommendationNode}
              onClose={() => handleSelectRecommendationNode(null)}
            />
          )}
        </div>
      )}
    </section>
  )
}
