import type {
  DashboardMetric,
  DashboardRanking,
  DashboardMetrics,
} from '../../types/dashboardMetrics'
import {DashboardRankingBarChart} from './ChartRanking'

type DashboardMetricPanelsProps = {
  dashboardMetrics: DashboardMetrics | null
  isLoading: boolean
  hasError: boolean
}

const METRIC_GROUPS = [
  {
    title: 'Dataset Coverage',
    description: 'General measures representing the dataset',
    metrics: [
      {id: 'event_artist_links', label: 'Event-artist links'},
      {id: 'event_promoter_links', label: 'Event-promoter links'},
      {id: 'events_venue_links', label: 'Event-venue links'},
      {id: 'artists_without_event', label: 'Artists without an event'},
      {id: 'promoters_without_event', label: 'Promoters without an event'},
      {id: 'venues_without_event', label: 'Venues without an event'},
      {id: 'events_without_artists', label: 'Events without artists'},
      {id: 'events_without_promoter', label: 'Events without promoter'},
      {id: 'events_without_venue', label: 'Events without venue'},
    ],
  },
  {
    title: 'Network Health / Distribution',
    description: 'Basic statistical measures of the dataset',
    metrics: [
      {id: 'avg_events_per_artist', label: 'Average events per artist'},
      {id: 'med_events_per_artist', label: 'Median events per artist'},
      {id: 'avg_events_per_promoter', label: 'Average events per promoter'},
      {id: 'med_events_per_promoter', label: 'Median events per promoter'},
      {id: 'med_promoters_per_event', label: 'Median promoters per event'},
      {id: 'med_genres_per_event', label: 'Median genres per event'},
    ],
  },
  {
    title: 'Semantic Coverage / Recommendation Input Readiness',
    description: 'Semantic availabilty and graph recommendation signals',
    metrics: [
      {id: 'artists_without_tags', label: 'Artists without tags'},
      {id: 'artists_with_embedding_input', label: 'Artists with embedding input'},
      {id: 'artists_with_graph_input', label: 'Artists with graph input'},
      {id: 'artists_with_both_inputs', label: 'Artists with both inputs'},
      {id: 'events_without_tags', label: 'Events without tags'},
      {id: 'events_with_embedding_input', label: 'Events with embedding input'},
      {id: 'events_with_graph_input', label: 'Events with graph input'},
      {id: 'events_with_both_inputs', label: 'Events with both inputs'},
    ],
  },
] as const

const RANKINGS = [
  {id: 'top_source_genres', label: 'Top source genres'},
  {id: 'top_extracted_genres', label: 'Top extracted genres'},
  {id: 'top_venues', label: 'Top venues'},
  {id: 'top_promoters', label: 'Top promoters'},
  {id: 'top_artists', label: 'Top artists'},
] as const

const NETWORK_METRIC_PAIRS = [
  ['avg_events_per_artist', 'med_events_per_artist'],
  ['avg_events_per_promoter', 'med_events_per_promoter'],
] as const

const DATASET_METRIC_GROUPS = [
  ['event_artist_links', 'event_promoter_links', 'events_venue_links'],
  ['artists_without_event', 'promoters_without_event', 'venues_without_event'],
  ['events_without_artists', 'events_without_promoter', 'events_without_venue'],
] as const

const SEMANTIC_METRIC_GROUPS = [
  ['artists_without_tags', 'artists_with_embedding_input', 'artists_with_graph_input', 'artists_with_both_inputs'],
  ['events_without_tags', 'events_with_embedding_input', 'events_with_graph_input', 'events_with_both_inputs'],
] as const

const statusClass: Record<string, string> = {
  good: 'border-[var(--promoter-border)] bg-[var(--promoter-soft)]',
  warning: 'border-[var(--venue)] bg-[color-mix(in_srgb,var(--venue)_12%,transparent)]',
  critical: 'border-[var(--event-border-soft)] bg-[var(--event-soft)]',
  neutral: 'border-[var(--surface-border-soft)] bg-[var(--surface-soft)]',
}

