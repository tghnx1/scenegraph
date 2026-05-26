import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchEntityDetail } from '../api/entityDetails'
import { fetchSearch } from '../api/search'
import { useGraphStore } from '../store/graphStore'
import type { EntityDetail } from '../types/entityDetail'
import { graphEntityId, type NodeType } from '../types/graph'
import type { SearchResponse, SearchResult } from '../types/search'
import { useDebouncedValue } from './hooks/useDebouncedValue'
import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { SearchQueryForm } from './components/SearchQuery.tsx'

export function GraphPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedIdParam = searchParams.get('selectedId')
  const selectedDetailType = selectedNode
    ? selectedNode.type
    : selectedTypeParam
      ? selectedTypeParam
      : null
  const selectedDetailNodeId = selectedNode ? selectedNode.id : selectedIdParam
  const selectedDetailId = selectedDetailType && selectedDetailNodeId
    ? String(graphEntityId(selectedDetailNodeId, selectedDetailType as NodeType) ?? selectedDetailNodeId)
    : null

  const { data: selectedEntityDetail, isLoading: isSelectedEntityDetailLoading } = useApi<EntityDetail | null>(
    () => (
      selectedDetailType && selectedDetailId
        ? fetchEntityDetail(selectedDetailType as NodeType, selectedDetailId)
        : Promise.resolve(null)
    ),
    [selectedDetailType, selectedDetailId]
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
    () => (
      debouncedSearchValue.length >= 2 &&
        debouncedSearchValue === searchValue.trim() &&
        debouncedSearchValue !== submittedQuery.trim()
        ? fetchSearch(debouncedSearchValue)
        : Promise.resolve({ query: '', results: [] })
    ),
    [debouncedSearchValue, searchValue, submittedQuery]
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
    setSelected(null)
  }, [searchParams, setSearchParams, setSelected])

  const handleSearchValueChange = useCallback((nextValue: string) => {
    setSearchValue(nextValue)
  }, [])

  const handleSelectSearchResult = useCallback(
    (result: SearchResult) => {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', result.name)
      nextParams.set('selectedType', result.type)
      nextParams.set('selectedId', result.id)
      nextParams.delete('artist')
      setSearchValue(result.name)
      setSelected(null)
      setSearchParams(nextParams, { replace: false })
    },
    [searchParams, setSearchParams, setSelected]
  )

  const searchResults = searchData?.results ?? []
  const trimmedSearchValue = searchValue.trim()
  const trimmedSubmittedQuery = submittedQuery.trim()
  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const shouldFetchDropdownSearch =
    debouncedSearchValue.length >= 2 &&
    debouncedSearchValue === trimmedSearchValue &&
    debouncedSearchValue !== trimmedSubmittedQuery
  const dropdownSearchResults = shouldFetchDropdownSearch ? dropdownSearchData?.results ?? [] : []
  const detailsSearchError = searchError
  const isDetailsSearchLoading = isSearchLoading || isSelectedEntityDetailLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const detailsSelectedNode = selectedEntityDetail ? null : selectedNode

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

          <DetailsPanel
            searchQuery={submittedQuery}
            searchResults={searchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={detailsSelectedNode}
            selectedEntityDetail={selectedEntityDetail}
          />
        </article>
      </aside>

      <section className="graph-main">
        <ScenegraphMapPanel />
      </section>
    </div>
  )
}
