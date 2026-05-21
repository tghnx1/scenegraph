import type { CSSProperties } from 'react'

export type AuthRole = 'user' | 'admin'

interface LoginPageProps {
  onLogin: (role: AuthRole) => void
}

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

const loginButtonStyle: CSSProperties = {
  textDecoration: 'none',
  color: colorVar('--text-muted'),
  padding: '6px 10px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 600,
  transition: 'all 120ms ease',
  cursor: 'pointer',
  border: `1px solid ${colorAlpha('--text', 18)}`,
  background: colorAlpha('--text', 6),
  font: 'inherit',
}

export function LoginPage({ onLogin }: LoginPageProps) {
  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 24 }}>
      <section
        style={{
          width: 'min(420px, 100%)',
          padding: 24,
          borderRadius: 8,
          background: colorAlpha('--background', 72),
          border: `1px solid ${colorAlpha('--text', 18)}`,
          boxShadow: 'var(--surface-shadow)',
        }}
      >
        <span className="search-query-label">Login page</span>
        <h1 style={{ marginTop: 8, fontSize: 32 }}>Choose role</h1>
        <div style={{ display: 'grid', gap: 12, marginTop: 24 }}>
          <button type="button" style={loginButtonStyle} onClick={() => onLogin('user')}>
            User
          </button>
          <button type="button" style={loginButtonStyle} onClick={() => onLogin('admin')}>
            Admin
          </button>
        </div>
      </section>
    </div>
  )
}
