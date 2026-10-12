function HorsePedigree({ horse }) {
  return (
    <section className="profile-section">
      <div className="section-title"><h2>Dòng dõi</h2></div>
      <div className="info-grid"><div className="info-item"><span>Ngựa cha</span><strong>{horse?.sireName || 'Chưa có thông tin'}</strong></div><div className="info-item"><span>Ngựa mẹ</span><strong>{horse?.damName || 'Chưa có thông tin'}</strong></div></div>
    </section>
  )
}

export default HorsePedigree
