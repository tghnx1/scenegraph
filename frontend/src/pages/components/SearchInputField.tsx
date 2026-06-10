import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { SearchEntityType, SearchResult, SearchSort } from '../../types/search'

const SEARCH_RESULT_TABS: { type: SearchEntityType; label: string }[] = [
  { type: 'artist', label: 'Artists' },
  { type: 'venue', label: 'Venues' },
  { type: 'promoter', label: 'Promoters' },
  { type: 'event', label: 'Events' },
]

const SEARCH_SORT_OPTIONS: { value: SearchSort; label: string }[] = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'name_asc', label: 'Name A-Z' },
  { value: 'name_desc', label: 'Name Z-A' },
  { value: 'id_asc', label: 'ID ascending' },
  { value: 'id_desc', label: 'ID descending' },
]

interface SearchInputFieldProps {
  inputId: string
  label?: string
  placeholder?: string
  value: string
  onChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onClear: () => void
  showClear: boolean
  results?: SearchResult[]
  isLoading?: boolean
  activeResultType?: SearchEntityType
  onActiveResultTypeChange?: (type: SearchEntityType) => void
  activeSort?: SearchSort
  onActiveSortChange?: (sort: SearchSort) => void
  showResultTabs?: boolean
  showResultsWhenEmpty?: boolean
  canLoadMore?: boolean
  onLoadMore?: () => void
  onSelectResult?: (result: SearchResult) => void
}

function getResultMeta(result: SearchResult) {
  return result.id
}

