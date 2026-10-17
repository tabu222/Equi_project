import { vetDateTime } from './vetDomain.js'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { addMedicalAmendment, getMedicalAmendments } from '../../api/vetApi.ts'
import HorseAvatar from '../../components/horse/HorseAvatar.jsx'
import { formatHorseCode } from '../../components/horse/horseDisplay.js'
import { HealthBadge, TrainingBadge, Unavailable } from './VetWorkspace.jsx'
import { latestSigned, recordHealthLabels, trainingLabels, vetError } from './vetDomain.js'

const tabs = { overview: 'Tổng quan sức khỏe', history: 'Lịch sử khám', treatments: 'Điều trị và đơn thuốc', injuries: 'Chấn thương và phục hồi', training: 'Điều kiện huấn luyện', calendar: 'Lịch y tế' }

function RecordDetails({ record, canAmend }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')
  const [content, setContent] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [retry, setRetry] = useState(0)
  const submitting = useRef(false)
  useEffect(() => {
    if (record.recordStatus !== 'Signed') return undefined
    let active = true
    getMedicalAmendments(record.id).then(rows => { if (active) { setItems(rows); setError('') } })
      .catch(e => { if (active) setError(vetError(e, 'Không thể tải lịch sử đính chính.')) })
    return () => { active = false }
  }, [record.id, record.recordStatus, retry])
  async function submit(event) {
    event.preventDefault()
    if (submitting.current || !reason.trim() || !content.trim()) return
    submitting.current = true
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await addMedicalAmendment(record.id, reason, content)
      setItems(rows => rows ? [...rows, result] : null)
      setRetry(v => v + 1)
      setReason(''); setContent(''); setMessage('Đã lưu đính chính; bệnh án gốc được giữ nguyên.')
    } catch (e) { setError(vetError(e, 'Chưa xác nhận lưu đính chính. Hãy tải lại lịch sử trước khi gửi lại.')) }
    finally { submitting.current = false; setBusy(false) }
  }
  return <div className="vet-record-details">
    <dl className="vet-details">{[
      ['Loại khám', record.examType], ['Thời điểm khám (giờ CLB)', vetDateTime(record.examDate)],
      ['Bác sĩ', record.vetName], ['Hồ sơ tiếp nhận liên quan', record.registrationRequestId ? `#${record.registrationRequestId}` : 'Không có'],
      ['Cân nặng', record.weightKg == null ? 'Chưa ghi' : `${record.weightKg} kg`], ['Chiều cao', record.heightCm == null ? 'Chưa ghi' : `${record.heightCm} cm`],
      ['Triệu chứng', record.symptoms], ['Chẩn đoán', record.diagnosis], ['Vị trí chấn thương ghi nhận', record.injuryLocation],
      ['Hướng điều trị', record.treatmentPlan], ['Kết luận', record.conclusion], ['Sức khỏe', recordHealthLabels[record.healthStatus]],
      ['Điều kiện tập', trainingLabels[record.trainingEligibility]], ['Hạn chế cụ thể', record.restrictionNote],
      ['Ngày tái khám', record.followUpDate], ['Ghi chú', record.note],
      ['Trạng thái phiếu', record.recordStatus === 'Signed' ? 'Đã chốt' : 'Nháp'],
      ...(record.recordStatus === 'Signed' ? [['Người chốt', record.vetName], ['Thời điểm chốt', vetDateTime(record.signedAt)]] : []),
    ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Chưa ghi nhận'}</dd></div>)}</dl>
    {record.recordStatus === 'Signed' && <section className="vet-amendments"><h3>Đính chính bệnh án</h3><p>Phiếu đã chốt được giữ nguyên. Chốt phiếu là xác nhận trong hệ thống, chưa phải chữ ký số.</p>
      {error && <p className="error-message" role="alert">{error} <button type="button" onClick={() => { setItems(null); setRetry(v => v + 1) }}>Tải lại lịch sử</button></p>}
      {!items && !error && <p role="status">Đang tải lịch sử đính chính…</p>}
      {items?.length === 0 && <p>Chưa có đính chính.</p>}
      {items?.map(item => <article className="vet-amendment" key={item.id}><strong>{item.author} · {vetDateTime(item.at)}</strong><p>Lý do: {item.reason}</p><p>{item.content}</p></article>)}
      {canAmend && <form onSubmit={submit}><label className="form-field"><span>Lý do đính chính</span><input required maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label><label className="form-field"><span>Nội dung đính chính</span><textarea required rows={3} value={content} onChange={e => setContent(e.target.value)} /></label><button className="button" disabled={busy || !items || !!error || !reason.trim() || !content.trim()}>{busy ? 'Đang lưu…' : 'Thêm đính chính'}</button></form>}
      {message && <p className="success-message" role="status">{message}</p>}
    </section>}
  </div>
}

export default function VetMedicalProfile({ horse, records, currentUser, onRefresh, activeRequestId }) {
  const [params, setParams] = useSearchParams()
  const tab = Object.hasOwn(tabs, params.get('tab')) ? params.get('tab') : 'overview'
  const [selected, setSelected] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState('')
  const latest = latestSigned(records, horse.id)
  const currentExam = records.find(r => r.registrationRequestId === activeRequestId && r.examType === 'Initial Exam')
  const selectedRecord = records.find(r => r.id === selected)
  const canManage = currentUser.permissions.includes('MEDICAL_MANAGE')
  const injuries = records.filter(r => r.injuryLocation)
  async function refresh() {
    if (refreshing) return
    setRefreshing(true); setRefreshError('')
    try { await onRefresh(horse.id) } catch { setRefreshError('Không thể tải lại hồ sơ. Vui lòng thử lại.') }
    finally { setRefreshing(false) }
  }
  return <main className="page-content vet-workspace">
    <Link className="breadcrumb-back-button" to="/vet/herd">← Sức khỏe toàn đàn</Link>
    <header className="page-heading vet-profile-heading"><div className="vet-profile-identity"><HorseAvatar horseId={horse.id} documents={horse.documents} name={horse.name} /><div><p className="eyebrow">HỒ SƠ Y TẾ</p><h1>{horse.name}</h1><p>{formatHorseCode(horse.code)} · Microchip: {horse.microchipNumber || 'Chưa cập nhật'}</p><small>Ô chuồng: {horse.currentStall?.StallNumber || 'Chưa xếp chuồng'}</small></div></div><div className="profile-actions"><button className="button button-secondary" disabled={refreshing} onClick={refresh}>{refreshing ? 'Đang tải…' : 'Tải lại hồ sơ'}</button><button className="button vet-emergency" disabled aria-describedby="vet-lock-unavailable">Khóa tập khẩn cấp</button></div></header>
    <p id="vet-lock-unavailable" className="vet-caption">Khóa khẩn cấp chưa khả dụng. Kết luận điều kiện tập trên phiếu chưa xác nhận đã áp dụng khóa tập.</p>
    {refreshError && <p className="error-message" role="alert">{refreshError}</p>}
    <div className="vet-profile-badges"><HealthBadge status={horse.healthStatus} /><TrainingBadge record={latest} /></div>
    <nav className="vet-tabs" aria-label="Các phần hồ sơ y tế">{Object.entries(tabs).map(([key, label]) => <Link key={key} to={`?tab=${key}`} aria-current={tab === key ? 'page' : undefined} onClick={() => setSelected('')}>{label}</Link>)}</nav>
    {tab === 'overview' && <div className="vet-two-columns"><section className="panel"><h2>Sức khỏe hiện tại</h2><HealthBadge status={horse.healthStatus} /><p>Cập nhật: {vetDateTime(horse.updatedAt)}</p><h3>Kết luận đã chốt gần nhất</h3>{latest ? <><p>{latest.conclusion || 'Chưa ghi kết luận'}</p><p>{latest.vetName} · {vetDateTime(latest.examDate)}</p><button className="button button-secondary" onClick={() => { setParams({ tab: 'history' }); setSelected(latest.id) }}>Xem kết quả</button></> : <p>Chưa có bệnh án đã chốt.</p>}</section><section className="panel"><h2>Khám đầu vào</h2><p>Trạng thái hồ sơ đăng ký: {({ PENDING_EXAM: 'Chờ khám / xử lý tiếp nhận', APPROVED: 'Đã tiếp nhận', REJECTED: 'Bị từ chối', ARCHIVED: 'Đã lưu trữ', SUBMITTED: 'Chờ xác minh', DRAFT: 'Nháp đăng ký' })[horse.profileStatus] || 'Chưa xác định'}</p><p>Phiếu khám: {currentExam ? currentExam.recordStatus === 'Signed' ? 'Đã chốt' : 'Nháp' : 'Chưa có phiếu cho lần đăng ký hiện tại'}</p>
      {currentExam?.recordStatus === 'Signed' ? <button className="button" onClick={() => { setParams({ tab: 'history' }); setSelected(currentExam.id) }}>Xem kết quả</button> : horse.profileStatus === 'PENDING_EXAM' && canManage ? currentExam && currentExam.vetId !== currentUser.id ? <p>Phiếu nháp đang do {currentExam.vetName} xử lý.</p> : <Link className="button" to={`/vet/horses/${horse.id}/examination`}>{currentExam ? 'Tiếp tục phiếu nháp' : 'Bắt đầu khám'}</Link> : null}<p>Vet đưa kết luận; Manager quyết định tiếp nhận.</p></section></div>}
    {tab === 'history' && <section className="panel"><h2>Lịch sử khám · {records.length} phiếu</h2>{!records.length && <p>Chưa có phiếu khám.</p>}<div className="vet-record-list">{records.map(record => <button key={record.id} className={`vet-record-button${selected === record.id ? ' selected' : ''}`} onClick={() => setSelected(record.id)}><strong>Phiếu #{record.id} · {record.examType}</strong><span>{vetDateTime(record.examDate)} · {record.vetName}</span><span className="vet-pill">{record.recordStatus === 'Signed' ? 'Đã chốt' : 'Nháp'}</span></button>)}</div>{selectedRecord && <RecordDetails key={selectedRecord.id} record={selectedRecord} canAmend={canManage} />}</section>}
    {tab === 'treatments' && <><section className="panel"><h2>Hướng điều trị ghi trong bệnh án</h2>{records.filter(r => r.treatmentPlan).map(r => <article className="vet-amendment" key={r.id}><strong>Phiếu #{r.id} · {r.recordStatus === 'Signed' ? 'Đã chốt' : 'Nháp'} · {vetDateTime(r.examDate)}</strong><p>{r.treatmentPlan}</p></article>)}{!records.some(r => r.treatmentPlan) && <p>Chưa ghi hướng điều trị.</p>}</section><Unavailable title="Đơn thuốc có cấu trúc" action="Thêm đơn thuốc">Chưa thể lưu thuốc, liều và đơn vị, đường dùng, tần suất, ngày dùng hoặc thời gian ngưng thuốc. Nội dung bệnh án chưa phải danh sách thuốc đang dùng.</Unavailable></>}
    {tab === 'injuries' && <><section className="panel"><h2>Vị trí chấn thương đã ghi nhận</h2>{injuries.map(r => <article className="vet-amendment" key={r.id}><strong>Phiếu #{r.id} · {r.recordStatus === 'Signed' ? 'Đã chốt' : 'Nháp'} · {vetDateTime(r.examDate)}</strong><p>{r.injuryLocation}</p></article>)}{!injuries.length && <p>Chưa ghi vị trí chấn thương trong bệnh án.</p>}</section><Unavailable title="Theo dõi chấn thương và phục hồi" action="Tạo dấu chấn thương">Chưa có mô hình cơ / xương để xem 3D và chưa thể lưu điểm đánh dấu, bên cơ thể hoặc lịch sử tái đánh giá. Hiện vị trí chỉ được ghi bằng chữ trong phiếu khám đầu vào; chưa có hồ sơ phục hồi riêng.</Unavailable></>}
    {tab === 'training' && <><section className="panel"><h2>Điều kiện tập theo kết luận gần nhất</h2><TrainingBadge record={latest} /><p>{latest?.restrictionNote || 'Chưa ghi hạn chế cụ thể.'}</p>{latest && <p>{latest.vetName} · {vetDateTime(latest.signedAt)} · Phiếu #{latest.id}</p>}<p>Sức khỏe và điều kiện tập được kết luận riêng. Không tự mở hạn chế theo ngày dự kiến.</p></section><Unavailable title="Khóa / mở khóa huấn luyện" action="Điều chỉnh khóa tập">Chưa thể xác nhận khóa hiện hành, các buổi tập bị ảnh hưởng hoặc áp dụng giới hạn bài tập tại đây. Mở khóa cần kết luận tái khám và lý do.</Unavailable></>}
    {tab === 'calendar' && <><section className="panel"><h2>Ngày tái khám theo kết luận gần nhất</h2><p>{latest?.followUpDate || 'Chưa có chỉ định ngày tái khám.'}</p><p>Đây là ngày chỉ định trên bệnh án, chưa phải lịch đã đặt; chưa xác nhận đã hoàn thành tái khám.</p><Link to="/vet/calendar">Xem các mốc tái khám của đàn →</Link></section><Unavailable title="Lịch y tế của ngựa" action="Đặt lịch">Tiêm phòng, tẩy giun, chăm sóc móng, khám định kỳ và nhắc việc tự động chưa khả dụng.</Unavailable></>}
  </main>
}
