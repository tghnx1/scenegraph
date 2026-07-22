import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PromoterRecommendationsPanel, type PromoterRecommendationsPanelProps } from './RecommendationPanel'
import type { PromoterRecommendationResponse, RecommendationJobResponse } from '../../types/recommendation'

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
  onSelectNode: vi.fn(),
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
    render(
      <PromoterRecommendationsPanel
        {...baseProps({
          profileReadiness: {
            isLoading: false,
            hasBiography: false,
            manualArtistCount: 0,
            requiredManualArtistCount: 3,
          },
          onCompleteProfile: vi.fn(),
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
    expect(screen.getByRole('button', { name: 'Complete profile' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Add bio/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Add artists you know/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Check again/i })).not.toBeInTheDocument()
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

  it('keeps the current recommendations visible while updating them', async () => {
    const initialJob = createDeferred<RecommendationJobResponse>()
    const updateJob = createDeferred<RecommendationJobResponse>()

    api.post
      .mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
      .mockResolvedValueOnce({ jobId: 'job-2', status: 'queued' })
    api.get
      .mockReturnValueOnce(initialJob.promise)
      .mockReturnValueOnce(updateJob.promise)

    render(
      <PromoterRecommendationsPanel
        {...baseProps({ autoLoad: false })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))

    expect(await screen.findByTestId('recommendation-loading')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preparing…' })).toBeDisabled()

    initialJob.resolve(makeJobResponse('job-1', completedResult))
    expect(await screen.findByText('First Promoter')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Update recommendations' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reset' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Update recommendations' }))

    expect(screen.getByText('First Promoter')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Updating…' })).toBeDisabled()
    expect(screen.queryByTestId('recommendation-loading')).not.toBeInTheDocument()

    updateJob.resolve(makeJobResponse('job-2', refreshedResult))
    expect(await screen.findByText('Updated Promoter')).toBeInTheDocument()
    expect(screen.queryByText('First Promoter')).not.toBeInTheDocument()
    expect(screen.queryByText('Couldn’t update recommendations. Your previous results are still shown.')).not.toBeInTheDocument()
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
        {...baseProps({ autoLoad: false })}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    initialJob.resolve(makeJobResponse('job-1', completedResult))

    expect(await screen.findByText('First Promoter')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Update recommendations' }))

    expect(await screen.findByText('Couldn’t update recommendations. Your previous results are still shown.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getByText('First Promoter')).toBeInTheDocument()
    expect(screen.queryByText('Complete your artist profile to unlock recommendations.')).not.toBeInTheDocument()
  })
})
