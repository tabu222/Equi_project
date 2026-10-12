import { useState } from 'react'
import { Link } from 'react-router-dom'
import StatusBadge from '../../components/common/StatusBadge.jsx'

const healthStatuses = [
  ['ELIGIBLE', 'Đủ điều kiện'], ['MONITORING', 'Theo dõi'], ['INJURED', 'Chấn thương'], ['ISOLATION', 'Cách ly'],
]
const eligibilityOptions = [['Eligible', 'Đủ điều kiện'], ['Restricted', 'Hạn chế'], ['Not Eligible', 'Không đủ điều kiện']]

function VetExaminationForm({ horse, currentUser, owner, onSaveDraft, onFinalize, onHorseSaved }) {
  const existing = [...(horse.examinations || [])].reverse().find((item) => item.status === 'DRAFT') || {}
  const assessment = horse.healthAssessment || {}
  const [form, setForm] = useState(() => ({
    examinedAt: (existing.examinedAt || new Date().toISOString()).slice(0, 10),
    weightKg: existing.weightKg ?? '', heightCm: existing.heightCm ?? '',
    symptoms: existing.symptoms || '', diagnosis: existing.diagnosis || '', treatmentPlan: existing.treatmentPlan || '',
    conclusion: existing.conclusion || assessment.conclusion || '', healthStatus: existing.healthStatus || '',
    trainingEligibility: existing.trainingEligibility || assessment.trainingEligibility || '',
    purpose: existing.purpose || 'Khám đầu vào', exerciseRestrictions: existing.exerciseRestrictions || '',
    followUpDate: existing.followUpDate || '',
  }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const initialExam = ['PENDING_EXAM', 'PENDING_COMPLETION'].includes(horse.profileStatus)

  function change(key, value) { setForm((current) => ({ ...current, [key]: value })) }

  async function save(sign, event) {
    event?.preventDefault()
    setError(''); setMessage('')
    if (sign && (!form.examinedAt || !form.healthStatus || !form.trainingEligibility || !form.conclusion.trim())) {
      setError('Vui lòng nhập ngày khám, tình trạng sức khỏe, khả năng tập luyện và kết luận.')
      return
    }
    if (sign && new Date(form.examinedAt) > new Date()) { setError('Ngày khám không được ở tương lai.'); return }
    setSaving(true)
    try {
      const payload = { ...form, weightKg: form.weightKg === '' ? undefined : Number(form.weightKg), heightCm: form.heightCm === '' ? undefined : Number(form.heightCm) }
      const saved = await (sign ? onFinalize : onSaveDraft)(horse.id, currentUser, payload)
      onHorseSaved(saved)
      setMessage(sign ? 'Đã ký kết luận khám.' : 'Đã lưu phiếu khám nháp.')
    } catch (saveError) { setError(saveError.message || 'Không thể lưu phiếu khám.') }
    finally { setSaving(false) }
  }

  return <main className="page-content narrow-content">
    <div className="breadcrumb"><Link to={`/vet/horses/${horse.id}`}>Hồ sơ ngựa</Link><span aria-hidden="true">/</span><span>Phiếu khám</span></div>
    <header className="page-heading"><div><p className="eyebrow">BÁC SĨ THÚ Y · {initialExam ? 'KHÁM ĐẦU VÀO' : 'KHÁM THEO DÕI'}</p><h1>{horse.name}</h1><p>Mã ngựa #{horse.code || horse.id} · {horse.breed} · Chủ sở hữu: {owner?.fullName || 'Chưa có thông tin'}</p></div></header>
    <section className="horse-context-card"><div><h2>{horse.name}</h2><p>Trạng thái hồ sơ: {horse.profileStatus}</p></div><StatusBadge status={horse.healthStatus} type="health" /></section>
    {error && <div className="alert-banner" role="alert">{error}</div>}{message && <p className="success-message" role="status">{message}</p>}
    <section className="panel form-panel"><h2>Phiếu khám</h2>
      <form onSubmit={(event) => void save(true, event)}>
        <label className="form-field"><span>Ngày khám</span><input type="date" required value={form.examinedAt} onChange={(event) => change('examinedAt', event.target.value)} /></label>
        <div className="horse-form-grid">
          <label className="form-field"><span>Cân nặng (kg)</span><input type="number" min="0" step="0.1" value={form.weightKg} onChange={(event) => change('weightKg', event.target.value)} /></label>
          <label className="form-field"><span>Chiều cao (cm)</span><input type="number" min="0" step="0.1" value={form.heightCm} onChange={(event) => change('heightCm', event.target.value)} /></label>
        </div>
        <label className="form-field"><span>Triệu chứng</span><textarea rows="3" value={form.symptoms} onChange={(event) => change('symptoms', event.target.value)} /></label>
        <label className="form-field"><span>Chẩn đoán</span><textarea rows="3" value={form.diagnosis} onChange={(event) => change('diagnosis', event.target.value)} /></label>
        <label className="form-field"><span>Điều trị</span><textarea rows="3" value={form.treatmentPlan} onChange={(event) => change('treatmentPlan', event.target.value)} /></label>
        <label className="form-field"><span>Kết luận</span><textarea required rows="3" value={form.conclusion} onChange={(event) => change('conclusion', event.target.value)} /></label>
        <div className="horse-form-grid">
          <label className="form-field"><span>Tình trạng sức khỏe</span><select required value={form.healthStatus} onChange={(event) => change('healthStatus', event.target.value)}><option value="">Chọn tình trạng</option>{healthStatuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="form-field"><span>Khả năng tập luyện</span><select required value={form.trainingEligibility} onChange={(event) => change('trainingEligibility', event.target.value)}><option value="">Chọn kết luận</option>{eligibilityOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>
        {form.trainingEligibility === 'Restricted' && <label className="form-field"><span>Hạn chế vận động</span><textarea required rows="2" value={form.exerciseRestrictions} onChange={(event) => change('exerciseRestrictions', event.target.value)} /></label>}
        <label className="form-field"><span>Ngày tái khám</span><input type="date" value={form.followUpDate} onChange={(event) => change('followUpDate', event.target.value)} /></label>
        <div className="form-actions"><button className="button button-secondary" type="button" disabled={saving} onClick={() => void save(false)}>{saving ? 'Đang lưu...' : 'Lưu nháp'}</button><button className="button" type="submit" disabled={saving}>{saving ? 'Đang lưu...' : 'Ký kết luận'}</button></div>
      </form>
    </section>
  </main>
}

export default VetExaminationForm
