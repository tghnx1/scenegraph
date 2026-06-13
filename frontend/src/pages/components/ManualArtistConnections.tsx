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
  return (
    <section className="grid gap-3" aria-labelledby="manual-artist-connections-heading">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2">
        <div>
          <h3 id="manual-artist-connections-heading">Artists you know</h3>
          <p className="m-0 text-sm text-[var(--text-muted)]">Add artists from their details panel.</p>
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
