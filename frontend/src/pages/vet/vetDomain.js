// The legacy FE name ELIGIBLE here means Healthy, never permission to train.
export const healthLabels = {
  ELIGIBLE: 'Đủ điều kiện sức khỏe', MONITORING: 'Cần theo dõi', INJURED: 'Chấn thương',
  ISOLATION: 'Cách ly', RECOVERING: 'Đang hồi phục', NOT_ASSESSED: 'Chưa đánh giá',
}
export const recordHealthLabels = { Healthy: 'Khỏe mạnh', Monitor: 'Cần theo dõi', Injured: 'Chấn thương', Recovering: 'Đang hồi phục', Isolated: 'Cách ly' }
export const trainingLabels = { Eligible: 'Đủ điều kiện tập', Restricted: 'Hạn chế tập', 'Not Eligible': 'Không được tập' }
export const clubTimezone = 'Asia/Ho_Chi_Minh'
export function vetDateTime(value) {
  if (!value) return 'Chưa cập nhật'
  const normalized = String(value).replace(' ', 'T')
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}+07:00`)
  if (!Number.isFinite(date.getTime())) return 'Chưa cập nhật'
  return new Intl.DateTimeFormat('vi-VN', { timeZone: clubTimezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(date)
}
export function clubToday(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: clubTimezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now)
  const get = (type) => parts.find(p => p.type === type).value
  return `${get('year')}-${get('month')}-${get('day')}`
}
export function clubDateTimeInput(value) {
  // SQL DATETIME2 is local club time (USE_TZ=False). Offset timestamps are converted explicitly.
  if (value && !/(Z|[+-]\d\d:\d\d)$/i.test(value)) return value.replace(' ', 'T').slice(0, 19)
  const now = value ? new Date(value) : new Date()
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: clubTimezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(now)
  const get = type => parts.find(p => p.type === type).value
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}:${get('second')}`
}
export function latestSigned(records, horseId) {
  return records.filter(r => r.horseId === horseId && r.recordStatus === 'Signed')
    .sort((a, b) => b.examDate.localeCompare(a.examDate) || Number(b.id) - Number(a.id))[0]
}
export function dueGroup(day, today = clubToday()) {
  return !day ? 'unknown' : day < today ? 'overdue' : day === today ? 'today' : 'upcoming'
}
export function vetError(error, fallback = 'Không thể tải dữ liệu. Vui lòng thử lại.') {
  if (error?.status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
  if (error?.status === 404) return 'Không tìm thấy hồ sơ hoặc bạn không có quyền truy cập.'
  return fallback
}
