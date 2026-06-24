import {useState} from 'react'
import {Link} from 'react-router-dom'
import { X } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import type {ManualArtistConnection} from '../../api/manualArtistConnections'

export interface ManualArtistConnectionsProps {
  connections: ManualArtistConnection[]
  isLoading: boolean
  pendingArtistId: number | null
  error: string | null
  onRemove: (connectedArtistId: number) => Promise<void>
}

export function ManualArtistConnections({
  connections,
  isLoading,
  pendingArtistId,
  error,
  onRemove,
}: ManualArtistConnectionsProps) {
  const [isInfoOpen, setIsInfoOpen] = useState(false)

  return (
    <section className="grid gap-3" aria-labelledby="manual-artist-connections-heading">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2">
        <div className="flex items-center gap-1.5">
          <h3 id="manual-artist-connections-heading">Artists you know</h3>
          <span className="relative inline-grid place-items-center">
            <button
              type="button"
              className="grid size-5 cursor-help place-items-center rounded-full border border-[var(--surface-border)] bg-[var(--surface-panel)] p-0 text-[var(--text-muted)] opacity-90 transition-all hover:-translate-y-px hover:border-[var(--focus-border)] hover:bg-[var(--surface-strong)] hover:text-[var(--text)] hover:opacity-100 focus-visible:-translate-y-px focus-visible:border-[var(--focus-border)] focus-visible:bg-[var(--surface-strong)] focus-visible:text-[var(--text)] focus-visible:opacity-100 focus-visible:outline-none"
              aria-label="Explain how to add artists"
              aria-expanded={isInfoOpen}
              onClick={() => setIsInfoOpen((isOpen) => !isOpen)}
              onBlur={() => setIsInfoOpen(false)}
            >
              <span className="block size-[13px] rounded-full text-center font-serif text-[0.7rem] font-extrabold italic leading-[13px]" aria-hidden="true">i</span>
            </button>
            {isInfoOpen && (
              <span
                className="absolute left-0 top-[calc(100%+8px)] z-20 w-[min(300px,calc(100vw-48px))] rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-left text-[0.82rem] font-semibold leading-snug text-[var(--text)] shadow-[var(--surface-shadow)] max-[700px]:left-1/2 max-[700px]:right-auto max-[700px]:top-auto max-[700px]:bottom-[calc(100%+8px)] max-[700px]:z-[120] max-[700px]:max-h-[45dvh] max-[700px]:w-[min(300px,calc(100vw-32px))] max-[700px]:-translate-x-1/2 max-[700px]:translate-y-0 max-[700px]:overflow-y-auto"
                role="tooltip"
              >
                Add artists from their details panel.
              </span>
            )}
          </span>
        </div>
      </div>

      {error && <p className="m-0 rounded-xl border border-[var(--event-border-soft)] bg-[var(--event-soft)] p-3 text-sm text-[var(--event)]">{error}</p>}
      {isLoading ? (
        <p>Loading known artists...</p>
      ) : connections.length > 0 ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-8">
          {connections.map((connection) => (
            <div className="relative" key={connection.connectedArtistId}>
              <Link
                to={`/graph?selectedType=artist&selectedId=${connection.connectedArtistId}`}
                className="grid min-h-full gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 pr-10 text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]"
              >
                <strong>{connection.connectedArtistName}</strong>
                <span className="text-sm text-[var(--text-muted)]">Manual connection</span>
              </Link>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="absolute right-2 top-2 size-7 rounded-full"
                onClick={() => void onRemove(connection.connectedArtistId)}
                disabled={pendingArtistId === connection.connectedArtistId}
                aria-label={`Remove ${connection.connectedArtistName} from manual connections`}
                title={pendingArtistId === connection.connectedArtistId ? 'Removing...' : 'Remove connection'}
              >
                <X aria-hidden="true" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="m-0 text-sm text-[var(--text-muted)]">No manually linked artists yet.</p>
      )}
    </section>
  )
}
