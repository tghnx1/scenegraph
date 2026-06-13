import {useEffect, useState} from 'react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/utils'
import type {DashboardEntity} from '../../types/dashboardComposition'
import {GraphDateInput} from './GraphDataFilter'

export type OverviewChartItem = {
  id: DashboardEntity
  label: string
  value: number | null | undefined
  color: string
}

type OverviewChartProps = {
  items: OverviewChartItem[]
  isUnavailable: boolean
  formatValue: (value: number | string | null | undefined) => string | number
  selectedItemIds: DashboardEntity[]
  onToggleItem: (id: DashboardEntity) => void
  dateFrom: string
  dateTo: string
  displayedDateFrom?: string
  displayedDateTo?: string
  onDateRangeChange: (dateFrom: string, dateTo: string) => void
}

type ChartMode = 'donut' | 'waffle' | 'stackedbar'

function polarToCartesian(center: number, radius: number, angleInDegrees: number) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180

  return {
    x: center + radius * Math.cos(angleInRadians),
    y: center + radius * Math.sin(angleInRadians),
  }
}

function describeChartSegment(
  center: number,
  outerRadius: number,
  innerRadius: number,
  startAngle: number,
  endAngle: number,
) {
  const outerStart = polarToCartesian(center, outerRadius, endAngle)
  const outerEnd = polarToCartesian(center, outerRadius, startAngle)
  const innerStart = polarToCartesian(center, innerRadius, startAngle)
  const innerEnd = polarToCartesian(center, innerRadius, endAngle)
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1'

  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 0 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerStart.x} ${innerStart.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 1 ${innerEnd.x} ${innerEnd.y}`,
    'Z',
  ].join(' ')
}

function buildWaffleCells(items: OverviewChartItem[], total: number) {
  const cellCount = 100

  if (total <= 0) {
    return Array<OverviewChartItem | null>(cellCount).fill(null)
  }

  const allocations = items.map((item) => {
    const exactCount = ((item.value ?? 0) / total) * cellCount

    return {
      item,
      count: Math.floor(exactCount),
      remainder: exactCount % 1,
    }
  })
  let remainingCells = cellCount - allocations.reduce((sum, allocation) => sum + allocation.count, 0)

  allocations
    .slice()
    .sort((a, b) => b.remainder - a.remainder)
    .forEach((allocation) => {
      if (remainingCells > 0) {
        allocation.count += 1
        remainingCells -= 1
      }
    })

  const cells = allocations.flatMap((allocation) => Array<OverviewChartItem>(allocation.count).fill(allocation.item))

  return [...cells, ...Array<null>(Math.max(0, cellCount - cells.length)).fill(null)].slice(0, cellCount)
}

export function OverviewChart({
  items,
  isUnavailable,
  formatValue,
  selectedItemIds,
  onToggleItem,
  dateFrom,
  dateTo,
  displayedDateFrom,
  displayedDateTo,
  onDateRangeChange,
}: OverviewChartProps) {
  const [activeStat, setActiveStat] = useState<string | null>(null)
  const [chartMode, setChartMode] = useState<ChartMode>('donut')
  const dateFromValue = dateFrom || displayedDateFrom || ''
  const dateToValue = dateTo || displayedDateTo || ''
  const [draftDateFrom, setDraftDateFrom] = useState(dateFromValue)
  const [draftDateTo, setDraftDateTo] = useState(dateToValue)

  useEffect(() => {
    setDraftDateFrom(dateFromValue)
    setDraftDateTo(dateToValue)
  }, [dateFromValue, dateToValue])
  const chartSize = 360
  const center = chartSize / 2
  const radius = 156
  const innerRadius = 94
  const ringRadius = (radius + innerRadius) / 2
  const ringWidth = radius - innerRadius
  const resolvedItems = isUnavailable ? [] : items.filter((item) => typeof item.value === 'number' && item.value > 0)
  const total = resolvedItems.reduce((sum, item) => sum + (item.value ?? 0), 0)
  const centerValue = isUnavailable ? '-' : formatValue(total)
  const waffleCells = buildWaffleCells(resolvedItems, total)
  let currentAngle = 0

  const chartModeControls = (
    <div className="grid gap-1 rounded-xl bg-[var(--surface-input)] p-1" role="group" aria-label="Dataset overview chart type">
        <Button
          type="button"
          size="sm"
          variant={chartMode === 'donut' ? 'default' : 'ghost'}
          className={cn('w-full justify-start rounded-lg', chartMode === 'donut' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]')}
          aria-pressed={chartMode === 'donut'}
          onClick={() => setChartMode('donut')}
        >
          Donut
        </Button>
        <Button
          type="button"
          size="sm"
          variant={chartMode === 'waffle' ? 'default' : 'ghost'}
          className={cn('w-full justify-start rounded-lg', chartMode === 'waffle' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]')}
          aria-pressed={chartMode === 'waffle'}
          onClick={() => setChartMode('waffle')}
        >
          Waffle
        </Button>
        <Button
          type="button"
          size="sm"
          variant={chartMode === 'stackedbar' ? 'default' : 'ghost'}
          className={cn('w-full justify-start rounded-lg', chartMode === 'stackedbar' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]')}
          aria-pressed={chartMode === 'stackedbar'}
          onClick={() => setChartMode('stackedbar')}
        >
          Stacked
        </Button>
      </div>
  )

  const entityFilters = (
    <div className="grid gap-2" aria-label="Dataset overview legend">
      <span className="inline-flex items-center gap-1.5 text-[0.72rem] uppercase tracking-[0.14em] text-[var(--accent)]">Filter by Entities</span>
      <div className="grid gap-2">
        {items.map((item) => (
          <button
            type="button"
            key={item.id}
            className={cn(
              'inline-flex min-w-0 items-center gap-2 rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-3 py-2 text-sm font-semibold text-[var(--text)] transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)] disabled:opacity-50',
              selectedItemIds.includes(item.id) && 'border-[var(--selection-border)] bg-[var(--selection-soft)]',
            )}
            aria-pressed={selectedItemIds.includes(item.id)}
            disabled={isUnavailable}
            onClick={() => onToggleItem(item.id)}
            onMouseEnter={() => !isUnavailable && setActiveStat(item.label)}
            onMouseLeave={() => setActiveStat(null)}
          >
            <i className="size-2.5 shrink-0 rounded-full" style={{background: item.color}} aria-hidden="true" />
            <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  )

  const dateFilter = (
    <form
      className="grid gap-2"
      aria-label="Filter dataset by event date range"
      onSubmit={(event) => {
        event.preventDefault()
        onDateRangeChange(draftDateFrom, draftDateTo)
      }}
    >
      <span className="inline-flex items-center gap-1.5 text-[0.72rem] uppercase tracking-[0.14em] text-[var(--accent)]">Filter by Date</span>
      <div className="grid gap-2">
        <GraphDateInput
          label="Date from"
          value={draftDateFrom}
          disabled={isUnavailable}
          onCommit={(value) => setDraftDateFrom(value ?? '')}
        />
        <GraphDateInput
          label="Date to"
          value={draftDateTo}
          disabled={isUnavailable}
          onCommit={(value) => setDraftDateTo(value ?? '')}
        />
      </div>
      <Button
        type="submit"
        size="sm"
        className="w-fit rounded-full"
        disabled={isUnavailable}
      >
        Apply dates
      </Button>
    </form>
  )

  return (
    <div className="grid grid-cols-[140px_minmax(0,1fr)_220px] items-stretch gap-4 max-[1050px]:grid-cols-1">
      <aside className="grid content-start gap-2 max-[1050px]:grid-cols-[auto_1fr]">
        <span className="inline-flex items-center gap-1.5 text-[0.72rem] uppercase tracking-[0.14em] text-[var(--accent)] max-[1050px]:self-center">Chart</span>
        {chartModeControls}
      </aside>
      <div className={cn(
        'relative grid min-h-[260px] place-items-center rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4',
        chartMode === 'stackedbar' && 'min-h-[180px]',
      )}>
        {chartMode === 'donut' ? (
          <>
            <svg
              className="size-[min(300px,100%)]"
              viewBox={`0 0 ${chartSize} ${chartSize}`}
              role="img"
              aria-label={`Dataset overview distribution, ${centerValue} total nodes`}
            >
              <circle className="fill-none stroke-[var(--control-bg)] [stroke-width:16]" cx={center} cy={center} r={ringRadius} />
              {total > 0 && resolvedItems.map((item) => {
                const value = item.value ?? 0
                const segmentAngle = (value / total) * 360
                const startAngle = currentAngle
                const endAngle = currentAngle + segmentAngle
                currentAngle = endAngle

                return segmentAngle >= 359.999 ? (
                  <circle
                    key={item.label}
                    className="cursor-pointer outline-none transition-opacity hover:opacity-80 focus-visible:opacity-80"
                    cx={center}
                    cy={center}
                    r={ringRadius}
                    fill="none"
                    style={{stroke: item.color, strokeWidth: ringWidth}}
                    tabIndex={0}
                    aria-label={`${item.label}: ${formatValue(value)}`}
                    onMouseEnter={() => setActiveStat(item.label)}
                    onMouseLeave={() => setActiveStat(null)}
                    onFocus={() => setActiveStat(item.label)}
                    onBlur={() => setActiveStat(null)}
                  />
                ) : (
                  <path
                    key={item.label}
                    className="cursor-pointer outline-none transition-opacity hover:opacity-80 focus-visible:opacity-80"
                    d={describeChartSegment(center, radius, innerRadius, startAngle, endAngle)}
                    fill={item.color}
                    tabIndex={0}
                    aria-label={`${item.label}: ${formatValue(value)}`}
                    onMouseEnter={() => setActiveStat(item.label)}
                    onMouseLeave={() => setActiveStat(null)}
                    onFocus={() => setActiveStat(item.label)}
                    onBlur={() => setActiveStat(null)}
                  />
                )
              })}
              <circle className="fill-[var(--surface-panel)]" cx={center} cy={center} r={innerRadius - 3} />
            </svg>
            <div className="absolute grid place-items-center text-center">
              <strong>{centerValue}</strong>
              <span className="text-xs text-[var(--text-muted)]">Total nodes</span>
            </div>
          </>
        ) : chartMode === 'waffle' ? (
          <div className="grid gap-3 justify-items-center">
            <div
              className="grid grid-cols-10 gap-1"
              role="img"
              aria-label={`Dataset overview waffle chart, ${centerValue} total nodes`}
            >
              {waffleCells.map((item, index) => (
                <span
                  key={`${item?.label ?? 'empty'}-${index}`}
                  className="size-4 rounded-[4px] bg-[var(--control-bg)] outline-none transition-transform hover:scale-110 focus-visible:scale-110"
                  style={item ? {background: item.color} : undefined}
                  tabIndex={item ? 0 : -1}
                  aria-label={item ? `${item.label}: ${formatValue(item.value)}` : undefined}
                  onMouseEnter={() => item && setActiveStat(item.label)}
                  onMouseLeave={() => setActiveStat(null)}
                  onFocus={() => item && setActiveStat(item.label)}
                  onBlur={() => setActiveStat(null)}
                />
              ))}
            </div>
            <div className="grid place-items-center text-center">
              <strong>{centerValue}</strong>
              <span className="text-xs text-[var(--text-muted)]">Total nodes</span>
            </div>
          </div>
        ) : (
          <div
            className="grid w-full gap-4"
            role="img"
            aria-label={`Dataset overview stacked bar chart, ${centerValue} total nodes`}
          >
            <div className="grid place-items-center text-center">
              <strong>{centerValue}</strong>
              <span className="text-xs text-[var(--text-muted)]">Total nodes</span>
            </div>
            <div className="flex h-8 w-full overflow-hidden rounded-full border border-[var(--surface-border)] bg-[var(--control-bg)]">
              {total > 0 ? resolvedItems.map((item) => {
                const value = item.value ?? 0
                const width = `${(value / total) * 100}%`

                return (
                  <span
                    key={item.label}
                    className="block h-full cursor-pointer outline-none transition-opacity hover:opacity-80 focus-visible:opacity-80"
                    style={{width, background: item.color}}
                    tabIndex={0}
                    aria-label={`${item.label}: ${formatValue(value)}`}
                    onMouseEnter={() => setActiveStat(item.label)}
                    onMouseLeave={() => setActiveStat(null)}
                    onFocus={() => setActiveStat(item.label)}
                    onBlur={() => setActiveStat(null)}
                  />
                )
              }) : (
                <span className="block h-full w-full bg-[var(--control-bg)]" />
              )}
            </div>
          </div>
        )}
        {activeStat && (
          <div className="absolute right-4 top-4 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-dropdown)] px-3 py-2 text-sm shadow-[var(--surface-shadow)]" role="tooltip">
            <span>{activeStat}</span>
            <strong>{formatValue(items.find((item) => item.label === activeStat)?.value)}</strong>
          </div>
        )}
      </div>
      <aside className="grid content-start gap-4">
        {entityFilters}
        {dateFilter}
      </aside>
    </div>
  )
}
