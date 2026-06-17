import type {DashboardEntity, DashboardStatus} from '../../types/dashboardComposition'
import {OverviewChart, type OverviewChartItem} from './ChartOverview'

type DashboardStatisticsProps = {
  dashboardStatus: DashboardStatus | null
  isLoading: boolean
  hasError: boolean
  selectedEntities: DashboardEntity[]
  onToggleEntity: (entity: DashboardEntity) => void
  dateFrom: string
  dateTo: string
  onDateRangeChange: (dateFrom: string, dateTo: string) => void
}

const ENTITY_OPTIONS: Array<{id: DashboardEntity; label: string; color: string}> = [
  {id: 'events', label: 'Events', color: 'var(--event)'},
  {id: 'artists', label: 'Artists', color: 'var(--artist)'},
  {id: 'promoters', label: 'Promoters', color: 'var(--promoter)'},
  {id: 'venues', label: 'Venues', color: 'var(--venue)'},
]

const DATASET_OVERVIEW_DESCRIPTION = 'Total events, artists, promoters, and venues in the current dataset.'

function formatNumber(value: number | string | null | undefined) {
  return typeof value === 'number' ? value.toLocaleString() : value ?? '-'
}

export function DashboardStatistics({
  dashboardStatus,
  isLoading,
  hasError,
  selectedEntities,
  onToggleEntity,
  dateFrom,
  dateTo,
  onDateRangeChange,
}: DashboardStatisticsProps) {
  const values = new Map(dashboardStatus?.items.map((item) => [item.id, item.value]))
  const overviewStats: OverviewChartItem[] = ENTITY_OPTIONS.map((item) => ({
    ...item,
    value: values.get(item.id),
  }))

  return (
    <article className="rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Dataset Overview</span>
          <span className="group relative inline-grid place-items-center normal-case tracking-normal">
            <button
              type="button"
              className="grid size-5 cursor-help place-items-center rounded-full border border-[var(--surface-border)] bg-[var(--surface-panel)] p-0 text-[var(--text-muted)] opacity-90 transition-all hover:-translate-y-px hover:border-[var(--focus-border)] hover:bg-[var(--surface-strong)] hover:text-[var(--text)] hover:opacity-100 focus-visible:-translate-y-px focus-visible:border-[var(--focus-border)] focus-visible:bg-[var(--surface-strong)] focus-visible:text-[var(--text)] focus-visible:opacity-100 focus-visible:outline-none"
              aria-label="Explain Dataset Overview"
              aria-describedby="dataset-overview-tooltip"
            >
              <span className="block size-[13px] rounded-full text-center font-serif text-[0.7rem] font-extrabold italic leading-[13px]" aria-hidden="true">i</span>
            </button>
            <span
              id="dataset-overview-tooltip"
              className="pointer-events-none absolute left-0 top-[calc(100%+8px)] z-20 hidden w-[min(300px,calc(100vw-48px))] rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-left text-[0.82rem] font-semibold leading-snug text-[var(--text)] shadow-[var(--surface-shadow)] group-hover:block group-focus-within:block"
              role="tooltip"
            >
              {DATASET_OVERVIEW_DESCRIPTION}
            </span>
          </span>
        </div>
        <span className="rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2.5 py-1 text-xs font-semibold text-[var(--text-muted)]">General metrics</span>
      </div>
      <div className="mt-4">
        <OverviewChart
          items={overviewStats}
          isUnavailable={isLoading || hasError}
          formatValue={formatNumber}
          selectedItemIds={selectedEntities}
          onToggleItem={onToggleEntity}
          dateFrom={dateFrom}
          dateTo={dateTo}
          displayedDateFrom={dashboardStatus?.from?.slice(0, 10)}
          displayedDateTo={dashboardStatus?.to?.slice(0, 10)}
          onDateRangeChange={onDateRangeChange}
        />
      </div>
    </article>
  )
}
