import {render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {describe, expect, it, vi} from 'vitest'
import {MemoryRouter} from 'react-router-dom'
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
      events: [
        { id: 11, title: 'Club Night', event_date: '2026-07-01', venue_name: 'Kater' },
      ],
      connected_artists: [
        { id: 201, name: 'ALIS.', shared_events: 3 },
      ],
      genres: ['Techno'],
      extracted_tags: {
        style: ['dark disco'],
        genre: ['Techno'],
        label: ['Kekos Club'],
        residency: ['We Are Gays'],
      },
    })

    const onBiographyStatusChange = vi.fn()

    render(
      <MemoryRouter>
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
        />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Artist profile')).toBeInTheDocument()
    expect(screen.getByRole('heading', {name: 'Holywanderer', level: 2})).toBeInTheDocument()
    expect(screen.queryByText('Describe your sound, roles, labels, collectives and residencies.')).not.toBeInTheDocument()
    expect(screen.queryByText('Add artists you genuinely know or have worked with. More relevant connections can broaden your promoter network.')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', {name: 'Biography'})).toBeInTheDocument()
    expect(screen.getByText('No biography added yet.')).toBeInTheDocument()
    expect(screen.getByText('Describe your sound, styles, roles, labels, collectives and residencies.')).toBeInTheDocument()
    expect(screen.getByText('Extracted tags and linked events that feed into your recommendations:')).toBeInTheDocument()
    expect(screen.getByText('Genres')).toBeInTheDocument()
    expect(screen.getByText('Techno')).toBeInTheDocument()
    expect(screen.getByText('Styles')).toBeInTheDocument()
    expect(screen.getByText('dark disco')).toBeInTheDocument()
    expect(screen.getByText('Labels')).toBeInTheDocument()
    expect(screen.getByText('Kekos Club')).toBeInTheDocument()
    expect(screen.getByText('Residencies')).toBeInTheDocument()
    expect(screen.getByText('We Are Gays')).toBeInTheDocument()
    expect(screen.getByText('Artists you played with')).toBeInTheDocument()
    expect(screen.getByText('ALIS.')).toBeInTheDocument()
    expect(screen.getByText('3 shared events')).toBeInTheDocument()
    expect(screen.getByText('Biography')).toBeInTheDocument()
    expect(screen.getByText('Events')).toBeInTheDocument()
    expect(screen.getByText('Club Night')).toBeInTheDocument()
    expect(screen.getByText('2026-07-01 · Kater')).toBeInTheDocument()

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
      extracted_tags: {},
    })

    render(
      <MemoryRouter>
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
        />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Long bio text.')).toBeInTheDocument()
    expect(screen.getByText('Artist profile')).toBeInTheDocument()
    expect(screen.getByText('Biography')).toBeInTheDocument()
    expect(screen.queryByRole('button', {name: 'Add biography'})).not.toBeInTheDocument()
    expect(screen.queryByRole('button', {name: 'Edit biography'})).not.toBeInTheDocument()
    expect(screen.getByText('Artists you played with')).toBeInTheDocument()
    expect(screen.getByText('No linked artists yet.')).toBeInTheDocument()
  })
})
