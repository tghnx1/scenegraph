import type {DashboardEntity, DashboardStatus} from '../../types/dashboardComposition'
import {OverviewChart, type OverviewChartItem} from './OverviewChart'

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
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Dataset Overview</span>
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
