import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import { registrationGroupLabel } from '../../components/horse/registrationGroups.js'

function CompleteIntake({ horses, horse: horseOverride, stalls = [], stallError = '', onRetryStalls, permissions = [], onUpdateHorse, onSubmitHorse, onVerifyHorse, onRejectHorse, onApproveHorse, onArchiveHorse }) {
  const { horseId } = useParams()
  const horse = horseOverride ?? horses.find((item) => String(item.id) === String(horseId))
  const [horseCode, setHorseCode] = useState(horse?.code || '')
  const [stallId, setStallId] = useState('')
  const [managerNote, setManagerNote] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [archiveReason, setArchiveReason] = useState('')
  const [profile, setProfile] = useState(() => horse ? profileValues(horse) : {})
  const [savedProfile, setSavedProfile] = useState(() => horse ? profileValues(horse) : {})
  const [confirmArchive, setConfirmArchive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  if (!horse) {
    return <main className="page-content"><section className="panel"><h1>Không tìm thấy ngựa</h1><Link to="/manager/horses">Quay lại danh sách ngựa</Link></section></main>
  }

  const signed = horse.initialExamSigned === true
  const health = horse.healthAssessment?.healthStatus
  const eligibility = horse.healthAssessment?.trainingEligibility
  const healthPasses = health === 'ELIGIBLE' || health === 'MONITORING'
  const eligibilityPasses = eligibility === 'Eligible' || eligibility === 'Restricted'
  const canApprove = horse.profileStatus === 'PENDING_EXAM' && signed && healthPasses && eligibilityPasses && Boolean(horseCode.trim())
  const canRegister = permissions.includes('HORSE_REGISTER') || permissions.includes('HORSE_REGISTER_REVIEW')
  const canReview = permissions.includes('HORSE_REGISTER_REVIEW')
  const canArchive = permissions.includes('HORSE_ARCHIVE')
  const canEdit = canRegister && (horse.profileStatus === 'DRAFT' || horse.profileStatus === 'REJECTED')
  const approvalBlockers = []
  if (!signed) approvalBlockers.push('Cần Vet chốt phiếu khám đầu vào.')
  if (signed && !healthPasses) approvalBlockers.push('Kết luận sức khỏe phải là Healthy hoặc Monitor.')
  if (signed && healthPasses && !eligibilityPasses) approvalBlockers.push('TrainingEligibility không được là Not Eligible.')
  if (signed && healthPasses && eligibilityPasses && !horseCode.trim()) approvalBlockers.push('Cần nhập mã ngựa trước khi duyệt.')

  async function runAction(action, successMessage) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await action()
      setMessage(successMessage)
      return true
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Không thể hoàn tất thao tác.')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function saveProfile(event) {
    event.preventDefault()
    const changes = Object.fromEntries(Object.entries(profile).filter(([key, value]) => value !== savedProfile[key]))
    if (!Object.keys(changes).length) {
      setMessage('Không có thay đổi để lưu.')
      return
    }
    const saved = await runAction(() => onUpdateHorse(horse.id, changes), 'Đã cập nhật hồ sơ.')
    if (saved) setSavedProfile({ ...profile })
  }

  function submit(event) {
    event.preventDefault()
    void runAction(() => onSubmitHorse(horse.id), 'Đã gửi hồ sơ đến câu lạc bộ.')
  }

  function reject(event) {
    event.preventDefault()
    if (!rejectReason.trim()) return
    void runAction(() => onRejectHorse(horse.id, rejectReason.trim()), 'Đã từ chối hồ sơ.')
  }

  function approve(event) {
    event.preventDefault()
    if (!canApprove) return
    void runAction(() => onApproveHorse(horse.id, {
      HorseCode: horseCode.trim(),
      ...(stallId ? { StallID: Number(stallId) } : {}),
      ...(managerNote.trim() ? { ManagerNote: managerNote.trim() } : {}),
    }), 'Đã duyệt và tiếp nhận hồ sơ.')
  }

  function archive(event) {
    event.preventDefault()
    if (!archiveReason.trim() || !confirmArchive) return
    void runAction(() => onArchiveHorse(horse.id, archiveReason.trim()), 'Đã lưu trữ hồ sơ.')
  }

  return (
    <main className="page-content">
      <div className="breadcrumb"><Link to={`/horses/${horse.id}`}>Hồ sơ ngựa</Link><span aria-hidden="true">/</span><span>Tiếp nhận / lưu trữ</span></div>
      <header className="page-heading"><div><p className="eyebrow">QUẢN LÝ CÂU LẠC BỘ · FLOW 1</p><h1>Xử lý hồ sơ ngựa</h1><p>Xác minh hồ sơ, duyệt sau khi khám đầu vào hoặc lưu trữ ngựa đã được tiếp nhận.</p></div></header>
      <section className="panel">
        <div className="horse-context-card"><div><h2>{horse.name}</h2><p>Mã ngựa #{horse.id} · {horse.breed}</p>{horse.profileStatus === 'PENDING_EXAM' && <p>{registrationGroupLabel(horse)}</p>}</div><StatusBadge status={horse.profileStatus} label={registrationGroupLabel(horse)} type="registration" /></div>
        {error && <p className="error-message" role="alert">{error}</p>}
        {message && <p className="success-message" role="status">{message}</p>}

        {canEdit && <form onSubmit={saveProfile} className="profile-section">
          <h2>Thông tin lý lịch</h2>
          <div className="horse-form-grid">
            <label className="form-field"><span>Tên ngựa</span><input required value={profile.name} onChange={(event) => setProfile((value) => ({ ...value, name: event.target.value }))} /></label>
            <label className="form-field"><span>Giống</span><input required value={profile.breed} onChange={(event) => setProfile((value) => ({ ...value, breed: event.target.value }))} /></label>
            <label className="form-field"><span>Ngày sinh</span><input type="date" required value={profile.dateOfBirth} onChange={(event) => setProfile((value) => ({ ...value, dateOfBirth: event.target.value }))} /></label>
            <label className="form-field"><span>Giới tính</span><select value={profile.sex} onChange={(event) => setProfile((value) => ({ ...value, sex: event.target.value }))}><option value="MALE">Đực</option><option value="FEMALE">Cái</option><option value="GELDING">Đực đã thiến</option></select></label>
            <label className="form-field"><span>Màu lông</span><input required value={profile.coatColor} onChange={(event) => setProfile((value) => ({ ...value, coatColor: event.target.value }))} /></label>
            <label className="form-field"><span>Hộ chiếu / đăng ký</span><input required value={profile.registrationNumber} onChange={(event) => setProfile((value) => ({ ...value, registrationNumber: event.target.value }))} /></label>
            <label className="form-field"><span>Microchip</span><input pattern="[0-9]{15}" required value={profile.microchipNumber} onChange={(event) => setProfile((value) => ({ ...value, microchipNumber: event.target.value }))} /></label>
            <label className="form-field"><span>Tên ngựa cha</span><input required value={profile.sireName} onChange={(event) => setProfile((value) => ({ ...value, sireName: event.target.value }))} /></label>
            <label className="form-field"><span>Tên ngựa mẹ</span><input required value={profile.damName} onChange={(event) => setProfile((value) => ({ ...value, damName: event.target.value }))} /></label>
          </div>
          <button className="button" type="submit" disabled={busy}>{busy ? 'Đang lưu...' : 'Lưu thay đổi lý lịch'}</button>
        </form>}

        {canRegister && horse.profileStatus === 'DRAFT' && <form onSubmit={submit} className="profile-section">
          <h2>Gửi hồ sơ đăng ký</h2>
          <button className="button" type="submit" disabled={busy}>{busy ? 'Đang gửi...' : 'Gửi hồ sơ'}</button>
        </form>}

        {canRegister && horse.profileStatus === 'REJECTED' && <form onSubmit={submit} className="profile-section">
          <h2>Gửi lại hồ sơ</h2>
          <p>Hồ sơ bị từ chối có thể được sửa và gửi lại.</p>
          <button className="button" type="submit" disabled={busy}>{busy ? 'Đang gửi...' : 'Gửi lại hồ sơ'}</button>
        </form>}

        {canReview && horse.profileStatus === 'SUBMITTED' && <section className="profile-section">
          <h2>Đối chiếu hồ sơ</h2>
          <p>Sau khi xác minh hồ sơ và giấy tờ, ngựa sẽ được chuyển vào hàng đợi khám.</p>
          <button className="button" type="button" disabled={busy} onClick={() => void runAction(() => onVerifyHorse(horse.id), 'Đã xác minh hồ sơ; ngựa đang chờ Vet khám.')}>{busy ? 'Đang xử lý...' : 'Xác minh hồ sơ'}</button>
          <form onSubmit={reject} style={{ marginTop: 16 }}>
            <label className="form-field"><span>Lý do từ chối</span><textarea rows="3" value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} maxLength={1000} required /></label>
            <button className="button button-secondary" type="submit" disabled={busy || !rejectReason.trim()}>{busy ? 'Đang xử lý...' : 'Từ chối hồ sơ'}</button>
          </form>
        </section>}

        {canReview && horse.profileStatus === 'PENDING_EXAM' && <section className="profile-section">
          <h2>Duyệt và hoàn tất tiếp nhận</h2>
          {!signed && <p className="intake-blockers">Chờ Vet khám và chốt phiếu. Chưa thể duyệt hồ sơ.</p>}
          {signed && <div className="intake-vet-conclusion">
            <h3>Kết quả khám đầu vào</h3>
            <p>Sức khỏe: {health || 'Chưa có kết luận'} · Điều kiện tập: {eligibility || 'Chưa có kết luận'}</p>
            {horse.healthAssessment?.conclusion && <p>Kết luận: {horse.healthAssessment.conclusion}</p>}
            {horse.healthAssessment?.examDate && <p>Ngày khám: {horse.healthAssessment.examDate}</p>}
          </div>}
          {signed && approvalBlockers.length > 0 && <div className="intake-blockers"><h3>Chưa thể duyệt</h3><ul>{approvalBlockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul></div>}
          <form onSubmit={approve}>
            <label className="form-field"><span>Mã ngựa</span><input value={horseCode} onChange={(event) => setHorseCode(event.target.value)} maxLength={30} required /></label>
            <label className="form-field"><span>Chuồng trống (không bắt buộc)</span>
              <select value={stallId} onChange={(event) => setStallId(event.target.value)}>
                <option value="">Không xếp chuồng lúc tiếp nhận</option>
                {stalls.map((stall) => <option key={stall.id} value={stall.id}>{stall.stallNumber} · #{stall.id}</option>)}
              </select>
              {stallError && <span className="error-message" role="alert">{stallError} <button type="button" className="button button-secondary" onClick={onRetryStalls}>Tải lại chuồng</button></span>}
              {!stallError && stalls.length === 0 && <span>Không có chuồng trống; có thể tiếp nhận mà chưa xếp chuồng.</span>}
            </label>
            <label className="form-field"><span>Ghi chú quản lý</span><textarea rows="3" value={managerNote} onChange={(event) => setManagerNote(event.target.value)} maxLength={1000} /></label>
            <button className="button" type="submit" disabled={busy || !canApprove}>{busy ? 'Đang duyệt...' : 'Duyệt và tiếp nhận'}</button>
          </form>
          <form onSubmit={reject} style={{ marginTop: 20 }}>
            <label className="form-field"><span>Lý do từ chối</span><textarea rows="3" value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} maxLength={1000} required /></label>
            <button className="button button-secondary" type="submit" disabled={busy || !rejectReason.trim()}>{busy ? 'Đang xử lý...' : 'Từ chối hồ sơ'}</button>
          </form>
        </section>}

        {horse.profileStatus === 'APPROVED' && <p className="success-message">Hồ sơ đã được tiếp nhận. Mã ngựa: {horse.code || 'chưa có'}.</p>}
        {horse.profileStatus === 'ARCHIVED' && <p>Hồ sơ đã lưu trữ. Lý do: {horse.archiveReason || 'Không có thông tin'}.</p>}
      </section>

      {canArchive && horse.profileStatus === 'APPROVED' && <section className="panel archive-panel" style={{ marginTop: 24 }}>
        <h2>Lưu trữ hồ sơ</h2>
        <form onSubmit={archive}>
          <label className="form-field" htmlFor="archive-reason"><span>Lý do lưu trữ</span><textarea id="archive-reason" rows="3" required placeholder="Nhập lý do lưu trữ..." value={archiveReason} onChange={(event) => setArchiveReason(event.target.value)} maxLength={1000} /></label>
          <label className="check-field"><input type="checkbox" required checked={confirmArchive} onChange={(event) => setConfirmArchive(event.target.checked)} /><span>Tôi xác nhận lưu trữ hồ sơ.</span></label>
          <button className="button archive-submit" type="submit" disabled={busy || !archiveReason.trim() || !confirmArchive}>{busy ? 'Đang lưu trữ...' : 'Lưu trữ hồ sơ'}</button>
        </form>
      </section>}
    </main>
  )
}

function profileValues(horse) {
  return {
    name: horse.name,
    breed: horse.breed,
    dateOfBirth: horse.dateOfBirth,
    sex: horse.sex,
    coatColor: horse.coatColor,
    registrationNumber: horse.registrationNumber,
    microchipNumber: horse.microchipNumber,
    sireName: horse.sireName,
    damName: horse.damName,
  }
}

export default CompleteIntake
