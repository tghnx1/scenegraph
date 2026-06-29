import { useEffect, useState } from 'react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import { displayDateToIsoDate, isoDateToDisplayDate } from '@/shared/lib/validation'
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
  date: 'Dates in DD.MM.YYYY format.',
}
const EGO_FILTER_DESCRIPTIONS = {
  ...FILTER_DESCRIPTIONS,
  genre: 'Genre filtering is disabled while viewing an ego graph.',
  date: 'Date filtering is disabled while viewing an ego graph.',
}

const groupClass = 'grid gap-2'
const labelClass = 'inline-flex items-center gap-1.5 text-[0.72rem] uppercase tracking-[0.14em] text-[var(--accent)]'
const inputClass = 'min-h-9 min-w-0 rounded-[10px] border border-[var(--control-border)] bg-[var(--surface-input)] px-3 py-2 text-sm font-[inherit] text-[var(--text)] outline-none transition-[border-color,box-shadow] placeholder:text-[var(--text-placeholder)] focus:border-[var(--focus-border)] focus:shadow-[0_0_0_3px_var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-60'
const filterButtonClass = 'cursor-pointer rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-3 py-2 text-sm font-semibold text-[var(--text)] transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)] disabled:cursor-not-allowed disabled:opacity-50'

interface GraphFiltersProps {
  filters: GraphParams
  genres: GenreOption[]
  isGenresLoading: boolean
  genresError: string | null
  displayedDateRange: { from: string; to: string } | null
  isEgoGraphMode?: boolean
  onChange: (filters: GraphParams) => void
}

interface GraphDateInputProps {
  label: string
  value: string
  onCommit: (value: string | undefined) => void
  disabled?: boolean
}

