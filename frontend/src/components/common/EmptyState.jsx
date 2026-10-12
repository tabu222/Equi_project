function EmptyState({
  title = 'Không tìm thấy dữ liệu',
  description = 'Không có dữ liệu phù hợp với điều kiện hiện tại.',
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 5.5h16v13H4z" /><path d="M8 10h8M8 14h5" /></svg></div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  )
}

export default EmptyState
