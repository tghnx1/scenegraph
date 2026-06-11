import {useState} from 'react'

export type OverviewChartItem = {
  label: string
  value: number | null | undefined
  color: string
}

type OverviewChartProps = {
  items: OverviewChartItem[]
  isUnavailable: boolean
  formatValue: (value: number | string | null | undefined) => string | number
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

export function OverviewChart({items, isUnavailable, formatValue}: OverviewChartProps) {
  const [activeStat, setActiveStat] = useState<string | null>(null)
  const [chartMode, setChartMode] = useState<ChartMode>('donut')
  const chartSize = 220
  const center = chartSize / 2
  const radius = 94
  const innerRadius = 56
  const ringRadius = (radius + innerRadius) / 2
  const ringWidth = radius - innerRadius
  const resolvedItems = isUnavailable ? [] : items.filter((item) => typeof item.value === 'number' && item.value > 0)
  const total = resolvedItems.reduce((sum, item) => sum + (item.value ?? 0), 0)
  const centerValue = isUnavailable ? '-' : formatValue(total)
  const waffleCells = buildWaffleCells(resolvedItems, total)
  let currentAngle = 0

  return (
    <div className="dashboard-overview-chart">
      <div className={`dashboard-chart-wrap dashboard-chart-wrap--${chartMode}`}>
        {chartMode === 'donut' ? (
          <>
            <svg
              className="dashboard-chart"
              viewBox={`0 0 ${chartSize} ${chartSize}`}
              role="img"
              aria-label={`Dataset overview distribution, ${centerValue} total nodes`}
            >
              <circle className="dashboard-chart-empty" cx={center} cy={center} r={ringRadius} />
              {total > 0 && resolvedItems.map((item) => {
                const value = item.value ?? 0
                const segmentAngle = (value / total) * 360
                const startAngle = currentAngle
                const endAngle = currentAngle + segmentAngle
                currentAngle = endAngle

                return segmentAngle >= 359.999 ? (
                  <circle
                    key={item.label}
                    className="dashboard-chart-segment"
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
                    className="dashboard-chart-segment"
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
              <circle className="dashboard-chart-center-fill" cx={center} cy={center} r={innerRadius - 3} />
            </svg>
            <div className="dashboard-chart-center">
              <strong>{centerValue}</strong>
              <span>Total nodes</span>
            </div>
          </>
        ) : chartMode === 'waffle' ? (
          <div className="dashboard-waffle-stack">
            <div
              className="dashboard-waffle-chart"
              role="img"
              aria-label={`Dataset overview waffle chart, ${centerValue} total nodes`}
            >
              {waffleCells.map((item, index) => (
                <span
                  key={`${item?.label ?? 'empty'}-${index}`}
                  className="dashboard-waffle-cell"
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
            <div className="dashboard-waffle-total">
              <strong>{centerValue}</strong>
              <span>Total nodes</span>
            </div>
          </div>
        ) : (
          <div
            className="dashboard-stackedbar-chart"
            role="img"
            aria-label={`Dataset overview stacked bar chart, ${centerValue} total nodes`}
          >
            <div className="dashboard-stackedbar-total">
              <strong>{centerValue}</strong>
              <span>Total nodes</span>
            </div>
            <div className="dashboard-stackedbar-bar">
              {total > 0 ? resolvedItems.map((item) => {
                const value = item.value ?? 0
                const width = `${(value / total) * 100}%`

                return (
                  <span
                    key={item.label}
                    className="dashboard-stackedbar-segment"
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
                <span className="dashboard-stackedbar-empty" />
              )}
            </div>
          </div>
        )}
        {activeStat && (
          <div className="dashboard-chart-tooltip" role="tooltip">
            <span>{activeStat}</span>
            <strong>{formatValue(items.find((item) => item.label === activeStat)?.value)}</strong>
          </div>
        )}
      </div>
      <div className="dashboard-chart-side">
        <div className="dashboard-chart-mode" role="group" aria-label="Dataset overview chart type">
          <button
            type="button"
            aria-pressed={chartMode === 'donut'}
            onClick={() => setChartMode('donut')}
          >
            Donut
          </button>
          <button
            type="button"
            aria-pressed={chartMode === 'waffle'}
            onClick={() => setChartMode('waffle')}
          >
            Waffle
          </button>
          <button
            type="button"
            aria-pressed={chartMode === 'stackedbar'}
            onClick={() => setChartMode('stackedbar')}
          >
            Stacked
          </button>
        </div>
        <div className="dashboard-chart-legend" aria-label="Dataset overview legend">
          {items.map((item) => (
            <span
              key={item.label}
              className="dashboard-chart-legend-item"
              onMouseEnter={() => !isUnavailable && setActiveStat(item.label)}
              onMouseLeave={() => setActiveStat(null)}
            >
              <i style={{background: item.color}} aria-hidden="true" />
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
