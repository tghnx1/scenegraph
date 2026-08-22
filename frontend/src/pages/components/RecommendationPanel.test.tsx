import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PromoterRecommendationsPanel, type PromoterRecommendationsPanelProps } from './RecommendationPanel'
import type {
  PromoterRecommendationResponse,
  RecommendationJobResponse,
  RecommendationJobStateResponse,
} from '../../types/recommendation'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}))
const scenegraphMapPanelMock = vi.hoisted(() => vi.fn(() => <div data-testid="graph-panel" />))

vi.mock('@/api/client', () => ({ api }))
vi.mock('../hooks/useRecommendationJobUpdates', () => ({ useRecommendationJobUpdates: vi.fn() }))
vi.mock('./LoadingScreen', () => ({
  RecommendationLoading: ({ activity }: { activity: string }) => (
    <div data-testid="recommendation-loading">{activity}</div>
  ),
}))
vi.mock('./GraphPanel', () => ({ ScenegraphMapPanel: scenegraphMapPanelMock }))
vi.mock('./ExportRecommendation', () => ({ RecommendationExportMenu: () => null }))

function createStorageMock(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial))
  return {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => store.set(key, String(value))),
    removeItem: vi.fn((key: string) => store.delete(key)),
    clear: vi.fn(() => store.clear()),
  }
}

function recommendationResult(name: string, promoterId: number): PromoterRecommendationResponse {
  return {
    entityId: 61,
    entityType: 'artist',
    recommendations: [{
      id: promoterId,
      type: 'promoter',
      name,
      score: 0.91,
      baseScore: 0.82,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'medium',
    }],
    graph: { nodes: [], links: [] },
  }
}

const baseResult = (name: string, promoterId: number): PromoterRecommendationResponse => ({
  entityId: 61,
  entityType: 'artist',
  recommendations: [{
    id: promoterId,
    type: 'promoter',
    name,
    score: 0.91,
    baseScore: 0.82,
    feedbackBoost: 0,
    feedbackState: null,
    reasons: ['shared extracted genres: dark disco'],
    promoterSizeSegment: 'medium',
  }],
  graph: {
    nodes: [],
    links: [],
  },
})

