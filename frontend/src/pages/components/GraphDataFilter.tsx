import { useEffect, useState } from 'react'
import type { GraphParams } from '../../api/graph'
import type { GenreOption } from '../../api/genres'

const FALLBACK_GENRE_OPTIONS = [
  { name: 'Disco', value: 'disco' },
  { name: 'House', value: 'house' },
  { name: 'Techno', value: 'techno' },
  { name: 'Trance', value: 'trance' },
]

const LIMIT_OPTIONS = [100, 250, 500]
const FILTER_DESCRIPTIONS = {
  genre: 'Filter the by event genres. Choose All genres to undo the filter.',
  limit: 'Limit the number of events. Higher limits make the rendering heavier.',
}

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const DISPLAY_DATE_PATTERN = /^\d{2}\.\d{2}\.\d{4}$/

function isoDateToDisplayDate(value: string) {
  if (!ISO_DATE_PATTERN.test(value)) return value

  const [year, month, day] = value.split('-')
  return `${day}.${month}.${year}`
}

function displayDateToIsoDate(value: string) {
  if (!DISPLAY_DATE_PATTERN.test(value)) return null

  const [day, month, year] = value.split('.')
  const date = new Date(Number(year), Number(month) - 1, Number(day))

  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day)
  ) {
    return null
  }

  return `${year}-${month}-${day}`
}

interface GraphFiltersProps {
  filters: GraphParams
  genres: GenreOption[]
  isGenresLoading: boolean
  genresError: string | null
  displayedDateRange: { from: string; to: string } | null
  onChange: (filters: GraphParams) => void
}

interface GraphDateInputProps {
  label: string
  value: string
  onCommit: (value: string | undefined) => void
}

function GraphDateInput({ label, value, onCommit }: GraphDateInputProps) {
  const displayValue = isoDateToDisplayDate(value)
  const [inputValue, setInputValue] = useState(displayValue)

  useEffect(() => {
    setInputValue(displayValue)
  }, [displayValue])

  const handleChange = (nextValue: string) => {
    setInputValue(nextValue)

    if (!nextValue) {
      onCommit(undefined)
      return
    }

    const nextIsoDate = displayDateToIsoDate(nextValue)
    if (nextIsoDate) {
      onCommit(nextIsoDate)
    }
  }

  const handleBlur = () => {
    if (inputValue && !displayDateToIsoDate(inputValue)) {
      setInputValue(displayValue)
    }
  }

  return (
    <input
      className="graph-filter-date"
      type="text"
      value={inputValue}
      inputMode="numeric"
      maxLength={10}
      placeholder="DD.MM.YYYY"
      pattern="\d{2}\.\d{2}\.\d{4}"
      title="Use DD.MM.YYYY, for example 11.06.2026"
      onChange={(event) => handleChange(event.target.value)}
      onBlur={handleBlur}
      aria-label={label}
    />
  )
}

export function GraphFilters({
  filters,
  genres,
  isGenresLoading,
  genresError,
  displayedDateRange,
  onChange,
}: GraphFiltersProps) {
  const [activeInfo, setActiveInfo] = useState<keyof typeof FILTER_DESCRIPTIONS | null>(null)
  const updateFilter = (next: Partial<GraphParams>) => {
    onChange({ ...filters, ...next })
  }
  const genreOptions = genres.length > 0 ? genres : FALLBACK_GENRE_OPTIONS
  const dateFromValue = filters.dateFrom ?? displayedDateRange?.from ?? ''
  const dateToValue = filters.dateTo ?? displayedDateRange?.to ?? ''

  const renderInfoButton = (key: keyof typeof FILTER_DESCRIPTIONS, label: string) => {
    const isActive = activeInfo === key

    return (
      <span className={`graph-filter-info graph-filter-info--${key}`}>
        <button
          type="button"
          className="graph-filter-info-button"
          aria-label={`Explain ${label}`}
          aria-expanded={isActive}
          onClick={() => setActiveInfo(isActive ? null : key)}
          onBlur={() => setActiveInfo(null)}
        >
          <span aria-hidden="true">i</span>
        </button>
        {isActive && (
          <span className="graph-filter-info-popover" role="tooltip">
            {FILTER_DESCRIPTIONS[key]}
          </span>
        )}
      </span>
    )
  }

  return (
    <section className="graph-filter-panel" aria-label="Graph filters">
      <div className="graph-filter-group">
        <span className="graph-filter-label">
          Filter by Genre
          {renderInfoButton('genre', 'Filter by Genre')}
        </span>
        <select
          className="graph-filter-select"
          value={filters.genre ?? ''}
          onChange={(event) => updateFilter({ genre: event.target.value || undefined })}
          disabled={isGenresLoading && genreOptions.length === 0}
          aria-label="Genre"
        >
          <option value="">
            {isGenresLoading && genres.length === 0 ? 'Loading genres...' : 'All genres'}
          </option>
          {genreOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.name}
            </option>
          ))}
        </select>
        {genresError && (
          <span className="graph-filter-help">Using fallback genres.</span>
        )}
      </div>

      <div className="graph-filter-group">
        <span className="graph-filter-label">Filter by Date</span>
        <div className="graph-filter-date-row">
          <GraphDateInput
            label="Date from"
            value={dateFromValue}
            onCommit={(dateFrom) => updateFilter({ dateFrom })}
          />
          <GraphDateInput
            label="Date to"
            value={dateToValue}
            onCommit={(dateTo) => updateFilter({ dateTo })}
          />
        </div>
      </div>

      <div className="graph-filter-group">
        <span className="graph-filter-label">
          Event Limit
          {renderInfoButton('limit', 'Event Limit')}
        </span>
        <div className="graph-filter-buttons">
          {LIMIT_OPTIONS.map((limit) => (
            <button
              key={limit}
              type="button"
              className={`graph-filter-button${filters.limit === limit ? ' active' : ''}`}
              onClick={() => updateFilter({ limit })}
            >
              {limit}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
