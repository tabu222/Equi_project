function HorsePedigree({ horse }) {
  return (
    <section className="profile-section">
      <div className="section-title"><h2>Dòng dõi</h2></div>
      <p className="profile-copy">{horse?.pedigree || 'Chưa có thông tin phả hệ.'}</p>
    </section>
  )
}

export default HorsePedigree
