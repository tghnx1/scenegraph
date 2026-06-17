interface RecommendationLoadingProps {
  activity: string
}

const linkClass = 'fill-none stroke-[var(--graph-line)] stroke-[3] opacity-60'
const nodeBaseClass = 'animate-pulse stroke-[var(--surface-panel)] stroke-[3]'

export function RecommendationLoading({ activity }: RecommendationLoadingProps) {
  return (
    <div className="grid place-items-center gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-8 text-center" role="status" aria-live="polite">
      <svg
        className="h-auto w-[min(260px,100%)]"
        viewBox="0 0 220 106"
        aria-hidden="true"
      >
        <path className={linkClass} d="M 24 53 L 79 23" />
        <path className={linkClass} d="M 24 53 L 79 83" />
        <path className={linkClass} d="M 79 23 L 140 36" />
        <path className={linkClass} d="M 79 83 L 140 70" />
        <path className={linkClass} d="M 140 36 L 195 53" />
        <path className={linkClass} d="M 140 70 L 195 53" />
        <circle className={nodeBaseClass} fill="var(--artist)" cx="24" cy="53" r="10" />
        <circle className={nodeBaseClass} fill="var(--artist)" cx="79" cy="23" r="8" />
        <circle className={nodeBaseClass} fill="var(--artist)" cx="79" cy="83" r="8" />
        <circle className={nodeBaseClass} fill="var(--event)" cx="140" cy="36" r="8" />
        <circle className={nodeBaseClass} fill="var(--event)" cx="140" cy="70" r="8" />
        <circle className={nodeBaseClass} fill="var(--promoter)" cx="195" cy="53" r="11" />
      </svg>
      <strong>Preparing recommendations</strong>
      <p className="m-0 text-sm font-semibold text-[var(--text)]">{activity}</p>
      <p className="m-0 max-w-sm text-sm text-[var(--text-muted)]">
        This may take a while, you know, wizard things.
      </p>
    </div>
  )
}
