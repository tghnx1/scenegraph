/* import { useParams } from 'react-router-dom'
import { useApi }     from '../hooks/useApi'
import { fetchArtist, fetchSimilarArtists } from '../api/artists'

export function ArtistPage() {
  const { id } = useParams<{ id: string }>()

  const { data: artist,  isLoading: l1 } = useApi(() => fetchArtist(id!), [id])
  const { data: similar, isLoading: l2 } = useApi(() => fetchSimilarArtists(id!), [id])

  if (l1 || l2)  return <div style={{ padding: 24 }}>Loading...</div>
  if (!artist)   return <div style={{ padding: 24 }}>Artist not found</div>

  return (
    <div style={{ padding: 32, maxWidth: 600 }}>
      <h1>{artist.name}</h1>
      <p>{artist.genres.map(g => g.name).join(', ')}</p>
      {artist.bio && <p>{artist.bio}</p>}

      <h2 style={{ marginTop: 24 }}>Similar artists</h2>
      {similar?.map(s => (
        <div key={s.artist.id}>
          <strong>{s.artist.name}</strong> — {s.sharedEvents} shared events
        </div>
      ))}
    </div>
  )
} */

import { useParams, useNavigate } from 'react-router-dom'
import { useApi }                  from '../hooks/useApi'
import { fetchArtist, fetchSimilarArtists } from '../api/artists'

export function ArtistPage() {
  const { id }     = useParams<{ id: string }>()
  const navigate   = useNavigate()

  // Two separate API calls — both re-fetch if id changes
  const { data: artist,  isLoading: l1, error: e1 } =
    useApi(() => fetchArtist(id!), [id])

  const { data: similar, isLoading: l2 } =
    useApi(() => fetchSimilarArtists(id!), [id])

  if (l1 || l2) return <p style={{padding:32}}>Loading...</p>
  if (e1)       return <p style={{padding:32}}>Error: {e1}</p>
  if (!artist)  return <p style={{padding:32}}>Artist not found</p>

  return (
    <div style={{ padding:32, maxWidth:640 }}>

      {/* Back button */}
      <button
        onClick={() => navigate('/graph')}
        style={{ marginBottom:20, cursor:'pointer' }}
      >
        ← Back to graph
      </button>

      {/* Artist header */}
      <h1 style={{ fontSize:28, marginBottom:6 }}>{artist.name}</h1>
      <p style={{ color:'#888', marginBottom:12 }}>
        {artist.genres.map(g => g.name).join(' · ')}
      </p>
      {artist.bio && <p style={{ marginBottom:24 }}>{artist.bio}</p>}

      {/* Event count */}
      {artist.eventCount !== undefined && (
        <p style={{ marginBottom:24, color:'#888' }}>
          {artist.eventCount} events in Berlin
        </p>
      )}

      {/* Similar artists */}
      <h2 style={{ fontSize:18, marginBottom:12 }}>
        Similar artists
      </h2>

      {similar && similar.length === 0 && (
        <p style={{ color:'#888' }}>
          No co-appearances found yet.
        </p>
      )}

      {similar?.map(s => (
        <div
          key={s.artist.id}
          onClick={() => navigate(`/artist/${s.artist.id}`)}
          style={{
            padding:'12px 0',
            borderBottom:'1px solid #222',
            cursor:'pointer',
            display:'flex',
            justifyContent:'space-between'
          }}
        >
          <span>{s.artist.name}</span>
          <span style={{ color:'#888', fontSize:13 }}>
            {s.sharedEvents} shared events
          </span>
        </div>
      ))}

    </div>
  )
}