/* import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { GraphPage }  from './pages/GraphPage'
import { MapPage }    from './pages/MapPage'
import { ArtistPage } from './pages/ArtistPage'

export default function App() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <nav
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid #eee',
          display: 'flex',
          gap: '16px',
        }}
      >
        <NavLink to="/graph">Graph</NavLink>
        <NavLink to="/map">Map</NavLink>
      </nav>

      <main style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/artist/:id" element={<ArtistPage />} />
        </Routes>
      </main>
    </div>
  )
}
 */

//maybe better colours
import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { GraphPage } from './pages/GraphPage'
import { MapPage } from './pages/MapPage'
import { ArtistPage } from './pages/ArtistPage'

const shellStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  height: '100vh',
  color: '#e5e7eb',
  background:
    'radial-gradient(1000px 520px at 12% -10%, rgba(59,130,246,0.22), transparent 60%), radial-gradient(900px 460px at 95% 0%, rgba(16,185,129,0.18), transparent 55%), #0b1220',
}

const navStyle: React.CSSProperties = {
  padding: '12px 20px',
  borderBottom: '1px solid rgba(148, 163, 184, 0.25)',
  background: 'rgba(11, 18, 32, 0.55)',
  backdropFilter: 'blur(6px)',
  display: 'flex',
  gap: 12,
}

const linkBaseStyle: React.CSSProperties = {
  textDecoration: 'none',
  color: '#cbd5e1',
  padding: '6px 10px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 600,
  transition: 'all 120ms ease',
}

export default function App() {
  return (
    <div style={shellStyle}>
      <nav style={navStyle}>
        <NavLink
          to="/graph"
          style={({ isActive }) => ({
            ...linkBaseStyle,
            background: isActive ? 'rgba(59,130,246,0.22)' : 'transparent',
            color: isActive ? '#eff6ff' : '#cbd5e1',
            border: isActive ? '1px solid rgba(96,165,250,0.45)' : '1px solid transparent',
          })}
        >
          Graph
        </NavLink>

        <NavLink
          to="/map"
          style={({ isActive }) => ({
            ...linkBaseStyle,
            background: isActive ? 'rgba(16,185,129,0.2)' : 'transparent',
            color: isActive ? '#ecfeff' : '#cbd5e1',
            border: isActive ? '1px solid rgba(52,211,153,0.45)' : '1px solid transparent',
          })}
        >
          Map
        </NavLink>
      </nav>

      <main style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/artist/:id" element={<ArtistPage />} />
        </Routes>
      </main>
    </div>
  )
}