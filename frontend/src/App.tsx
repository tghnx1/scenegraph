import { useState, type CSSProperties } from 'react'
import { Routes, Route, Navigate, NavLink, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { GraphPage } from './pages/GraphPage'
import { DashboardPage } from './pages/DashboardPage'
import {
  hexToRgba,
  LINK_HIGHLIGHT,
  ACCENT_WARM,
  BACKGROUND,
  TEXT,
  TEXT_MUTED,
} from './styles/colors'

function LegalPage({ section }: { section: string }) {
  const titles: Record<string, string> = {
    privacy: 'Privacy Policy',
    terms: 'Terms of Service',
    impressum: 'Impressum',
    cookies: 'Cookie Settings',
    contact: 'Contact',
  }

  return (
    <div style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>{titles[section] || 'Legal'}</h1>
      <p style={{ color: TEXT_MUTED, marginTop: '20px' }}>
        This page is a placeholder for {titles[section]?.toLowerCase() || 'legal information'}.
      </p>
    </div>
  )
}

function SearchRedirect() {
  const [searchParams] = useSearchParams()
  return <Navigate to={`/graph?${searchParams.toString()}`} replace />
}

function ArtistRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/graph?artist=${encodeURIComponent(id ?? '')}`} replace />
}



const shellStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  height: '100dvh',
  minHeight: '100vh',
  color: TEXT,
  background: `radial-gradient(1000px 520px at 12% -10%, ${hexToRgba(LINK_HIGHLIGHT, 0.18)}, transparent 60%), radial-gradient(900px 460px at 95% 0%, ${hexToRgba(ACCENT_WARM, 0.15)}, transparent 55%), ${BACKGROUND}`,
}

const navStyle: CSSProperties = {
  padding: '12px 20px',
  borderBottom: `1px solid ${hexToRgba(TEXT, 0.18)}`,
  background: hexToRgba(BACKGROUND, 0.55),
  backdropFilter: 'blur(6px)',
  display: 'flex',
  alignItems: 'center',
  gap: 12,
}

const footerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 20px',
  borderTop: `1px solid ${hexToRgba(TEXT, 0.15)}`,
  background: hexToRgba(BACKGROUND, 0.72),
  color: TEXT_MUTED,
  fontSize: 13,
}

const linkBaseStyle: CSSProperties = {
  textDecoration: 'none',
  color: TEXT_MUTED,
  padding: '6px 10px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 600,
  transition: 'all 120ms ease',
}

const navSpacerStyle: CSSProperties = {
  flex: 1,
}

const authButtonStyle: CSSProperties = {
  ...linkBaseStyle,
  cursor: 'pointer',
  border: `1px solid ${hexToRgba(TEXT, 0.18)}`,
  background: hexToRgba(TEXT, 0.06),
  font: 'inherit',
  fontSize: 14,
}

export default function App() {
  const location = useLocation()
  const isGraphActive = location.pathname === '/graph'
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(localStorage.getItem('token')))

  const handleAuthClick = () => {
    if (isAuthenticated) {
      localStorage.removeItem('token')
      setIsAuthenticated(false)
      return
    }

    window.location.href = '/login'
  }

  return (
    <div style={shellStyle}>
      <nav style={navStyle}>
        <a
          href="/graph"
          style={{
            ...linkBaseStyle,
            background: isGraphActive ? hexToRgba(LINK_HIGHLIGHT, 0.2) : 'transparent',
            color: isGraphActive ? TEXT : TEXT_MUTED,
            border: isGraphActive ? `1px solid ${hexToRgba(LINK_HIGHLIGHT, 0.45)}` : '1px solid transparent',
          }}
        >
          Graph
        </a>

        <NavLink
          to="/dashboard"
          style={({ isActive }) => ({
            ...linkBaseStyle,
            background: isActive ? hexToRgba(ACCENT_WARM, 0.2) : 'transparent',
            color: isActive ? TEXT : TEXT_MUTED,
            border: isActive ? `1px solid ${hexToRgba(ACCENT_WARM, 0.45)}` : '1px solid transparent',
          })}
        >
          Dashboard
        </NavLink>
        <span style={navSpacerStyle} />
        <button type="button" style={authButtonStyle} onClick={handleAuthClick}>
          {isAuthenticated ? 'Logout' : 'Login'}
        </button>
      </nav>

      <main style={{ flex: 1, overflowX: 'hidden', overflowY: 'auto' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/search" element={<SearchRedirect />} />
          <Route path="/artist/:id" element={<ArtistRedirect />} />
          <Route path="/privacy-policy" element={<LegalPage section="privacy" />} />
          <Route path="/terms-of-service" element={<LegalPage section="terms" />} />
          <Route path="/impressum" element={<LegalPage section="impressum" />} />
          <Route path="/cookie-settings" element={<LegalPage section="cookies" />} />
          <Route path="/contact" element={<LegalPage section="contact" />} />
        </Routes>
      </main>

      <footer style={footerStyle}>
        <span>© 2026 Scenegraph</span>
        <div style={{ display: 'flex', gap: '16px' }}>
          <NavLink to="/privacy-policy" style={{ ...linkBaseStyle, color: TEXT_MUTED, fontSize: 12, padding: '4px 8px' }}>
            Privacy Policy
          </NavLink>
          <NavLink to="/terms-of-service" style={{ ...linkBaseStyle, color: TEXT_MUTED, fontSize: 12, padding: '4px 8px' }}>
            Terms
          </NavLink>
          <NavLink to="/impressum" style={{ ...linkBaseStyle, color: TEXT_MUTED, fontSize: 12, padding: '4px 8px' }}>
            Impressum
          </NavLink>
          <NavLink to="/contact" style={{ ...linkBaseStyle, color: TEXT_MUTED, fontSize: 12, padding: '4px 8px' }}>
            Contact
          </NavLink>
        </div>
      </footer>
    </div>
  )
}
