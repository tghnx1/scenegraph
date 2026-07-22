import {useState} from 'react'
import {ChevronDown} from 'lucide-react'
import {Button} from '@/shared/ui/button'
import {cn} from '@/shared/lib/cn-utils'

const SIGNAL_ROWS = [
  {
    title: 'Biography',
    text: 'Describe your sound, roles, labels, collectives and residencies.',
  },
  {
    title: 'Artists you know',
    text: 'Add artists you genuinely know or have worked with. More relevant connections can broaden your promoter network.',
  },
] as const

const RECOMMENDATION_SIGNALS = [
  'your biography and its overall meaning',
  'explicitly mentioned styles and genres',
  'artist roles such as DJ, producer or live act',
  'labels and imprints',
  'collectives and crews',
  'named residencies',
  'artists you personally know or have worked with',
  'your existing event history and co-played artists',
  'similarity between your events and promoter events',
  'promoter activity, recency and scale',
  'your Interested / Not relevant feedback',
]

export function RecommendationSignalsHelp() {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <section className="grid gap-4 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4 md:p-5">
      <div className="grid gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Improve your matches</span>
        <p className="m-0 text-sm leading-6 text-[var(--text-muted)]">
          More specific profile information gives SceneGraph more signals to find relevant promoters.
        </p>
      </div>

      <div className="grid gap-2">
        {SIGNAL_ROWS.map((row) => (
          <div
            key={row.title}
            className="grid gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] px-3 py-2.5 md:grid-cols-[9rem_minmax(0,1fr)] md:gap-3"
          >
            <span className="text-sm font-semibold text-[var(--text)]">{row.title}</span>
            <p className="m-0 text-sm leading-6 text-[var(--text-muted)]">{row.text}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-3">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="w-fit gap-2 px-2 text-[var(--text-muted)]"
          onClick={() => setIsExpanded((current) => !current)}
          aria-expanded={isExpanded}
        >
          How recommendations work
          <ChevronDown className={cn('size-4 transition-transform', isExpanded && 'rotate-180')} aria-hidden="true" />
        </Button>

        {isExpanded && (
          <div className="grid gap-3 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-4">
            <p className="m-0 text-sm font-semibold text-[var(--text)]">SceneGraph combines:</p>
            <ul className="m-0 grid gap-2 pl-4 text-sm leading-6 text-[var(--text-muted)]">
              {RECOMMENDATION_SIGNALS.map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
            <p className="m-0 text-sm leading-6 text-[var(--text-muted)]">
              Specific and accurate information is more useful than a long generic bio.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