const completedResult = baseResult('First Promoter', 10)
const refreshedResult = baseResult('Updated Promoter', 11)
const multiRecommendationResult: PromoterRecommendationResponse = {
  entityId: 61,
  entityType: 'artist',
  recommendations: [
    {
      id: 10,
      type: 'promoter',
      name: 'North Collective',
      score: 0.92,
      baseScore: 0.84,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'large',
    },
    {
      id: 11,
      type: 'promoter',
      name: 'East Sessions',
      score: 0.41,
      baseScore: 0.36,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'small',
    },
  ],
  graph: {
    nodes: [],
    links: [],
  },
}
const genreSourceRecommendationResult: PromoterRecommendationResponse = {
  entityId: 61,
  entityType: 'artist',
  recommendations: [
    {
      id: 20,
      type: 'promoter',
      name: 'Genre Sources Collective',
      score: 0.74,
      baseScore: 0.62,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'small',
      reasonDetails: {
        sharedExtractedGenres: ['dark disco'],
        sharedExtractedGenreSources: {
          'dark disco': [
            {
              eventId: 1,
              raEventId: '1001',
              title: 'Event 1',
              eventDate: '2026-06-01',
              sourceType: 'event_genres',
            },
            {
              eventId: 2,
              raEventId: '1002',
              title: 'Event 2',
              eventDate: '2026-06-02',
              sourceType: 'event_extracted_tags',
            },
            {
              eventId: 3,
              raEventId: '1003',
              title: 'Event 3',
              eventDate: '2026-06-03',
              sourceType: 'event_genres',
            },
            {
              eventId: 4,
              raEventId: '1004',
              title: 'Event 4',
              eventDate: '2026-06-04',
              sourceType: 'event_extracted_tags',
            },
          ],
        },
      },
    },
  ],
  graph: {
    nodes: [],
    links: [],
  },
}
const analyticsGraphResult: PromoterRecommendationResponse = {
  ...multiRecommendationResult,
  analyticsGraph: {
    nodes: [{ id: 'analytics-node', type: 'artist', entityId: 61, name: 'Holywanderer', genres: [] }],
    links: [],
  },
}
const pagedRecommendationResults = {
  firstPage: {
    entityId: 61,
    entityType: 'artist',
    recommendations: Array.from({ length: 20 }, (_, index) => ({
      id: 100 + index,
      type: 'promoter',
      name: `Promoter ${index + 1}`,
      score: 1 - index * 0.01,
      baseScore: 0.8,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'medium',
    })),
    recommendationsTotal: 21,
    recommendationsOffset: 0,
    recommendationsLimit: 20,
    recommendationsHasMore: true,
    largeRecommendations: [],
    mediumRecommendations: Array.from({ length: 20 }, (_, index) => ({
      id: 100 + index,
      type: 'promoter',
      name: `Promoter ${index + 1}`,
      score: 1 - index * 0.01,
      baseScore: 0.8,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'medium',
    })),
    smallRecommendations: [],
    warmRecommendations: [],
    discoveryRecommendations: [],
    graph: {
      nodes: [
        { id: 'artist-61', entityId: 61, type: 'artist', name: 'Holywanderer', genres: [] },
        { id: 'promoter-100', entityId: 100, type: 'promoter', name: 'Promoter 1', genres: [] },
      ],
      links: [
        { source: 'artist-61', target: 'promoter-100', relationship: 'recommendation', weight: 1 },
      ],
    },
  } satisfies PromoterRecommendationResponse,
  secondPage: {
    entityId: 61,
    entityType: 'artist',
    recommendations: [
      {
        id: 120,
        type: 'promoter',
        name: 'Promoter 21',
        score: 0.79,
        baseScore: 0.8,
        feedbackBoost: 0,
        feedbackState: null,
        reasons: ['shared extracted genres: dark disco'],
        promoterSizeSegment: 'medium',
      },
    ],
    recommendationsTotal: 21,
    recommendationsOffset: 20,
    recommendationsLimit: 20,
    recommendationsHasMore: false,
    largeRecommendations: [],
    mediumRecommendations: [
      {
        id: 120,
        type: 'promoter',
        name: 'Promoter 21',
        score: 0.79,
        baseScore: 0.8,
        feedbackBoost: 0,
        feedbackState: null,
        reasons: ['shared extracted genres: dark disco'],
        promoterSizeSegment: 'medium',
      },
    ],
    smallRecommendations: [],
    warmRecommendations: [],
    discoveryRecommendations: [],
    graph: {
      nodes: [
        { id: 'artist-61', entityId: 61, type: 'artist', name: 'Holywanderer', genres: [] },
        { id: 'promoter-100', entityId: 100, type: 'promoter', name: 'Promoter 1', genres: [] },
        { id: 'promoter-120', entityId: 120, type: 'promoter', name: 'Promoter 21', genres: [] },
      ],
      links: [
        { source: 'artist-61', target: 'promoter-100', relationship: 'recommendation', weight: 1 },
        { source: 'artist-61', target: 'promoter-120', relationship: 'recommendation', weight: 1 },
      ],
    },
  } satisfies PromoterRecommendationResponse,
}
const emptyRecommendationResult: PromoterRecommendationResponse = {
  entityId: 61,
  entityType: 'artist',
  recommendations: [],
  graph: {
    nodes: [],
    links: [],
  },
}

