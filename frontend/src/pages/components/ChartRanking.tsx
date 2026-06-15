import {useState} from 'react'
import type {DashboardRankingItem} from '../../types/dashboardStats'

type DashboardRankingBarChartProps = {
  items?: DashboardRankingItem[]
  rankingLabel: string
}

function itemLabel(item: DashboardRankingItem) {
  return item.label ?? item.name ?? String(item.id ?? '-')
}

function itemValue(item: DashboardRankingItem) {
  const value = item.value ?? item.count
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }

  return 0
}

function formatValue(value: number) {
  return value.toLocaleString(undefined, {maximumFractionDigits: 2})
}

export function DashboardRankingBarChart({items, rankingLabel}: DashboardRankingBarChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const chartId = rankingLabel.replace(/[^a-z0-9]+/gi, '-').toLowerCase()
  const entries = (items ?? []).slice(0, 5).map((item) => ({
    item,
    label: itemLabel(item),
    value: itemValue(item),
  }))
  const maximum = Math.max(...entries.map((entry) => entry.value), 0)

  if (entries.length === 0) {
    return <p className="mb-0 mt-3 text-sm text-[var(--text-muted)]">No ranking data available.</p>
  }

  return (
    <ol
      className="mt-3 grid list-none gap-2 p-0"
      aria-label={`${rankingLabel} horizontal bar chart`}
    >
      {entries.map((entry, index) => {
        const width = maximum > 0 ? `${(entry.value / maximum) * 100}%` : '0%'
        const isActive = activeIndex === index

        return (
          <li className="grid grid-cols-[1rem_minmax(0,1fr)_auto] items-center gap-2" key={entry.item.id ?? `${entry.label}-${index}`}>
            <span className="text-[0.68rem] font-semibold text-[var(--text-muted)]">{index + 1}</span>
            <div className="relative min-w-0">
              <div className="h-5 overflow-hidden rounded-md border border-[var(--surface-border-soft)] bg-[var(--control-bg)]">
                <button
                  type="button"
                  className="block h-full min-w-1 cursor-help rounded-[5px] border-0 bg-[var(--accent)] p-0 opacity-75 outline-none transition-[opacity,filter] hover:opacity-100 hover:brightness-110 focus-visible:opacity-100 focus-visible:brightness-110"
                  style={{width}}
                  aria-label={`${entry.label}: ${formatValue(entry.value)}`}
                  aria-describedby={isActive ? `${chartId}-${index}-tooltip` : undefined}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseLeave={() => setActiveIndex(null)}
                  onFocus={() => setActiveIndex(index)}
                  onBlur={() => setActiveIndex(null)}
                />
              </div>
              {isActive && (
                <span
                  id={`${chartId}-${index}-tooltip`}
                  className="pointer-events-none absolute bottom-[calc(100%+6px)] left-0 z-20 w-max max-w-[min(220px,calc(100vw-48px))] rounded-lg border border-[var(--surface-border)] bg-[var(--surface-dropdown)] px-2.5 py-1.5 text-xs font-semibold leading-snug text-[var(--text)] shadow-[var(--surface-shadow)]"
                  role="tooltip"
                >
                  {entry.label}: {formatValue(entry.value)}
                </span>
              )}
            </div>
            <strong className="text-xs tabular-nums text-[var(--text)]">{formatValue(entry.value)}</strong>
          </li>
        )
      })}
    </ol>
  )
}
