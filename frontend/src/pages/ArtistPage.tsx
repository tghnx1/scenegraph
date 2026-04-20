import { useParams } from 'react-router-dom'
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
}