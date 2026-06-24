export const USERNAME_PATTERN = /^[a-zA-Z0-9_-]{3,32}$/
export const EMAIL_MAX_LENGTH = 254
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128
export const BIOGRAPHY_MAX_LENGTH = 6000

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const DISPLAY_DATE_PATTERN = /^\d{2}\.\d{2}\.\d{4}$/
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isoDateToDisplayDate(value: string) {
  if (!ISO_DATE_PATTERN.test(value)) return value

  const [year, month, day] = value.split('-')
  return `${day}.${month}.${year}`
}

export function displayDateToIsoDate(value: string) {
  if (!DISPLAY_DATE_PATTERN.test(value)) return null

  const [day, month, year] = value.split('.')
  const date = new Date(Number(year), Number(month) - 1, Number(day))

  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day)
  ) {
    return null
  }

  return `${year}-${month}-${day}`
}

export function validateUsername(value: string) {
  if (!USERNAME_PATTERN.test(value.trim())) {
    return 'Username must be 3-32 characters and contain only letters, numbers, _ or -'
  }

  return null
}

export function validateEmail(value: string) {
  const email = value.trim()

  if (email.length > EMAIL_MAX_LENGTH || !EMAIL_PATTERN.test(email)) {
    return 'Invalid email'
  }

  return null
}

export function validatePassword(value: string) {
  if (value.length < PASSWORD_MIN_LENGTH) {
    return 'Password must be at least 8 characters'
  }

  if (value.length > PASSWORD_MAX_LENGTH) {
    return 'Password is too long'
  }

  return null
}

export function validateLoginForm(username: string, password: string) {
  const usernameError = validateUsername(username)
  if (usernameError) return usernameError

  if (!password) {
    return 'Password is required'
  }

  return null
}

export function validateRegistrationForm(
  username: string,
  email: string,
  password: string,
  passwordConfirm: string,
) {
  if (password !== passwordConfirm) {
    return 'Passwords do not match'
  }

  return validateUsername(username) ?? validateEmail(email) ?? validatePassword(password)
}

export function validateChangePasswordForm(
  currentPassword: string,
  newPassword: string,
  newPasswordConfirm: string,
) {
  if (!currentPassword) {
    return 'Current password is required'
  }

  if (newPassword !== newPasswordConfirm) {
    return 'New passwords do not match'
  }

  if (currentPassword === newPassword) {
    return 'New password must be different from current password'
  }

  return validatePassword(newPassword)
}

export function validateBiography(value: string) {
  if (value.length > BIOGRAPHY_MAX_LENGTH) {
    return `Biography must be at most ${BIOGRAPHY_MAX_LENGTH} characters.`
  }

  return null
}
