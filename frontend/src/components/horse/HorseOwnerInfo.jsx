function HorseOwnerInfo({ owner, updatedAt, clubName }) {
  return (
    <section className="profile-section profile-info-card">
      <div className="section-title"><h2>Chủ sở hữu</h2></div>
      <div className="info-grid">
        <div className="info-item"><span>Họ và tên</span><strong>{owner?.fullName || 'Chưa có thông tin chủ sở hữu.'}</strong></div>
      </div>
      <div className="section-title"><h2>Câu lạc bộ</h2></div>
      <div className="info-grid">
        <div className="info-item"><span>Tên câu lạc bộ</span><strong>{clubName || 'Chưa cập nhật'}</strong></div>
        <div className="info-item"><span>Cập nhật hồ sơ</span><strong>{updatedAt || 'Chưa cập nhật'}</strong></div>
      </div>
    </section>
  )
}

export default HorseOwnerInfo
