export type ThemeName = 'light' | 'dark'

export function getStoredTheme(): ThemeName {
  if (typeof localStorage === 'undefined') return 'light'
  return localStorage.getItem('scenegraph-theme') === 'dark' ? 'dark' : 'light'
}

export function applyStoredTheme() {
  if (typeof document === 'undefined') return
  document.documentElement.dataset.theme = getStoredTheme()
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
