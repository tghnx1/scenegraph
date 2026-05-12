import type { GraphParams } from '../../../api/graph.ts'

const GENRE_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'Techno', value: 'techno' },
  { label: 'House', value: 'house' },
  { label: 'Trance', value: 'trance' },
  { label: 'Disco', value: 'disco' },
]

const LIMIT_OPTIONS = [100, 250, 500, 1000]

interface GraphFiltersProps {
  filters: GraphParams
  onChange: (filters: GraphParams) => void
}

export function GraphFilters({ filters, onChange }: GraphFiltersProps) {
  const updateFilter = (next: Partial<GraphParams>) => {
    onChange({ ...filters, ...next })
  }

  return (
    <section className="graph-filter-panel" aria-label="Graph filters">
      <div className="graph-filter-group">
        <span className="graph-filter-label">Genre</span>
        <div className="graph-filter-buttons">
          {GENRE_OPTIONS.map((option) => {
            const isActive = (filters.genre ?? '') === option.value
            return (
              <button
                key={option.value || 'all'}
                type="button"
                className={`graph-filter-button${isActive ? ' active' : ''}`}
                onClick={() => updateFilter({ genre: option.value || undefined })}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="graph-filter-group">
        <span className="graph-filter-label">Date</span>
        <div className="graph-filter-date-row">
          <input
            className="graph-filter-date"
            type="date"
            value={filters.dateFrom ?? ''}
            max={filters.dateTo}
            onChange={(event) => updateFilter({ dateFrom: event.target.value || undefined })}
            aria-label="Date from"
          />
          <input
            className="graph-filter-date"
            type="date"
            value={filters.dateTo ?? ''}
            min={filters.dateFrom}
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
