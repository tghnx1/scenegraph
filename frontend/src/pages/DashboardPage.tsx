import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchSearch } from '../api/search.ts'
import { useApi } from '../hooks/useApi.ts'
import { useGraphStore } from '../store/graphStore.ts'
import type { SearchResponse, SearchResult } from '../types/search.ts'
import { GraphSidebarDetails } from './components/DetailsPanel.tsx'
import { SearchQueryForm } from './components/SearchQueryForm.tsx'
import { useDebouncedValue } from './hooks/useDebouncedValue.ts'

const stats = [
  { label: 'Connected nodes', value: '0' },
  { label: 'Shared events', value: '0' },
  { label: 'Recommendations', value: '0' },
]

const legendItems = [
  { label: 'Artists', className: 'artist' },
  { label: 'Venues', className: 'venue' },
  { label: 'Events', className: 'event' },
]

export function DashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const [selectedSearchResult, setSelectedSearchResult] = useState<SearchResult | null>(null)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)

  const {
    data: searchData,
    isLoading: isSearchLoading,
    error: searchError,
  } = useApi<SearchResponse>(
    () => (submittedQuery ? fetchSearch(submittedQuery) : Promise.resolve({ query: '', results: [] })),
    [submittedQuery]
  )

  const { data: dropdownSearchData, isLoading: isDropdownSearchLoading } = useApi<SearchResponse>(
    () => (debouncedSearchValue.length >= 2 ? fetchSearch(debouncedSearchValue) : Promise.resolve({ query: '', results: [] })),
    [debouncedSearchValue]
  )

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

  const handleSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const nextQuery = searchValue.trim()
      if (!nextQuery) return
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', nextQuery)
      nextParams.delete('artist')
      nextParams.delete('selectedType')
      nextParams.delete('selectedId')
      setSelectedSearchResult(null)
      setSelected(null)
      setSearchParams(nextParams, { replace: true })
    },
    [searchParams, searchValue, setSearchParams, setSelected]
  )

  const handleClearSearch = useCallback(() => {
    setSearchValue('')
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('q')
    nextParams.delete('artist')
    nextParams.delete('selectedType')
    nextParams.delete('selectedId')
    setSearchParams(nextParams, { replace: true })
    setSelectedSearchResult(null)
    setSelected(null)
  }, [searchParams, setSearchParams, setSelected])

  const handleSearchValueChange = useCallback((nextValue: string) => {
    setSearchValue(nextValue)
  }, [])

  const handleSelectSearchResult = useCallback(
    (result: SearchResult) => {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', result.label)
      nextParams.set('selectedType', result.type)
      nextParams.set('selectedId', result.id)
      nextParams.delete('artist')
      setSearchValue(result.label)
      setSelectedSearchResult(result)
      setSelected(null)
      setSearchParams(nextParams, { replace: true })
    },
    [searchParams, setSearchParams, setSelected]
  )

  const searchResults = searchData?.results ?? []
  const trimmedSearchValue = searchValue.trim()
  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const dropdownSearchResults = debouncedSearchValue === trimmedSearchValue ? dropdownSearchData?.results ?? [] : []
  const detailSearchResults = selectedSearchResult ? [selectedSearchResult] : searchResults
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)

  return (
    <div className="dashboard-page">
      <section className="dashboard-grid" aria-label="Dashboard overview">
        <article className="dashboard-panel profile-panel">
          <div className="panel-heading">
            <span className="search-query-label">Profile</span>
            <button type="button">Edit</button>
          </div>
          <h2>Artist biography</h2>
          <p>Self biography and claimed account fields appear here.</p>
          <div className="profile-fields">
            <span>Name</span>
            <span>Genres</span>
            <span>Location</span>
          </div>
        </article>

        <article className="dashboard-panel context-panel">
          <div className="panel-heading">
            <span className="search-query-label">Node details</span>
          </div>
          <GraphSidebarDetails
            searchQuery={submittedQuery}
            searchResults={detailSearchResults}
            isSearchLoading={isSearchLoading}
            searchError={searchError}
            selectedNode={null}
            selectedArtist={null}
            isArtistLoading={false}
            artistError={null}
            similarArtists={[]}
          />
        </article>

        <article className="dashboard-panel side-panel recommendations-panel">
          <div className="panel-heading">
            <span className="search-query-label">Recommendations</span>
            <span className="panel-status">Draft</span>
          </div>
          <div className="placeholder-list">
            <span>Recommended names</span>
            <span>A list of names/connections.</span>
          </div>
        </article>

        <article className="dashboard-panel stats-panel">
          <div className="panel-heading">
            <span className="search-query-label">Statistics</span>
            <span className="panel-status">Overview</span>
          </div>
          <div className="stat-grid">
            {stats.map((item) => (
              <div key={item.label} className="stat-tile">
                <strong>{item.value}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div className="chart-placeholder" aria-label="Chart placeholder" />
        </article>

        <section className="graph-workspace" aria-label="Dashboard graph workspace">
          <article className="dashboard-panel graph-panel">
            <SearchQueryForm
              inputId="dashboard-search-query-input"
              value={searchValue}
              onChange={handleSearchValueChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              showClear={hasActiveSearchState}
              results={dropdownSearchResults}
              isLoading={isDropdownWaiting || isDropdownSearchLoading}
              onSelectResult={handleSelectSearchResult}
            />

            <div className="panel-heading">
              <span className="search-query-label">Graph display</span>
              <div className="graph-panel-actions">
                <button type="button">Filter by date</button>
                <button type="button">Filter by limit</button>
              </div>
            </div>
            <div className="dashboard-graph-placeholder" />
            <div className="legend-bar">
              <strong>Legends bar</strong>
              <div>
                {legendItems.map((item) => (
                  <span key={item.label} className={`legend-dot ${item.className}`}>
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
          </article>
        </section>

        <article className="dashboard-panel side-panel communications-panel">
          <div className="panel-heading">
            <span className="search-query-label">Communications</span>
            <span className="panel-status">Inbox</span>
          </div>
          <div className="placeholder-list">
            <span>Clickable contact names</span>
            <span>Open a chat</span>
          </div>
        </article>

        <article className="dashboard-panel empty-panel" aria-label="Empty dashboard panel" />
      </section>
    </div>
  )
}
