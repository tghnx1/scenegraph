import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { GraphPage }  from './pages/GraphPage'
import { MapPage }    from './pages/MapPage'
import { ArtistPage } from './pages/ArtistPage'

export default function App() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>

      <nav style={{ padding: '12px 20px', borderBottom: '1px solid #eee',
                    display: 'flex', gap: '16px' }}>
        <NavLink to="/graph">Graph</NavLink>
        <NavLink to="/map">Map</NavLink>
      </nav>

      <main style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/"           element={<Navigate to="/graph" />} />
          <Route path="/graph"      element={<GraphPage />} />
          <Route path="/map"        element={<MapPage />} />
          <Route path="/artist/:id" element={<ArtistPage />} />
        </Routes>
      </main>

    </div>
  )
}
