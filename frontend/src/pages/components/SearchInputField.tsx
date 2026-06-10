import { useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'
import { SEARCH_RESULT_LIMIT } from '../../api/search'
import type { SearchEntityType, SearchResult } from '../../types/search'

const SEARCH_RESULT_TABS: { type: SearchEntityType; label: string }[] = [
  { type: 'artist', label: 'Artists' },
  { type: 'venue', label: 'Venues' },
  { type: 'promoter', label: 'Promoters' },
  { type: 'event', label: 'Events' },
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
  onSelectResult,
}: SearchInputFieldProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [activeResultIndex, setActiveResultIndex] = useState(-1)
  const limitedResults = results.slice(0, SEARCH_RESULT_LIMIT)
  const groupedResults = useMemo(
    () => Object.fromEntries(
      SEARCH_RESULT_TABS.map(({ type }) => [
        type,
        limitedResults.filter((result) => result.type === type),
      ])
    ) as Record<SearchEntityType, SearchResult[]>,
    [limitedResults]
  )
  const firstTabWithResults = SEARCH_RESULT_TABS.find(({ type }) => groupedResults[type].length > 0)?.type ?? 'artist'
  const [activeResultType, setActiveResultType] = useState<SearchEntityType>(firstTabWithResults)
  const visibleResults = groupedResults[activeResultType]
  const shouldShowDropdown = Boolean(onSelectResult && isDropdownOpen && value.trim().length >= 2 && (isLoading || results.length > 0))
  const activeResult = activeResultIndex >= 0 ? visibleResults[activeResultIndex] : undefined

  useEffect(() => {
    setActiveResultIndex(-1)
    setActiveResultType(firstTabWithResults)
  }, [value, results, firstTabWithResults])

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
    setActiveResultType(type)
    setActiveResultIndex(-1)
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
    <form className="search-query-form" onSubmit={handleSubmit}>
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
            window.setTimeout(() => setIsDropdownOpen(false), 120)
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
        <div id={`${inputId}-results`} className="search-query-dropdown">
          {isLoading && <div className="search-query-dropdown-status">Searching...</div>}
          {!isLoading && (
            <>
              <div className="search-query-tabs" role="tablist" aria-label="Search result types">
                {SEARCH_RESULT_TABS.map(({ type, label }) => {
                  const isActive = activeResultType === type
                  const resultCount = groupedResults[type].length

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
                      <strong>{resultCount}</strong>
                    </button>
                  )
                })}
              </div>

              <div
                id={`${inputId}-results-panel-${activeResultType}`}
                className="search-query-tab-panel"
                role="tabpanel"
                aria-labelledby={`${inputId}-tab-${activeResultType}`}
              >
                {visibleResults.length > 0 ? (
                  <div role="listbox" aria-label={`${activeResultType} search results`}>
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
                        <span>
                          <strong>{result.name}</strong>
                          {getResultMeta(result) && <small>{getResultMeta(result)}</small>}
                        </span>
                        <em>{result.type}</em>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="search-query-dropdown-status">No {activeResultType} matches</div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </form>
  )
}
