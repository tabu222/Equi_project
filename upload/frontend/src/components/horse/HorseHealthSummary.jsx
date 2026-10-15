function HorseHealthSummary({ children }) {
  return (
    <section className="profile-section">
      <div className="section-title"><h2>Sức khỏe</h2></div>
      {children ?? <p className="profile-copy">Chưa có dữ liệu sức khỏe bổ sung.</p>}
    </section>
  )
}

export default HorseHealthSummary
