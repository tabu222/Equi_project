function HorseOwnerInfo({ owner, ownerId }) {
  const resolvedOwnerId = owner?.ownerId ?? ownerId

  return (
    <section className="profile-section">
      <div className="section-title"><h2>Chủ sở hữu</h2></div>
      <div className="info-grid">
        <div className="info-item"><span>Họ và tên</span><strong>{owner?.fullName || 'Chưa có thông tin chủ sở hữu.'}</strong></div>
        <div className="info-item"><span>Mã chủ sở hữu</span><strong>{resolvedOwnerId ?? 'Chưa có thông tin'}</strong></div>
      </div>
    </section>
  )
}

export default HorseOwnerInfo
