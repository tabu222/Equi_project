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
  PENDING_EXAM: 'Chờ khám',
  PENDING_COMPLETION: 'Chờ hoàn tất',
  RECEIVED: 'Đã nhận',
  ARCHIVED: 'Đã lưu trữ',
  NOT_ASSESSED: 'Chưa đánh giá',
  ELIGIBLE: 'Đủ điều kiện',
  MONITORING: 'Theo dõi',
  COMPLETED: 'Đã khám',
  PENDING: 'Chờ khám',
}

function StatusBadge({ status, type = 'default', label }) {
  const normalizedStatus = status?.toLowerCase()

  return <span className={`status-badge status-${type}-${normalizedStatus}`}>{label || statusLabels[status] || status || 'Chưa xác định'}</span>
}

export default StatusBadge
