import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PromoterRecommendationsPanel, type PromoterRecommendationsPanelProps } from './RecommendationPanel'
import type { PromoterRecommendationResponse, RecommendationJobResponse } from '../../types/recommendation'

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
vi.mock('./ExportRecommendation', () => ({ RecommendationExportMenu: () => <div data-testid="export-menu" /> }))

const baseResult = (name: string, promoterId: number): PromoterRecommendationResponse => ({
  entityId: 61,
  entityType: 'artist',
  recommendations: [
    {
      id: promoterId,
      type: 'promoter',
      name,
      score: 0.91,
      baseScore: 0.82,
      feedbackBoost: 0,
      feedbackState: null,
      reasons: ['shared extracted genres: dark disco'],
      promoterSizeSegment: 'medium',
    },
  ],
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
const longRecommendationResult: PromoterRecommendationResponse = {
  entityId: 61,
  entityType: 'artist',
  recommendations: Array.from({ length: 21 }, (_, index) => ({
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
  graph: {
    nodes: [],
    links: [],
  },
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

function makeJobResponse(jobId: string, result: PromoterRecommendationResponse): RecommendationJobResponse {
  return {
    jobId,
    jobType: 'artist_promoters',
    artistId: 61,
    params: { limit: 50, debug: false },
    status: 'completed',
    result,
    createdAt: '2026-07-21T10:00:00.000Z',
    updatedAt: '2026-07-21T10:00:01.000Z',
  }
}

describe('PromoterRecommendationsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

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
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', analyticsGraphResult))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

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
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', analyticsGraphResult))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

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
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', multiRecommendationResult))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

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

  it('shows only three genre source events per genre until expanded', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', genreSourceRecommendationResult))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

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

  it('keeps the match count stable while loading more promoters', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', longRecommendationResult))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByText('21 matches')).toBeInTheDocument()
    expect(screen.getByText('Promoter 20')).toBeInTheDocument()
    expect(screen.queryByText('Promoter 21')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Show more promoters' }))

    expect(await screen.findByText('Promoter 21')).toBeInTheDocument()
    expect(screen.getByText('21 matches')).toBeInTheDocument()
  })

  it('keeps the promoters header visible when no recommendations match', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', emptyRecommendationResult))

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByRole('heading', { name: 'Recommended promoters', level: 3 })).toBeInTheDocument()
    expect(screen.getByText('0 matches')).toBeInTheDocument()
    expect(screen.getByText('No promoters matched this recommendation run.')).toBeInTheDocument()
  })

  it('autostarts recommendations once when the profile becomes ready', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockResolvedValueOnce(makeJobResponse('job-1', completedResult))

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
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1))
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
    const initialJob = createDeferred<RecommendationJobResponse>()

    api.post
      .mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get
      .mockReturnValueOnce(initialJob.promise)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({ autoLoad: false, profileChangedSinceRecommendations: true })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByTestId('recommendation-loading')).toBeInTheDocument()

    await act(async () => {
      initialJob.resolve(makeJobResponse('job-1', completedResult))
    })
    expect(await screen.findByText('First Promoter')).toBeInTheDocument()
    expect(screen.getByText('Your profile changed. Update recommendations to use the latest information.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Update recommendations' })).toBeEnabled()
    expect(screen.getByText('First Promoter')).toBeInTheDocument()
    expect(screen.queryByTestId('recommendation-loading')).not.toBeInTheDocument()
  })

  it('shows a reminder when the profile changed after recommendations were generated', async () => {
    const initialJob = createDeferred<RecommendationJobResponse>()
    const refreshJob = createDeferred<RecommendationJobResponse>()
    const onRecommendationsSynced = vi.fn()

    api.post
      .mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
      .mockResolvedValueOnce({ jobId: 'job-2', status: 'queued' })
    api.get
      .mockReturnValueOnce(initialJob.promise)
      .mockReturnValueOnce(refreshJob.promise)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          autoLoad: false,
          profileChangedSinceRecommendations: true,
          onRecommendationsSynced,
        })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    await act(async () => {
      initialJob.resolve(makeJobResponse('job-1', completedResult))
    })

    expect(await screen.findByText('Your profile changed. Update recommendations to use the latest information.')).toBeInTheDocument()
    expect(onRecommendationsSynced).toHaveBeenCalledTimes(1)

    const updateButtons = screen.getAllByRole('button', { name: 'Update recommendations' })
    fireEvent.click(updateButtons[0] ?? updateButtons[updateButtons.length - 1])

    expect(screen.getByText('First Promoter')).toBeInTheDocument()
    refreshJob.resolve(makeJobResponse('job-2', refreshedResult))

    expect(await screen.findByText('Updated Promoter')).toBeInTheDocument()
    expect(onRecommendationsSynced).toHaveBeenCalledTimes(2)
  })

  it('shows a non-blocking error when an update fails and keeps the previous recommendations visible', async () => {
    const initialJob = createDeferred<RecommendationJobResponse>()

    api.post
      .mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
      .mockResolvedValueOnce({ jobId: 'job-2', status: 'queued' })
    api.get
      .mockReturnValueOnce(initialJob.promise)
      .mockResolvedValueOnce({
        jobId: 'job-2',
        jobType: 'artist_promoters',
        artistId: 61,
        params: { limit: 50, debug: false },
        status: 'failed',
        errorMessage: 'Recommendation job failed',
        createdAt: '2026-07-21T10:00:00.000Z',
        updatedAt: '2026-07-21T10:00:01.000Z',
      })

    render(
      <PromoterRecommendationsPanel
        {...baseProps({ autoLoad: false, profileChangedSinceRecommendations: true })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    await act(async () => {
      initialJob.resolve(makeJobResponse('job-1', completedResult))
    })

    expect(await screen.findByText('First Promoter')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Update recommendations' }))

    expect(await screen.findByText('Couldn’t update recommendations. Your previous results are still shown.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getByText('First Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Complete your artist profile to unlock recommendations.')).not.toBeInTheDocument()
  })
})
