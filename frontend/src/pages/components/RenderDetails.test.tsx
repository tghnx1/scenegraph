import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { RenderDetails } from './RenderDetails'
import type { ArtistDetail } from '../../types/artist'
import type { PromoterDetail } from '../../types/promoter'

describe('RenderDetails', () => {
  it('shows biography-derived styles for selected artist details', () => {
    const result: ArtistDetail = {
      type: 'artist',
      id: 2178,
      name: 'Holywanderer',
      genres: [],
      bio: 'Artist biography',
      event_count: 0,
      events: [],
      connected_artists: [],
      extracted_tags: {
        style: ['Dark Disco', 'EBM', 'Italo'],
      },
    }

    render(
      <MemoryRouter>
        <RenderDetails result={result} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Dark Disco · EBM · Italo')).toBeInTheDocument()
    expect(screen.queryByText('No genres yet')).not.toBeInTheDocument()
  })

  it('keeps the empty-style fallback for selected artist details', () => {
    const result: ArtistDetail = {
      type: 'artist',
      id: 2178,
      name: 'Holywanderer',
      genres: ['Legacy genre'],
      bio: 'Artist biography',
      event_count: 0,
      events: [],
      connected_artists: [],
      extracted_tags: {
        style: [],
      },
    }

    render(
      <MemoryRouter>
        <RenderDetails result={result} />
      </MemoryRouter>,
    )

    expect(screen.getByText('No genres yet')).toBeInTheDocument()
    expect(screen.queryByText('Legacy genre')).not.toBeInTheDocument()
  })

  it('shows three promoter events by default and toggles the full list', async () => {
    const user = userEvent.setup()
    const result: PromoterDetail = {
      type: 'promoter',
      id: '42',
      name: 'Good Day Berlin Kultur und Veranstaltungen GmbH',
      event_count: 4,
      events: [
        {
          id: '1',
          title: 'Event 1',
          date: '2026-06-01T00:00:00.000Z',
          venue_name: 'Club A',
          artists: ['Artist A'],
          promoters: [],
        },
        {
          id: '2',
          title: 'Event 2',
          date: '2026-06-02T00:00:00.000Z',
          venue_name: 'Club B',
          artists: ['Artist B'],
          promoters: [],
        },
        {
          id: '3',
          title: 'Event 3',
          date: '2026-06-03T00:00:00.000Z',
          venue_name: 'Club C',
          artists: ['Artist C'],
          promoters: [],
        },
        {
          id: '4',
          title: 'Event 4',
          date: '2026-06-04T00:00:00.000Z',
          venue_name: 'Club D',
          artists: ['Artist D'],
          promoters: [],
        },
      ],
    }

    render(
      <MemoryRouter>
        <RenderDetails result={result} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', {name: 'Show all'})).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Event 1/i })).toHaveClass('w-full')
    expect(screen.getByText('Event 1')).toBeInTheDocument()
    expect(screen.getByText('Event 2')).toBeInTheDocument()
    expect(screen.getByText('Event 3')).toBeInTheDocument()
    expect(screen.queryByText('Event 4')).not.toBeInTheDocument()
    expect(screen.getByText('Showing 3 of 4 events.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', {name: 'Show all'}))

    expect(screen.getByRole('button', {name: 'Hide'})).toBeInTheDocument()
    expect(screen.getByText('Event 4')).toBeInTheDocument()
    expect(screen.queryByText('Showing 3 of 4 events.')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', {name: 'Hide'}))

    expect(screen.getByRole('button', {name: 'Show all'})).toBeInTheDocument()
    expect(screen.queryByText('Event 4')).not.toBeInTheDocument()
  })
})
