interface RecommendationLoadingProps {
  activity: string
}

export function RecommendationLoading({ activity }: RecommendationLoadingProps) {
  return (
    <div className="recommendations-loading" role="status" aria-live="polite">
      <svg
        className="recommendations-network"
        viewBox="0 0 220 106"
        aria-hidden="true"
      >
        <path className="recommendations-network-link link-1" d="M 24 53 L 79 23" />
        <path className="recommendations-network-link link-2" d="M 24 53 L 79 83" />
        <path className="recommendations-network-link link-3" d="M 79 23 L 140 36" />
        <path className="recommendations-network-link link-4" d="M 79 83 L 140 70" />
        <path className="recommendations-network-link link-5" d="M 140 36 L 195 53" />
        <path className="recommendations-network-link link-6" d="M 140 70 L 195 53" />
        <circle className="recommendations-network-node artist-node source-node" cx="24" cy="53" r="10" />
        <circle className="recommendations-network-node artist-node match-node-1" cx="79" cy="23" r="8" />
        <circle className="recommendations-network-node artist-node match-node-2" cx="79" cy="83" r="8" />
        <circle className="recommendations-network-node event-node event-node-1" cx="140" cy="36" r="8" />
        <circle className="recommendations-network-node event-node event-node-2" cx="140" cy="70" r="8" />
        <circle className="recommendations-network-node promoter-node" cx="195" cy="53" r="11" />
      </svg>
      <strong>Preparing recommendations</strong>
      <p className="recommendations-loading-activity">{activity}</p>
      <p className="recommendations-loading-note">
        This may take a while, you know, wizard things.
      </p>
    </div>
  )
}
