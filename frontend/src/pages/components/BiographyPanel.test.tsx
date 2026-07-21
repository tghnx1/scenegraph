import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BiographyPanel } from './BiographyPanel'

const fetchArtistBiography = vi.hoisted(() => vi.fn())
const updateArtistBiography = vi.hoisted(() => vi.fn())

vi.mock('../../api/entityDetails', () => ({
  fetchArtistBiography,
  updateArtistBiography,
}))

vi.mock('./ManualArtistConnections', () => ({
  ManualArtistConnections: () => <div data-testid="manual-connections" />,
}))

describe('BiographyPanel', () => {
  it('shows one add-bio action and hides the old setup banner when biography is empty', async () => {
    fetchArtistBiography.mockResolvedValueOnce({
      type: 'artist',
      id: 61,
      name: 'Holywanderer',
      bio: '',
      event_count: 0,
      events: [],
      connected_artists: [],
      genres: [],
    })

    const onBiographyStatusChange = vi.fn()

    render(
      <BiographyPanel
        artistId={61}
        selectedArtistName="Holywanderer"
        manualConnections={{
          connections: [],
          isLoading: false,
          pendingArtistId: null,
          error: null,
          onAdd: vi.fn(),
          onRemove: vi.fn(),
        }}
        canEditBiography
        hasApprovedArtistProfile
        onBiographyStatusChange={onBiographyStatusChange}
      />,
    )

    expect(await screen.findByText('No biography added yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add bio' })).toBeInTheDocument()
    expect(screen.queryByText('Complete your artist profile')).not.toBeInTheDocument()
    expect(screen.queryByText('Linked artists')).not.toBeInTheDocument()
    expect(screen.queryByText('No linked artists yet.')).not.toBeInTheDocument()
    expect(screen.getByTestId('manual-connections')).toBeInTheDocument()

    await waitFor(() => {
      expect(onBiographyStatusChange).toHaveBeenCalledWith({ isLoading: false, hasBiography: false })
    })
  })

  it('hides the linked artists section when there are no linked artists', async () => {
    fetchArtistBiography.mockResolvedValueOnce({
      type: 'artist',
      id: 61,
      name: 'Holywanderer',
      bio: 'Long bio text.',
      event_count: 0,
      events: [],
      connected_artists: [],
      genres: [],
    })

    render(
      <BiographyPanel
        artistId={61}
        selectedArtistName="Holywanderer"
        manualConnections={{
          connections: [],
          isLoading: false,
          pendingArtistId: null,
          error: null,
          onAdd: vi.fn(),
          onRemove: vi.fn(),
        }}
        canEditBiography={false}
        hasApprovedArtistProfile
      />,
    )

    expect(await screen.findByText('Long bio text.')).toBeInTheDocument()
    expect(screen.queryByText('Linked artists')).not.toBeInTheDocument()
    expect(screen.queryByText('No linked artists yet.')).not.toBeInTheDocument()
  })
})
