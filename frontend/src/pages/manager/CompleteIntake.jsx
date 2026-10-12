import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import StatusBadge from '../../components/common/StatusBadge.jsx'

function CompleteIntake({ horses, horse: horseOverride, onCompleteIntake, onArchiveHorse }) {
  const { horseId } = useParams()
  const horse = horseOverride || horses.find((item) => String(item.id) === String(horseId))
  const [horseCode, setHorseCode] = useState(horse?.code || '')
  const [managerNote, setManagerNote] = useState('')
  const [archiveReason, setArchiveReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  if (!horse) return <main className="page-content"><section className="panel"><h1>Không tìm thấy ngựa</h1><Link to="/manager/horses">Quay lại danh sách ngựa</Link></section></main>

  async function complete(event) {
    event.preventDefault()
    setBusy(true); setError(''); setMessage('')
    try { await onCompleteIntake(horse.id, { HorseCode: horseCode.trim(), ManagerNote: managerNote.trim() }); setMessage('Đã gửi yêu cầu hoàn tất tiếp nhận.') }
    catch (saveError) { setError(saveError.message || 'Không thể hoàn tất tiếp nhận.') }
    finally { setBusy(false) }
  }

  async function archive(event) {
    event.preventDefault()
    if (!confirmed || !archiveReason.trim()) return
    setBusy(true); setError(''); setMessage('')
    try { await onArchiveHorse(horse.id, archiveReason.trim()); setMessage('Hồ sơ đã được lưu trữ.') }
    catch (saveError) { setError(saveError.message || 'Không thể lưu trữ hồ sơ.') }
    finally { setBusy(false) }
  }

  const canComplete = horse.profileStatus === 'PENDING_COMPLETION'
  return <main className="page-content">
    <div className="breadcrumb"><Link to={`/horses/${horse.id}`}>Hồ sơ ngựa</Link><span aria-hidden="true">/</span><span>Tiếp nhận / lưu trữ</span></div>
    <header className="page-heading"><div><p className="eyebrow">QUẢN LÝ CÂU LẠC BỘ · TIẾP NHẬN</p><h1>Tiếp nhận hồ sơ</h1><p>Xác nhận kết quả khám đầu vào để hoàn tất tiếp nhận ngựa.</p></div></header>
    <section className="panel"><div className="horse-context-card"><div><h2>{horse.name}</h2><p>Mã ngựa #{horse.code || horse.id} · {horse.breed}</p></div><StatusBadge status={horse.profileStatus} type="registration" /></div>
      {canComplete ? <form onSubmit={complete} className="horse-form-grid" style={{ marginTop: 16 }}>
        <label className="form-field"><span>Mã ngựa</span><input required value={horseCode} onChange={(event) => setHorseCode(event.target.value)} /></label>
        <label className="form-field" style={{ gridColumn: '1 / -1' }}><span>Ghi chú của quản lý (không bắt buộc)</span><textarea rows="3" value={managerNote} onChange={(event) => setManagerNote(event.target.value)} /></label>
        <button className="button" type="submit" disabled={busy || !horseCode.trim()}>{busy ? 'Đang xử lý...' : 'Hoàn tất tiếp nhận'}</button>
      </form> : <p className="profile-copy">Chỉ hồ sơ có kết quả khám đầu vào đã ký mới đủ điều kiện hoàn tất tiếp nhận.</p>}
      {horse.profileStatus === 'RECEIVED' && <p className="success-message">Hồ sơ đã hoàn tất tiếp nhận.</p>}
    </section>
    <section className="panel archive-panel" style={{ marginTop: 24 }}><h2>Lưu trữ hồ sơ</h2><p>Chuyển hồ sơ sang trạng thái không hoạt động mà không xóa lịch sử.</p>
      {horse.profileStatus === 'ARCHIVED' ? <p>Hồ sơ này đã được lưu trữ.</p> : <form onSubmit={archive}>
        <label className="form-field"><span>Lý do lưu trữ</span><textarea required rows="3" maxLength={500} placeholder="Nhập lý do lưu trữ..." value={archiveReason} onChange={(event) => setArchiveReason(event.target.value)} /></label>
        <label className="check-field"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>Tôi xác nhận lưu trữ hồ sơ và giữ nguyên lịch sử liên quan.</span></label>
        <button className="button archive-submit" type="submit" disabled={busy || !confirmed || !archiveReason.trim()}>{busy ? 'Đang xử lý...' : 'Lưu trữ hồ sơ'}</button>
      </form>}
    </section>
    {error && <p className="error-message" role="alert">{error}</p>}{message && <p className="success-message" role="status">{message}</p>}
  </main>
}

export default CompleteIntake
