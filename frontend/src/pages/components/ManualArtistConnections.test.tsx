import { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ManualArtistConnections } from './ManualArtistConnections'
import type { ManualArtistConnection } from '../../api/manualArtistConnections'
import type { SearchResponse } from '../../types/search'

const searchMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/search', () => ({
  fetchSearch: searchMock,
}))

const baseProps = {
  isLoading: false,
  pendingArtistId: null,
  error: null,
}

const initialConnections: ManualArtistConnection[] = [
  {
    sourceArtistId: 61,
    connectedArtistId: 77,
    connectedArtistName: 'Neon Duo',
    createdAt: '2026-07-21T10:00:00.000Z',
    updatedAt: '2026-07-21T10:00:00.000Z',
  },
]

const searchResponse: SearchResponse = {
  query: 'neon',
  results: [
    {
      id: 88,
      type: 'artist',
      name: 'Neon Wave',
      biography_normalized: 'Berlin-based electronic live act and DJ duo.',
      biography_preview: 'Berlin-based electronic live act and DJ duo.',
      genres: ['New Wave', 'EBM'],
      latest_event_title: 'Night Drive',
    },
  ],
}

function Harness() {
  const [connections, setConnections] = useState<ManualArtistConnection[]>(initialConnections)

  return (
    <ManualArtistConnections
      {...baseProps}
      connections={connections}
      onAdd={async (connectedArtistId) => {
        const artist = searchResponse.results.find((result) => result.id === connectedArtistId)
        if (!artist) return
        setConnections((current) =>
          current.some((connection) => connection.connectedArtistId === connectedArtistId)
            ? current
            : [
                ...current,
                {
                  sourceArtistId: 61,
                  connectedArtistId: artist.id,
                  connectedArtistName: artist.name,
                  createdAt: '2026-07-22T10:00:00.000Z',
                  updatedAt: '2026-07-22T10:00:00.000Z',
                },
              ],
        )
      }}
      onRemove={async (connectedArtistId) => {
        setConnections((current) => current.filter((connection) => connection.connectedArtistId !== connectedArtistId))
      }}
    />
  )
}

describe('ManualArtistConnections', () => {
  beforeEach(() => {
    searchMock.mockReset()
    searchMock.mockImplementation(async (query: string) => {
      if (query.toLowerCase().includes('neon')) {
        return searchResponse
      }

      return { query, results: [] } satisfies SearchResponse
    })
  })

  it('shows existing connections while the search form is closed', () => {
    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    expect(screen.getByText('Artists you know')).toBeInTheDocument()
    expect(screen.getByText('Add 3–5 artists you know, collaborate with, or who can recommend you to promoters.')).toBeInTheDocument()
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add artist' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Search and add an artist' })).not.toBeInTheDocument()
  })

  it('keeps existing connections visible after opening add artist', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Add artist' }))

    expect(screen.getByRole('heading', { name: 'Search and add an artist' })).toBeInTheDocument()
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument()
  })

  it('keeps the search form open after adding an artist and shows the new connection', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Add artist' }))
    const input = screen.getByPlaceholderText('Search artist name...')
    await user.type(input, 'neon')

    const resultButton = await screen.findByRole('button', { name: /Neon Wave/i })
    await user.click(resultButton)

    await waitFor(() => expect(input).toHaveValue(''))
    expect(screen.getByRole('heading', { name: 'Search and add an artist' })).toBeInTheDocument()
    expect(screen.getByText('Neon Wave')).toBeInTheDocument()
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument()
  })

  it('closes the search form when Done is clicked and keeps all connection cards visible', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Add artist' }))
    await user.click(screen.getByRole('button', { name: 'Done' }))

    expect(screen.queryByRole('heading', { name: 'Search and add an artist' })).not.toBeInTheDocument()
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add artist' })).toBeInTheDocument()
  })

  it('removing a connection still works', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Remove Neon Duo from manual connections' }))

    await waitFor(() => expect(screen.queryByText('Neon Duo')).not.toBeInTheDocument())
  })
})
