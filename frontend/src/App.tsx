import { useState } from 'react'
import { Routes, Route, Navigate, NavLink, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { GraphPage } from './pages/GraphPage'
import { DashboardPage } from './pages/DashboardPage'
import { ProfilePage } from './pages/ProfilePage'
import { AgencyPage } from './pages/AgencyPage'
import { LoginPage } from './pages/LoginPage'
import { logout, type AuthRole } from './api/auth'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { AboutPage } from './pages/AboutPage'
import { applyTheme, getStoredTheme, type ThemeName } from './shared/styles/colors'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import { useLocation } from 'react-router-dom'

const navLinkClass = ({ isActive }: { isActive: boolean }) => cn(
  'rounded-lg border border-transparent px-2.5 py-1.5 text-sm font-semibold text-[var(--text-muted)] no-underline transition-all duration-150 hover:opacity-90',
  isActive && 'border-[color-mix(in_srgb,var(--link-highlight)_45%,transparent)] bg-[color-mix(in_srgb,var(--link-highlight)_20%,transparent)] text-[var(--text)]',
)

const footerLinkClass = ({ isActive }: { isActive: boolean }) => cn(
  navLinkClass({ isActive }),
  'px-2 py-1 text-xs',
)

function SearchRedirect() {
  const [searchParams] = useSearchParams()
  return <Navigate to={`/graph?${searchParams.toString()}`} replace />
}

function EntityRedirect({ type }: { type: 'artist' | 'promoter' | 'event' | 'venue' }) {
  const { id } = useParams<{ id: string }>()
  const selectedId = id?.startsWith(`${type}-`) ? id : `${type}-${id ?? ''}`
  return <Navigate to={`/graph?selectedType=${type}&selectedId=${encodeURIComponent(selectedId)}`} replace />
}

export default function App() {
  const navigate = useNavigate()
  const [authRole, setAuthRole] = useState<AuthRole | null>(() => {
    const storedToken = localStorage.getItem('token')
    const storedRole = localStorage.getItem('role')
    return storedToken && storedRole && ['artist', 'agent', 'admin'].includes(storedRole) 
      ? storedRole as AuthRole
      : null
  })
  const [themeName, setThemeName] = useState<ThemeName>(() => getStoredTheme())
  const isAuthenticated = Boolean(authRole)
  const canOpenDashboard = authRole === 'admin'
  const graphPage = authRole === 'artist'
    ? <ProfilePage />
    : authRole === 'agent' || authRole === 'admin'
      ? <AgencyPage />
      : <GraphPage />

  const location = useLocation()
  const isLoginPage = location.pathname === '/login'
  
  const handleAuthClick = async () => {
    if (isAuthenticated) {
      try {
        await logout()
      } catch {
        console.error('Logout logging failed')
        }

      localStorage.removeItem('token')
      localStorage.removeItem('role')
      localStorage.removeItem('username')
      localStorage.removeItem('user_id')
      localStorage.removeItem('artist_id')
      setAuthRole(null)
      return
    }

    if (isLoginPage) {
      window.dispatchEvent(new Event('show-login-form'))
      return
    }

    navigate('/login')
  }

  const handleLogin = (role: AuthRole, redirect = true) => {
    setAuthRole(role)

    if (redirect) {
      navigate(role === 'admin' ? '/dashboard' : '/profile')
    }
  }

  const handleThemeToggle = () => {
    const nextTheme = themeName === 'light' ? 'dark' : 'light'
    applyTheme(nextTheme)
    setThemeName(nextTheme)
  }

  const username = localStorage.getItem('username')

  return (
    <div className="flex h-dvh min-h-screen flex-col bg-[var(--background)] text-[var(--text)] [background:radial-gradient(1000px_520px_at_12%_-10%,color-mix(in_srgb,var(--link-highlight)_18%,transparent),transparent_60%),radial-gradient(900px_460px_at_95%_0%,color-mix(in_srgb,var(--accent-warm)_15%,transparent),transparent_55%),var(--background)]">
      <nav className="flex flex-wrap items-center gap-2 border-b border-[color-mix(in_srgb,var(--text)_18%,transparent)] bg-[color-mix(in_srgb,var(--background)_55%,transparent)] px-3 py-3 backdrop-blur-md sm:gap-3 sm:px-5">
        <NavLink to="/graph" className={navLinkClass}>
          Graph
        </NavLink>
        {canOpenDashboard && (
          <NavLink to="/dashboard" className={navLinkClass}>
            Dashboard
          </NavLink>
        )}
        
        <span className="flex-1" />
        {username && (
          <span className="text-sm text-[var(--text-muted)]">
            Logged in as {username}
          </span>
        )}
        {isAuthenticated && (
          <Button type="button" size="sm" variant="outline" onClick={() => navigate('/change-password')}>
            Change password
          </Button>
        )}
        <Button type="button" size="sm" variant="outline" onClick={handleThemeToggle}>
          {themeName === 'light' ? 'Dark' : 'Light'}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={handleAuthClick}>
          {isAuthenticated ? 'Logout' : 'Login'}
        </Button>
      </nav>

      <main className="flex-1 overflow-y-auto overflow-x-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={graphPage} />
          <Route path="/login" element={isAuthenticated ? <Navigate to="/graph" replace /> : <LoginPage onLogin={handleLogin} />} />
          <Route 
            path="/change-password" 
            element={
              isAuthenticated || localStorage.getItem('token')
                ? <ChangePasswordPage onLogin={handleLogin} />
                : <Navigate to="/login" replace />} 
          />
          <Route path="/dashboard" element={authRole === 'admin' ? <DashboardPage /> : <Navigate to={isAuthenticated ? '/graph' : '/login'} replace />} />
          <Route path="/profile" element={authRole === 'artist' || authRole === 'agent' ? <ProfilePage /> : <Navigate to={isAuthenticated ? '/graph' : '/login'} replace />} />
          <Route path="/search" element={<SearchRedirect />} />
          <Route path="/artist/:id" element={<EntityRedirect type="artist" />} />
          <Route path="/promoter/:id" element={<EntityRedirect type="promoter" />} />
          <Route path="/event/:id" element={<EntityRedirect type="event" />} />
          <Route path="/venue/:id" element={<EntityRedirect type="venue" />} />
          <Route path="/privacy-policy" element={<AboutPage page="privacy" />} />
          <Route path="/terms-of-service" element={<AboutPage page="terms" />} />
          {/* <Route path="/impressum" element={<AboutPage page="impressum" />} /> */}
          {/* <Route path="/cookie-settings" element={<AboutPage page="cookies" />} /> */}
          <Route path="/contact" element={<AboutPage page="contact" />} />
        </Routes>
      </main>

      <footer className="flex items-center justify-between border-t border-[color-mix(in_srgb,var(--text)_15%,transparent)] bg-[color-mix(in_srgb,var(--background)_72%,transparent)] px-5 py-3.5 text-[13px] text-[var(--text-muted)]">
        <span>© 2026 Scenegraph</span>
        <div className="flex gap-4">
          <NavLink to="/privacy-policy" className={footerLinkClass}>
            Privacy Policy
          </NavLink>
          <NavLink to="/terms-of-service" className={footerLinkClass}>
            Terms
          </NavLink>
          {/* <NavLink to="/impressum" className={footerLinkClass}>
            Impressum
          </NavLink> */}
          {/* <NavLink to="/cookie-settings" className={footerLinkClass}>
            Cookies
          </NavLink> */}
          <NavLink to="/contact" className={footerLinkClass}>
            Contact
          </NavLink>
        </div>
      </footer>
    </div>
  )
}
