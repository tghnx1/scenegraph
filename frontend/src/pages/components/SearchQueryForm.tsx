import type { FormEvent } from 'react'

interface SearchQueryFormProps {
  inputId: string
  value: string
  onChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onClear: () => void
  showClear: boolean
}

export function SearchQueryForm({ inputId, value, onChange, onSubmit, onClear, showClear }: SearchQueryFormProps) {
  return (
    <form className="search-query-form" onSubmit={onSubmit}>
      <label className="search-query-label" htmlFor={inputId}>
        Search Database
      </label>
      <div className="search-query-box">
        <input
          id={inputId}
          className="search-query-input"
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Search artists, venues, promoters, events..."
          aria-label="Search"
        />
        {showClear && (
          <button type="button" className="search-query-clear" onClick={onClear} aria-label="Clear search and selection">
            x
          </button>
        )}
      </div>
    </form>
  )
}
