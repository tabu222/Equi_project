const genderLabels = { Male: 'Đực', Female: 'Cái', Gelding: 'Đực đã thiến', MALE: 'Đực', FEMALE: 'Cái', GELDING: 'Đực đã thiến', UNKNOWN: 'Chưa có thông tin' }

export function formatHorseGender(gender) {
  return genderLabels[gender] || gender || 'Chưa có thông tin'
}

const eligibilityLabels = { Eligible: 'Đủ điều kiện tập', Restricted: 'Tập có hạn chế', 'Not Eligible': 'Không đủ điều kiện tập' }

export function formatEligibility(value) {
  return eligibilityLabels[value] || value || 'Chưa có kết luận'
}

// "2026-10-14" -> "14/10/2026"; "2026-10-14T12:00:00" -> "14/10/2026 12:00"
export function formatDate(value) {
  if (!value) return '—'
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value
}

export function formatDateTime(value) {
  if (!value) return '—'
  const time = /T(\d{2}:\d{2})/.exec(value)
  return time ? `${formatDate(value)} ${time[1]}` : formatDate(value)
}
