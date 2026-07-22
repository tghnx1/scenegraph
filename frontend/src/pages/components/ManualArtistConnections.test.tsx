import {useState} from 'react'
import {MemoryRouter} from 'react-router-dom'
import {render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {beforeEach, describe, expect, it, vi} from 'vitest'
import {ManualArtistConnections} from './ManualArtistConnections'
import type {ManualArtistConnection} from '../../api/manualArtistConnections'
import type {SearchResponse} from '../../types/search'

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

function makeConnections(count: number): ManualArtistConnection[] {
  return Array.from({length: count}, (_, index) => ({
    sourceArtistId: 61,
    connectedArtistId: 200 + index,
    connectedArtistName: `Artist ${index + 1}`,
    createdAt: '2026-07-21T10:00:00.000Z',
    updatedAt: '2026-07-21T10:00:00.000Z',
  }))
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

      return {query, results: []} satisfies SearchResponse
    })
  })

  it('shows exactly one Add artists tile when there are no connections', () => {
    render(
      <MemoryRouter>
        <ManualArtistConnections {...baseProps} connections={[]} onAdd={vi.fn()} onRemove={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Artists you know')).toBeInTheDocument()
    expect(screen.getByText('Add artists you genuinely know, have played with, collaborated with, or who could recommend you.')).toBeInTheDocument()
    expect(screen.getByText('More relevant connections can broaden your matches.')).toBeInTheDocument()
    expect(screen.getByText('Add at least 3 relevant artists to unlock recommendations.')).toBeInTheDocument()
    expect(screen.getByText('0 added')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Add artists'})).toBeInTheDocument()
    expect(screen.queryByRole('button', {name: 'Add artist'})).not.toBeInTheDocument()
  })

  it('shows progress text for different connection counts', () => {
    const {rerender} = render(
      <MemoryRouter>
        <ManualArtistConnections {...baseProps} connections={makeConnections(1)} onAdd={vi.fn()} onRemove={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Add 2 more to unlock recommendations.')).toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <ManualArtistConnections {...baseProps} connections={makeConnections(3)} onAdd={vi.fn()} onRemove={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Recommendations are unlocked. Adding more relevant artists can broaden your network.')).toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <ManualArtistConnections {...baseProps} connections={makeConnections(5)} onAdd={vi.fn()} onRemove={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Strong network context: 5 artists added.')).toBeInTheDocument()
  })

  it('renders the Add artists tile first in the grid before the connections', async () => {
    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    const grid = screen.getByTestId('manual-artist-connections-grid')
    expect(within(grid).getByRole('button', {name: 'Add artists'})).toBeInTheDocument()
    expect(grid.firstElementChild).toHaveAttribute('aria-label', 'Add artists')
    await screen.findByText('1 added')
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByText('Manual connection')).toHaveClass('sr-only')
  })

  it('opens the search panel and focuses the input when clicking Add artists', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', {name: 'Add artists'}))

    const input = screen.getByPlaceholderText('Search artist name...')
    await waitFor(() => expect(input).toHaveFocus())
    expect(screen.getByRole('heading', {name: 'Search and add an artist'})).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Done'})).toBeInTheDocument()
  })

  it('keeps the search panel open and focuses the existing input when Add artists is clicked again', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', {name: 'Add artists'}))
    const input = screen.getByPlaceholderText('Search artist name...')
    await waitFor(() => expect(input).toHaveFocus())

    await user.click(screen.getByRole('button', {name: 'Add artists'}))

    expect(screen.getAllByRole('heading', {name: 'Search and add an artist'})).toHaveLength(1)
    expect(input).toHaveFocus()
  })

  it('keeps existing connection cards visible while searching', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', {name: 'Add artists'}))

    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Done'})).toBeInTheDocument()
  })

  it('keeps the search open after adding an artist, clears the input, and appends the new artist', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', {name: 'Add artists'}))
    const input = screen.getByPlaceholderText('Search artist name...')
    await user.type(input, 'neon')

    const resultButton = await screen.findByRole('button', {name: /Neon Wave/i})
    await user.click(resultButton)

    await waitFor(() => expect(input).toHaveValue(''))
    expect(screen.getByRole('heading', {name: 'Search and add an artist'})).toBeInTheDocument()

    const grid = screen.getByTestId('manual-artist-connections-grid')
    const gridChildren = Array.from(grid.children)
    expect(gridChildren[0]).toHaveAttribute('aria-label', 'Add artists')
    expect(gridChildren[1]).toHaveTextContent('Neon Duo')
    expect(gridChildren[2]).toHaveTextContent('Neon Wave')
  })

  it('closes the search form with Done and keeps the grid visible', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', {name: 'Add artists'}))
    await user.click(screen.getByRole('button', {name: 'Done'}))

    expect(screen.queryByRole('heading', {name: 'Search and add an artist'})).not.toBeInTheDocument()
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Add artists'})).toBeInTheDocument()
  })

  it('removes only the selected connection and keeps Add artists first', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', {name: 'Remove Neon Duo from manual connections'}))

    await waitFor(() => expect(screen.queryByText('Neon Duo')).not.toBeInTheDocument())

    const grid = screen.getByTestId('manual-artist-connections-grid')
    expect(grid.firstElementChild).toHaveAttribute('aria-label', 'Add artists')
  })
})
