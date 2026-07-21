import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PromoterRecommendationsPanel, type PromoterRecommendationsPanelProps } from './RecommendationPanel'
import type { PromoterRecommendationResponse } from '../../types/recommendation'
import type { ArtistProfileReadiness } from '../profileReadiness'

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

const completedResult: PromoterRecommendationResponse = {
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
  onSelectNode: vi.fn(),
  ...overrides,
})

describe('PromoterRecommendationsPanel', () => {
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

    expect(screen.getByText('PROFILE SETUP')).toBeInTheDocument()
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

  it('autostarts recommendations once when the profile becomes ready', async () => {
    api.post.mockResolvedValueOnce({ jobId: 'job-1', status: 'queued' })
    api.get.mockResolvedValueOnce({
      jobId: 'job-1',
      jobType: 'artist_promoters',
      artistId: 61,
      params: { limit: 50, debug: false },
      status: 'completed',
      result: completedResult,
      createdAt: '2026-07-21T10:00:00.000Z',
      updatedAt: '2026-07-21T10:00:01.000Z',
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
})
