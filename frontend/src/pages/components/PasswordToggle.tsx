import { useState, type CSSProperties } from 'react'

interface PasswordInputProps {
  value: string
  onChange: (value: string) => void
  autoComplete: string
  inputStyle: CSSProperties
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
  inputStyle,
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
