import { useCallback, useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { clearSession, getAccessToken } from './api/apiClient.ts'
import {
  archiveHorse, completeHorseIntake, getAvailableStalls, getHorseById, getHorseDocuments, getHorses,
  getMedicalRecords, getPendingInitialExams, getProfileChangeRequests, getRegistrationHistory, rejectHorse,
  saveExaminationDraft, signMedicalRecord, submitHorse, updateHorse, verifyHorse,
} from './api/horseApi.ts'
import { getCurrentUser, getUsers, login } from './api/userApi.ts'
import HorseList from './pages/manager/HorseList.jsx'
import CompleteIntake from './pages/manager/CompleteIntake.jsx'
import ProfileChangeRequests from './pages/manager/ProfileChangeRequests.jsx'
import OwnerHorses from './pages/owner/OwnerHorses.jsx'
import OwnerHorseForm from './pages/owner/OwnerHorseForm.jsx'
import OwnerCorrectionRequest from './pages/owner/OwnerCorrectionRequest.jsx'
import HorsesNeedingExam from './pages/vet/HorsesNeedingExam.jsx'
import VetExaminationForm from './pages/vet/VetExaminationForm.tsx'
import HorseProfile from './components/horse/HorseProfile.jsx'
import { registrationGroupLabel } from './components/horse/registrationGroups.js'
import StatusBadge from './components/common/StatusBadge.jsx'
import './App.css'

const roleLabels = {
  manager: 'QUẢN LÝ CÂU LẠC BỘ',
  owner: 'CHỦ SỞ HỮU NGỰA',
  vet: 'BÁC SĨ THÚ Y',
}

function userRole(user) {
  if (user?.role === 'CLUB_MANAGER') return 'manager'
  if (user?.role === 'OWNER') return 'owner'
  if (user?.role === 'VET') return 'vet'
  return ''
}

function NavIcon({ kind }) {
  const common = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
  if (kind === 'owner') return <svg {...common}><circle cx="12" cy="8" r="3.5" /><path d="M5 20c.5-3.5 3.1-5.5 7-5.5s6.5 2 7 5.5" /></svg>
  if (kind === 'vet') return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="4" /><path d="M12 8v8M8 12h8" /></svg>
  return <svg {...common}><path d="M4 5h16M4 10h16M4 15h10M4 20h10" /><circle cx="19" cy="17.5" r="2.5" /></svg>
}

function LoginScreen({ onLogin, error, busy }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setFormError('')
    try {
      await onLogin(email.trim(), password)
    } catch (loginError) {
      setFormError(loginError instanceof Error ? loginError.message : 'Không thể đăng nhập.')
    }
  }

  return (
    <main className="page-content narrow-content">
      <section className="panel form-panel">
        <p className="eyebrow">EQUITRACK · ĐĂNG NHẬP</p>
        <h1>Đăng nhập</h1>
        <p>Đăng nhập bằng tài khoản của bạn để truy cập hồ sơ theo đúng quyền được cấp.</p>
        {(formError || error) && <p className="error-message" role="alert">{formError || error}</p>}
        <form onSubmit={submit}>
          <label className="form-field"><span>Email</span><input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label className="form-field"><span>Mật khẩu</span><input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          <button className="button" type="submit" disabled={busy}>{busy ? 'Đang đăng nhập...' : 'Đăng nhập'}</button>
        </form>
      </section>
    </main>
  )
}

