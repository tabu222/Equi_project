import { useEffect, useState } from 'react'
import { getMedicalRecords, getVaccinations } from '../../api/horseApi'
import EmptyState from '../common/EmptyState.jsx'
import StatusBadge from '../common/StatusBadge.jsx'
import { formatDate, formatDateTime } from './horseLabels.js'

// FE2-06: lịch sử khám và tiêm phòng (Manager, Vet). Owner chỉ xem tóm tắt sức khỏe theo quyền backend.

const examTypeLabels = {
  'Initial Exam': 'Khám đầu vào',
  'Routine Exam': 'Khám định kỳ',
  'Injury Exam': 'Khám chấn thương',
  'Follow-up': 'Tái khám',
  Emergency: 'Cấp cứu',
}
const vaccinationStatusLabels = { Scheduled: 'Đã lên lịch', Completed: 'Đã tiêm', Cancelled: 'Đã hủy', Missed: 'Bỏ lỡ' }

function HorseMedicalHistory({ horseId, records: providedRecords }) {
  const [records, setRecords] = useState(providedRecords || [])
  const [vaccinations, setVaccinations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([
      providedRecords ? Promise.resolve(providedRecords) : getMedicalRecords(String(horseId)),
      getVaccinations(String(horseId)),
    ]).then(([recordRows, vaccinationRows]) => {
      if (!active) return
      setRecords(recordRows)
      setVaccinations(vaccinationRows)
      setError('')
    }).catch((loadError) => {
      if (active) setError(loadError instanceof Error ? loadError.message : 'Không thể tải lịch sử y tế.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [horseId, providedRecords])

  return (
    <section className="panel profile-section" aria-label="Lịch sử y tế">
      <h2>Lịch sử khám và tiêm phòng</h2>
      {loading && <p className="profile-copy" role="status">Đang tải lịch sử y tế...</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {!loading && !error && <>
        <h3 className="medical-subtitle">Phiếu khám ({records.length})</h3>
        {records.length === 0 ? <EmptyState title="Chưa có phiếu khám" description="Các lần khám sẽ hiển thị tại đây." /> : (
          <div className="medical-timeline">
            {records.map((record) => (
              <article className="request-item" key={record.id}>
                <div className="request-item-heading">
                  <div><strong>{examTypeLabels[record.examType] || record.examType} · Phiếu #{record.id}</strong><small>{formatDateTime(record.examDate)} · BS {record.vetName || `#${record.vetId}`}</small></div>
                  <StatusBadge status={record.recordStatus} label={record.recordStatus === 'Signed' ? 'Đã chốt' : 'Nháp'} />
                </div>
                {record.conclusion && <p><b>Kết luận:</b> {record.conclusion}</p>}
                {record.diagnosis && <p><b>Chẩn đoán:</b> {record.diagnosis}</p>}
                <p>
                  {record.healthStatus && <><b>Sức khỏe:</b> <StatusBadge status={record.healthStatus} type="health" /> </>}
                  {record.trainingEligibility && <><b>Tập luyện:</b> <StatusBadge status={record.trainingEligibility} /></>}
                </p>
                {record.restrictionNote && <p><b>Hạn chế:</b> {record.restrictionNote}</p>}
                {record.followUpDate && <p><b>Tái khám:</b> {formatDate(record.followUpDate)}</p>}
              </article>
            ))}
          </div>
        )}
        <h3 className="medical-subtitle">Tiêm phòng ({vaccinations.length})</h3>
        {vaccinations.length === 0 ? <EmptyState title="Chưa có lịch tiêm phòng" description="Mũi tiêm và lịch nhắc sẽ hiển thị tại đây." /> : (
          <div className="medical-timeline">
            {vaccinations.map((item) => (
              <article className="request-item" key={item.id}>
                <div className="request-item-heading">
                  <div><strong>{item.vaccineName}</strong><small>{formatDate(item.vaccinationDate)}{item.vetName ? ` · BS ${item.vetName}` : ''}</small></div>
                  <StatusBadge status={item.status} label={item.isOverdue ? 'Quá hạn' : vaccinationStatusLabels[item.status] || item.status} />
                </div>
                {item.nextDueDate && <p><b>Mũi tiếp theo:</b> {formatDate(item.nextDueDate)}</p>}
                {item.note && <p>{item.note}</p>}
              </article>
            ))}
          </div>
        )}
      </>}
    </section>
  )
}

export default HorseMedicalHistory
