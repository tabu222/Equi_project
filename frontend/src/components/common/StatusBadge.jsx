const statusLabels = {
  Approved: 'Đã duyệt',
  Pending: 'Chờ duyệt',
  Submitted: 'Chờ xác minh',
  PendingExam: 'Chờ khám',
  Rejected: 'Từ chối',
  Inactive: 'Không hoạt động',
  Unknown: 'Chưa xác định',
  UNKNOWN: 'Chưa cập nhật',
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
  COMPLETED: 'Đã khám',
  PENDING: 'Chờ khám',
  NOT_STARTED: 'Chưa bắt đầu',
  Draft: 'Phiếu nháp',
  Signed: 'Đã chốt',
}

function StatusBadge({ status, type = 'default', label }) {
  const normalizedStatus = status?.toLowerCase()

  return <span className={`status-badge status-${type}-${normalizedStatus || 'unknown'}`}>{label || statusLabels[status] || status || 'Chưa cập nhật'}</span>
}

export default StatusBadge