const baseProps = (overrides: Partial<PromoterRecommendationsPanelProps> = {}): PromoterRecommendationsPanelProps => ({
  isActive: true,
  artistId: 61,
  artistName: 'Holywanderer',
  autoLoad: true,
  profileReadiness: {
    isLoading: false,
    hasBiography: true,
    manualArtistCount: 3,
    requiredManualArtistCount: 3,
  },
  onNavigateToSection: vi.fn(),
  ...overrides,
})

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function makeJobResponse(
  jobId: string,
  result: PromoterRecommendationResponse | null,
  status: RecommendationJobResponse['status'] = 'completed',
): RecommendationJobResponse {
  return {
    jobId,
    jobType: 'artist_promoters',
    artistId: 61,
    params: { limit: 200, debug: false },
    status,
    result,
    createdAt: '2026-07-21T10:00:00.000Z',
    updatedAt: '2026-07-21T10:00:01.000Z',
  }
}

function job(
  jobId: string,
  status: RecommendationJobResponse['status'],
  result?: PromoterRecommendationResponse,
): RecommendationJobResponse {
  return {
    jobId,
    jobType: 'artist_promoters',
    artistId: 61,
    params: { limit: 200, debug: false },
    status,
    result,
    createdAt: '2026-08-20T10:00:00Z',
    updatedAt: '2026-08-20T10:01:00Z',
  }
}

const bootstrapCompletedResult = recommendationResult('Database Promoter', 10)
const bootstrapCompletedJob = job('job-db-completed', 'completed', bootstrapCompletedResult)
const bootstrapActiveJob = job('job-db-active', 'running')
const bootstrapProps: PromoterRecommendationsPanelProps = {
  isActive: true,
  artistId: 61,
  artistName: 'Holywanderer',
  autoLoad: true,
  profileReadiness: {
    isLoading: false,
    hasBiography: true,
    manualArtistCount: 3,
    requiredManualArtistCount: 3,
  },
}

function mockState(state: RecommendationJobStateResponse) {
  api.get.mockImplementation((path: string) => {
    if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) return Promise.resolve(state)
    throw new Error(`Unexpected GET ${path}`)
  })
}

