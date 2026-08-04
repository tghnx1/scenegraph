import type { FormEvent } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfilePage } from './ProfilePage'
let manualConnectionsValue = {
  connections: [] as Array<{ id: number }>,
  connectedArtistIds: new Set<number>(),
  isLoading: false,
  pendingArtistId: null as number | null,
  error: null as string | null,
  add: vi.fn(),
  remove: vi.fn(),
  toggle: vi.fn(),
}

const graphPanelMock = vi.hoisted(() => vi.fn(() => <div data-testid="graph-panel" />))
const recommendationPanelMock = vi.hoisted(() => vi.fn(() => <div data-testid="recommendations-panel" />))
const detailsPanelMock = vi.hoisted(() => vi.fn(({ selectedNode, selectedEntityDetail }: { selectedNode: { name: string } | null; selectedEntityDetail: { name: string } | null }) => (
  <div data-testid="details-panel">
    <span>{selectedEntityDetail?.name ?? selectedNode?.name ?? 'empty'}</span>
  </div>
)))
const manualConnectionsMock = vi.hoisted(() => vi.fn(() => manualConnectionsValue))

vi.mock('./hooks/useManualArtistConnections.ts', () => ({
  useManualArtistConnections: manualConnectionsMock,
}))
vi.mock('./components/SearchInputField.tsx', () => ({
  SearchInputField: ({ value, onChange, onSubmit, onClear }: {
    value: string
    onChange: (value: string) => void
    onSubmit: (event: FormEvent<HTMLFormElement>) => void
    onClear: () => void
  }) => (
    <form onSubmit={onSubmit}>
      <label>
        Search Database
        <input
          aria-label="Search Database"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <button type="button" onClick={onClear}>Clear search</button>
    </form>
  ),
}))
vi.mock('./components/DetailsPanel.tsx', () => ({ DetailsPanel: detailsPanelMock }))
vi.mock('./components/GraphPanel.tsx', () => ({ ScenegraphMapPanel: graphPanelMock }))
vi.mock('./components/RecommendationPanel.tsx', () => ({
  PromoterRecommendationsPanel: recommendationPanelMock,
}))
vi.mock('../api/auth', () => ({
  getMe: vi.fn(async () => ({
    role: 'artist',
    artist_id: null,
    artist_name: null,
  })),
}))
vi.mock('../api/entityDetails', () => ({
  fetchEntityDetail: vi.fn(async (_type: string, id: string) => ({
    id: Number(id),
    type: 'artist',
    name: 'Selected Artist',
  })),
}))
vi.mock('../api/search', () => ({
  SEARCH_RESULT_LIMIT: 10,
  SEARCH_RESULT_MAX_LIMIT: 100,
  fetchSearch: vi.fn(async (query: string) => ({ query, results: [] })),
}))

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    manualConnectionsValue = {
      connections: [],
      connectedArtistIds: new Set<number>(),
      isLoading: false,
      pendingArtistId: null,
      error: null,
      add: vi.fn(),
      remove: vi.fn(),
      toggle: vi.fn(),
    }
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(),
      length: 0,
    })
  })

  it('shows the graph workspace when the workspace query selects graph', () => {
    render(
      <MemoryRouter initialEntries={['/profile?workspace=graph&q=holy&selectedType=artist&selectedId=61']}>
        <ProfilePage />
      </MemoryRouter>,
    )

    expect(screen.queryByTestId('recommendations-panel')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Search Database')).toHaveValue('holy')
    expect(screen.getByTestId('details-panel')).toHaveTextContent('empty')
  })

  it('shows the recommendations workspace by default and keeps the search state out of the graph panel', async () => {
    render(
      <MemoryRouter initialEntries={['/profile?q=holy']}>
        <ProfilePage />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('recommendations-panel')).toBeInTheDocument()
    expect(screen.queryByLabelText('Search Database')).not.toBeInTheDocument()
    expect(screen.queryByTestId('details-panel')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Promoter recommendations workspace')).toHaveClass('col-span-full')
  })

  it('hides the graph workspace toggle when graph visibility is disabled', async () => {
    manualConnectionsValue = {
      connections: [{ id: 1 }, { id: 2 }, { id: 3 }],
      connectedArtistIds: new Set<number>([1, 2, 3]),
      isLoading: false,
      pendingArtistId: null,
      error: null,
      add: vi.fn(),
      remove: vi.fn(),
      toggle: vi.fn(),
    }

    render(
      <MemoryRouter initialEntries={['/profile?workspace=graph']}>
        <ProfilePage showGraphTab={false} />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('recommendations-panel')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Graph' })).not.toBeInTheDocument()
  })

})
