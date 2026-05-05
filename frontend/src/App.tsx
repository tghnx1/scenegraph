/* import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { GraphPage }  from './pages/GraphPage'
import { DashboardPage }    from './pages/DashboardPage'
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
        <NavLink to="/dashboard">Dashboard</NavLink>
      </nav>

      <main style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/artist/:id" element={<ArtistPage />} />
        </Routes>
      </main>
    </div>
  )
}
 */

//maybe better colours
import type { CSSProperties, ReactNode } from 'react'
import { Routes, Route, Navigate, NavLink, Link } from 'react-router-dom'
import { GraphPage } from './pages/GraphPage'
import { DashboardPage } from './pages/DashboardPage'
import { ArtistPage } from './pages/ArtistPage'

type LegalPageProps = {
  title: string
  children: ReactNode
}

const shellStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  height: '100vh',
  color: '#e5e7eb',
  background:
    'radial-gradient(1000px 520px at 12% -10%, rgba(59,130,246,0.22), transparent 60%), radial-gradient(900px 460px at 95% 0%, rgba(16,185,129,0.18), transparent 55%), #0b1220',
}

const navStyle: CSSProperties = {
  padding: '12px 20px',
  borderBottom: '1px solid rgba(148, 163, 184, 0.25)',
  background: 'rgba(11, 18, 32, 0.55)',
  backdropFilter: 'blur(6px)',
  display: 'flex',
  gap: 12,
}

const footerStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '12px 18px',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 20px',
  borderTop: '1px solid rgba(148, 163, 184, 0.18)',
  background: 'rgba(11, 18, 32, 0.72)',
  color: '#94a3b8',
  fontSize: 13,
}

const footerLinksStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '10px 14px',
}

const legalLinkStyle: CSSProperties = {
  color: '#cbd5e1',
  textDecoration: 'none',
}

const linkBaseStyle: CSSProperties = {
  textDecoration: 'none',
  color: '#cbd5e1',
  padding: '6px 10px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 600,
  transition: 'all 120ms ease',
}

function LegalPage({ title, children }: LegalPageProps) {
  return (
    <section className="page">
      <article className="card">
        <p className="eyebrow">Legal</p>
        <h1>{title}</h1>
        <p className="lead">{children}</p>
      </article>
    </section>
  )
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
          to="/dashboard"
          style={({ isActive }) => ({
            ...linkBaseStyle,
            background: isActive ? 'rgba(16,185,129,0.2)' : 'transparent',
            color: isActive ? '#ecfeff' : '#cbd5e1',
            border: isActive ? '1px solid rgba(52,211,153,0.45)' : '1px solid transparent',
          })}
        >
          Dashboard
        </NavLink>
      </nav>

      <main style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/artist/:id" element={<ArtistPage />} />
          <Route
            path="/privacy-policy"
            element={
              <LegalPage title="Privacy Policy">
                - Empty - Explain what data are collected, why, how long, and how users can contact us.
              </LegalPage>
            }
          />
          <Route
            path="/terms-of-service"
            element={
              <LegalPage title="Terms of Service">
                - Empty - Rules for using the site, content ownership, limitations of liability, & acceptable use.
              </LegalPage>
            }
          />
          <Route
            path="/impressum"
            element={
              <LegalPage title="Impressum">
                - Empty - Publisher info, responsible person/company, address, & contact details.
              </LegalPage>
            }
          />
          <Route
            path="/cookie-settings"
            element={
              <LegalPage title="Cookie Settings">
                - Empty - Review cookie categories and update consent preferences here.
              </LegalPage>
            }
          />
          <Route
            path="/contact"
            element={
              <LegalPage title="Contact">
                Email, form, or other ways for contact.
              </LegalPage>
            }
          />
        </Routes>
      </main>

      <footer style={footerStyle}>
        <span>© 2026 Scenegraph</span>
        <div style={footerLinksStyle}>
          <Link to="/privacy-policy" style={legalLinkStyle}>
            Privacy Policy
          </Link>
          <Link to="/terms-of-service" style={legalLinkStyle}>
            Terms of Service
          </Link>
          <Link to="/impressum" style={legalLinkStyle}>
            Impressum
          </Link>
          <Link to="/contact" style={legalLinkStyle}>
            Contact
          </Link>
          <Link to="/cookie-settings" style={legalLinkStyle}>
            Cookie Settings
          </Link>
        </div>
      </footer>
    </div>
  )
}