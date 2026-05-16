import { useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { SearchResult } from '../../types/search.ts'

interface SearchQueryFormProps {
  inputId: string
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
  if (result.type === 'artist') {
    return result.genres.join(' · ') || `${result.eventCount} events`
  }
  if (result.type === 'venue') {
    return [result.district, `${result.eventCount} events`].filter(Boolean).join(' · ')
  }
  if (result.type === 'promoter') {
    return `${result.eventCount} events`
  }
  return result.date
}

export function SearchQueryForm({
  inputId,
  value,
  onChange,
  onSubmit,
  onClear,
  showClear,
  results = [],
  isLoading = false,
  onSelectResult,
}: SearchQueryFormProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [activeResultIndex, setActiveResultIndex] = useState(-1)
  const visibleResults = results.slice(0, 8)
  const shouldShowDropdown = Boolean(onSelectResult && isDropdownOpen && value.trim().length >= 2 && (isLoading || results.length > 0))
  const activeResult = activeResultIndex >= 0 ? visibleResults[activeResultIndex] : undefined

  useEffect(() => {
    setActiveResultIndex(-1)
  }, [value, results])

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
        Search Database
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
          placeholder="Search artists, venues, promoters, events..."
          aria-label="Search"
          aria-autocomplete="list"
          aria-expanded={shouldShowDropdown}
          aria-controls={`${inputId}-results`}
          aria-activedescendant={activeResult ? `${inputId}-result-${activeResult.type}-${activeResult.id}` : undefined}
        />
        {showClear && (
          <button type="button" className="search-query-clear" onClick={handleClear} aria-label="Clear search and selection">
            x
          </button>
        )}
      </div>

      {shouldShowDropdown && (
        <div id={`${inputId}-results`} className="search-query-dropdown" role="listbox">
          {isLoading && <div className="search-query-dropdown-status">Searching...</div>}
          {!isLoading &&
            visibleResults.map((result, index) => (
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
                  <strong>{result.label}</strong>
                  <small>{getResultMeta(result)}</small>
                </span>
                <em>{result.type}</em>
              </button>
            ))}
        </div>
      )}
    </form>
  )
}
