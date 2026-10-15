function HorsePedigree({ horse }) {
  return (
    <section className="profile-section">
      <div className="section-title"><h2>Dòng dõi</h2></div>
      <div className="info-grid">
        <div className="info-item"><span>Tên ngựa cha</span><strong>{horse?.sireName || '—'}</strong></div>
        <div className="info-item"><span>Tên ngựa mẹ</span><strong>{horse?.damName || '—'}</strong></div>
      </div>
    </section>
  )
}

export default HorsePedigree
