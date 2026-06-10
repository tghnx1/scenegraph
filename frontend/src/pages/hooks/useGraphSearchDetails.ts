import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchEntityDetail } from '../../api/entityDetails'
import { SEARCH_RESULT_LIMIT, SEARCH_RESULT_MAX_LIMIT, fetchSearch } from '../../api/search'
import { useApi } from '../../hooks/useApi'
import { useGraphStore } from '../../store/graphStore'
import type { EntityDetail } from '../../types/entityDetail'
import { graphEntityId, type NodeType } from '../../types/graph'
import type { SearchEntityType, SearchResponse, SearchResult, SearchSort } from '../../types/search'
import { useDebouncedValue } from './useDebouncedValue'

const EMPTY_SEARCH_RESPONSE: SearchResponse = { query: '', results: [] }
const SEARCH_ENTITY_TYPES: SearchEntityType[] = ['artist', 'venue', 'promoter', 'event']

function createDefaultLimitsByType() {
  return {
    artist: SEARCH_RESULT_LIMIT,
    venue: SEARCH_RESULT_LIMIT,
    promoter: SEARCH_RESULT_LIMIT,
    event: SEARCH_RESULT_LIMIT,
  }
}

function createEmptyResultsByType() {
  return {
    artist: [],
    venue: [],
    promoter: [],
    event: [],
  } satisfies Record<SearchEntityType, SearchResult[]>
}

export function useGraphSearchDetails() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const [dropdownSearchType, setDropdownSearchType] = useState<SearchEntityType>('artist')
  const [dropdownSearchSort, setDropdownSearchSort] = useState<SearchSort>('relevance')
  const [dropdownSearchLimitsByType, setDropdownSearchLimitsByType] = useState(createDefaultLimitsByType)
  const [dropdownSearchResultsByType, setDropdownSearchResultsByType] = useState(createEmptyResultsByType)
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
    () => (submittedQuery ? fetchSearch(submittedQuery) : Promise.resolve(EMPTY_SEARCH_RESPONSE)),
    [submittedQuery]
  )

  const trimmedSearchValue = searchValue.trim()
  const trimmedSubmittedQuery = submittedQuery.trim()
  const dropdownSearchLimit = dropdownSearchLimitsByType[dropdownSearchType]
  const shouldFetchDropdownSearch =
    debouncedSearchValue.length >= 2 &&
    debouncedSearchValue === trimmedSearchValue &&
    debouncedSearchValue !== trimmedSubmittedQuery

  const { data: dropdownSearchData, isLoading: isDropdownSearchLoading } = useApi<SearchResponse>(
    () => (
      shouldFetchDropdownSearch
        ? fetchSearch(debouncedSearchValue, dropdownSearchLimit, dropdownSearchType, dropdownSearchSort)
        : Promise.resolve(EMPTY_SEARCH_RESPONSE)
    ),
    [debouncedSearchValue, dropdownSearchLimit, dropdownSearchSort, dropdownSearchType, shouldFetchDropdownSearch]
  )

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

  useEffect(() => {
    setDropdownSearchLimitsByType(createDefaultLimitsByType())
    setDropdownSearchResultsByType(createEmptyResultsByType())
  }, [debouncedSearchValue, dropdownSearchSort])

  useEffect(() => {
    if (!shouldFetchDropdownSearch || !dropdownSearchData) return

    setDropdownSearchResultsByType((currentResults) => ({
      ...currentResults,
      [dropdownSearchType]: dropdownSearchData.results,
    }))
  }, [dropdownSearchData, dropdownSearchType, shouldFetchDropdownSearch])

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

  const handleLoadMoreDropdownResults = useCallback(() => {
    setDropdownSearchLimitsByType((currentLimits) => ({
      ...currentLimits,
      [dropdownSearchType]: Math.min(currentLimits[dropdownSearchType] + SEARCH_RESULT_LIMIT, SEARCH_RESULT_MAX_LIMIT),
    }))
  }, [dropdownSearchType])

  const handleSelectSearchResult = useCallback(
    (result: SearchResult) => {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', result.name)
      nextParams.set('selectedType', result.type)
      nextParams.set('selectedId', String(result.id))
      nextParams.delete('artist')
      setSearchValue(result.name)
      setSelected(null)
      setSearchParams(nextParams, { replace: false })
    },
    [searchParams, setSearchParams, setSelected]
  )

  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const dropdownSearchResults = shouldFetchDropdownSearch
    ? SEARCH_ENTITY_TYPES.flatMap((type) => dropdownSearchResultsByType[type])
    : []
  const activeDropdownSearchResults = dropdownSearchResultsByType[dropdownSearchType]
  const canLoadMoreDropdownResults =
    shouldFetchDropdownSearch &&
    !isDropdownWaiting &&
    !isDropdownSearchLoading &&
    dropdownSearchLimit < SEARCH_RESULT_MAX_LIMIT &&
    activeDropdownSearchResults.length >= dropdownSearchLimit
  const isDetailsSearchLoading = isSearchLoading || isSelectedEntityDetailLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const detailsSelectedNode = selectedEntityDetail ? null : selectedNode

  return {
    detailsPanelProps: {
      searchQuery: submittedQuery,
      searchResults: searchData?.results ?? [],
      isSearchLoading: isDetailsSearchLoading,
      searchError,
      selectedNode: detailsSelectedNode,
      selectedEntityDetail,
    },
    searchFormProps: {
      value: searchValue,
      onChange: handleSearchValueChange,
      onSubmit: handleSearchSubmit,
      onClear: handleClearSearch,
      showClear: hasActiveSearchState,
      results: dropdownSearchResults,
      isLoading: isDropdownWaiting || isDropdownSearchLoading,
      activeResultType: dropdownSearchType,
      onActiveResultTypeChange: setDropdownSearchType,
      activeSort: dropdownSearchSort,
      onActiveSortChange: setDropdownSearchSort,
      showResultsWhenEmpty: shouldFetchDropdownSearch,
      canLoadMore: canLoadMoreDropdownResults,
      onLoadMore: handleLoadMoreDropdownResults,
      onSelectResult: handleSelectSearchResult,
    },
    selectedNode,
    setSelected,
  }
}