export function GraphDateInput({ label, value, onCommit, disabled = false }: GraphDateInputProps) {
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
      className={inputClass}
      type="text"
      value={inputValue}
      inputMode="numeric"
      maxLength={10}
      placeholder="DD.MM.YYYY"
      pattern="\d{2}\.\d{2}\.\d{4}"
      disabled={disabled}
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
  isEgoGraphMode = false,
  onChange,
}: GraphFiltersProps) {
  const [activeInfo, setActiveInfo] = useState<keyof typeof FILTER_DESCRIPTIONS | null>(null)
  const filterDescriptions = isEgoGraphMode ? EGO_FILTER_DESCRIPTIONS : FILTER_DESCRIPTIONS
  const areEventFiltersDisabled = isEgoGraphMode
  const updateFilter = (next: Partial<GraphParams>) => {
    onChange({ ...filters, ...next })
  }
  const genreOptions = genres.length > 0 ? genres : FALLBACK_GENRE_OPTIONS
  const dateFromValue = filters.dateFrom ?? displayedDateRange?.from ?? ''
  const dateToValue = filters.dateTo ?? displayedDateRange?.to ?? ''
  const [draftDateFrom, setDraftDateFrom] = useState(dateFromValue)
  const [draftDateTo, setDraftDateTo] = useState(dateToValue)

  useEffect(() => {
    setDraftDateFrom(dateFromValue)
    setDraftDateTo(dateToValue)
  }, [dateFromValue, dateToValue])

  const renderInfoButton = (key: keyof typeof FILTER_DESCRIPTIONS, label: string) => {
    const isActive = activeInfo === key

    return (
      <span className="relative inline-grid place-items-center normal-case tracking-normal">
        <button
          type="button"
          className="grid size-5 cursor-help place-items-center rounded-full border border-[var(--surface-border)] bg-[var(--surface-panel)] p-0 text-[var(--text-muted)] opacity-90 transition-all hover:-translate-y-px hover:border-[var(--focus-border)] hover:bg-[var(--surface-strong)] hover:text-[var(--text)] hover:opacity-100 focus-visible:-translate-y-px focus-visible:border-[var(--focus-border)] focus-visible:bg-[var(--surface-strong)] focus-visible:text-[var(--text)] focus-visible:opacity-100 focus-visible:outline-none"
          aria-label={`Explain ${label}`}
          aria-expanded={isActive}
          onClick={() => setActiveInfo(isActive ? null : key)}
          onBlur={() => setActiveInfo(null)}
        >
          <span className="block size-[13px] rounded-full text-center font-serif text-[0.7rem] font-extrabold italic leading-[13px]" aria-hidden="true">i</span>
        </button>
        {isActive && (
          <span className={cn(
            'absolute top-[calc(100%+8px)] z-20 w-[min(300px,calc(100vw-48px))] rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-left text-[0.82rem] font-semibold leading-snug text-[var(--text)] shadow-[var(--surface-shadow)] max-[700px]:left-1/2 max-[700px]:right-auto max-[700px]:top-auto max-[700px]:bottom-[calc(100%+8px)] max-[700px]:z-[120] max-[700px]:max-h-[45dvh] max-[700px]:w-[min(300px,calc(100vw-32px))] max-[700px]:-translate-x-1/2 max-[700px]:translate-y-0 max-[700px]:overflow-y-auto',
            key === 'limit' ? 'right-0' : 'left-0',
          )} role="tooltip">
            {filterDescriptions[key]}
          </span>
        )}
      </span>
    )
  }

  return (
    <section className="grid gap-3.5 border-b border-[var(--surface-border-soft)] pb-4 min-[1100px]:grid-cols-[minmax(180px,1fr)_minmax(300px,1.35fr)_auto] min-[1100px]:items-end min-[1100px]:border-b-0 min-[1100px]:pb-0" aria-label="Graph filters">
      <div className={cn(groupClass, areEventFiltersDisabled && 'opacity-45 blur-[0.4px] grayscale')}>
        <span className={labelClass}>
          Filter by Genre
          {renderInfoButton('genre', 'Filter by Genre')}
        </span>
        <select
          className={inputClass}
          value={filters.genre ?? ''}
          onChange={(event) => updateFilter({ genre: event.target.value || undefined })}
          disabled={areEventFiltersDisabled || (isGenresLoading && genreOptions.length === 0)}
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
          <span className="text-[0.78rem] text-[var(--text-muted)]">Using fallback genres.</span>
        )}
      </div>

      <form
        className={cn(groupClass, 'min-w-0', areEventFiltersDisabled && 'opacity-45 blur-[0.4px] grayscale')}
        onSubmit={(event) => {
          event.preventDefault()
          if (areEventFiltersDisabled) return
          updateFilter({
            dateFrom: draftDateFrom || undefined,
            dateTo: draftDateTo || undefined,
          })
        }}
      >
        <span className={labelClass}>
          Filter by Date
          {renderInfoButton('date', 'Filter by Date')}
        </span>
        <div className="grid grid-cols-[repeat(2,minmax(0,1fr))_auto] gap-2">
          <GraphDateInput
            label="Date from"
            value={draftDateFrom}
            onCommit={(dateFrom) => setDraftDateFrom(dateFrom ?? '')}
            disabled={areEventFiltersDisabled}
          />
          <GraphDateInput
            label="Date to"
            value={draftDateTo}
            onCommit={(dateTo) => setDraftDateTo(dateTo ?? '')}
            disabled={areEventFiltersDisabled}
          />
          <Button
            type="submit"
            size="sm"
            className="rounded-full"
            disabled={areEventFiltersDisabled || (draftDateFrom === dateFromValue && draftDateTo === dateToValue)}
          >
            Apply dates
          </Button>
        </div>
      </form>

      <div className={groupClass}>
        <span className={labelClass}>
          Event Limit
          {renderInfoButton('limit', 'Event Limit')}
        </span>
        <div className="flex flex-wrap gap-2">
          {LIMIT_OPTIONS.map((limit) => (
            <button
              key={limit}
              type="button"
              className={cn(filterButtonClass, filters.limit === limit && 'border-[var(--selection-border-strong)] bg-[var(--selection-soft)] text-[var(--text)]')}
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
