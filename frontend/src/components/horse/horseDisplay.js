const missingValue = 'Chưa cập nhật'

export function formatHorseCode(code) {
  const normalized = String(code || '').replace(/^#+/, '').trim()
  return normalized ? `#${normalized}` : missingValue
}

export function formatHorseDate(value) {
  if (!value) return missingValue
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(String(value))
  if (!match) return missingValue
  const [, year, month, day] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  if (
    date.getFullYear() !== Number(year)
    || date.getMonth() !== Number(month) - 1
    || date.getDate() !== Number(day)
  ) return missingValue
  return `${day}/${month}/${year}`
}

export function formatHorseDateTime(value) {
  if (!value) return missingValue
  const normalized = String(value).replace(' ', 'T')
  const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const date = new Date(hasTimeZone ? normalized : `${normalized}+07:00`)
  if (Number.isNaN(date.getTime())) return missingValue
  const parts = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const part = (type) => parts.find((item) => item.type === type)?.value || ''
  return `${part('day')}/${part('month')}/${part('year')} ${part('hour')}`
}

export function getHorseAge(value) {
  const formatted = formatHorseDate(value)
  if (formatted === missingValue) return ''
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(formatted)
  if (!match) return ''
  const [, day, month, year] = match
  const birthDate = new Date(Number(year), Number(month) - 1, Number(day))
  const today = new Date()
  if (birthDate > today) return ''
  let age = today.getFullYear() - birthDate.getFullYear()
  const beforeBirthday = today.getMonth() < birthDate.getMonth()
    || (today.getMonth() === birthDate.getMonth() && today.getDate() < birthDate.getDate())
  if (beforeBirthday) age -= 1
  return age >= 0 ? `${age} tuổi` : ''
}

export function valueOrMissing(value) {
  return value === null || value === undefined || String(value).trim() === ''
    ? missingValue
    : value
}
