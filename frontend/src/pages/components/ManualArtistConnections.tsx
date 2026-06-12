import {Link} from 'react-router-dom'
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
    <section className="manual-artist-connections" aria-labelledby="manual-artist-connections-heading">
      <div className="biography-section-heading">
        <div>
          <h3 id="manual-artist-connections-heading">Artists you know</h3>
          <p>Add artists from their details panel.</p>
        </div>
        <span>{connections.length}</span>
      </div>

      {error && <p className="biography-message error">{error}</p>}
      {isLoading ? (
        <p>Loading known artists...</p>
      ) : connections.length > 0 ? (
        <div className="manual-artist-connection-list">
          {connections.map((connection) => (
            <div className="manual-artist-connection" key={connection.connectedArtistId}>
              <Link
                to={`/graph?selectedType=artist&selectedId=${connection.connectedArtistId}`}
                className="biography-linked-artist"
              >
                <strong>{connection.connectedArtistName}</strong>
                <span>Manual connection</span>
              </Link>
              <button
                type="button"
                onClick={() => void onRemove(connection.connectedArtistId)}
                disabled={pendingArtistId === connection.connectedArtistId}
                aria-label={`Remove ${connection.connectedArtistName} from manual connections`}
                title={pendingArtistId === connection.connectedArtistId ? 'Removing...' : 'Remove connection'}
              >
                <span aria-hidden="true">&times;</span>
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="biography-empty">No manually linked artists yet.</p>
      )}
    </section>
  )
}
