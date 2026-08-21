import { render, screen, waitFor } from '@testing-library/react'
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

vi.mock('@/api/client', () => ({ api }))
vi.mock('../hooks/useRecommendationJobUpdates', () => ({ useRecommendationJobUpdates: vi.fn() }))
vi.mock('./LoadingScreen', () => ({
  RecommendationLoading: ({ activity }: { activity: string }) => (
    <div data-testid="recommendation-loading">{activity}</div>
  ),
}))
vi.mock('./GraphPanel', () => ({ ScenegraphMapPanel: () => <div data-testid="graph-panel" /> }))
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

const completedResult = recommendationResult('Database Promoter', 10)
const completedJob = job('job-db-completed', 'completed', completedResult)
const activeJob = job('job-db-active', 'running')
const props: PromoterRecommendationsPanelProps = {
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
    if (path.endsWith('/promoters/jobs/state')) return Promise.resolve(state)
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
    mockState({ latestCompletedJob: completedJob, activeJob: null })
    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('shows completed data and attaches to an active refresh without POST', async () => {
    let resolveActive!: (value: RecommendationJobResponse) => void
    const activeResponse = new Promise<RecommendationJobResponse>((resolve) => { resolveActive = resolve })
    api.get.mockImplementation((path: string) => {
      if (path.endsWith('/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: completedJob, activeJob })
      }
      if (path.startsWith('/recommendations/jobs/job-db-active?')) return activeResponse
      throw new Error(`Unexpected GET ${path}`)
    })

    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    resolveActive(activeJob)
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('attaches to an active-only DB job and shows initial loading without POST', async () => {
    api.get.mockImplementation((path: string) => {
      if (path.endsWith('/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: null, activeJob })
      }
      if (path.startsWith('/recommendations/jobs/job-db-active?')) return Promise.resolve(activeJob)
      throw new Error(`Unexpected GET ${path}`)
    })

    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByTestId('recommendation-loading')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('creates exactly one job when durable state is empty', async () => {
    api.get.mockImplementation((path: string) => {
      if (path.endsWith('/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: null, activeJob: null })
      }
      if (path.startsWith('/recommendations/jobs/job-new?')) return Promise.resolve(job('job-new', 'queued'))
      throw new Error(`Unexpected GET ${path}`)
    })
    api.post.mockResolvedValue({ jobId: 'job-new', status: 'queued' })

    render(<PromoterRecommendationsPanel {...props} />)

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    expect(api.post).toHaveBeenCalledWith(
      '/recommendations/artists/61/promoters/jobs',
      { limit: 200, debug: false },
    )
  })

  it('restores a completed result after remount (F5 semantics) without POST', async () => {
    mockState({ latestCompletedJob: completedJob, activeJob: null })
    const first = render(<PromoterRecommendationsPanel {...props} />)
    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()

    first.unmount()
    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('loads a completed DB result in a new tab with empty sessionStorage', async () => {
    mockState({ latestCompletedJob: completedJob, activeJob: null })
    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(window.sessionStorage.getItem).not.toHaveBeenCalled()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('ignores a stale sessionStorage job in favor of newer DB state', async () => {
    const storageKey = 'scenegraph:recommendation-job:61:61'
    vi.stubGlobal('sessionStorage', createStorageMock({ [storageKey]: 'job-stale' }))
    mockState({ latestCompletedJob: completedJob, activeJob: null })
    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining('job-stale'))
    expect(window.sessionStorage.setItem).toHaveBeenCalledWith(storageKey, completedJob.jobId)
    expect(api.post).not.toHaveBeenCalled()
  })

  it('keeps the previous completed result visible while an active refresh runs', async () => {
    const refreshed = recommendationResult('Refreshed Promoter', 11)
    let resolveActive!: (value: RecommendationJobResponse) => void
    const activeResponse = new Promise<RecommendationJobResponse>((resolve) => { resolveActive = resolve })
    api.get.mockImplementation((path: string) => {
      if (path.endsWith('/promoters/jobs/state')) {
        return Promise.resolve({ latestCompletedJob: completedJob, activeJob })
      }
      if (path.startsWith('/recommendations/jobs/job-db-active?')) return activeResponse
      throw new Error(`Unexpected GET ${path}`)
    })

    render(<PromoterRecommendationsPanel {...props} />)

    expect(await screen.findByText('Database Promoter')).toBeInTheDocument()
    resolveActive(job('job-db-active', 'completed', refreshed))
    expect(await screen.findByText('Refreshed Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Database Promoter')).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })
})
