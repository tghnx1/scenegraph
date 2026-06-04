import { useState } from 'react'
import { Routes, Route, Navigate, NavLink, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { GraphPage } from './pages/GraphPage'
import { DashboardPage } from './pages/DashboardPage'
import { ProfilePage } from './pages/ProfilePage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import type { AuthRole } from './api/auth'
import { applyTheme, getStoredTheme, type ThemeName } from './styles/colors'
import { AdminUsersPage } from './pages/AdminUsersPage'

const colorVar = (name: string) => `var(${name})`

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
  const artistId = id?.startsWith('artist-') ? id : `artist-${id ?? ''}`
  return <Navigate to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artistId)}`} replace />
}

export default function App() {
  const navigate = useNavigate()
  const [authRole, setAuthRole] = useState<AuthRole | null>(() => {
    const storedToken = localStorage.getItem('token')
    const storedRole = localStorage.getItem('role')
    return storedToken && (storedRole === 'user' || storedRole === 'admin') ? storedRole : null
  })
  const [themeName, setThemeName] = useState<ThemeName>(() => getStoredTheme())
  const isAuthenticated = Boolean(authRole)

  const handleAuthClick = () => {
    if (isAuthenticated) {
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      localStorage.removeItem('username')
      localStorage.removeItem('user_id')
      setAuthRole(null)
      return
    }

    navigate('/login')
  }

  const handleLogin = (role: AuthRole) => {
    setAuthRole(role)
  }

  const handleThemeToggle = () => {
    const nextTheme = themeName === 'light' ? 'dark' : 'light'
    applyTheme(nextTheme)
    setThemeName(nextTheme)
  }

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <NavLink to="/graph" className="app-nav-link">
          Graph
        </NavLink>
        {authRole === 'user' && (
          <NavLink to="/profile" className="app-nav-link">
            Profile
          </NavLink>
        )}
        {authRole === 'admin' && (
          <NavLink to="/dashboard" className="app-nav-link">
            Dashboard
          </NavLink>
        )}
        {authRole === 'admin' && (
          <NavLink to="/admin/users" className="app-nav-link">
            Pending users
          </NavLink>
        )}
        <span className="app-nav-spacer" />
        <button type="button" className="app-nav-button" onClick={handleThemeToggle}>
          {themeName === 'light' ? 'Dark' : 'Light'}
        </button>
        <button type="button" className="app-nav-button" onClick={handleAuthClick}>
          {isAuthenticated ? 'Logout' : 'Login'}
        </button>
      </nav>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/login" element={isAuthenticated ? <Navigate to="/graph" replace /> : <LoginPage onLogin={handleLogin} />} />
          <Route path="/register" element={isAuthenticated ? <Navigate to="/graph" replace /> : <RegisterPage />} />
          <Route path="/dashboard" element={authRole === 'admin' ? <DashboardPage /> : <Navigate to={isAuthenticated ? '/graph' : '/login'} replace />} />
          <Route path="/profile" element={authRole === 'user' ? <ProfilePage /> : <Navigate to={isAuthenticated ? '/graph' : '/login'} replace />} />
          <Route path="/search" element={<SearchRedirect />} />
          <Route path="/artist/:id" element={<ArtistRedirect />} />
          <Route path="/privacy-policy" element={<LegalPage section="privacy" />} />
          <Route path="/terms-of-service" element={<LegalPage section="terms" />} />
          <Route path="/impressum" element={<LegalPage section="impressum" />} />
          <Route path="/cookie-settings" element={<LegalPage section="cookies" />} />
          <Route path="/contact" element={<LegalPage section="contact" />} />
          <Route
            path="/admin/users"
            element={
              isAuthenticated && authRole === 'admin'
                ? <AdminUsersPage />
                : <Navigate to="/login" replace />
            }
          />
        </Routes>
      </main>

      <footer className="app-footer">
        <span>© 2026 Scenegraph</span>
        <div className="app-footer-links">
          <NavLink to="/privacy-policy" className="app-nav-link">
            Privacy Policy
          </NavLink>
          <NavLink to="/terms-of-service" className="app-nav-link">
            Terms
          </NavLink>
          <NavLink to="/impressum" className="app-nav-link">
            Impressum
          </NavLink>
          <NavLink to="/contact" className="app-nav-link">
            Contact
          </NavLink>
        </div>
      </footer>
    </div>
  )
}
