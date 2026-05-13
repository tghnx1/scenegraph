import { useState, type FormEvent } from 'react'
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
  const shouldShowDropdown = Boolean(onSelectResult && isDropdownOpen && value.trim().length >= 2 && (isLoading || results.length > 0))

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    setIsDropdownOpen(false)
    onSubmit(event)
  }

  const handleClear = () => {
    setIsDropdownOpen(false)
    onClear()
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
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setIsDropdownOpen(false)
            }
          }}
          onBlur={() => {
            window.setTimeout(() => setIsDropdownOpen(false), 120)
          }}
          placeholder="Search artists, venues, promoters, events..."
          aria-label="Search"
          aria-autocomplete="list"
          aria-expanded={shouldShowDropdown}
          aria-controls={`${inputId}-results`}
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
            results.slice(0, 8).map((result) => (
              <button
                key={`${result.type}-${result.id}`}
                type="button"
                className="search-query-option"
                role="option"
                aria-selected="false"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setIsDropdownOpen(false)
                  onSelectResult?.(result)
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
