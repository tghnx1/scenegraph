//centralized color palette (Nord)
export const NODE_COLORS: Record<string, string> = {
  artist:    '#B48EAD',
  venue:     '#A3BE8C',
  promoter:  '#88C0D0',
  event:     '#BF616A',
  selection: '#EBCB8B',
}

export const LINK_HIGHLIGHT = '#EBCB8B'
export const LINK_DIM = '#D8DEE9'
export const BACKGROUND = '#3B4252'
export const TEXT = '#EBF3EF'
export const TEXT_MUTED = '#C9D6D1'
export const ACCENT = '#7FE0D2'
export const ACCENT_WARM = '#D08770'
export const SHADOW = '#000000'
export const GRADIENT_START = '#071117'
export const GRADIENT_MID = '#0f2733'
export const GRADIENT_END = '#16384a'

export const PALETTE: Record<string, string> = {
  '--nord-artist': NODE_COLORS.artist,
  '--nord-venue': NODE_COLORS.venue,
  '--nord-promoter': NODE_COLORS.promoter,
  '--nord-event': NODE_COLORS.event,
  '--nord-selection': NODE_COLORS.selection,
  '--nord-link-highlight': LINK_HIGHLIGHT,
  '--nord-link-dim': LINK_DIM,
  '--nord-background': BACKGROUND,
  '--nord-text': TEXT,
  '--nord-text-muted': TEXT_MUTED,
  '--nord-accent': ACCENT,
  '--nord-accent-warm': ACCENT_WARM,
  '--nord-shadow': SHADOW,
  '--nord-gradient-start': GRADIENT_START,
  '--nord-gradient-mid': GRADIENT_MID,
  '--nord-gradient-end': GRADIENT_END,
}

export function applyCssVars() {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  Object.entries(PALETTE).forEach(([k, v]) => root.style.setProperty(k, v))
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
  getCssVar,
  hexToRgba,
}
