import {useState} from 'react'
import type {DashboardStatus, DashboardTopListItem} from '../../types/status'

type DashboardStatisticsProps = {
  dashboardStatus: DashboardStatus | null
  isLoading: boolean
  hasError: boolean
}

type MetricRow = {
  label: string
  value: number | string | null | undefined
  percent?: number | null
  precision?: number
  description?: string
}

function PanelHeading({ label, status }: { label: string; status: string }) {
  return (
    <div className="panel-heading">
      <span className="search-query-label">{label}</span>
      <span className="panel-status">{status}</span>
    </div>
  )
}

function formatNumber(value: number | string | null | undefined, precision = 0) {
  if (typeof value === 'number') {
    return value.toLocaleString(undefined, {
      maximumFractionDigits: precision,
      minimumFractionDigits: precision,
    })
  }

  return value ?? '-'
}

function formatPercent(value: number | null | undefined) {
  return typeof value === 'number' ? `${value.toFixed(1)}%` : '-'
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, {year: 'numeric', month: 'short', day: 'numeric'})
}

function MetricList({items}: {items: MetricRow[]}) {
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null)

  return (
    <div className="dashboard-metric-list">
      {items.map((item) => {
        const isActive = activeTooltip === item.label

        return (
          <div key={item.label} className="dashboard-metric-row">
            <span>{item.label}</span>
            <strong>{formatNumber(item.value, item.precision)}</strong>
            <small>{formatPercent(item.percent)}</small>
            {item.description && (
              <div className="dashboard-metric-info">
                <button
                  type="button"
                  className="dashboard-info-button"
                  aria-label={`Explain ${item.label}`}
                  aria-expanded={isActive}
                  onClick={() => setActiveTooltip(isActive ? null : item.label)}
                  onBlur={() => setActiveTooltip(null)}
                >
                  <span aria-hidden="true">i</span>
                </button>
                {isActive && (
                  <div className="dashboard-info-popover" role="tooltip">
                    {item.description}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function TopList({label, items}: {label: string; items?: DashboardTopListItem[]}) {
  const entries = items?.slice(0, 5) ?? []

  return (
    <section className="dashboard-top-list">
      <div className="dashboard-section-heading">
        <span>{label}</span>
      </div>
      {entries.length > 0 ? (
        <ol>
          {entries.map((item) => (
            <li key={item.name}>
              <span>{item.name}</span>
              <strong>{formatNumber(item.value)}</strong>
            </li>
          ))}
        </ol>
      ) : (
        <div className="dashboard-empty-list">-</div>
      )}
    </section>
  )
}

function loadingItems(items: MetricRow[]) {
  return items.map((item) => ({...item, value: undefined, percent: null}))
}

export function DashboardStatistics({dashboardStatus, isLoading, hasError}: DashboardStatisticsProps) {
  const overviewStats = [
    { label: 'Total events', value: dashboardStatus?.events },
    { label: 'Total artists', value: dashboardStatus?.artists },
    { label: 'Total promoters', value: dashboardStatus?.promoters },
    { label: 'Total venues', value: dashboardStatus?.venues },
  ]

  const eventDateStats = [
    { label: 'First event date', value: formatDate(dashboardStatus?.first_event_date) },
    { label: 'Last event date', value: formatDate(dashboardStatus?.last_event_date) },
  ]

  const dataCoverage: MetricRow[] = [
    {
      label: 'Artists missing biography',
      value: dashboardStatus?.artists_no_bio,
      percent: dashboardStatus?.artists_no_bio_percent,
      description: 'Artists with empty biography.',
    },
    {
      label: 'Artists missing genres',
      value: dashboardStatus?.artists_no_genre,
      percent: dashboardStatus?.artists_no_genre_percent,
      description: 'Artists with no genre.',
    },
    {
      label: 'Events missing description',
      value: dashboardStatus?.events_no_desc,
      percent: dashboardStatus?.events_no_desc_percent,
      description: 'Events with no description.',
    },
    {
      label: 'Events missing genres',
      value: dashboardStatus?.events_no_genres,
      percent: dashboardStatus?.events_no_genres_percent,
      description: 'Events with no genre.',
    },
  ]

  const networkHealth: MetricRow[] = [
    {
      label: 'Events without artists',
      value: dashboardStatus?.events_without_artists,
      percent: dashboardStatus?.events_without_artists_percent,
      description: 'Events with no artist links.',
    },
    {
      label: 'Events without promoters',
      value: dashboardStatus?.events_without_promoters,
      percent: dashboardStatus?.events_without_promoters_percent,
      description: 'Events with no promoter links.',
    },
    {
      label: 'Events without venues',
      value: dashboardStatus?.events_without_venues,
      percent: dashboardStatus?.events_without_venues_percent,
      description: 'Events with no venues links.',
    },
    {
      label: 'Avg artists per event',
      value: dashboardStatus?.avg_artists_per_event,
      precision: 2,
      description: 'The mean number of artist links per event (susceptible to outliers).',
    },
    {
      label: 'Median artists per event',
      value: dashboardStatus?.median_artists_per_event,
      precision: 1,
      description: 'The typical artist count per event (less susceptible to outliers).',
    },
    {
      label: 'Avg promoters per event',
      value: dashboardStatus?.avg_promoters_per_event,
      precision: 2,
      description: 'The mean number of promoter links per event.',
    },
    {
      label: 'Avg genres per event',
      value: dashboardStatus?.avg_genres_per_event,
      precision: 2,
      description: 'The mean number of (RA) genre links per event.',
    },
  ]

  const semanticCoverage: MetricRow[] = [
    {
      label: 'Artists with extracted tags',
      value: dashboardStatus?.artists_with_extracted_tags,
      percent: dashboardStatus?.artists_with_extracted_tags_percent,
      description: 'Artists that have semantic tags extracted from profile text, such as role, residency, label, or scene cues.',
    },
    {
      label: 'Artists with extracted genres',
      value: dashboardStatus?.artists_with_extracted_genres,
      percent: dashboardStatus?.artists_with_extracted_genres_percent,
      description: 'Artists that have inferred genre/style labels from the extraction pipeline.',
    },
    {
      label: 'Artist embeddings',
      value: dashboardStatus?.artist_embeddings,
      percent: dashboardStatus?.artist_embeddings_percent,
      description: 'Artists with vector embeddings used for semantic search and recommendations.',
    },
    {
      label: 'Event embeddings',
      value: dashboardStatus?.event_embeddings,
      percent: dashboardStatus?.event_embeddings_percent,
      description: 'Events with vector embeddings used for semantic similarity.',
    },
    {
      label: 'Event extracted tags',
      value: dashboardStatus?.events_with_extracted_tags,
      percent: dashboardStatus?.events_with_extracted_tags_percent,
      description: 'Events with semantic tags produced by the extraction pipeline.',
    },
    {
      label: 'Event extracted genres',
      value: dashboardStatus?.events_with_extracted_genres,
      percent: dashboardStatus?.events_with_extracted_genres_percent,
      description: 'Events with inferred genre/style labels from extraction.',
    },
    {
      label: 'Recommendation feedback rows',
      value: dashboardStatus?.recommendation_feedback_rows,
      percent: dashboardStatus?.recommendation_feedback_rows_percent,
      description: 'Stored user feedback entries for recommendation candidates.',
    },
  ]

  return (
    <>
      <article className="dashboard-panel dashboard-panel-full">
        <PanelHeading label="Dataset Overview" status="General metrics" />
        <div className="dashboard-overview">
          {overviewStats.map((item) => (
            <div key={item.label} className="dashboard-stat-card">
              <span>{item.label}</span>
              <strong>{isLoading || hasError ? '-' : formatNumber(item.value)}</strong>
            </div>
          ))}
          <div className="dashboard-stat-card dashboard-date-card">
            {eventDateStats.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{isLoading || hasError ? '-' : item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </article>

      <article className="dashboard-panel">
        <PanelHeading label="Data Coverage" status="Missing entries/Information completeness" />
        <MetricList items={isLoading || hasError ? loadingItems(dataCoverage) : dataCoverage} />
      </article>

      <article className="dashboard-panel">
        <PanelHeading label="Network Health" status="Connectivity" />
        <MetricList items={isLoading || hasError ? loadingItems(networkHealth) : networkHealth} />
      </article>

      <article className="dashboard-panel">
        <PanelHeading label="Semantic Coverage" status="Extraction/Embedding readiness" />
        <MetricList items={isLoading || hasError ? loadingItems(semanticCoverage) : semanticCoverage} />
      </article>

      <article className="dashboard-panel">
        <PanelHeading label="Top List" status="Scene distribution" />
        <div className="dashboard-top-grid">
          <TopList label="Top 5 RA genre" items={dashboardStatus?.top_ra_genres} />
          <TopList label="Top 5 extracted genre" items={dashboardStatus?.top_extracted_genres} />
          <TopList label="Top 5 venues" items={dashboardStatus?.top_venues} />
          <TopList label="Top 5 promoters" items={dashboardStatus?.top_promoters} />
        </div>
      </article>
    </>
  )
}
