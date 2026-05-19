import { useState, type CSSProperties } from 'react'
import { Routes, Route, Navigate, NavLink, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { GraphPage } from './pages/GraphPage'
import { DashboardPage } from './pages/DashboardPage'
import { ProfilePage } from './pages/ProfilePage'
import { applyTheme, getStoredTheme, type ThemeName } from './styles/colors'

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

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
      <p style={{ color: colorVar('--text-muted'), marginTop: '20px' }}>
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
  color: colorVar('--text'),
  background: `radial-gradient(1000px 520px at 12% -10%, ${colorAlpha('--link-highlight', 18)}, transparent 60%), radial-gradient(900px 460px at 95% 0%, ${colorAlpha('--accent-warm', 15)}, transparent 55%), ${colorVar('--background')}`,
}

const navStyle: CSSProperties = {
  padding: '12px 20px',
  borderBottom: `1px solid ${colorAlpha('--text', 18)}`,
  background: colorAlpha('--background', 55),
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
  borderTop: `1px solid ${colorAlpha('--text', 15)}`,
  background: colorAlpha('--background', 72),
  color: colorVar('--text-muted'),
  fontSize: 13,
}

const linkBaseStyle: CSSProperties = {
  textDecoration: 'none',
  color: colorVar('--text-muted'),
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
  border: `1px solid ${colorAlpha('--text', 18)}`,
  background: colorAlpha('--text', 6),
  font: 'inherit',
  fontSize: 14,
}

export default function App() {
  const location = useLocation()
  const isGraphActive = location.pathname === '/graph'
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(localStorage.getItem('token')))
  const [themeName, setThemeName] = useState<ThemeName>(() => getStoredTheme())

  const handleAuthClick = () => {
    if (isAuthenticated) {
      localStorage.removeItem('token')
      setIsAuthenticated(false)
      return
    }

    window.location.href = '/login'
  }

  const handleThemeToggle = () => {
    const nextTheme = themeName === 'light' ? 'dark' : 'light'
    applyTheme(nextTheme)
    setThemeName(nextTheme)
  }

  return (
    <div style={shellStyle}>
      <nav style={navStyle}>
        <a
          href="/graph"
          style={{
            ...linkBaseStyle,
            background: isGraphActive ? colorAlpha('--link-highlight', 20) : 'transparent',
            color: isGraphActive ? colorVar('--text') : colorVar('--text-muted'),
            border: isGraphActive ? `1px solid ${colorAlpha('--link-highlight', 45)}` : '1px solid transparent',
          }}
        >
          Graph
        </a>
        <NavLink
          to="/profile"
          style={({ isActive }) => ({
            ...linkBaseStyle,
            background: isActive ? colorAlpha('--accent-warm', 20) : 'transparent',
            color: isActive ? colorVar('--text') : colorVar('--text-muted'),
            border: isActive ? `1px solid ${colorAlpha('--accent-warm', 45)}` : '1px solid transparent',
          })}
        >
          Profile
        </NavLink>
        <NavLink
          to="/dashboard"
          style={({ isActive }) => ({
            ...linkBaseStyle,
            background: isActive ? colorAlpha('--accent-warm', 20) : 'transparent',
            color: isActive ? colorVar('--text') : colorVar('--text-muted'),
            border: isActive ? `1px solid ${colorAlpha('--accent-warm', 45)}` : '1px solid transparent',
          })}
        >
          Dashboard
        </NavLink>
        <span style={navSpacerStyle} />
        <button type="button" style={authButtonStyle} onClick={handleThemeToggle}>
          {themeName === 'light' ? 'Dark' : 'Light'}
        </button>
        <button type="button" style={authButtonStyle} onClick={handleAuthClick}>
          {isAuthenticated ? 'Logout' : 'Login'}
        </button>
      </nav>

      <main style={{ flex: 1, overflowX: 'hidden', overflowY: 'auto' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage themeName={themeName} />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage themeName={themeName} />} />
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
          <NavLink to="/privacy-policy" style={{ ...linkBaseStyle, color: colorVar('--text-muted'), fontSize: 12, padding: '4px 8px' }}>
            Privacy Policy
          </NavLink>
          <NavLink to="/terms-of-service" style={{ ...linkBaseStyle, color: colorVar('--text-muted'), fontSize: 12, padding: '4px 8px' }}>
            Terms
          </NavLink>
          <NavLink to="/impressum" style={{ ...linkBaseStyle, color: colorVar('--text-muted'), fontSize: 12, padding: '4px 8px' }}>
            Impressum
          </NavLink>
          <NavLink to="/contact" style={{ ...linkBaseStyle, color: colorVar('--text-muted'), fontSize: 12, padding: '4px 8px' }}>
            Contact
          </NavLink>
        </div>
      </footer>
    </div>
  )
}
