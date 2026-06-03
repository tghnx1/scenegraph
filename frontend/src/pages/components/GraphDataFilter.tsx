import type { GraphParams } from '../../api/graph'
import type { GenreOption } from '../../api/genres'

const FALLBACK_GENRE_OPTIONS = [
  { name: 'Disco', value: 'disco' },
  { name: 'House', value: 'house' },
  { name: 'Techno', value: 'techno' },
  { name: 'Trance', value: 'trance' },
]

const LIMIT_OPTIONS = [100, 250, 500]

interface GraphFiltersProps {
  filters: GraphParams
  genres: GenreOption[]
  isGenresLoading: boolean
  genresError: string | null
  displayedDateRange: { from: string; to: string } | null
  onChange: (filters: GraphParams) => void
}

export function GraphFilters({
  filters,
  genres,
  isGenresLoading,
  genresError,
  displayedDateRange,
  onChange,
}: GraphFiltersProps) {
  const updateFilter = (next: Partial<GraphParams>) => {
    onChange({ ...filters, ...next })
  }
  const genreOptions = genres.length > 0 ? genres : FALLBACK_GENRE_OPTIONS
  const dateFromValue = filters.dateFrom ?? displayedDateRange?.from ?? ''
  const dateToValue = filters.dateTo ?? displayedDateRange?.to ?? ''

  return (
    <section className="graph-filter-panel" aria-label="Graph filters">
      <div className="graph-filter-group">
        <span className="graph-filter-label">Filter by Genre</span>
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
          <input
            className="graph-filter-date"
            type="date"
            value={dateFromValue}
            max={dateToValue}
            onChange={(event) => updateFilter({ dateFrom: event.target.value || undefined })}
            aria-label="Date from"
          />
          <input
            className="graph-filter-date"
            type="date"
            value={dateToValue}
            min={dateFromValue}
            onChange={(event) => updateFilter({ dateTo: event.target.value || undefined })}
            aria-label="Date to"
          />
        </div>
      </div>

      <div className="graph-filter-group">
        <span className="graph-filter-label">Event Limit</span>
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
