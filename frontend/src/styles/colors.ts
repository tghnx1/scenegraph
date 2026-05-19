// centralized color palette (Everforest Light Medium fallback)
export type ThemeName = 'light' | 'dark'

export const NODE_COLORS: Record<string, string> = {
  artist:    'rgb(223, 105, 186)',
  venue:     '#3A94C5',
  promoter:  '#35a77c',
  event:     '#f85552',
  selection: '#dfa000',
}

export function getStoredTheme(): ThemeName {
  if (typeof localStorage === 'undefined') return 'light'
  return localStorage.getItem('scenegraph-theme') === 'dark' ? 'dark' : 'light'
}

export const LINK_HIGHLIGHT = '#dfa000'
export const LINK_DIM = '#939f91'
export const BACKGROUND = '#fdf6e3'
export const TEXT = '#5c6a72'
export const TEXT_MUTED = '#829181'
export const ACCENT = '#35a77c'
export const ACCENT_WARM = '#f57d26'
export const SHADOW = '#000000'
export const GRADIENT_START = '#fdf6e3'
export const GRADIENT_MID = '#f4f0d9'
export const GRADIENT_END = '#f2efdf'

export const PALETTE: Record<string, string> = {
  '--artist': NODE_COLORS.artist,
  '--venue': NODE_COLORS.venue,
  '--promoter': NODE_COLORS.promoter,
  '--event': NODE_COLORS.event,
  '--selection': NODE_COLORS.selection,
  '--link-highlight': LINK_HIGHLIGHT,
  '--link-dim': LINK_DIM,
  '--background': BACKGROUND,
  '--text': TEXT,
  '--text-muted': TEXT_MUTED,
  '--accent': ACCENT,
  '--accent-warm': ACCENT_WARM,
  '--shadow': SHADOW,
  '--gradient-1': GRADIENT_START,
  '--gradient-2': GRADIENT_MID,
  '--gradient-3': GRADIENT_END,
}

export function applyCssVars() {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.dataset.theme = getStoredTheme()
}

export function applyTheme(theme: ThemeName) {
  if (typeof document === 'undefined') return
  document.documentElement.dataset.theme = theme
  localStorage.setItem('scenegraph-theme', theme)
}

export const getCssVar = (name: string) => {
  if (typeof window === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export function hexToRgba(hex: string, alpha = 1) {
  const h = hex.replace('#', '')
  const normalized = h.length === 3 ? h.split('').map(c => c + c).join('') : h
  const bigint = parseInt(normalized, 16)
  const r = (bigint >> 16) & 255
  const g = (bigint >> 8) & 255
  const b = bigint & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export default {
  NODE_COLORS,
  LINK_HIGHLIGHT,
  LINK_DIM,
  BACKGROUND,
  TEXT,
  TEXT_MUTED,
  ACCENT,
  ACCENT_WARM,
  GRADIENT_START,
  GRADIENT_MID,
  GRADIENT_END,
  PALETTE,
  applyCssVars,
  applyTheme,
  getStoredTheme,
  getCssVar,
  hexToRgba,
}
