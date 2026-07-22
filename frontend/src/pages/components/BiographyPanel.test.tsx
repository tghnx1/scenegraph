import {render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {describe, expect, it, vi} from 'vitest'
import {BiographyPanel} from './BiographyPanel'

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
  it('shows the artist profile eyebrow and keeps the add/edit control inside the Biography section', async () => {
    const user = userEvent.setup()
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
        onProfileChanged={vi.fn()}
      />,
    )

    expect(await screen.findByText('Artist profile')).toBeInTheDocument()
    expect(screen.getByRole('heading', {name: 'Holywanderer', level: 2})).toBeInTheDocument()
    expect(screen.getByText('Improve your matches')).toBeInTheDocument()
    expect(screen.queryByText('Describe your sound, roles, labels, collectives and residencies.')).not.toBeInTheDocument()
    expect(screen.queryByText('Add artists you genuinely know or have worked with. More relevant connections can broaden your promoter network.')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', {name: 'Biography'})).toBeInTheDocument()
    expect(screen.getByText('No biography added yet.')).toBeInTheDocument()
    expect(screen.getByText('Describe your sound, styles, roles, labels, collectives and residencies.')).toBeInTheDocument()

    const biographySection = screen.getByRole('heading', {name: 'Biography'}).closest('section')
    expect(biographySection).not.toBeNull()
    expect(within(biographySection as HTMLElement).getByRole('button', {name: 'Add biography'})).toBeInTheDocument()
    expect(within(biographySection as HTMLElement).queryByRole('button', {name: 'Add bio'})).not.toBeInTheDocument()

    expect(screen.queryByRole('button', {name: 'Edit biography'})).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', {name: 'Add biography'}))
    expect(screen.getByPlaceholderText('Describe your sound and scene. Mention your styles, roles, labels, collectives, residencies, and relevant artistic background.')).toBeInTheDocument()
    expect(screen.getByText('Styles and genres')).toBeInTheDocument()
    expect(screen.getByText('Labels and imprints')).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('Describe your sound and scene. Mention your styles, roles, labels, collectives, residencies, and relevant artistic background.'), 'DJ from Berlin.')
    expect(screen.getByText('Your bio is quite short. A few specific sentences will give recommendations more useful context.')).toBeInTheDocument()

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
    expect(screen.getByText('Artist profile')).toBeInTheDocument()
    expect(screen.getByRole('heading', {name: 'Biography'})).toBeInTheDocument()
    expect(screen.queryByRole('button', {name: 'Add biography'})).not.toBeInTheDocument()
    expect(screen.queryByRole('button', {name: 'Edit biography'})).not.toBeInTheDocument()
    expect(screen.queryByText('Linked artists')).not.toBeInTheDocument()
    expect(screen.queryByText('No linked artists yet.')).not.toBeInTheDocument()
  })
})
