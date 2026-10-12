import { useCallback, useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { apiGet } from './api/apiClient.js'
import { login, logout } from './api/authApi.js'
import { accessTokenKey } from './config/api.js'
import { archiveHorse, finalizeExamination, getHorseById, getHorses, getPendingInitialExams, getProfileChangeRequests, normalizeUser, saveExaminationDraft, submitProfileChangeRequest, approveHorse } from './api/horseApi.js'
import LoginScreen from './components/layout/LoginScreen.jsx'
import HorseProfile from './components/horse/HorseProfile.jsx'
import HorseList from './pages/manager/HorseList.jsx'
import CompleteIntake from './pages/manager/CompleteIntake.jsx'
import OwnerHorses from './pages/owner/OwnerHorses.jsx'
import OwnerCorrectionRequest from './pages/owner/OwnerCorrectionRequest.jsx'
import HorsesNeedingExam from './pages/vet/HorsesNeedingExam.jsx'
import VetExaminationForm from './pages/vet/VetExaminationForm.jsx'
import PostExamStatus from './pages/vet/PostExamStatus.jsx'
import './App.css'

const roleMap = { CLUB_MANAGER: 'manager', HORSE_OWNER: 'owner', OWNER: 'owner', VETERINARIAN: 'vet', VET: 'vet' }

function AuthenticatedApp({ currentUser, onSignOut }) {
  const role = roleMap[currentUser.role] || roleMap[currentUser.roles?.[0]] || ''
  const home = role === 'owner' ? '/owner/horses' : role === 'vet' ? '/vet/horses-needing-exam' : '/manager/horses'
  const [horses, setHorses] = useState([])
  const [owners, setOwners] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const reloadHorses = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const rows = role === 'vet' ? await getPendingInitialExams() : await getHorses()
      setHorses(rows)
      const ownerIds = [...new Set(rows.map((horse) => horse.ownerUserId).filter(Boolean))]
      if (ownerIds.length && role !== 'owner') {
        try {
          const users = await apiGet('/users')
          const normalizedUsers = users.map(normalizeUser).filter((user) => user.role === 'OWNER')
          setOwners(normalizedUsers.map((user) => ({ ownerId: user.id, fullName: user.fullName })))
        } catch { setOwners([]) }
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không thể tải dữ liệu.')
    } finally { setLoading(false) }
  }, [role])

  useEffect(() => { void Promise.resolve().then(reloadHorses) }, [reloadHorses])

  const visibleOwners = useMemo(() => owners, [owners])
  const currentOwner = currentUser

  async function archive(id, reason) {
    const saved = await archiveHorse(id, reason)
    setHorses((current) => current.map((horse) => horse.id === saved.id ? saved : horse))
  }

  async function complete(id, values) {
    const saved = await approveHorse(id, values)
    setHorses((current) => current.map((horse) => horse.id === saved.id ? saved : horse))
  }

  return <div className="app-shell">
    <aside className="app-sidebar">
      <Link className="brand" to={home}><span className="brand-mark">E</span><span><strong>EQUITRACK</strong><small>RACETRACK PERFORMANCE</small></span></Link>
      <p className="sidebar-label">KHÔNG GIAN LÀM VIỆC</p>
      <nav className="side-nav" aria-label="Điều hướng chính">
        {role === 'manager' && <Link to="/manager/horses">Danh sách ngựa</Link>}
        {role === 'owner' && <Link to="/owner/horses">Ngựa của tôi</Link>}
        {role === 'vet' && <Link to="/vet/horses-needing-exam">Hồ sơ khám</Link>}
      </nav>
      <div className="sidebar-support"><strong>Cần hỗ trợ?</strong><span>Liên hệ quản lý câu lạc bộ</span></div>
    </aside>
    <div className="app-main">
      <header className="topbar"><div className="topbar-workspace"><span className="topbar-kicker">{role === 'owner' ? 'CHỦ SỞ HỮU NGỰA' : role === 'vet' ? 'BÁC SĨ THÚ Y' : 'QUẢN LÝ CÂU LẠC BỘ'}</span><strong>EQUITRACK</strong></div><div className="topbar-account"><span className="avatar">{currentUser.fullName?.slice(0, 1) || 'E'}</span><div className="account-name"><strong>{currentUser.fullName}</strong><span>Đang hoạt động</span></div><button className="button button-secondary" type="button" onClick={onSignOut}>Đăng xuất</button></div></header>
      {error && <div className="alert-banner" role="alert">{error} <button type="button" onClick={() => void reloadHorses()}>Thử lại</button></div>}
      {loading ? <main className="page-content"><section className="panel" role="status">Đang tải dữ liệu...</section></main> : <Routes>
        <Route path="/" element={<Navigate to={home} replace />} />
        <Route path="/manager/horses" element={role === 'manager' ? <HorseList horses={horses} owners={visibleOwners} currentUser={currentUser} /> : <Navigate to={home} replace />} />
        <Route path="/manager/horses/:horseId/intake" element={role === 'manager' ? <IntakeRoute horses={horses} onArchive={archive} onComplete={complete} /> : <Navigate to={home} replace />} />
        <Route path="/owner/horses" element={role === 'owner' ? <OwnerHorses horses={horses} currentUser={currentOwner} owners={visibleOwners} /> : <Navigate to={home} replace />} />
        <Route path="/owner/horses/:horseId" element={<ProfileRoute horses={horses} owners={visibleOwners} role="owner" />} />
        <Route path="/owner/horses/:horseId/correction-request" element={role === 'owner' ? <CorrectionRoute horses={horses} currentUser={currentUser} /> : <Navigate to={home} replace />} />
        <Route path="/owner/horses/:horseId/post-exam" element={<OwnerStatusRoute horses={horses} currentUser={currentUser} />} />
        <Route path="/vet/horses-needing-exam" element={role === 'vet' ? <HorsesNeedingExam horses={horses} currentUser={currentUser} owners={visibleOwners} /> : <Navigate to={home} replace />} />
        <Route path="/vet/horses/:horseId" element={<ProfileRoute horses={horses} owners={visibleOwners} role="vet" />} />
        <Route path="/vet/horses/:horseId/examination" element={role === 'vet' ? <VetExamRoute currentUser={currentUser} onSaved={reloadHorses} /> : <Navigate to={home} replace />} />
        <Route path="/horses/:horseId" element={<ProfileRoute horses={horses} owners={visibleOwners} role={role} />} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>}
      <footer className="app-footer">EQUITRACK · Quản lý đào tạo ngựa đua</footer>
    </div>
  </div>
}

