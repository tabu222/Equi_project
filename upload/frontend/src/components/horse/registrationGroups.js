export const registrationFilters = [
  ['NeedsAction', 'Cần xử lý'],
  ['Submitted', 'Chờ xác minh'],
  ['WaitingExam', 'Chờ khám'],
  ['Examined', 'Đã khám, chờ xử lý'],
  ['Approved', 'Đã tiếp nhận'],
  ['Draft', 'Nháp'],
  ['Rejected', 'Từ chối'],
  ['Archived', 'Lưu trữ'],
  ['All', 'Tất cả'],
]

export function registrationGroup(horse) {
  if (horse.profileStatus === 'SUBMITTED') return 'Submitted'
  if (horse.profileStatus === 'PENDING_EXAM') {
    if (horse.initialExamSigned === true) return 'Examined'
    if (horse.initialExamSigned === false) return 'WaitingExam'
    return 'Unknown'
  }
  if (horse.profileStatus === 'APPROVED') return 'Approved'
  if (horse.profileStatus === 'DRAFT') return 'Draft'
  if (horse.profileStatus === 'REJECTED') return 'Rejected'
  if (horse.profileStatus === 'ARCHIVED') return 'Archived'
  return 'Unknown'
}

export function matchesRegistrationFilter(horse, filter) {
  const group = registrationGroup(horse)
  if (filter === 'NeedsAction') return group === 'Submitted' || group === 'Examined'
  if (filter === 'All') return true
  return group === filter
}

export function registrationGroupLabel(horse) {
  const group = registrationGroup(horse)
  if (group === 'WaitingExam') return 'Chờ Vet khám và chốt phiếu'
  if (group === 'Examined') return 'Đã khám, chờ xử lý'
  if (group === 'Submitted') return 'Chờ xác minh'
  if (group === 'Approved') return 'Đã tiếp nhận'
  if (group === 'Draft') return 'Nháp'
  if (group === 'Rejected') return 'Từ chối'
  if (group === 'Archived') return 'Lưu trữ'
  if (horse.profileStatus === 'PENDING_EXAM') return 'Chưa xác định tình trạng phiếu khám'
  return horse.profileStatus
}