describe('PromoterRecommendationsPanel durable state bootstrap', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('localStorage', createStorageMock({ user_id: '61' }))
    vi.stubGlobal('sessionStorage', createStorageMock())
  })

  it('shows the latest completed DB job without creating a job', async () => {
    mockState({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('shows completed data and attaches to an active refresh without POST', async () => {
    let resolveActive!: (value: RecommendationJobResponse) => void
    const activeResponse = new Promise<RecommendationJobResponse>((resolve) => { resolveActive = resolve })
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: bootstrapActiveJob })
      }
      if (path.startsWith('/recommendations/jobs/job-db-active?')) return activeResponse
      throw new Error(`Unexpected GET ${path}`)
    })

    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    resolveActive(bootstrapActiveJob)
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('attaches to an active-only DB job and shows initial loading without POST', async () => {
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: null, activeJob: bootstrapActiveJob })
      }
      if (path.startsWith('/recommendations/jobs/job-db-active?')) return Promise.resolve(bootstrapActiveJob)
      throw new Error(`Unexpected GET ${path}`)
    })

    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByTestId('recommendation-loading')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('creates exactly one job when durable state is empty', async () => {
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: null, activeJob: null })
      }
      if (path.startsWith('/recommendations/jobs/job-new?')) return Promise.resolve(job('job-new', 'queued'))
      throw new Error(`Unexpected GET ${path}`)
    })
    api.post.mockResolvedValue({ jobId: 'job-new', status: 'queued' })

    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    expect(api.post).toHaveBeenCalledWith(
      '/recommendations/artists/61/promoters/jobs',
      { limit: 200, debug: false },
    )
  })

  it('restores a completed result after remount (F5 semantics) without POST', async () => {
    mockState({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
    const first = render(<PromoterRecommendationsPanel {...bootstrapProps} />)
    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()

    first.unmount()
    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('loads a completed DB result in a new tab with empty sessionStorage', async () => {
    mockState({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(window.sessionStorage.getItem).not.toHaveBeenCalled()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('ignores a stale sessionStorage job in favor of newer DB state', async () => {
    const storageKey = 'scenegraph:recommendation-job:61:61'
    vi.stubGlobal('sessionStorage', createStorageMock({ [storageKey]: 'job-stale' }))
    mockState({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining('job-stale'))
    expect(window.sessionStorage.setItem).toHaveBeenCalledWith(storageKey, bootstrapCompletedJob.jobId)
    expect(api.post).not.toHaveBeenCalled()
  })

  it('keeps the previous completed result visible while an active refresh runs', async () => {
    const refreshed = recommendationResult('Refreshed Promoter', 11)
    let resolveActive!: (value: RecommendationJobResponse) => void
    const activeResponse = new Promise<RecommendationJobResponse>((resolve) => { resolveActive = resolve })
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: bootstrapActiveJob })
      }
      if (path.startsWith('/recommendations/jobs/job-db-active?')) return activeResponse
      throw new Error(`Unexpected GET ${path}`)
    })

    render(<PromoterRecommendationsPanel {...bootstrapProps} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    resolveActive(job('job-db-active', 'completed', refreshed))
    expect(await screen.findByText('Refreshed Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Database Promoter')).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('PromoterRecommendationsPanel legacy UX coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('localStorage', createStorageMock({ user_id: '61' }))
    vi.stubGlobal('sessionStorage', createStorageMock())
  })

  function mockEmptyStateAndJob(result: PromoterRecommendationResponse) {
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: null, activeJob: null })
      }
      if (path.startsWith('/recommendations/jobs/job-1?')) return Promise.resolve(makeJobResponse('job-1', result))
      if (path.startsWith('/recommendations/jobs/job-2?')) return Promise.resolve(makeJobResponse('job-2', refreshedResult))
      if (path.startsWith('/recommendations/jobs/job-restore-2?')) return Promise.resolve(makeJobResponse('job-restore-2', refreshedResult))
      if (path.startsWith('/recommendations/jobs/job-restore-new?')) return Promise.resolve(makeJobResponse('job-restore-new', refreshedResult))
      throw new Error(`Unexpected GET ${path}`)
    })
  }

  async function waitForBootstrapState() {
    await waitFor(() => expect(api.get).toHaveBeenCalled())
  }

  it('shows a neutral readiness check while biography and manual artists are loading', () => {
    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: true,
            hasBiography: null,
            manualArtistCount: 0,
            requiredManualArtistCount: 3,
          },
        })}
      />,
    )

    expect(screen.getByText('Checking your artist profile…')).toBeInTheDocument()
    expect(screen.queryByTestId('recommendation-loading')).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('shows a compact setup card when the profile is incomplete', () => {
    const onNavigateToSection = vi.fn()
    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: false,
            hasBiography: false,
            manualArtistCount: 0,
            requiredManualArtistCount: 3,
          },
          onNavigateToSection,
        })}
      />,
    )

    expect(screen.getByText('Profile setup')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Complete your profile to generate recommendations' })).toBeInTheDocument()
    expect(screen.getByText('Complete these steps and recommendations will start automatically.')).toBeInTheDocument()
    expect(screen.getByText('Biography')).toBeInTheDocument()
    expect(screen.getByText('Missing')).toBeInTheDocument()
    expect(screen.getByText('Artists you know')).toBeInTheDocument()
    expect(screen.getByText('0 of 3 added')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Biography: Missing' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Artists you know: 0 of 3 added' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Complete profile' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Add bio/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Add artists you know/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Check again/i })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Biography: Missing' }))
    fireEvent.click(screen.getByRole('button', { name: 'Artists you know: 0 of 3 added' }))
    expect(onNavigateToSection).toHaveBeenNthCalledWith(1, 'biography')
    expect(onNavigateToSection).toHaveBeenNthCalledWith(2, 'manual_artists')
  })

  it('shows the ready-state prompt for artist profiles and uses the full button label', () => {
    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileReadiness: {
            isLoading: false,
            hasBiography: true,
            manualArtistCount: 3,
            requiredManualArtistCount: 3,
          },
        })}
      />,
    )

    expect(screen.getByText('Recommendations are ready to generate.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Get recommendations' })).toBeInTheDocument()
    expect(screen.queryByText('Complete your artist profile to unlock recommendations.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reset' })).not.toBeInTheDocument()
  })

  it('passes the static legend only to the recommendation graph', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    mockEmptyStateAndJob(analyticsGraphResult)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    await waitFor(() => expect(scenegraphMapPanelMock).toHaveBeenCalled())
    const lastCallArgs = scenegraphMapPanelMock.mock.calls[scenegraphMapPanelMock.mock.calls.length - 1]?.[0]

    expect(lastCallArgs).toEqual(expect.objectContaining({
      showFilters: false,
      showNodeTypeFilter: false,
      showNodeTypeLegend: true,
      providedData: analyticsGraphResult.graph,
    }))
  })

  it('opens the compact graph by default and allows switching to the analytics graph', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    mockEmptyStateAndJob(analyticsGraphResult)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByText('Artist-only path')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show analytics graph' })).toBeInTheDocument()

    const graphCall = scenegraphMapPanelMock.mock.calls.at(-1)?.[0]
    expect(graphCall).toEqual(expect.objectContaining({
      providedData: analyticsGraphResult.graph,
    }))

    fireEvent.click(screen.getByRole('button', { name: 'Show analytics graph' }))

    expect(await screen.findByText('Full analytics graph')).toBeInTheDocument()
    const compactGraphCall = scenegraphMapPanelMock.mock.calls.at(-1)?.[0]
    expect(compactGraphCall).toEqual(expect.objectContaining({
      providedData: analyticsGraphResult.analyticsGraph,
    }))
  })

  it('renders a recommended promoters list header with a visible match count', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    mockEmptyStateAndJob(multiRecommendationResult)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByRole('heading', { name: 'Recommended promoters', level: 3 })).toBeInTheDocument()
    expect(screen.getByText('Promoters matched to your profile, network and scene activity.')).toBeInTheDocument()
    expect(screen.getByText('2 matches')).toBeInTheDocument()

    const header = screen.getByRole('heading', { name: 'Recommended promoters', level: 3 }).closest('header')
    expect(header?.querySelector('[aria-hidden="true"]')).toHaveClass('bg-[var(--promoter)]')
    expect(screen.getByText('Promoter size: large')).toBeInTheDocument()
    expect(screen.getByLabelText('Promoter size: Large')).toBeInTheDocument()
    expect(screen.queryAllByText(/^Promoter$/i)).toHaveLength(0)
  })

  it('highlights the matching graph node when a promoter is selected from the list', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    mockEmptyStateAndJob(multiRecommendationResult)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    await user.click(screen.getByRole('button', { name: 'Get recommendations' }))
    await screen.findByRole('heading', { name: 'Recommended promoters', level: 3 })

    await user.click(screen.getByRole('button', { name: /North Collective/ }))

    const lastGraphCall = scenegraphMapPanelMock.mock.calls.at(-1)?.[0]
    expect(lastGraphCall).toEqual(expect.objectContaining({
      selectedNodeId: 'promoter-10',
    }))
  })

  it('shows only three genre source events per genre until expanded', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    mockEmptyStateAndJob(genreSourceRecommendationResult)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    await user.click(screen.getByRole('button', { name: 'Get recommendations' }))
    await user.click(await screen.findByRole('button', { name: /Genre Sources Collective/i }))

    expect(screen.getByText('Genre sources')).toBeInTheDocument()
    expect(screen.getAllByText('dark disco')).toHaveLength(2)
    expect(screen.getByText('Event 1')).toBeInTheDocument()
    expect(screen.getByText('Event 2')).toBeInTheDocument()
    expect(screen.getByText('Event 3')).toBeInTheDocument()
    expect(screen.queryByText('Event 4')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show all' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Show all' }))

    expect(screen.getByRole('button', { name: 'Hide' })).toBeInTheDocument()
    expect(screen.getByText('Event 4')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Hide' }))

    expect(screen.getByRole('button', { name: 'Show all' })).toBeInTheDocument()
    expect(screen.queryByText('Event 4')).not.toBeInTheDocument()
  })

  it('automatically loads the next promoter page when the list is scrolled near the bottom', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get
      .mockImplementationOnce((path: string) => {
        if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
          return Promise.resolve({ latestCompletedJob: null, activeJob: null })
        }
        throw new Error(`Unexpected GET ${path}`)
      })
      .mockResolvedValueOnce(makeJobResponse('job-1', pagedRecommendationResults.firstPage))
      .mockResolvedValueOnce(makeJobResponse('job-1', pagedRecommendationResults.secondPage))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    await waitForBootstrapState()
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByText('20 of 21 matches')).toBeInTheDocument()
    expect(screen.getByText('Promoter 20')).toBeInTheDocument()
    expect(screen.queryByText('Promoter 21')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show more promoters' })).not.toBeInTheDocument()

    const recommendationList = screen.getByRole('region', { name: 'Recommended promoters' })
    Object.defineProperty(recommendationList, 'clientHeight', { configurable: true, value: 300 })
    Object.defineProperty(recommendationList, 'scrollHeight', { configurable: true, value: 520 })
    Object.defineProperty(recommendationList, 'scrollTop', { configurable: true, value: 260, writable: true })

    fireEvent.scroll(recommendationList)

    expect(await screen.findByText('Promoter 21')).toBeInTheDocument()
    expect(screen.getByText('21 matches')).toBeInTheDocument()

    const lastGraphCall = scenegraphMapPanelMock.mock.calls.at(-1)?.[0]
    expect(lastGraphCall).toEqual(expect.objectContaining({
      providedData: expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({ id: 'promoter-100' }),
          expect.objectContaining({ id: 'promoter-120' }),
        ]),
      }),
    }))
  })

  it('keeps the promoters header visible when no recommendations match', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    mockEmptyStateAndJob(emptyRecommendationResult)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    await waitForBootstrapState()
    await waitForBootstrapState()
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByRole('heading', { name: 'Recommended promoters', level: 3 })).toBeInTheDocument()
    expect(screen.getByText('0 matches')).toBeInTheDocument()
    expect(screen.getByText('No promoters matched this recommendation run.')).toBeInTheDocument()
  })

  it('autostarts recommendations once when the profile becomes ready', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: null, activeJob: null })
      }
      if (path.startsWith('/recommendations/jobs/job-1?')) return Promise.resolve(makeJobResponse('job-1', completedResult))
      throw new Error(`Unexpected GET ${path}`)
    })

    const { rerender } = render(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: false,
            hasBiography: false,
            manualArtistCount: 0,
            requiredManualArtistCount: 3,
          },
        })}
      />,
    )

    await waitForBootstrapState()
    expect(api.post).not.toHaveBeenCalled()

    rerender(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: false,
            hasBiography: true,
            manualArtistCount: 3,
            requiredManualArtistCount: 3,
          },
        })}
      />,
    )

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(3))
    expect(screen.queryByText('Complete your profile to generate recommendations')).not.toBeInTheDocument()
  })

  it('shows the stale-profile fallback card when the backend still rejects the ready profile', async () => {
    api.post.mockRejectedValueOnce(new Error('404: No text-embedding-3-small embedding found for artist 61. Run scripts/generate_embeddings.py first.'))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: false,
            hasBiography: true,
            manualArtistCount: 3,
            requiredManualArtistCount: 3,
          },
        })}
      />,
    )

    expect(await screen.findByText('Your profile was updated, but recommendations are not ready yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('navigates to a profile section from the setup card when biography is already present', () => {
    const onNavigateToSection = vi.fn()

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: false,
            hasBiography: true,
            manualArtistCount: 1,
            requiredManualArtistCount: 3,
          },
          onNavigateToSection,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Biography: Added' }))
    fireEvent.click(screen.getByRole('button', { name: 'Artists you know: 1 of 3 added' }))

    expect(onNavigateToSection).toHaveBeenNthCalledWith(1, 'biography')
    expect(onNavigateToSection).toHaveBeenNthCalledWith(2, 'manual_artists')
  })

  it('keeps the current recommendations visible while updating them', async () => {
    const refreshJob = createDeferred<RecommendationJobResponse>()

    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
      }
      if (path.startsWith('/recommendations/jobs/job-1?')) return refreshJob.promise
      throw new Error(`Unexpected GET ${path}`)
    })

    render(
      <PromoterRecommendationsPanel
        {...baseProps({ autoLoad: false, profileChangedSinceRecommendations: true, profileChangeRevision: 1 })}
      />,
    )

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Update recommendations' }))

    expect(screen.getByText('Database Promoter')).toBeInTheDocument()
    expect(screen.queryByTestId('recommendation-loading')).not.toBeInTheDocument()

    await act(async () => {
      refreshJob.resolve(makeJobResponse('job-1', refreshedResult))
    })

    expect(await screen.findByText('Updated Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Database Promoter')).not.toBeInTheDocument()
  })

  it('shows a reminder when the profile changed after recommendations were generated', async () => {
    const onRecommendationsSynced = vi.fn()
    let stateRequestCount = 0

    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        stateRequestCount += 1
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
      }
      throw new Error(`Unexpected GET ${path}`)
    })

    const { rerender } = render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: false,
          onRecommendationsSynced,
        })}
      />,
    )

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()

    rerender(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: true,
          profileChangeRevision: 1,
          onRecommendationsSynced,
        })}
      />,
    )

    await waitFor(() => expect(stateRequestCount).toBeGreaterThanOrEqual(2))
    expect(screen.getByText('Database Promoter')).toBeInTheDocument()
    expect(screen.getByText('Your profile changed. Update recommendations to use the latest information.')).toBeInTheDocument()
    expect(screen.queryByText('Your recommendations are updating automatically…')).not.toBeInTheDocument()
    expect(onRecommendationsSynced).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['add', 1],
    ['delete', 2],
  ])('re-reads durable state after manual connection %s and attaches to the backend job', async (_mutation, revision) => {
    const activeRefresh = createDeferred<RecommendationJobResponse>()
    const refreshedResult = recommendationResult('Auto Refreshed Promoter', 12)
    const onRecommendationsSynced = vi.fn()
    let stateRequestCount = 0

    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        stateRequestCount += 1
        if (stateRequestCount === 1) {
          return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
        }
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: job('job-auto-refresh', 'running') })
      }
      if (path.startsWith('/recommendations/jobs/job-auto-refresh?')) return activeRefresh.promise
      throw new Error(`Unexpected GET ${path}`)
    })

    const { rerender } = render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: false,
          onRecommendationsSynced,
        })}
      />,
    )

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()

    rerender(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: true,
          profileChangeRevision: revision,
          onRecommendationsSynced,
        })}
      />,
    )

    await waitFor(() => expect(stateRequestCount).toBeGreaterThanOrEqual(2))
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getByText('Database Promoter')).toBeInTheDocument()
    expect(screen.getByText('Your recommendations are updating automatically…')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Update recommendations' })).not.toBeInTheDocument()

    await act(async () => {
      activeRefresh.resolve(job('job-auto-refresh', 'completed', refreshedResult))
    })

    expect(await screen.findByText('Auto Refreshed Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Database Promoter')).not.toBeInTheDocument()
    expect(onRecommendationsSynced).toHaveBeenCalledTimes(1)
  })

  it('clears the profile-changed flag when a completed refresh is already in durable state before mount', async () => {
    const completedRefreshResult = recommendationResult('Completed Before Mount', 13)
    const onRecommendationsSynced = vi.fn()
    let stateRequestCount = 0

    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        stateRequestCount += 1
        return Promise.resolve({
          latestCompletedJob: job('job-completed-before-mount', 'completed', completedRefreshResult),
          activeJob: null,
        })
      }
      throw new Error(`Unexpected GET ${path}`)
    })

    const { rerender } = render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: true,
          profileChangeRevision: 1,
          onRecommendationsSynced,
        })}
      />,
    )

    expect(await screen.findByText('Completed Before Mount')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    expect(onRecommendationsSynced).toHaveBeenCalledTimes(1)
    expect(stateRequestCount).toBe(1)
    expect(screen.getByText('Your profile changed. Update recommendations to use the latest information.')).toBeInTheDocument()
    expect(screen.queryByText('Your recommendations are updating automatically…')).not.toBeInTheDocument()

    rerender(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: false,
          profileChangeRevision: 1,
          onRecommendationsSynced,
        })}
      />,
    )

    expect(screen.queryByText('Your profile changed. Update recommendations to use the latest information.')).not.toBeInTheDocument()
  })

  it('re-reads durable state after feedback and attaches to the backend refresh job', async () => {
    const user = userEvent.setup()
    const activeRefresh = createDeferred<RecommendationJobResponse>()
    const feedbackActiveJob = job('job-feedback-active', 'running')
    const refreshedFeedbackResult = recommendationResult('Feedback Refreshed Promoter', 12)
    let stateRequestCount = 0

    api.post.mockResolvedValueOnce({ id: 501 })
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        stateRequestCount += 1
        if (stateRequestCount === 1) {
          return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
        }
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: feedbackActiveJob })
      }
      if (path.startsWith('/recommendations/jobs/job-feedback-active?')) return activeRefresh.promise
      throw new Error(`Unexpected GET ${path}`)
    })

    render(
      <PromoterRecommendationsPanel
        {...baseProps({ autoLoad: false, profileChangedSinceRecommendations: true, profileChangeRevision: 1 })}
      />,
    )

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Interested' }))

    await waitFor(() => expect(stateRequestCount).toBeGreaterThanOrEqual(2))
    expect(api.get).toHaveBeenCalledWith('/recommendations/artists/61/promoters/jobs/state?recommendations_offset=0&recommendations_limit=20')
    expect(api.get).toHaveBeenCalledWith('/recommendations/jobs/job-feedback-active?recommendations_offset=0&recommendations_limit=20')
    expect(api.post.mock.calls.some(([path]) => path === '/recommendations/artists/61/promoters/jobs')).toBe(false)
    expect(screen.getByText('Database Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Feedback Refreshed Promoter')).not.toBeInTheDocument()

    await act(async () => {
      activeRefresh.resolve(job('job-feedback-active', 'completed', refreshedFeedbackResult))
    })

    expect(await screen.findByText('Feedback Refreshed Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Database Promoter')).not.toBeInTheDocument()
  })

  it('shows a non-blocking error when an update fails and keeps the previous recommendations visible', async () => {
    api.post
      .mockResolvedValueOnce({ jobId: 'job-2', status: 'queued' })
    api.get.mockImplementation((path: string) => {
      if (path.startsWith('/recommendations/artists/61/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: bootstrapCompletedJob, activeJob: null })
      }
      if (path.startsWith('/recommendations/jobs/job-2?')) {
        return Promise.resolve({
          jobId: 'job-2',
          jobType: 'artist_promoters',
          artistId: 61,
          params: { limit: 200, debug: false },
          status: 'failed',
          errorMessage: 'Recommendation job failed',
          createdAt: '2026-07-21T10:00:00.000Z',
          updatedAt: '2026-07-21T10:00:01.000Z',
        })
      }
      throw new Error(`Unexpected GET ${path}`)
    })

    render(
      <PromoterRecommendationsPanel
        {...baseProps({ autoLoad: false, profileChangedSinceRecommendations: true, profileChangeRevision: 1 })}
      />,
    )

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(await screen.findByText('Your profile changed. Update recommendations to use the latest information.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Update recommendations' }))

    expect(await screen.findByText('Couldn’t update recommendations. Your previous results are still shown.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getByText('Database Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Complete your artist profile to unlock recommendations.')).not.toBeInTheDocument()
  })
})