export function SearchInputField({
  inputId,
  label = 'Search Database',
  placeholder = 'Search artists, venues, promoters, events...',
  value,
  onChange,
  onSubmit,
  onClear,
  showClear,
  results = [],
  isLoading = false,
  activeResultType: controlledActiveResultType,
  onActiveResultTypeChange,
  activeSort = 'relevance',
  onActiveSortChange,
  showResultTabs = true,
  showResultsWhenEmpty = false,
  canLoadMore = false,
  onLoadMore,
  onSelectResult,
}: SearchInputFieldProps) {
  const formRef = useRef<HTMLFormElement | null>(null)
  const dropdownRef = useRef<HTMLDivElement | null>(null)
  const pendingScrollTopRef = useRef<number | null>(null)
  const pendingResultCountRef = useRef<number | null>(null)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [activeResultIndex, setActiveResultIndex] = useState(-1)
  const groupedResults = useMemo(
    () => Object.fromEntries(
      SEARCH_RESULT_TABS.map(({ type }) => [
        type,
        results.filter((result) => result.type === type),
      ])
    ) as Record<SearchEntityType, SearchResult[]>,
    [results]
  )
  const firstTabWithResults = SEARCH_RESULT_TABS.find(({ type }) => groupedResults[type].length > 0)?.type ?? 'artist'
  const [internalActiveResultType, setInternalActiveResultType] = useState<SearchEntityType>(firstTabWithResults)
  const [hasManualTabSelection, setHasManualTabSelection] = useState(false)
  const activeResultType = controlledActiveResultType ?? internalActiveResultType
  const isActiveResultTypeControlled = controlledActiveResultType !== undefined
  const visibleResults = showResultTabs ? groupedResults[activeResultType] : results
  const shouldShowDropdown = Boolean(
    onSelectResult &&
    isDropdownOpen &&
    value.trim().length >= 2 &&
    (isLoading || results.length > 0 || showResultsWhenEmpty)
  )
  const activeResult = activeResultIndex >= 0 ? visibleResults[activeResultIndex] : undefined

  useEffect(() => {
    setActiveResultIndex(-1)
    setHasManualTabSelection(false)
  }, [value])

  useEffect(() => {
    setActiveResultIndex(-1)
  }, [value, results])

  useEffect(() => {
    if (!isActiveResultTypeControlled && !hasManualTabSelection) {
      setInternalActiveResultType(firstTabWithResults)
    }
  }, [firstTabWithResults, hasManualTabSelection, isActiveResultTypeControlled])

  useEffect(() => {
    if (pendingScrollTopRef.current === null) return
    if (isLoading) return
    if (pendingResultCountRef.current !== null && visibleResults.length <= pendingResultCountRef.current) return

    window.requestAnimationFrame(() => {
      if (dropdownRef.current && pendingScrollTopRef.current !== null) {
        dropdownRef.current.scrollTop = pendingScrollTopRef.current
      }

      pendingScrollTopRef.current = null
      pendingResultCountRef.current = null
    })
  }, [isLoading, visibleResults.length])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    setIsDropdownOpen(false)
    setActiveResultIndex(-1)
    onSubmit(event)
  }

  const handleClear = () => {
    setIsDropdownOpen(false)
    setActiveResultIndex(-1)
    onClear()
  }

  const selectResult = (result: SearchResult) => {
    setIsDropdownOpen(false)
    setActiveResultIndex(-1)
    onSelectResult?.(result)
  }

  const selectTab = (type: SearchEntityType) => {
    setHasManualTabSelection(true)
    if (isActiveResultTypeControlled) {
      onActiveResultTypeChange?.(type)
    } else {
      setInternalActiveResultType(type)
    }
    setActiveResultIndex(-1)
  }

  const handleSortChange = (sort: SearchSort) => {
    dropdownRef.current?.scrollTo({ top: 0 })
    pendingScrollTopRef.current = null
    pendingResultCountRef.current = null
    setActiveResultIndex(-1)
    onActiveSortChange?.(sort)
  }

  const handleLoadMore = () => {
    pendingScrollTopRef.current = dropdownRef.current?.scrollTop ?? null
    pendingResultCountRef.current = visibleResults.length
    setActiveResultIndex(-1)
    onLoadMore?.()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsDropdownOpen(false)
      setActiveResultIndex(-1)
      return
    }

    if (!onSelectResult || visibleResults.length === 0) {
      return
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setIsDropdownOpen(true)
      setActiveResultIndex((currentIndex) => (currentIndex + 1) % visibleResults.length)
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setIsDropdownOpen(true)
      setActiveResultIndex((currentIndex) => (currentIndex <= 0 ? visibleResults.length - 1 : currentIndex - 1))
      return
    }

    if (event.key === 'Enter' && shouldShowDropdown && activeResult) {
      event.preventDefault()
      selectResult(activeResult)
    }
  }

  return (
    <form className="search-query-form" ref={formRef} onSubmit={handleSubmit}>
      <label className="search-query-label" htmlFor={inputId}>
        {label}
      </label>
      <div className="search-query-box">
        <input
          id={inputId}
          className="search-query-input"
          type="search"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          value={value}
          onChange={(event) => {
            setIsDropdownOpen(true)
            onChange(event.target.value)
          }}
          onFocus={() => setIsDropdownOpen(true)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            window.setTimeout(() => {
              if (formRef.current?.contains(document.activeElement)) return
              setIsDropdownOpen(false)
            }, 120)
          }}
          placeholder={placeholder}
          aria-label="Search"
          aria-autocomplete="list"
          aria-expanded={shouldShowDropdown}
          aria-controls={`${inputId}-results-panel-${activeResultType}`}
          aria-activedescendant={activeResult ? `${inputId}-result-${activeResult.type}-${activeResult.id}` : undefined}
        />
        {showClear && (
          <button type="button" className="search-query-clear" onClick={handleClear} aria-label="Clear search and selection">
            x
          </button>
        )}
      </div>

      {shouldShowDropdown && (
        <div id={`${inputId}-results`} className="search-query-dropdown" ref={dropdownRef}>
          {isLoading && <div className="search-query-dropdown-status">Searching...</div>}
          {!isLoading && (
            <>
              {showResultTabs && (
                <div className="search-query-controls">
                  <div className="search-query-tabs" role="tablist" aria-label="Search result types">
                    {SEARCH_RESULT_TABS.map(({ type, label }) => {
                      const isActive = activeResultType === type

                      return (
                        <button
                          key={type}
                          id={`${inputId}-tab-${type}`}
                          type="button"
                          className={`search-query-tab${isActive ? ' search-query-tab--active' : ''}`}
                          role="tab"
                          aria-selected={isActive}
                          aria-controls={`${inputId}-results-panel-${type}`}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => selectTab(type)}
                        >
                          <span>{label}</span>
                        </button>
                      )
                    })}
                  </div>

                  <label className="search-query-sort">
                    <span>Sort</span>
                    <select
                      value={activeSort}
                      onChange={(event) => handleSortChange(event.target.value as SearchSort)}
                    >
                      {SEARCH_SORT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}

              <div
                id={`${inputId}-results-panel-${activeResultType}`}
                className="search-query-tab-panel"
                role={showResultTabs ? 'tabpanel' : undefined}
                aria-labelledby={showResultTabs ? `${inputId}-tab-${activeResultType}` : undefined}
              >
                {visibleResults.length > 0 ? (
                  <div role="listbox" aria-label={showResultTabs ? `${activeResultType} search results` : 'Search results'}>
                    {visibleResults.map((result, index) => (
                      <button
                        key={`${result.type}-${result.id}`}
                        id={`${inputId}-result-${result.type}-${result.id}`}
                        type="button"
                        className={`search-query-option${index === activeResultIndex ? ' search-query-option--active' : ''}`}
                        role="option"
                        aria-selected={index === activeResultIndex}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => {
                          selectResult(result)
                        }}
                      >
                        <span className="search-query-option-index">{index + 1}</span>
                        <span className="search-query-option-text">
                          <strong>{result.name}</strong>
                          {getResultMeta(result) && <small>{getResultMeta(result)}</small>}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="search-query-dropdown-status">No {activeResultType} matches</div>
                )}
              </div>

              {canLoadMore && (
                <button
                  type="button"
                  className="search-query-load-more"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={handleLoadMore}
                >
                  Load more results
                </button>
              )}
            </>
          )}
        </div>
      )}
    </form>
  )
}
