import { login, register, type AuthRole } from '../api/auth'
import { type CSSProperties, useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { validateArtistProfileName, validateLoginForm, validateRegistrationForm } from '@/shared/lib/validation'
import { SEARCH_RESULT_LIMIT, fetchSearch } from '../api/search'
import { useApi } from '../api/useApi'
import type { SearchResponse, SearchResult } from '../types/search'
import { useDebouncedValue } from './hooks/useDebouncedValue'

interface LoginPageProps {
  onLogin: (role: AuthRole, redirect?: boolean) => void }

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) =>
  `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

type RegistrationMode = 'search' | 'new_artist'
const EMPTY_SEARCH_RESPONSE: SearchResponse = { query: '', results: [] }

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

const inputStyle: CSSProperties = {
  width: '100%',
  minWidth: 0,
  border: `1px solid ${colorAlpha('--text', 18)}`,
  borderRadius: 8,
  background: colorAlpha('--background', 64),
  color: colorVar('--text'),
  font: 'inherit',
  padding: '10px 12px',
  outline: 'none',
}

const artistClaimMeta = (artist: SearchResult) => {
  const normalizedBio = artist.biography_normalized?.trim()
  const bioSnippet = normalizedBio || artist.biography_preview?.trim() || 'No bio yet'
  const latestEvent = artist.latest_event_title
    ? `Latest event: ${artist.latest_event_title}${artist.latest_event_date ? ` · ${artist.latest_event_date}` : ''}`
    : 'No recent events'
  const genres = artist.genres?.length
    ? [...new Set(artist.genres.map((genre) => genre.trim()).filter(Boolean))].join(' · ')
    : 'No tags yet'
  const eventCount = artist.event_count ?? 0
  const source = artist.ra_artist_id ? 'Resident Advisor profile' : 'User-created profile'

  return { bioSnippet, latestEvent, genres, eventCount, source }
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate()
  const [username, setUsername] = useState(localStorage.getItem('last_username') ?? '')   // for keeping the username in the login mask
  const [password, setPassword] = useState('')
  const [error, setError] = useState(() => {
    const message = sessionStorage.getItem('auth_message') ?? ''
    sessionStorage.removeItem('auth_message')
    return message
  })

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [instagramUrl, setInstagramUrl] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [registrationMode, setRegistrationMode] = useState<RegistrationMode>('search')
  const [artistSearchValue, setArtistSearchValue] = useState('')
  const [selectedArtist, setSelectedArtist] = useState<SearchResult | null>(null)
  const debouncedArtistSearchValue = useDebouncedValue(artistSearchValue.trim(), 350)
  const shouldFetchArtistSearch =
    isRegistering &&
    registrationMode === 'search' &&
    debouncedArtistSearchValue.length >= 2 &&
    debouncedArtistSearchValue === artistSearchValue.trim()
  const { data: artistSearchData, isLoading: isArtistSearchLoading } = useApi<SearchResponse>(
    () => (
      shouldFetchArtistSearch
        ? fetchSearch(debouncedArtistSearchValue, SEARCH_RESULT_LIMIT, 'artist')
        : Promise.resolve(EMPTY_SEARCH_RESPONSE)
    ),
    [debouncedArtistSearchValue, shouldFetchArtistSearch]
  )
  const artistResults = (artistSearchData?.results ?? []).filter((result) => result.type === 'artist')
  const isArtistSearchWaiting = artistSearchValue.trim().length >= 2 && debouncedArtistSearchValue !== artistSearchValue.trim()

  useEffect(() => {
    const showLoginForm = () => {
      setError('')
      setIsRegistering(false)
    }
    window.addEventListener('show-login-form', showLoginForm)
    return () => {
      window.removeEventListener('show-login-form', showLoginForm)
    }
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    const cleanUsername = username.trim()
    const cleanEmail = email.trim()

    if (isRegistering) {
      const validationError = validateRegistrationForm(cleanUsername, cleanEmail, instagramUrl, password, passwordConfirm)
      if (validationError) {
        setError(validationError)
        return
      }
      if (registrationMode === 'search' && selectedArtist === null) {
        setError('Please select your artist profile from the search results.')
        return
      }
      if (registrationMode === 'new_artist') {
        const artistNameError = validateArtistProfileName(artistSearchValue)
        if (artistNameError) {
          setError(artistNameError)
          return
        }
      }

      setIsSubmitting(true)
      try {
        const response = await register({
          username: cleanUsername,
          email: cleanEmail,
          instagram_url: instagramUrl.trim(),
          password,
          password_confirm: passwordConfirm,
          artist_id: registrationMode === 'search' ? selectedArtist?.id ?? null : null,
          new_artist_name: registrationMode === 'new_artist' ? artistSearchValue.trim() : null,
        })

        if (!response.success) {
          setError(response.message)
          return
        }

        setError('Registration submitted. Your account will be available after manual review.')
        setIsRegistering(false)
        setPassword('')
        setPasswordConfirm('')
        setEmail('')
        setInstagramUrl('')
        setArtistSearchValue('')
        setSelectedArtist(null)
        setRegistrationMode('search')
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : 'Registration failed.')
      } finally {
        setIsSubmitting(false)
      }
      return
    }

    const validationError = validateLoginForm(cleanUsername, password)
    if (validationError) {
      setError(validationError)
      return
    }

    setIsSubmitting(true)

    try {
      const response = await login(cleanUsername, password)
      if (!response.success || !response.access_token) {
        setError(response.message || 'Invalid username or password')
        return
      }
      sessionStorage.removeItem('auth_message')
      setError('')

      const authenticatedUsername = response.username ?? cleanUsername
      const role: AuthRole =
        response.role === 'admin' 
          ? 'admin' 
          : response.role === 'agent'
            ? 'agent'
            : 'artist'

      localStorage.setItem('token', response.access_token)
      localStorage.setItem('role', role)
      localStorage.setItem('username', authenticatedUsername)
      localStorage.setItem('last_username', authenticatedUsername)

      if (response.user_id !== undefined) {
        localStorage.setItem('user_id', String(response.user_id))
      }

      if (response.artist_id) {
         localStorage.setItem('artist_id', String(response.artist_id))
      } else {
         localStorage.removeItem('artist_id')
      }

      //console.log('must_change_password:', response.must_change_password)
      if (response.must_change_password)
      {
        navigate('/change-password?forced=true', { replace: true })
        return
      }
      onLogin(role)

    } catch {
      setError('Login failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

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
        <span className="search-query-label">
          {isRegistering ? 'Register Page' : 'Login page'}
        </span>
        <h1 style={{ marginTop: 8, fontSize: 32 }}>
          {isRegistering ? 'Register' : 'Sign in'}
        </h1>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14, marginTop: 24 }}>
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Login username
            <input
              style={inputStyle}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
            {isRegistering && (
              <span style={{ fontSize: 12, color: colorVar('--text-muted') }}>
                This is your login handle for sign in. It can be different from your public artist name.
              </span>
            )}
          </label>
          {isRegistering && (
            <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
              Email
              <input
                style={inputStyle}
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
          )}
          {isRegistering && (
            <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
              Instagram URL
              <input
                style={inputStyle}
                type="url"
                value={instagramUrl}
                onChange={(event) => setInstagramUrl(event.target.value)}
                placeholder="https://www.instagram.com/yourprofile"
                autoComplete="url"
                required
              />
            </label>
          )}
          {isRegistering && (
            <div style={{ display: 'grid', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14, flex: 1 }}>
                  {registrationMode === 'search' ? 'Artist profile search' : 'New artist profile name'}
                  <input
                    style={inputStyle}
                    type={registrationMode === 'search' ? 'search' : 'text'}
                    value={artistSearchValue}
                    onChange={(event) => {
                      const nextValue = event.target.value
                      setArtistSearchValue(nextValue)
                      if (registrationMode === 'search') {
                        setSelectedArtist((currentArtist) => (
                          currentArtist && currentArtist.name !== nextValue ? null : currentArtist
                        ))
                      }
                    }}
                    placeholder={
                      registrationMode === 'search'
                        ? 'Search your artist name...'
                        : 'Enter the artist name to create'
                    }
                    autoComplete="off"
                    required
                  />
                  <span style={{ fontSize: 12, color: colorVar('--text-muted') }}>
                    This is your public artist name. It can be the same as another artist name.
                  </span>
                </label>
              </div>

              {registrationMode === 'search' && selectedArtist && (
                <div
                  style={{
                    display: 'grid',
                    gap: 6,
                    border: `1px solid ${colorAlpha('--text', 18)}`,
                    borderRadius: 10,
                    background: colorAlpha('--background', 90),
                    padding: 12,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <strong style={{ color: colorVar('--text') }}>Selected profile: {selectedArtist.name}</strong>
                    <button
                      type="button"
                      style={{ ...loginButtonStyle, padding: '4px 8px', fontSize: 12 }}
                      onClick={() => {
                        setSelectedArtist(null)
                        setArtistSearchValue('')
                      }}
                    >
                      Clear
                    </button>
                  </div>
                  {(() => {
                    const meta = artistClaimMeta(selectedArtist)
                    return (
                      <div style={{ display: 'grid', gap: 4, color: colorVar('--text-muted'), fontSize: 13 }}>
                        <span>{meta.source}</span>
                        <span>{meta.bioSnippet}</span>
                        <span>{meta.latestEvent}</span>
                        <span>{meta.genres}</span>
                        <span>{meta.eventCount} linked events</span>
                      </div>
                    )
                  })()}
                </div>
              )}

              {registrationMode === 'search' && artistSearchValue.trim().length >= 2 && !selectedArtist && (
                <div
                  style={{
                    display: 'grid',
                    gap: 4,
                    maxHeight: 200,
                    overflowY: 'auto',
                    border: `1px solid ${colorAlpha('--text', 18)}`,
                    borderRadius: 8,
                    background: colorAlpha('--background', 92),
                    padding: 6,
                  }}
                >
                  {(isArtistSearchWaiting || isArtistSearchLoading) && (
                    <span style={{ padding: '8px 10px', color: colorVar('--text-muted') }}>Searching...</span>
                  )}
                  {!isArtistSearchWaiting && !isArtistSearchLoading && artistResults.length === 0 && (
                    <span style={{ padding: '8px 10px', color: colorVar('--text-muted') }}>No artist matches</span>
                  )}
                  {!isArtistSearchWaiting && !isArtistSearchLoading && artistResults.map((artist) => (
                    <button
                      key={artist.id}
                      type="button"
                      style={{
                        ...loginButtonStyle,
                        display: 'grid',
                        gap: 4,
                        textAlign: 'left',
                        color: colorVar('--text'),
                      }}
                      onClick={() => {
                        setSelectedArtist(artist)
                        setArtistSearchValue(artist.name)
                      }}
                    >
                      <strong>{artist.name}</strong>
                      {(() => {
                        const meta = artistClaimMeta(artist)
                        return (
                          <>
                            <span style={{ color: colorVar('--text-muted'), fontSize: 12, fontWeight: 500 }}>
                              {meta.source} · {meta.eventCount} linked events
                            </span>
                            <span style={{ color: colorVar('--text-muted'), fontSize: 12, fontWeight: 500 }}>
                              {meta.bioSnippet}
                            </span>
                            <span style={{ color: colorVar('--text-muted'), fontSize: 12, fontWeight: 500 }}>
                              {meta.latestEvent}
                            </span>
                            <span style={{ color: colorVar('--text-muted'), fontSize: 12, fontWeight: 500 }}>
                              {meta.genres}
                            </span>
                          </>
                        )
                      })()}
                    </button>
                  ))}
                  {!isArtistSearchWaiting && !isArtistSearchLoading && artistSearchValue.trim().length >= 2 && (
                    <button
                      type="button"
                      style={{
                        ...loginButtonStyle,
                        display: 'grid',
                        gap: 4,
                        textAlign: 'left',
                        color: colorVar('--text'),
                        marginTop: 4,
                        borderStyle: 'dashed',
                      }}
                      onClick={() => {
                        setRegistrationMode('new_artist')
                        setSelectedArtist(null)
                      }}
                    >
                      <strong>Create new artist "{artistSearchValue.trim()}"</strong>
                      <span style={{ color: colorVar('--text-muted'), fontSize: 12, fontWeight: 500 }}>
                        None of these profiles are mine. Create a new artist profile with this name.
                      </span>
                    </button>
                  )}
                </div>
              )}

              {registrationMode === 'new_artist' && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  <button
                    type="button"
                    style={loginButtonStyle}
                    onClick={() => {
                      setRegistrationMode('search')
                      setSelectedArtist(null)
                    }}
                  >
                    Search existing profiles instead
                  </button>
                </div>
              )}
            </div>
          )}
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Password
            <input
              style={inputStyle}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {isRegistering && (
            <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
              Confirm password
              <input
                style={inputStyle}
                type="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                required
              />
            </label>
          )}
          {error && <p style={{ margin: 0, color: 'var(--danger, #d94848)', fontSize: 14 }}>{error}</p>}
          <button type="submit" style={loginButtonStyle} disabled={isSubmitting}>
            {isSubmitting
              ? isRegistering
                ? 'Registering...'
                : 'Signing in...'
              : isRegistering
                ? 'Register'
                : 'Sign in'}
          </button>
          <button
            type="button"
            style={loginButtonStyle}
            onClick={() => {
              if (!isRegistering) {
                setUsername('')
                setEmail('')
                setInstagramUrl('')
                setPassword('')
                setPasswordConfirm('')
                setArtistSearchValue('')
                setSelectedArtist(null)
                setRegistrationMode('search')
              }
              setIsRegistering(!isRegistering)
              setError('')
            }}
          >
            {isRegistering ? 'Back to sign in' : 'Create account'}
          </button>
        </form>
      </section>
    </div>
  )
}