function formatValue(value: number | string | null | undefined, maximumFractionDigits = 2) {
  if (typeof value === 'number') {
    return value.toLocaleString(undefined, {maximumFractionDigits})
  }

  return value ?? '-'
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return '-'

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function SubpanelHeading({title, description}: {title: string; description: string}) {
  return (
    <div className="flex items-center gap-1.5">
      <h2 className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">{title}</h2>
      <span className="group relative inline-grid place-items-center normal-case tracking-normal">
        <button
          type="button"
          className="grid size-5 cursor-help place-items-center rounded-full border border-[var(--surface-border)] bg-[var(--surface-panel)] p-0 text-[var(--text-muted)] opacity-90 transition-all hover:-translate-y-px hover:border-[var(--focus-border)] hover:bg-[var(--surface-strong)] hover:text-[var(--text)] hover:opacity-100 focus-visible:-translate-y-px focus-visible:border-[var(--focus-border)] focus-visible:bg-[var(--surface-strong)] focus-visible:text-[var(--text)] focus-visible:opacity-100 focus-visible:outline-none"
          aria-label={`Explain ${title}`}
          aria-describedby={`dashboard-subpanel-${title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`}
        >
          <span className="block size-[13px] rounded-full text-center font-serif text-[0.7rem] font-extrabold italic leading-[13px]" aria-hidden="true">i</span>
        </button>
        <span
          id={`dashboard-subpanel-${title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`}
          className="pointer-events-none absolute left-0 top-[calc(100%+8px)] z-20 hidden w-[min(300px,calc(100vw-48px))] rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-left text-[0.82rem] font-semibold leading-snug text-[var(--text)] shadow-[var(--surface-shadow)] group-hover:block group-focus-within:block"
          role="tooltip"
        >
          {description}
        </span>
      </span>
    </div>
  )
}

function MetricCard({
  metric,
  fallbackLabel,
  showStatus = true,
}: {
  metric?: DashboardMetric
  fallbackLabel: string
  showStatus?: boolean
}) {
  const cardStatus = showStatus ? metric?.status : 'neutral'

  return (
    <div className={`rounded-xl border p-3 ${statusClass[cardStatus ?? 'neutral'] ?? statusClass.neutral}`}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-[var(--text-muted)]">{metric?.label ?? fallbackLabel}</span>
        {showStatus && metric?.status && (
          <span className="rounded-full border border-current px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide opacity-75">
            {metric.status}
          </span>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <strong className="text-2xl text-[var(--text)]">{formatValue(metric?.value)}</strong>
        {typeof metric?.percentage === 'number' && (
          <span className="text-sm font-semibold text-[var(--text-muted)]">{formatValue(metric.percentage, 1)}%</span>
        )}
        {typeof metric?.total === 'number' && (
          <span className="text-xs text-[var(--text-muted)]">of {formatValue(metric.total)}</span>
        )}
      </div>
      {/* {hasDetails && (
        <details className="mt-3 border-t border-[var(--surface-border-soft)] pt-2 text-xs text-[var(--text-muted)]">
          <summary className="cursor-pointer font-semibold text-[var(--text)]">About this metric</summary>
          <div className="mt-2 grid gap-2 leading-relaxed">
            {metric?.meaning && <p className="m-0">{metric.meaning}</p>}
            {metric?.whyItMatters && <p className="m-0"><strong>Why it matters:</strong> {metric.whyItMatters}</p>}
            {metric?.fix && <p className="m-0"><strong>Suggested fix:</strong> {metric.fix}</p>}
          </div>
        </details>
      )} */}
    </div>
  )
}

function MetricCluster({
  ids,
  definitions,
  metrics,
  isUnavailable,
  showStatus = true,
}: {
  ids: readonly string[]
  definitions: Map<string, {label: string}>
  metrics: Map<string, DashboardMetric>
  isUnavailable: boolean
  showStatus?: boolean
}) {
  return (
    <section className="rounded-2xl border border-[var(--surface-border-soft)] bg-[color-mix(in_srgb,var(--surface-soft)_65%,transparent)] p-3">
      <div className="grid gap-3">
        {ids.map((id) => {
          const definition = definitions.get(id)
          return definition && (
            <MetricCard
              key={id}
              metric={isUnavailable ? undefined : metrics.get(id)}
              fallbackLabel={definition.label}
              showStatus={showStatus}
            />
          )
        })}
      </div>
    </section>
  )
}

function GroupedMetricGrid({
  group,
  metricGroups,
  metrics,
  isUnavailable,
  className = 'md:grid-cols-2',
  statuslessMetricGroups = [],
}: {
  group: MetricGroup
  metricGroups: readonly (readonly string[])[]
  metrics: Map<string, DashboardMetric>
  isUnavailable: boolean
  className?: string
  statuslessMetricGroups?: readonly string[]
}) {
  const metricDefinitions = new Map<string, {id: string; label: string}>(
    group.metrics.map((metric) => [metric.id, metric]),
  )

  return (
    <div className={`mt-4 grid gap-3 ${className}`}>
      {metricGroups.map((metricGroup) => (
        <MetricCluster
          key={metricGroup[0]}
          ids={metricGroup}
          definitions={metricDefinitions}
          metrics={metrics}
          isUnavailable={isUnavailable}
          showStatus={!statuslessMetricGroups.includes(metricGroup[0])}
        />
      ))}
    </div>
  )
}

function NetworkMetricGrid({
  group,
  metrics,
  isUnavailable,
}: {
  group: MetricGroup
  metrics: Map<string, DashboardMetric>
  isUnavailable: boolean
}) {
  const metricDefinitions = new Map(group.metrics.map((metric) => [metric.id, metric]))
  const pairedIds = new Set(NETWORK_METRIC_PAIRS.flatMap((pair) => pair))
  const unpairedMetrics = group.metrics.filter((metric) => !pairedIds.has(metric.id as (typeof NETWORK_METRIC_PAIRS)[number][number]))

  return (
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {NETWORK_METRIC_PAIRS.map((pair) => (
        <MetricCluster
          key={pair[0]}
          ids={pair}
          definitions={metricDefinitions}
          metrics={metrics}
          isUnavailable={isUnavailable}
          showStatus={false}
        />
      ))}
      <div className="grid gap-3">
        {unpairedMetrics.map((metric) => (
          <MetricCard
            key={metric.id}
            metric={isUnavailable ? undefined : metrics.get(metric.id)}
            fallbackLabel={metric.label}
            showStatus={false}
          />
        ))}
      </div>
    </div>
  )
}

function RankingCard({ranking, fallbackLabel}: {ranking?: DashboardRanking; fallbackLabel: string}) {
  const label = ranking?.label ?? fallbackLabel

  return (
    <section className="rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3">
      <h3 className="m-0 text-sm font-semibold text-[var(--text)]">{label}</h3>
      <DashboardRankingBarChart items={ranking?.items} rankingLabel={label} />
      {/* {(ranking?.meaning || ranking?.whyItMatters) && (
        <details className="mt-3 border-t border-[var(--surface-border-soft)] pt-2 text-xs text-[var(--text-muted)]">
          <summary className="cursor-pointer font-semibold text-[var(--text)]">About this ranking</summary>
          {ranking.meaning && <p className="mb-0 mt-2 leading-relaxed">{ranking.meaning}</p>}
          {ranking.whyItMatters && <p className="mb-0 mt-2 leading-relaxed"><strong>Why it matters:</strong> {ranking.whyItMatters}</p>}
        </details>
      )} */}
    </section>
  )
}

type MetricGroup = (typeof METRIC_GROUPS)[number]

function MetricGroupPanel({
  group,
  metrics,
  isUnavailable,
  latestSourcePayload,
  showTimestamp = false,
}: {
  group: MetricGroup
  metrics: Map<string, DashboardMetric>
  isUnavailable: boolean
  latestSourcePayload?: string | null
  showTimestamp?: boolean
}) {
  return (
    <article className="rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SubpanelHeading title={group.title} description={group.description} />
        {showTimestamp && (
          <div className="rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] px-3 py-2 text-right">
            <div className="text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">Latest source payload</div>
            <time className="mt-1 block text-sm font-semibold text-[var(--text)]">
              {isUnavailable ? '-' : formatTimestamp(latestSourcePayload)}
            </time>
          </div>
        )}
      </div>
      {group.title === 'Dataset Coverage' ? (
        <GroupedMetricGrid
          group={group}
          metricGroups={DATASET_METRIC_GROUPS}
          metrics={metrics}
          isUnavailable={isUnavailable}
          className="md:grid-cols-3"
          statuslessMetricGroups={['event_artist_links']}
        />
      ) : group.title === 'Network Health / Distribution' ? (
        <NetworkMetricGrid group={group} metrics={metrics} isUnavailable={isUnavailable} />
      ) : (
        <GroupedMetricGrid group={group} metricGroups={SEMANTIC_METRIC_GROUPS} metrics={metrics} isUnavailable={isUnavailable} />
      )}
    </article>
  )
}

export function DashboardMetricPanels({dashboardMetrics, isLoading, hasError}: DashboardMetricPanelsProps) {
  const metrics = new Map(dashboardMetrics?.metrics.map((metric) => [metric.id, metric]))
  const rankings = new Map(dashboardMetrics?.rankings.map((ranking) => [ranking.id, ranking]))
  const isUnavailable = isLoading || hasError
  const latestSourcePayload = dashboardMetrics?.timestamps?.latest_source_payload
    ?? dashboardMetrics?.latest_source_payload

  return (
    <>
      <MetricGroupPanel
        group={METRIC_GROUPS[0]}
        metrics={metrics}
        isUnavailable={isUnavailable}
        latestSourcePayload={latestSourcePayload}
        showTimestamp
      />

      {METRIC_GROUPS.slice(1).map((group) => (
        <MetricGroupPanel
          key={group.title}
          group={group}
          metrics={metrics}
          isUnavailable={isUnavailable}
        />
      ))}

      <article className="rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
        <SubpanelHeading title="Top List" description="Most represented entities and genres in the dataset" />
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          {RANKINGS.map((ranking, index) => (
            <div key={ranking.id} className={`xl:col-span-2 ${index === 3 ? 'xl:col-start-2' : ''}`}>
              <RankingCard
                ranking={isUnavailable ? undefined : rankings.get(ranking.id)}
                fallbackLabel={ranking.label}
              />
            </div>
          ))}
        </div>
      </article>
    </>
  )
}