function HorseProfilePage({ horse, role, registrationHistory = [], onRefresh, onSubmitRegistration, registrationBusy, registrationError, registrationMessage, canRegister }) {
  const backTo = role === 'owner' ? '/owner/horses' : role === 'vet' ? '/vet/horses-needing-exam' : '/manager/horses'
  const rejection = [...registrationHistory].reverse().find((item) => item.status === 'Rejected' && item.managerNote)?.managerNote
  const healthContent = horse ? <div className="health-summary-grid">
    <div className="info-item"><span>Tình trạng sức khỏe hiện tại</span><StatusBadge status={horse.healthStatus} type="health" /></div>
    <div className="info-item"><span>Khám đầu vào</span><StatusBadge status={horse.initialExamSigned ? 'COMPLETED' : 'PENDING'} type="exam" /></div>
    {horse.healthAssessment && <>
      <div className="info-item"><span>HealthStatus</span><strong>{horse.healthAssessment.healthStatus || 'Chưa có kết luận'}</strong></div>
      <div className="info-item"><span>TrainingEligibility</span><strong>{horse.healthAssessment.trainingEligibility || 'Chưa có kết luận'}</strong></div>
      {horse.healthAssessment.conclusion && <div className="info-item"><span>Kết luận</span><strong>{horse.healthAssessment.conclusion}</strong></div>}
      {horse.healthAssessment.examDate && <div className="info-item"><span>Ngày khám</span><strong>{horse.healthAssessment.examDate}</strong></div>}
    </>}
    <div className="info-item"><span>Cập nhật gần nhất</span><strong>{horse.updatedAt || 'Chưa có thông tin'}</strong></div>
  </div> : undefined

  return (
    <main className="page-content">
      <div className="horse-actions">
        <Link className="breadcrumb-back-button" to={backTo}>← Quay lại danh sách ngựa</Link>
        {horse && <div className="profile-actions">
          {role === 'manager' && <Link className="button" to={`/manager/horses/${horse.id}/intake`}>Xử lý Flow 1</Link>}
          {role === 'owner' && canRegister && (horse.profileStatus === 'DRAFT' || horse.profileStatus === 'REJECTED') && <Link className="button button-secondary" to={`/owner/horses/${horse.id}/edit`}>Sửa hồ sơ</Link>}
          {role === 'owner' && canRegister && (horse.profileStatus === 'DRAFT' || horse.profileStatus === 'REJECTED') && <button className="button" type="button" onClick={() => void onSubmitRegistration(horse.id)} disabled={registrationBusy}>{registrationBusy ? 'Đang gửi...' : 'Gửi đăng ký'}</button>}
          {role === 'owner' && horse.profileStatus === 'APPROVED' && <Link className="button" to={`/owner/horses/${horse.id}/correction-request`}>Yêu cầu sửa hồ sơ</Link>}
          {role === 'vet' && horse.profileStatus === 'PENDING_EXAM' && <Link className="button" to={`/vet/horses/${horse.id}/examination`}>Khám đầu vào</Link>}
        </div>}
      </div>
      {role === 'owner' && registrationError && <p className="error-message" role="alert">{registrationError}</p>}
      {role === 'owner' && registrationMessage && <p className="success-message" role="status">{registrationMessage}</p>}
      {role === 'owner' && horse.profileStatus === 'REJECTED' && (rejection || horse.rejectionReason) && <section className="rejection-reason" aria-label="Lý do từ chối"><strong>Lý do từ chối</strong><p>{rejection || horse.rejectionReason}</p></section>}
      <HorseProfile horse={horse} owner={horse?.ownerName ? { fullName: horse.ownerName } : undefined} documents={horse?.documents} healthContent={healthContent} registrationLabel={role === 'manager' ? registrationGroupLabel(horse) : undefined} />
      {registrationHistory.length > 0 && <section className="panel profile-section"><h2>Lịch sử đăng ký</h2><div className="request-list">{registrationHistory.map((item) => <article className="request-item" key={item.id}><strong>Yêu cầu #{item.id} · {item.status}</strong><p>Ngày gửi: {item.requestDate || '—'}{item.reviewedAt ? ` · Ngày xử lý: ${item.reviewedAt}` : ''}</p>{item.managerNote && <p>Ghi chú Manager: {item.managerNote}</p>}</article>)}</div></section>}
      {horse && <button className="button button-secondary" type="button" onClick={() => void onRefresh(horse.id)}>Tải lại hồ sơ</button>}
    </main>
  )
}

function HorseProfileRoute({ currentUser, horses, onRefresh, onHorseUpdated }) {
  const { horseId } = useParams()
  const role = userRole(currentUser)
  const cachedHorse = horses.find((horse) => String(horse.id) === String(horseId))
  const [horse, setHorse] = useState(cachedHorse || null)
  const [registrationHistory, setRegistrationHistory] = useState([])
  const [loadedHorseId, setLoadedHorseId] = useState('')
  const [error, setError] = useState('')
  const [registrationBusy, setRegistrationBusy] = useState(false)
  const [registrationError, setRegistrationError] = useState('')
  const [registrationMessage, setRegistrationMessage] = useState('')

  const load = useCallback(async () => {
    try {
      const [result, documents, history] = await Promise.all([
        getHorseById(String(horseId)),
        getHorseDocuments(String(horseId)),
        getRegistrationHistory(String(horseId)),
      ])
      setError('')
      setHorse({ ...result, documents })
      setRegistrationHistory(history)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không thể tải hồ sơ ngựa.')
    } finally {
      setLoadedHorseId(String(horseId))
    }
  }, [horseId])

  useEffect(() => { void load() }, [load])
  const loading = loadedHorseId !== String(horseId)
  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải hồ sơ ngựa...</section></main>
  if (error) return <main className="page-content"><section className="panel" role="alert"><h1>Không thể tải hồ sơ</h1><p>{error}</p><button className="button" type="button" onClick={() => { setError(''); setLoadedHorseId(''); void load() }}>Thử lại</button></section></main>
  async function sendRegistration(id) {
    setRegistrationBusy(true)
    setRegistrationError('')
    setRegistrationMessage('')
    try {
      const saved = await submitHorse(id)
      const updated = { ...saved, documents: horse?.documents || [] }
      setHorse(updated)
      onHorseUpdated(updated)
      setRegistrationMessage('Đã gửi hồ sơ đến CLB')
    } catch (submitError) {
      setRegistrationError(submitError instanceof Error ? submitError.message : 'Không thể gửi hồ sơ đăng ký.')
    } finally {
      setRegistrationBusy(false)
    }
  }

  return <HorseProfilePage
    horse={horse}
    role={role}
    registrationHistory={registrationHistory}
    onRefresh={async (id) => { await load(); await onRefresh(id) }}
    onSubmitRegistration={sendRegistration}
    registrationBusy={registrationBusy}
    registrationError={registrationError}
    registrationMessage={registrationMessage}
    canRegister={currentUser.permissions.includes('HORSE_REGISTER')}
  />
}

function ManagerIntakeRoute({ horses, permissions, onUpdateHorse, onSubmitHorse, onVerifyHorse, onRejectHorse, onApproveHorse, onArchiveHorse }) {
  const { horseId } = useParams()
  const [horse, setHorse] = useState(null)
  const [error, setError] = useState('')
  const [loadedId, setLoadedId] = useState('')
  const [stalls, setStalls] = useState([])
  const [stallError, setStallError] = useState('')
  const [stallReloadCount, setStallReloadCount] = useState(0)

  const loadHorse = useCallback(async () => {
    try {
      const result = await getHorseById(String(horseId))
      setHorse(result)
      setError('')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không thể tải chi tiết hồ sơ.')
    } finally {
      setLoadedId(String(horseId))
    }
  }, [horseId])

  useEffect(() => { void loadHorse() }, [loadHorse])
  useEffect(() => {
    let current = true
    getAvailableStalls().then((result) => {
      if (current) {
        setStalls(result)
        setStallError('')
      }
    }).catch((loadError) => {
      if (current) {
        setStalls([])
        setStallError(loadError instanceof Error ? loadError.message : 'Không thể tải danh sách chuồng trống.')
      }
    })
    return () => { current = false }
  }, [stallReloadCount])
  const loading = loadedId !== String(horseId)
  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải chi tiết hồ sơ...</section></main>
  if (error || !horse) return <main className="page-content"><section className="panel" role="alert"><h1>Không thể tải hồ sơ</h1><p>{error || 'Không tìm thấy hồ sơ ngựa.'}</p><button className="button" type="button" onClick={() => { setLoadedId(''); void loadHorse() }}>Thử lại</button></section></main>

  async function applyHorseAction(action) {
    const saved = await action()
    setHorse(saved)
    return saved
  }

  return <CompleteIntake
    horses={horses}
    horse={horse}
    stalls={stalls}
    stallError={stallError}
    onRetryStalls={() => setStallReloadCount((count) => count + 1)}
    permissions={permissions}
    onUpdateHorse={(id, changes) => applyHorseAction(() => onUpdateHorse(id, changes))}
    onSubmitHorse={(id) => applyHorseAction(() => onSubmitHorse(id))}
    onVerifyHorse={(id) => applyHorseAction(() => onVerifyHorse(id))}
    onRejectHorse={(id, reason) => applyHorseAction(() => onRejectHorse(id, reason))}
    onApproveHorse={(id, payload) => applyHorseAction(() => onApproveHorse(id, payload))}
    onArchiveHorse={(id, reason) => applyHorseAction(() => onArchiveHorse(id, reason))}
  />
}

function OwnerCorrectionRoute({ horses }) {
  const { horseId } = useParams()
  const horse = horses.find((item) => String(item.id) === String(horseId))
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    let current = true
    getProfileChangeRequests(String(horseId)).then((result) => {
      if (current) {
        setRequests(result)
        setError('')
      }
    }).catch((loadError) => {
      if (current) setError(loadError instanceof Error ? loadError.message : 'Không thể tải lịch sử yêu cầu.')
    }).finally(() => {
      if (current) setLoading(false)
    })
    return () => { current = false }
  }, [horseId, reloadCount])

  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải yêu cầu sửa hồ sơ...</section></main>
  if (error) return <main className="page-content"><section className="panel" role="alert"><h1>Không thể tải yêu cầu</h1><p>{error}</p><button className="button" type="button" onClick={() => { setLoading(true); setReloadCount((count) => count + 1) }}>Thử lại</button></section></main>

  return <OwnerCorrectionRequest
    horse={horse}
    requests={requests}
    onSubmitted={(saved) => setRequests((current) => [saved, ...current])}
  />
}

function VetHorseRoute({ currentUser, initialExams, onRefresh, examination = false }) {
  const { horseId } = useParams()
  const [horse, setHorse] = useState(null)
  const [records, setRecords] = useState([])
  const [registrationHistory, setRegistrationHistory] = useState([])
  const [loadedHorseId, setLoadedHorseId] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async (preserveExistingError = false) => {
    try {
      const [horseResult, recordResult, documents, history] = await Promise.all([
        getHorseById(String(horseId)),
        getMedicalRecords(String(horseId)),
        getHorseDocuments(String(horseId)),
        getRegistrationHistory(String(horseId)),
      ])
      setError('')
      setHorse({ ...horseResult, documents })
      setRecords(recordResult)
      setRegistrationHistory(history)
      return true
    } catch (loadError) {
      if (!preserveExistingError) setError(loadError instanceof Error ? loadError.message : 'Không thể tải hồ sơ khám.')
      return false
    } finally {
      setLoadedHorseId(String(horseId))
    }
  }, [horseId])

  useEffect(() => { void load() }, [load])

  const loading = loadedHorseId !== String(horseId)
  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải hồ sơ khám...</section></main>
  if (error) return <main className="page-content"><section className="panel" role="alert"><h1>Không thể tải hồ sơ khám</h1><p>{error}</p><button className="button" type="button" onClick={() => { setError(''); setLoadedHorseId(''); void load() }}>Thử lại</button></section></main>
  if (!horse) return null

  const pendingExam = initialExams.find((item) => String(item.horse.id) === String(horse.id))
  const requestStatus = {
    PENDING_EXAM: 'PendingExam',
    APPROVED: 'Approved',
    REJECTED: 'Rejected',
  }[horse.profileStatus]
  const activeRequest = requestStatus
    ? registrationHistory.find((item) => item.status === requestStatus)
    : undefined
  const draft = pendingExam?.draftMedicalRecordId
    ? records.find((record) => record.id === pendingExam.draftMedicalRecordId
      && record.registrationRequestId === pendingExam.requestId
      && record.examType === 'Initial Exam'
      && record.recordStatus === 'Draft')
    : undefined
  const signedRecord = activeRequest
    ? records.find((record) => record.registrationRequestId === activeRequest.id
      && record.examType === 'Initial Exam'
      && record.recordStatus === 'Signed')
    : undefined
  if (examination) {
    return <VetExaminationForm
      horse={horse}
      currentUser={currentUser}
      draft={draft}
      signedRecord={signedRecord}
      onSaveDraft={saveExaminationDraft}
      onSign={signMedicalRecord}
      onAfterSign={async () => {
        const loaded = await load(true)
        if (!loaded) throw new Error('Phiếu đã chốt nhưng không tải lại được hồ sơ. Hãy tải lại để xác nhận dữ liệu mới nhất.')
        await onRefresh(horse.id)
      }}
    />
  }

  const owner = horse.ownerName || ''
  return (
    <main className="page-content">
      <div className="horse-actions"><Link className="breadcrumb-back-button" to="/vet/horses-needing-exam">← Quay lại hàng đợi</Link>
        {horse.profileStatus === 'PENDING_EXAM' && <Link className="button" to={`/vet/horses/${horse.id}/examination`}>Mở khám đầu vào</Link>}
      </div>
      <HorseProfilePage horse={horse} role="vet" registrationHistory={registrationHistory} onRefresh={async (id) => { await load(); await onRefresh(id) }} />
      <section className="panel profile-section"><h2>Phiếu khám</h2>{records.length === 0 ? <p>Chưa có phiếu khám.</p> : records.map((record) => <article key={record.id}><strong>#{record.id} · {record.examType} · {record.recordStatus}</strong><p>Vet: {record.vetName || `#${record.vetId}`} · {record.examDate || 'Chưa có ngày'}</p><p>{record.conclusion}</p></article>)}</section>
      {owner && <span className="sr-only">Chủ sở hữu: {owner}</span>}
    </main>
  )
}

function AppContent() {
  const [currentUser, setCurrentUser] = useState(null)
  const [authChecking, setAuthChecking] = useState(Boolean(getAccessToken()))
  const [authError, setAuthError] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)
  const [horses, setHorses] = useState([])
  const [users, setUsers] = useState([])
  const [initialExams, setInitialExams] = useState([])
  const [loadingData, setLoadingData] = useState(Boolean(getAccessToken()))
  const [loadError, setLoadError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    const expire = () => {
      setCurrentUser(null)
      setAuthError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
    }
    window.addEventListener('equi:session-expired', expire)
    return () => window.removeEventListener('equi:session-expired', expire)
  }, [])

  useEffect(() => {
    if (!getAccessToken()) {
      return
    }
    let current = true
    getCurrentUser().then((user) => {
      if (current) {
        setCurrentUser(user)
        setAuthError('')
      }
    }).catch((error) => {
      if (current) {
        clearSession()
        setAuthError(error instanceof Error ? error.message : 'Không thể xác minh phiên đăng nhập.')
      }
    }).finally(() => {
      if (current) setAuthChecking(false)
    })
    return () => { current = false }
  }, [])

  const loadData = useCallback(async () => {
    if (!currentUser) return
    try {
      const [horseRows, ownerRows, examRows] = await Promise.all([
        getHorses(),
        currentUser.role === 'CLUB_MANAGER' ? getUsers('HORSE_OWNER') : Promise.resolve([]),
        currentUser.role === 'VET' ? getPendingInitialExams() : Promise.resolve([]),
      ])
      setHorses(horseRows)
      setUsers(ownerRows)
      setInitialExams(examRows)
    } catch (error) {
      setHorses([])
      setUsers([])
      setInitialExams([])
      setLoadError(error instanceof Error ? error.message : 'Không thể tải dữ liệu.')
    } finally {
      setLoadingData(false)
    }
  }, [currentUser])

  useEffect(() => { void loadData() }, [loadData, reloadCount])

  const retryLoad = () => {
    setLoadingData(true)
    setLoadError('')
    setReloadCount((count) => count + 1)
  }

  async function handleLogin(email, password) {
    setLoggingIn(true)
    setLoadingData(true)
    setAuthError('')
    setLoadError('')
    try {
      const result = await login(email, password)
      setCurrentUser(result.user)
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Không thể đăng nhập.')
      throw error
    } finally {
      setLoggingIn(false)
    }
  }

  function logout() {
    clearSession()
    setCurrentUser(null)
    setLoadingData(false)
    setHorses([])
    setUsers([])
    setInitialExams([])
    setAuthError('')
  }

  function syncHorse(savedHorse) {
    setHorses((current) => current.map((horse) => String(horse.id) === String(savedHorse.id) ? savedHorse : horse))
    setInitialExams((current) => current.filter((item) => String(item.horse.id) !== String(savedHorse.id)))
  }

  async function refreshHorse(horseId) {
    const horse = await getHorseById(String(horseId))
    syncHorse(horse)
    return horse
  }

  async function refreshVetData(horseId) {
    const [horse, examRows] = await Promise.all([
      getHorseById(String(horseId)),
      getPendingInitialExams(),
    ])
    syncHorse(horse)
    setInitialExams(examRows)
    return horse
  }

  async function actionOnHorse(action) {
    const saved = await action
    syncHorse(saved)
    return saved
  }

  const role = userRole(currentUser)
  const home = role === 'owner' ? '/owner/horses' : role === 'vet' ? '/vet/horses-needing-exam' : '/manager/horses'
  const ownerList = useMemo(() => users.map((user) => ({ ownerId: user.id, id: user.id, fullName: user.fullName })), [users])

  if (authChecking) return <main className="page-content"><section className="panel" role="status">Đang xác minh phiên đăng nhập...</section></main>
  if (!currentUser) return <LoginScreen onLogin={handleLogin} error={authError} busy={loggingIn} />

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Link className="brand" to={home}><span className="brand-mark">E</span><span><strong>EQUITRACK</strong><small>RACETRACK PERFORMANCE</small></span></Link>
        <p className="sidebar-label">KHÔNG GIAN LÀM VIỆC</p>
        <nav className="side-nav" aria-label="Điều hướng chính">
          {role === 'manager' && <>
            <NavLink end to="/manager/horses"><NavIcon kind="manager" /><span>Danh sách ngựa</span></NavLink>
            {currentUser.permissions.includes('PROFILE_EDIT_APPROVE') && <NavLink to="/manager/profile-change-requests"><NavIcon kind="manager" /><span>Yêu cầu sửa hồ sơ</span></NavLink>}
          </>}
          {role === 'owner' && <NavLink end to="/owner/horses"><NavIcon kind="owner" /><span>Ngựa của tôi</span></NavLink>}
          {role === 'vet' && <NavLink end to="/vet/horses-needing-exam"><NavIcon kind="vet" /><span>Hàng đợi khám</span></NavLink>}
        </nav>
        <div className="sidebar-support"><strong>Cần hỗ trợ?</strong><span>Liên hệ quản lý câu lạc bộ</span><span className="support-link">Trung tâm hỗ trợ</span></div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-workspace"><span className="topbar-kicker">{roleLabels[role]}</span><strong>{currentUser.clubId ? `Câu lạc bộ #${currentUser.clubId}` : 'Equi'}</strong></div>
          <div className="topbar-account"><div className="topbar-user"><span className="avatar" aria-hidden="true">{currentUser.fullName.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span><div className="account-name"><strong>{currentUser.fullName}</strong><span><i />{loadingData ? 'Đang tải...' : 'Đang hoạt động'}</span></div></div><button className="button button-secondary" type="button" onClick={logout}>Đăng xuất</button></div>
        </header>
        {loadError && <div className="alert-banner" role="alert" style={{ margin: '12px 24px 0', background: '#fff4f4', color: '#7a1d1d', border: '1px solid #f7c2c2', borderRadius: 8, padding: '10px 12px' }}>{loadError} <button type="button" onClick={retryLoad}>Thử lại</button></div>}
        {loadingData && <main className="page-content"><section className="panel" role="status">Đang tải dữ liệu...</section></main>}
        {!loadingData && !loadError && <Routes>
          <Route path="/" element={<Navigate to={home} replace />} />
          <Route path="/manager/horses" element={role === 'manager' ? <HorseList owners={ownerList} /> : <Navigate to={home} replace />} />
          <Route path="/manager/profile-change-requests" element={role === 'manager' && currentUser.permissions.includes('PROFILE_EDIT_APPROVE') ? <ProfileChangeRequests onHorseRefresh={refreshHorse} /> : <Navigate to={home} replace />} />
          <Route path="/manager/horses/:horseId/intake" element={role === 'manager' ? <ManagerIntakeRoute
            horses={horses}
            permissions={currentUser.permissions}
            onUpdateHorse={(id, changes) => actionOnHorse(updateHorse(id, changes))}
            onSubmitHorse={(id) => actionOnHorse(submitHorse(id))}
            onVerifyHorse={(id) => actionOnHorse(verifyHorse(id))}
            onRejectHorse={(id, reason) => actionOnHorse(rejectHorse(id, reason))}
            onApproveHorse={(id, payload) => actionOnHorse(completeHorseIntake(id, payload))}
            onArchiveHorse={(id, reason) => actionOnHorse(archiveHorse(id, reason))}
          /> : <Navigate to={home} replace />} />
          <Route path="/owner/horses" element={role === 'owner' ? <OwnerHorses horses={horses} currentUser={currentUser} owners={[{ ownerId: currentUser.id, fullName: currentUser.fullName }]} /> : <Navigate to={home} replace />} />
          <Route path="/owner/horses/new" element={role === 'owner' && currentUser.permissions.includes('HORSE_REGISTER') ? <OwnerHorseForm currentUser={currentUser} onSaved={(horse) => setHorses((current) => [horse, ...current.filter((item) => String(item.id) !== String(horse.id))])} /> : <Navigate to={home} replace />} />
          <Route path="/owner/horses/:horseId/edit" element={role === 'owner' && currentUser.permissions.includes('HORSE_REGISTER') ? <OwnerHorseForm currentUser={currentUser} onSaved={syncHorse} /> : <Navigate to={home} replace />} />
          <Route path="/vet/horses-needing-exam" element={role === 'vet' ? <HorsesNeedingExam initialExams={initialExams} onRetry={retryLoad} /> : <Navigate to={home} replace />} />
                  <Route path="/vet/horses/:horseId" element={role === 'vet' ? <VetHorseRoute currentUser={currentUser} initialExams={initialExams} onRefresh={refreshVetData} /> : <Navigate to={home} replace />} />
                  <Route path="/vet/horses/:horseId/examination" element={role === 'vet' ? <VetHorseRoute currentUser={currentUser} initialExams={initialExams} onRefresh={refreshVetData} examination /> : <Navigate to={home} replace />} />
          <Route path="/owner/horses/:horseId" element={role === 'owner' ? <HorseProfileRoute currentUser={currentUser} horses={horses} onRefresh={refreshHorse} onHorseUpdated={syncHorse} /> : <Navigate to={home} replace />} />
          <Route path="/owner/horses/:horseId/correction-request" element={role === 'owner' ? <OwnerCorrectionRoute horses={horses} /> : <Navigate to={home} replace />} />
          <Route path="/horses/:horseId" element={<HorseProfileRoute currentUser={currentUser} horses={horses} onRefresh={refreshHorse} onHorseUpdated={syncHorse} />} />
          <Route path="*" element={<main className="page-content"><section className="panel"><h1>Không tìm thấy trang</h1><Link to={home}>Quay lại</Link></section></main>} />
        </Routes>}
        <footer className="app-footer">EQUITRACK · FLOW 1</footer>
      </div>
    </div>
  )
}

function App() {
  return <BrowserRouter><AppContent /></BrowserRouter>
}

export default App