function ProfileRoute({ horses, owners, role }) {
  const { horseId } = useParams()
  const horse = horses.find((item) => item.id === String(horseId))
  const owner = owners.find((item) => String(item.ownerId) === horse?.ownerUserId) || horse?.owner
  return <main className="page-content"><Link className="breadcrumb-back-button" to={role === 'owner' ? '/owner/horses' : role === 'vet' ? '/vet/horses-needing-exam' : '/manager/horses'}>← Quay lại danh sách</Link><HorseProfile horse={horse} owner={owner} documents={horse?.documents} /></main>
}

function IntakeRoute({ horses, onArchive, onComplete }) {
  const { horseId } = useParams()
  return <CompleteIntake horses={horses} horse={horses.find((item) => item.id === String(horseId))} onArchiveHorse={onArchive} onCompleteIntake={onComplete} />
}

function CorrectionRoute({ horses, currentUser }) {
  const { horseId } = useParams()
  const [requests, setRequests] = useState([])
  useEffect(() => { getProfileChangeRequests(horseId).then(setRequests).catch(() => setRequests([])) }, [horseId])
  async function submitRequest(request) {
    await submitProfileChangeRequest(request)
    setRequests(await getProfileChangeRequests(horseId))
  }
  return <OwnerCorrectionRequest horses={horses} requests={requests} currentUser={currentUser} onSubmitRequest={submitRequest} />
}

function OwnerStatusRoute({ horses }) {
  const { horseId } = useParams()
  const horse = horses.find((item) => item.id === String(horseId))
  return <PostExamStatus horse={horse} viewerRole="owner" />
}

function VetExamRoute({ currentUser, onSaved }) {
  const { horseId } = useParams()
  const [horse, setHorse] = useState(null)
  useEffect(() => { getHorseById(horseId).then(setHorse).catch(() => setHorse(null)) }, [horseId])
  if (!horse) return <main className="page-content"><section className="panel">Đang tải hồ sơ khám...</section></main>
  return <VetExaminationForm horse={horse} currentUser={currentUser} owner={horse.owner} onSaveDraft={saveExaminationDraft} onFinalize={finalizeExamination} onHorseSaved={(saved) => { setHorse(saved); void onSaved() }} />
}

function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [checkingSession, setCheckingSession] = useState(Boolean(localStorage.getItem(accessTokenKey)))
  useEffect(() => {
    if (!localStorage.getItem(accessTokenKey)) return
    apiGet('/auth/me').then((user) => setCurrentUser(normalizeUser(user))).catch(() => { logout(); setCurrentUser(null) }).finally(() => setCheckingSession(false))
  }, [])
  async function handleLogin(email, password) { setCurrentUser(normalizeUser(await login(email, password))) }
  function handleSignOut() { logout(); setCurrentUser(null) }
  if (checkingSession) return <main className="login-shell"><section className="panel">Đang kiểm tra phiên đăng nhập...</section></main>
  return currentUser ? <AuthenticatedApp currentUser={currentUser} onSignOut={handleSignOut} /> : <LoginScreen onLogin={handleLogin} />
}

export default function RootApp() { return <BrowserRouter><App /></BrowserRouter> }
