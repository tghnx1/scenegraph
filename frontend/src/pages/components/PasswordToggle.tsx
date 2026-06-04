import { useState, type CSSProperties } from 'react'

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

export const authButtonStyle: CSSProperties = {
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

export const authInputStyle: CSSProperties = {
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

interface PasswordInputProps {
  value: string
  onChange: (value: string) => void
  autoComplete: string
  inputStyle?: CSSProperties
  textColor?: string
  showLabel?: string
  hideLabel?: string
  ariaShowLabel?: string
  ariaHideLabel?: string
  required?: boolean
}

export function PasswordInput({
  value,
  onChange,
  autoComplete,
  inputStyle = authInputStyle,
  textColor = 'var(--text-muted)',
  showLabel = 'Show',
  hideLabel = 'Hide',
  ariaShowLabel = 'Show password',
  ariaHideLabel = 'Hide password',
  required = false,
}: PasswordInputProps) {
  const [isVisible, setIsVisible] = useState(false)

  const passwordInputStyle: CSSProperties = {
    ...inputStyle,
    paddingRight: 64,
  }

  const passwordToggleStyle: CSSProperties = {
    position: 'absolute',
    right: 8,
    top: '50%',
    transform: 'translateY(-50%)',
    border: 0,
    background: 'transparent',
    color: textColor,
    cursor: 'pointer',
    font: 'inherit',
    fontSize: 13,
    fontWeight: 700,
    padding: '4px 6px',
  }

  return (
    <span style={{ position: 'relative', display: 'block' }}>
      <input
        style={passwordInputStyle}
        type={isVisible ? 'text' : 'password'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        required={required}
      />
      <button
        type="button"
        style={passwordToggleStyle}
        onClick={() => setIsVisible((current) => !current)}
        aria-label={isVisible ? ariaHideLabel : ariaShowLabel}
      >
        {isVisible ? hideLabel : showLabel}
      </button>
    </span>
  )
}
