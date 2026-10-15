const statusLabels = {
  Approved: 'Đã duyệt',
  Pending: 'Chờ duyệt',
  Rejected: 'Từ chối',
  Inactive: 'Không hoạt động',
  Unknown: 'Chưa xác định',
  Healthy: 'Khỏe mạnh',
  Monitor: 'Theo dõi',
  Injured: 'Chấn thương',
  Recovering: 'Đang hồi phục',
  Isolated: 'Cách ly',
  DRAFT: 'Bản nháp',
  SUBMITTED: 'Chờ xác minh',
  PENDING_EXAM: 'Chờ khám',
  APPROVED: 'Đã tiếp nhận',
  REJECTED: 'Bị từ chối',
  ARCHIVED: 'Đã lưu trữ',
  NOT_ASSESSED: 'Chưa đánh giá',
  ELIGIBLE: 'Đủ điều kiện',
  MONITORING: 'Theo dõi',
  INJURED: 'Chấn thương',
  RECOVERING: 'Đang hồi phục',
  ISOLATION: 'Cách ly',
  Eligible: 'Đủ điều kiện tập',
  Restricted: 'Tập có hạn chế',
  'Not Eligible': 'Không đủ điều kiện tập',
  Draft: 'Nháp',
  Signed: 'Đã chốt',
  COMPLETED: 'Đã khám',
  PENDING: 'Chờ khám',
}

function StatusBadge({ status, type = 'default', label }) {
  const normalizedStatus = status?.toLowerCase()

  return <span className={`status-badge status-${type}-${normalizedStatus}`}>{label || statusLabels[status] || status || 'Chưa xác định'}</span>
}

export default StatusBadge
