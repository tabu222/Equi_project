import { formatHorseGender } from './horseLabels.js'
import { formatHorseDate, valueOrMissing } from './horseDisplay.js'

function Value({ label, children }) {
  return <div className="info-item"><span>{label}</span><strong>{children ?? 'Chưa cập nhật'}</strong></div>
}

function HorseBasicInfo({ horse }) {
  return (
    <section className="profile-section profile-info-card">
      <div className="section-title"><h2>Thông tin nhận diện</h2></div>
      <div className="info-grid">
        <Value label="Mã ngựa">{valueOrMissing(horse.code)}</Value>
        <Value label="Tên ngựa">{valueOrMissing(horse.name)}</Value>
        <Value label="Giống">{valueOrMissing(horse.breed)}</Value>
        <Value label="Ngày sinh">{formatHorseDate(horse.dateOfBirth)}</Value>
        <Value label="Giới tính">{horse.sex === 'UNKNOWN' ? 'Chưa cập nhật' : formatHorseGender(horse.sex)}</Value>
        <Value label="Màu lông">{valueOrMissing(horse.coatColor)}</Value>
        <Value label="Microchip">{valueOrMissing(horse.microchipNumber)}</Value>
        <Value label="Hộ chiếu / đăng ký">{valueOrMissing(horse.registrationNumber)}</Value>
      </div>
    </section>
  )
}

export default HorseBasicInfo
