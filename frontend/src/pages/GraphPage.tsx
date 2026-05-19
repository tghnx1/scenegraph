import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi } from '../hooks/useApi.ts'
import { fetchArtist, fetchSimilarArtists } from '../api/artists.ts'
import { fetchSearch, fetchSearchResultById } from '../api/search.ts'
import { useGraphStore } from '../store/graphStore.ts'
import type { Artist, SimilarArtist } from '../types/artist.ts'
import type { SearchEntityType, SearchResponse, SearchResult } from '../types/search.ts'
import { useDebouncedValue } from './hooks/useDebouncedValue.ts'
import { GraphSidebarDetails } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/ScenegraphMapPanel.tsx'
import { SearchQueryForm } from './components/SearchQueryForm.tsx'

function isSearchEntityType(value: string | null): value is SearchEntityType {
  return value === 'artist' || value === 'venue' || value === 'promoter' || value === 'event'
}

export function GraphPage({ themeName }: { themeName?: string } = {}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedType = isSearchEntityType(selectedTypeParam) ? selectedTypeParam : null
  const selectedId = searchParams.get('selectedId') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const [selectedSearchResult, setSelectedSearchResult] = useState<SearchResult | null>(null)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)
  const selectedArtistId = selectedNode?.type === 'artist' ? selectedNode.id : null

  const { data: selectedArtist } = useApi<Artist | null>(
    () => (selectedArtistId ? fetchArtist(selectedArtistId) : Promise.resolve(null)),
    [selectedArtistId]
  )

  const { data: similarArtists } = useApi<SimilarArtist[]>(
    () => (selectedArtistId ? fetchSimilarArtists(selectedArtistId) : Promise.resolve([] as SimilarArtist[])),
    [selectedArtistId]
  )

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

  const {
    data: selectedResultFromUrl,
    isLoading: isSelectedResultLoading,
    error: selectedResultError,
  } = useApi<SearchResult | null>(
    () => (
      selectedType && selectedId
        ? fetchSearchResultById(selectedType, selectedId, submittedQuery)
        : Promise.resolve(null)
    ),
    [selectedType, selectedId, submittedQuery]
  )

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

  useEffect(() => {
    if (!selectedType || !selectedId) {
      setSelectedSearchResult(null)
    }
  }, [selectedType, selectedId])

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
      setSelectedSearchResult(null)
      setSelected(null)
      setSearchParams(nextParams, { replace: false })
    },
    [searchParams, setSearchParams, setSelected]
  )

  const similarArtistLinks = similarArtists ?? []
  const searchResults = searchData?.results ?? []
  const activeSelectedSearchResult =
    selectedSearchResult?.type === selectedType && selectedSearchResult.id === selectedId
      ? selectedSearchResult
      : selectedResultFromUrl
  const trimmedSearchValue = searchValue.trim()
  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const dropdownSearchResults = debouncedSearchValue === trimmedSearchValue ? dropdownSearchData?.results ?? [] : []
  const detailSearchResults = activeSelectedSearchResult ? [activeSelectedSearchResult] : searchResults
  const detailsSearchError = selectedResultError ?? searchError
  const isDetailsSearchLoading = isSelectedResultLoading || isSearchLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)

  return (
    <div className="graph-page-shell">
      <aside className="graph-sidebar">
        <article className="graph-sidebar-card">
          <div className="graph-sidebar-search">
            <SearchQueryForm
              inputId="graph-search-query-input"
              value={searchValue}
              onChange={handleSearchValueChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              showClear={hasActiveSearchState}
              results={dropdownSearchResults}
              isLoading={isDropdownWaiting || isDropdownSearchLoading}
              onSelectResult={handleSelectSearchResult}
            />
            {/* <p className="search-query-hint">Enter a name, then press Enter to update the search.</p> */}
          </div>

          <GraphSidebarDetails
            searchQuery={submittedQuery}
            searchResults={detailSearchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={activeSelectedSearchResult ? null : selectedNode}
            selectedArtist={selectedArtist}
            similarArtists={similarArtistLinks}
          />
        </article>
      </aside>

      <section className="graph-main">
        <ScenegraphMapPanel themeName={themeName} />
      </section>
    </div>
  )
}
