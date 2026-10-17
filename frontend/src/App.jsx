import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  createBrowserRouter,
  RouterProvider,
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
} from 'react-router-dom'

import {
  ApiError,
  clearSession,
  getAccessToken,
} from './api/apiClient.ts'

import {
  archiveHorse,
  clearPendingHorseDocumentUploads,
  completeHorseIntake,
  getAvailableStalls,
  getClubs,
  getHorseById,
  getHorseDocuments,
  getHorses,
  getMedicalRecords,
  getPendingInitialExams,
  getProfileChangeRequests,
  getRegistrationHistory,
  rejectHorse,
  saveExaminationDraft,
  signMedicalRecord,
  submitHorse,
  updateHorse,
  verifyHorse,
} from './api/horseApi.ts'

import {
  getCurrentUser,
  getUsers,
  login,
} from './api/userApi.ts'

import HorseList from './pages/manager/HorseList.jsx'
import CreateHorse from './pages/manager/CreateHorse.jsx'
import CompleteIntake from './pages/manager/CompleteIntake.jsx'
import ProfileChangeRequests from './pages/manager/ProfileChangeRequests.jsx'

import OwnerHorses from './pages/owner/OwnerHorses.jsx'
import OwnerHorseForm from './pages/owner/OwnerHorseForm.jsx'
import LoginScreen from './components/layout/LoginScreen.jsx'
import OwnerCorrectionRequest from './pages/owner/OwnerCorrectionRequest.jsx'

import HorsesNeedingExam from './pages/vet/HorsesNeedingExam.jsx'
import VetExaminationForm from './pages/vet/VetExaminationForm.tsx'
import VetWorkspace from './pages/vet/VetWorkspace.jsx'
import VetMedicalProfile from './pages/vet/VetMedicalProfile.jsx'
import { vetError } from './pages/vet/vetDomain.js'

import HorseProfile from './components/horse/HorseProfile.jsx'
import {
  registrationGroupLabel,
} from './components/horse/registrationGroups.js'



import StatusBadge from './components/common/StatusBadge.jsx'
import LandingPage from './pages/landing/LandingPage.jsx'
import { formatHorseDateTime, valueOrMissing } from './components/horse/horseDisplay.js'

import './App.css'

const roleLabels = { manager: 'Quản lý câu lạc bộ', owner: 'Chủ sở hữu ngựa', vet: 'Bác sĩ thú y' }

function userRole(user) {
  if (user?.role === 'CLUB_MANAGER') {
    return 'manager'
  }

  if (
    user?.role === 'OWNER' ||
    user?.role === 'HORSE_OWNER'
  ) {
    return 'owner'
  }

  if (
    user?.role === 'VET' ||
    user?.role === 'VETERINARIAN'
  ) {
    return 'vet'
  }

  return ''
}

function NavIcon({ kind }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }

  if (kind === 'owner') {
    return (
      <svg {...common}>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c.5-3.5 3.1-5.5 7-5.5s6.5 2 7 5.5" />
      </svg>
    )
  }

  if (kind === 'vet') {
    return (
      <svg {...common}>
        <rect
          x="4"
          y="4"
          width="16"
          height="16"
          rx="4"
        />
        <path d="M12 8v8M8 12h8" />
      </svg>
    )
  }

  return (
    <svg {...common}>
      <path d="M4 5h16M4 10h16M4 15h10M4 20h10" />
      <circle cx="19" cy="17.5" r="2.5" />
    </svg>
  )
}

function useClubName(clubId) {
  const [lookup, setLookup] = useState({ clubId: '', name: '', error: '' })

  useEffect(() => {
    if (!clubId) return undefined
    let active = true
    getClubs()
      .then((clubs) => {
        if (!active) return
        const club = clubs.find((item) => String(item.id) === String(clubId))
        setLookup({
          clubId: String(clubId),
          name: club?.name || '',
          error: club ? '' : 'Không tìm thấy tên câu lạc bộ từ dữ liệu hiện có.',
        })
      })
      .catch((error) => {
        if (active) {
          setLookup({
            clubId: String(clubId),
            name: '',
            error: error instanceof Error ? error.message : 'Không thể tải tên câu lạc bộ.',
          })
        }
      })
    return () => {
      active = false
    }
  }, [clubId])

  return String(lookup.clubId) === String(clubId)
    ? { clubName: lookup.name, clubError: lookup.error }
    : { clubName: '', clubError: '' }
}

function HorseProfilePage({
  horse,
  role,
  currentUser,
  registrationHistory = [],
  medicalRecords = [],
  onRefresh,
  onSubmitRegistration,
  registrationBusy,
  registrationError,
  registrationMessage,
  canRegister,
  canManageRegistration,
  canRequestCorrection,
  canVetExamine,
}) {
  const { clubName, clubError } = useClubName(horse?.clubId)

  const backTo =
    role === 'owner'
      ? '/owner/horses'
      : role === 'vet'
        ? '/vet/overview'
        : '/manager/horses'

  const rejection = [
    ...registrationHistory,
  ]
    .find(
      (item) =>
        item.status === 'Rejected' &&
        item.managerNote,
    )?.managerNote

  const healthContent = horse ? (
    <div className="health-summary-grid">
      <div className="info-item">
        <span>
          Tình trạng sức khỏe hiện tại
        </span>

        <StatusBadge
          status={horse.healthStatus}
          type="health"
        />
      </div>

      <div className="info-item">
        <span>Khám đầu vào</span>

        <StatusBadge
          status={
            horse.initialExamSigned
              ? 'COMPLETED'
              : horse.profileStatus === 'PENDING_EXAM'
                ? 'PENDING'
                : 'NOT_STARTED'
          }
          type="exam"
        />
      </div>

      {horse.healthAssessment && (
        <>
          <div className="info-item">
            <span>Kết quả khám gần nhất</span>

            <StatusBadge
              status={horse.healthAssessment.healthStatus}
              type="health"
            />
          </div>

          <div className="info-item">
            <span>Điều kiện tập luyện</span>

            <strong>
              {({
                Eligible: 'Đủ điều kiện',
                Restricted: 'Hạn chế',
                'Not Eligible': 'Không đủ điều kiện',
              })[horse.healthAssessment.trainingEligibility]
                || valueOrMissing(horse.healthAssessment.trainingEligibility)}
            </strong>
          </div>

          {horse.healthAssessment
            .conclusion && (
            <div className="info-item">
              <span>Kết luận</span>

              <strong>
                {
                  horse.healthAssessment
                    .conclusion
                }
              </strong>
            </div>
          )}

          {horse.healthAssessment
            .examDate && (
            <div className="info-item">
              <span>Ngày khám</span>

              <strong>
                {formatHorseDateTime(horse.healthAssessment.examDate)}
              </strong>
            </div>
          )}
        </>
      )}

      <div className="info-item">
        <span>Cập nhật gần nhất</span>

        <strong>
          {formatHorseDateTime(horse.updatedAt)}
        </strong>
      </div>
    </div>
  ) : undefined

  return (
    <main className="page-content">
      <div className="horse-actions">
        <Link
          className="breadcrumb-back-button"
          to={backTo}
        >
          ← Quay lại danh sách ngựa
        </Link>

        {horse && (
          <div className="profile-actions">
            {role === 'manager' && canManageRegistration && (
              <Link
                className="button"
                to={`/manager/horses/${horse.id}/intake`}
              >
                Xử lý Flow 1
              </Link>
            )}

            {role === 'owner' &&
              canRegister &&
              (horse.profileStatus ===
                'DRAFT' ||
                horse.profileStatus ===
                  'REJECTED') && (
                <Link
                  className="button button-secondary"
                  to={`/owner/horses/${horse.id}/edit`}
                >
                  Sửa hồ sơ
                </Link>
              )}

            {role === 'owner' &&
              canRegister &&
              (horse.profileStatus ===
                'DRAFT' ||
                horse.profileStatus ===
                  'REJECTED') && (
                <button
                  className="button"
                  type="button"
                  onClick={() =>
                    void onSubmitRegistration(
                      horse.id,
                    )
                  }
                  disabled={registrationBusy}
                >
                  {registrationBusy
                    ? 'Đang gửi...'
                    : 'Gửi đăng ký'}
                </button>
              )}

            {role === 'owner' &&
              canRequestCorrection &&
              horse.profileStatus ===
                'APPROVED' && (
                <Link
                  className="button"
                  to={`/owner/horses/${horse.id}/correction-request`}
                >
                  Yêu cầu sửa hồ sơ
                </Link>
              )}

            {role === 'vet' &&
              canVetExamine &&
              horse.profileStatus ===
                'PENDING_EXAM' && (
                <Link
                  className="button"
                  to={`/vet/horses/${horse.id}/examination`}
                >
                  Khám đầu vào
                </Link>
              )}
          </div>
        )}
      </div>

      {role === 'owner' &&
        registrationError && (
          <p
            className="error-message"
            role="alert"
          >
            {registrationError}
          </p>
        )}

      {role === 'owner' &&
        registrationMessage && (
          <p
            className="success-message"
            role="status"
          >
            {registrationMessage}
          </p>
        )}

      {role === 'owner' &&
        horse.profileStatus ===
          'REJECTED' &&
        (rejection ||
          horse.rejectionReason) && (
          <section
            className="rejection-reason"
            aria-label="Lý do từ chối"
          >
            <strong>
              Lý do từ chối
            </strong>

            <p>
              {rejection ||
                horse.rejectionReason}
            </p>
          </section>
        )}

      {clubError && <p className="profile-data-warning" role="status">Không thể hiển thị tên câu lạc bộ: {clubError}</p>}

      <HorseProfile
        horse={horse}
        owner={
          horse?.ownerName
            ? {
                fullName:
                  horse.ownerName,
              }
            : role === 'owner' && String(horse?.ownerUserId) === String(currentUser.id)
              ? currentUser
              : undefined
        }
        clubName={clubName}
        documents={horse?.documents}
        healthContent={healthContent}
        medicalRecords={medicalRecords}
        registrationHistory={registrationHistory}
        registrationLabel={
          role === 'manager'
            ? registrationGroupLabel(
                horse,
              )
            : undefined
        }
      />

      {horse && (
        <button
          className="button button-secondary"
          type="button"
          onClick={() =>
            void onRefresh(horse.id)
          }
        >
          Tải lại hồ sơ
        </button>
      )}
    </main>
  )
}

function HorseProfileRoute({
  currentUser,
  horses,
  onRefresh,
  onHorseUpdated,
}) {
  const { horseId } = useParams()

  const role =
    userRole(currentUser)

  const cachedHorse =
    horses.find(
      (horse) =>
        String(horse.id) ===
        String(horseId),
    )

  const [horse, setHorse] =
    useState(
      cachedHorse || null,
    )

  const [
    registrationHistory,
    setRegistrationHistory,
  ] = useState([])

  const [medicalRecords, setMedicalRecords] = useState([])

  const [
    loadedHorseId,
    setLoadedHorseId,
  ] = useState('')

  const [error, setError] =
    useState('')

  const [
    registrationBusy,
    setRegistrationBusy,
  ] = useState(false)

  const [
    registrationError,
    setRegistrationError,
  ] = useState('')

  const [
    registrationMessage,
    setRegistrationMessage,
  ] = useState('')

  const load = useCallback(
    async () => {
      try {
        const [
          result,
          documents,
          history,
          records,
        ] = await Promise.all([
          getHorseById(
            String(horseId),
          ),

          getHorseDocuments(
            String(horseId),
          ),

          getRegistrationHistory(
            String(horseId),
          ),

          role === 'manager'
            ? getMedicalRecords(String(horseId))
            : Promise.resolve([]),
        ])

        setError('')

        setHorse({
          ...result,
          documents,
        })

        setRegistrationHistory(
          history,
        )
        setMedicalRecords(records)
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : 'Không thể tải hồ sơ ngựa.',
        )
      } finally {
        setLoadedHorseId(
          String(horseId),
        )
      }
    },
    [horseId, role],
  )

  useEffect(() => {
    void load()
  }, [load])

  const loading =
    loadedHorseId !==
    String(horseId)

  if (loading) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="status"
        >
          Đang tải hồ sơ ngựa...
        </section>
      </main>
    )
  }

  if (error) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="alert"
        >
          <h1>
            Không thể tải hồ sơ
          </h1>

          <p>{error}</p>

          <button
            className="button"
            type="button"
            onClick={() => {
              setError('')
              setLoadedHorseId('')
              void load()
            }}
          >
            Thử lại
          </button>
        </section>
      </main>
    )
  }

  async function sendRegistration(
    id,
  ) {
    setRegistrationBusy(true)
    setRegistrationError('')
    setRegistrationMessage('')

    try {
      const saved =
        await submitHorse(id)

      const updated = {
        ...saved,
        documents:
          horse?.documents || [],
      }

      setHorse(updated)

      onHorseUpdated(updated)

      setRegistrationHistory(await getRegistrationHistory(id))
      setRegistrationMessage('Đã gửi hồ sơ đến CLB')
    } catch (submitError) {
      setRegistrationError(
        submitError instanceof Error
          ? submitError.message
          : 'Không thể gửi hồ sơ đăng ký.',
      )
    } finally {
      setRegistrationBusy(false)
    }
  }

  return (
    <HorseProfilePage
      horse={horse}
      role={role}
      currentUser={currentUser}
      registrationHistory={
        registrationHistory
      }
      medicalRecords={medicalRecords}
      onRefresh={async (id) => {
        await load()
        await onRefresh(id)
      }}
      onSubmitRegistration={
        sendRegistration
      }
      registrationBusy={
        registrationBusy
      }
      registrationError={
        registrationError
      }
      registrationMessage={
        registrationMessage
      }
      canRegister={
        currentUser.permissions.includes(
          'HORSE_REGISTER',
        )
      }
      canManageRegistration={(
        ((currentUser.permissions.includes('HORSE_REGISTER') || currentUser.permissions.includes('HORSE_REGISTER_REVIEW'))
          && ['DRAFT', 'REJECTED'].includes(horse?.profileStatus))
        || (currentUser.permissions.includes('HORSE_REGISTER_REVIEW')
          && ['SUBMITTED', 'PENDING_EXAM'].includes(horse?.profileStatus))
        || (currentUser.permissions.includes('HORSE_ARCHIVE') && horse?.profileStatus === 'APPROVED')
      )}
      canRequestCorrection={currentUser.permissions.includes('PROFILE_EDIT_REQUEST')}
      canVetExamine={currentUser.permissions.includes('MEDICAL_MANAGE')}
    />
  )
}

function ManagerIntakeRoute({
  horses,
  permissions,
  onUpdateHorse,
  onSubmitHorse,
  onVerifyHorse,
  onRejectHorse,
  onApproveHorse,
  onArchiveHorse,
}) {
  const { horseId } = useParams()

  const [horse, setHorse] =
    useState(null)

  const [error, setError] =
    useState('')

  const [loadedId, setLoadedId] =
    useState('')

  const [stalls, setStalls] =
    useState([])

  const [
    stallError,
    setStallError,
  ] = useState('')

  const [
    stallReloadCount,
    setStallReloadCount,
  ] = useState(0)

  const loadHorse =
    useCallback(
      async () => {
        try {
          const result =
            await getHorseById(
              String(horseId),
            )

          setHorse(result)

          setError('')
        } catch (loadError) {
          setError(
            loadError instanceof
              Error
              ? loadError.message
              : 'Không thể tải chi tiết hồ sơ.',
          )
        } finally {
          setLoadedId(
            String(horseId),
          )
        }
      },
      [horseId],
    )

  useEffect(() => {
    void loadHorse()
  }, [loadHorse])

  useEffect(() => {
    let current = true

    getAvailableStalls()
      .then((result) => {
        if (current) {
          setStalls(result)
          setStallError('')
        }
      })
      .catch((loadError) => {
        if (current) {
          setStalls([])

          setStallError(
            loadError instanceof
              Error
              ? loadError.message
              : 'Không thể tải danh sách chuồng trống.',
          )
        }
      })

    return () => {
      current = false
    }
  }, [horseId, stallReloadCount])

  const loading =
    loadedId !== String(horseId)

  if (loading) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="status"
        >
          Đang tải chi tiết hồ sơ...
        </section>
      </main>
    )
  }

  if (error || !horse) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="alert"
        >
          <h1>
            Không thể tải hồ sơ
          </h1>

          <p>
            {error ||
              'Không tìm thấy hồ sơ ngựa.'}
          </p>

          <button
            className="button"
            type="button"
            onClick={() => {
              setLoadedId('')
              void loadHorse()
            }}
          >
            Thử lại
          </button>
        </section>
      </main>
    )
  }

  async function applyHorseAction(
    action,
  ) {
    const saved =
      await action()

    setHorse(saved)
    if (saved.profileStatus === 'APPROVED' || saved.profileStatus === 'ARCHIVED') {
      setStallReloadCount((count) => count + 1)
    }

    return saved
  }

  return (
    <CompleteIntake
      horses={horses}
      horse={horse}
      stalls={stalls}
      stallError={stallError}
      onRetryStalls={() =>
        setStallReloadCount(
          (count) => count + 1,
        )
      }
      permissions={permissions}
      onUpdateHorse={(
        id,
        changes,
      ) =>
        applyHorseAction(() =>
          onUpdateHorse(
            id,
            changes,
          ),
        )
      }
      onSubmitHorse={(id) =>
        applyHorseAction(() =>
          onSubmitHorse(id),
        )
      }
      onVerifyHorse={(id) =>
        applyHorseAction(() =>
          onVerifyHorse(id),
        )
      }
      onRejectHorse={(
        id,
        reason,
      ) =>
        applyHorseAction(() =>
          onRejectHorse(
            id,
            reason,
          ),
        )
      }
      onApproveHorse={(
        id,
        payload,
      ) =>
        applyHorseAction(() =>
          onApproveHorse(
            id,
            payload,
          ),
        )
      }
      onArchiveHorse={(
        id,
        reason,
      ) =>
        applyHorseAction(() =>
          onArchiveHorse(
            id,
            reason,
          ),
        )
      }
    />
  )
}

function OwnerCorrectionRoute({
  horses,
}) {
  const { horseId } = useParams()

  const horse =
    horses.find(
      (item) =>
        String(item.id) ===
        String(horseId),
    )

  const [requests, setRequests] =
    useState([])

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState('')

  const [
    reloadCount,
    setReloadCount,
  ] = useState(0)

  useEffect(() => {
    let current = true

    getProfileChangeRequests(
      String(horseId),
    )
      .then((result) => {
        if (current) {
          setRequests(result)
          setError('')
        }
      })
      .catch((loadError) => {
        if (current) {
          setError(
            loadError instanceof
              Error
              ? loadError.message
              : 'Không thể tải lịch sử yêu cầu.',
          )
        }
      })
      .finally(() => {
        if (current) {
          setLoading(false)
        }
      })

    return () => {
      current = false
    }
  }, [
    horseId,
    reloadCount,
  ])

  if (loading) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="status"
        >
          Đang tải yêu cầu sửa hồ
          sơ...
        </section>
      </main>
    )
  }

  if (error) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="alert"
        >
          <h1>
            Không thể tải yêu cầu
          </h1>

          <p>{error}</p>

          <button
            className="button"
            type="button"
            onClick={() => {
              setLoading(true)

              setReloadCount(
                (count) =>
                  count + 1,
              )
            }}
          >
            Thử lại
          </button>
        </section>
      </main>
    )
  }

  return (
    <OwnerCorrectionRequest
      key={horseId}
      horse={horse}
      requests={requests}
      onSubmitted={(saved) =>
        setRequests(
          (current) => [
            saved,
            ...current,
          ],
        )
      }
    />
  )
}

function VetHorseRoute({
  currentUser,
  onRefresh,
  examination = false,
}) {
  const { horseId } = useParams()
  const [conflictNotice, setConflictNotice] = useState('')

  const [horse, setHorse] =
    useState(null)

  const [records, setRecords] =
    useState([])

  const [
    registrationHistory,
    setRegistrationHistory,
  ] = useState([])

  const [
    loadedHorseId,
    setLoadedHorseId,
  ] = useState('')

  const [error, setError] =
    useState('')

  const load = useCallback(
    async (
      preserveExistingError = false,
    ) => {
      try {
        const [
          horseResult,
          recordResult,
          documents,
          history,
        ] = await Promise.all([
          getHorseById(
            String(horseId),
          ),

          getMedicalRecords(
            String(horseId),
          ),

          getHorseDocuments(
            String(horseId),
          ),

          getRegistrationHistory(
            String(horseId),
          ),
        ])

        setError('')

        setHorse({
          ...horseResult,
          documents,
        })

        setRecords(recordResult)

        setRegistrationHistory(
          history,
        )

        return true
      } catch (loadError) {
        if (!preserveExistingError) {
          setError(
            vetError(loadError, 'Không thể tải hồ sơ khám. Vui lòng thử lại.'),
          )
        }

        return false
      } finally {
        setLoadedHorseId(
          String(horseId),
        )
      }
    },
    [horseId],
  )

  useEffect(() => {
    void load()
  }, [load])

  const loading =
    loadedHorseId !==
    String(horseId)

  if (loading) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="status"
        >
          Đang tải hồ sơ khám...
        </section>
      </main>
    )
  }

  if (error) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="alert"
        >
          <h1>
            Không thể tải hồ sơ khám
          </h1>

          <p>{error}</p>

          <button
            className="button"
            type="button"
            onClick={() => {
              setError('')
              setLoadedHorseId('')
              void load()
            }}
          >
            Thử lại
          </button>
        </section>
      </main>
    )
  }

  if (!horse) {
    return null
  }

  const requestStatus = {
    PENDING_EXAM: 'PendingExam',
    APPROVED: 'Approved',
    REJECTED: 'Rejected',
  }[horse.profileStatus]

  const activeRequest =
    requestStatus
      ? registrationHistory.find(
          (item) =>
            item.status ===
            requestStatus,
        )
      : undefined

  const draft = activeRequest ? records.find(record =>
    record.registrationRequestId === activeRequest.id
    && record.examType === 'Initial Exam' && record.recordStatus === 'Draft') : undefined

  const signedRecord =
    activeRequest
      ? records.find(
          (record) =>
            record.registrationRequestId ===
              activeRequest.id &&
            record.examType ===
              'Initial Exam' &&
            record.recordStatus ===
              'Signed',
        )
      : undefined

  if (examination) {
    return (
      <VetExaminationForm
        key={`${horse.id}:${activeRequest?.id || ''}:${draft?.id || ''}`}
        horse={horse}
        currentUser={
          currentUser
        }
        draft={draft}
        signedRecord={
          signedRecord
        }
        onSaveDraft={saveExaminationDraft}
        onConflict={async () => {
          setConflictNotice('Trạng thái ca khám đã thay đổi hoặc lần lưu chưa được xác nhận. Đã yêu cầu cập nhật hàng chờ; hãy đối chiếu dữ liệu mới nhất trước khi tiếp tục.')
          const results = await Promise.allSettled([onRefresh(horse.id), load(true)])
          if (results.some(result => result.status === 'rejected' || result.value === false)) {
            throw new Error('Không thể cập nhật đầy đủ hàng chờ và hồ sơ.')
          }
        }}
        conflictNotice={conflictNotice}
        onSign={
          signMedicalRecord
        }
        onAfterSign={async () => {
          const loaded =
            await load(true)

          if (!loaded) {
            throw new Error(
              'Phiếu đã chốt nhưng không tải lại được hồ sơ. Hãy tải lại để xác nhận dữ liệu mới nhất.',
            )
          }

          await onRefresh(
            horse.id,
          )
        }}
      />
    )
  }

  return <VetMedicalProfile horse={horse} records={records} currentUser={currentUser}
    activeRequestId={activeRequest?.id}
    onRefresh={async (id) => {
      const loaded = await load()
      if (!loaded) throw new Error('Không thể tải lại hồ sơ.')
      await onRefresh(id)
    }} />
}

function AppContent() {
  const location = useLocation()

  const [
    currentUser,
    setCurrentUser,
  ] = useState(null)

  const [
    authChecking,
    setAuthChecking,
  ] = useState(
    Boolean(getAccessToken()),
  )

  const [
    authError,
    setAuthError,
  ] = useState('')

  const [
    loggingIn,
    setLoggingIn,
  ] = useState(false)

  const [horses, setHorses] =
    useState([])

  const [users, setUsers] =
    useState([])

  const [
    initialExams,
    setInitialExams,
  ] = useState([])

  const [
    loadingData,
    setLoadingData,
  ] = useState(
    Boolean(getAccessToken()),
  )

  const [
    loadError,
    setLoadError,
  ] = useState('')

  const [
    reloadCount,
    setReloadCount,
  ] = useState(0)

  useEffect(() => {
    const expire = () => {
      clearPendingHorseDocumentUploads()
      setCurrentUser(null)

      setAuthError(
        'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
      )
    }

    window.addEventListener(
      'equi:session-expired',
      expire,
    )

    return () =>
      window.removeEventListener(
        'equi:session-expired',
        expire,
      )
  }, [])

  useEffect(() => {
    if (!getAccessToken()) {
      setAuthChecking(false)
      return
    }

    let current = true

    getCurrentUser()
      .then((user) => {
        if (current) {
          setCurrentUser(user)
          setAuthError('')
        }
      })
      .catch((error) => {
        if (current) {
          if (error instanceof ApiError && error.status === 401) {
            clearPendingHorseDocumentUploads()
            clearSession()
          }

          setCurrentUser(null)

          setAuthError(
            error instanceof Error
              ? error.message
              : 'Không thể xác minh phiên đăng nhập.',
          )
        }
      })
      .finally(() => {
        if (current) {
          setAuthChecking(false)
        }
      })

    return () => {
      current = false
    }
  }, [])

  const loadData = useCallback(
    async () => {
      if (!currentUser || !userRole(currentUser)) {
        setLoadingData(false)
        return
      }

      setLoadingData(true)

      try {
        const [
          horseRows,
          ownerRows,
          examRows,
        ] = await Promise.all([
          getHorses(),

          currentUser.role ===
          'CLUB_MANAGER'
            ? getUsers(
                'HORSE_OWNER',
              )
            : Promise.resolve([]),

          currentUser.role ===
            'VET' ||
          currentUser.role ===
            'VETERINARIAN'
            ? getPendingInitialExams()
            : Promise.resolve([]),
        ])

        setHorses(horseRows)

        setUsers(ownerRows)

        setInitialExams(
          examRows,
        )

        setLoadError('')
      } catch (error) {
        setHorses([])
        setUsers([])
        setInitialExams([])

        setLoadError(
          userRole(currentUser) === 'vet' ? 'Không thể tải dữ liệu thú y. Vui lòng thử lại.' : error instanceof Error
            ? error.message
            : 'Không thể tải dữ liệu.',
        )
      } finally {
        setLoadingData(false)
      }
    },
    [currentUser],
  )

  useEffect(() => {
    void loadData()
  }, [
    loadData,
    reloadCount,
  ])

  const retryLoad = () => {
    setLoadingData(true)

    setLoadError('')

    setReloadCount(
      (count) => count + 1,
    )
  }

  async function handleLogin(
    email,
    password,
  ) {
    setLoggingIn(true)
    setLoadingData(true)
    setAuthError('')
    setLoadError('')

    try {
      const result =
        await login(
          email,
          password,
        )

      setCurrentUser(
        result.user,
      )
    } catch (error) {
      setAuthError(
        error instanceof Error
          ? error.message
          : 'Không thể đăng nhập.',
      )

      throw error
    } finally {
      setLoggingIn(false)
    }
  }

  function logout() {
    clearPendingHorseDocumentUploads()
    clearSession()

    setCurrentUser(null)

    setLoadingData(false)

    setHorses([])

    setUsers([])

    setInitialExams([])

    setAuthError('')
    setLoadError('')
  }

  function syncHorse(
    savedHorse,
  ) {
    setHorses((current) =>
      current.map((horse) =>
        String(horse.id) ===
        String(savedHorse.id)
          ? savedHorse
          : horse,
      ),
    )

    setInitialExams(
      (current) =>
        current.filter(
          (item) =>
            String(
              item.horse.id,
            ) !==
            String(
              savedHorse.id,
            ),
        ),
    )
  }

  async function refreshHorse(
    horseId,
  ) {
    const horse =
      await getHorseById(
        String(horseId),
      )

    syncHorse(horse)

    return horse
  }

  async function refreshVetData(
    horseId,
  ) {
    const [
      horse,
      examRows,
    ] = await Promise.all([
      getHorseById(
        String(horseId),
      ),

      getPendingInitialExams(),
    ])

    syncHorse(horse)

    setInitialExams(
      examRows,
    )

    return horse
  }

  async function actionOnHorse(
    action,
  ) {
    const saved =
      await action

    syncHorse(saved)

    return saved
  }

  const role =
    userRole(currentUser)

  const home =
    role === 'owner'
      ? '/owner/horses'
      : role === 'vet'
        ? '/vet/overview'
        : '/manager/horses'

  const ownerList =
    useMemo(
      () =>
        users.map((user) => ({
          ownerId: user.id,
          id: user.id,
          fullName:
            user.fullName,
        })),
      [users],
    )

  /*
   * ======================================
   * PUBLIC LANDING PAGE
   * ======================================
   *
   * Trang "/" luôn truy cập được,
   * không cần đăng nhập.
   */
  if (location.pathname === '/') {
    return <LandingPage />
  }

  /*
   * ======================================
   * AUTH CHECKING
   * ======================================
   */
  if (authChecking) {
    return (
      <main className="page-content">
        <section
          className="panel"
          role="status"
        >
          Đang xác minh phiên đăng
          nhập...
        </section>
      </main>
    )
  }

  /*
   * ======================================
   * LOGIN
   * ======================================
   */
  if (
    location.pathname ===
    '/login'
  ) {
    if (currentUser) {
      return (
        <Navigate
          to={home}
          replace
        />
      )
    }

    return (
      <LoginScreen
        onLogin={
          handleLogin
        }
        error={authError}
        busy={loggingIn}
      />
    )
  }

  /*
   * ======================================
   * PROTECTED ROUTES
   * ======================================
   *
   * Chưa login mà truy cập Manager,
   * Owner hoặc Vet thì về /login.
   */
  if (!currentUser) {
    return (
      <Navigate
        to="/login"
        replace
      />
    )
  }

  if (!role) {
    return <main className="page-content narrow-content"><section className="panel">
      <h1>Vai trò chưa có không gian Flow 1</h1>
      <p>Tài khoản {currentUser.email} đã đăng nhập. Flow 1 hỗ trợ Owner, Club Manager và Vet.</p>
      <button className="button" type="button" onClick={logout}>Đăng xuất</button>
    </section></main>
  }

  return (
    <div className={`app-shell${role === 'vet' ? ' vet-shell' : ''}`}>
      <aside className="app-sidebar">
        <Link
          className="brand"
          to={home}
        >
          <span className="brand-mark" aria-hidden="true">
            <img src="/equitrack-mark.jpg" alt="" />
          </span>

          <span>
            <strong>
              EQUITRACK
            </strong>

            <small>
              RACEHORSE PERFORMANCE
            </small>
          </span>
        </Link>

        <p className="sidebar-label">
          KHÔNG GIAN LÀM VIỆC
        </p>

        <nav
          className="side-nav"
          aria-label="Điều hướng chính"
        >
          {role ===
            'manager' && (
            <>
              <NavLink
                end
                to="/manager/horses"
              >
                <NavIcon kind="manager" />

                <span>
                  Danh sách ngựa
                </span>
              </NavLink>

              {currentUser.permissions.includes(
                'PROFILE_EDIT_APPROVE',
              ) && (
                <NavLink to="/manager/profile-change-requests">
                  <NavIcon kind="manager" />

                  <span>
                    Yêu cầu sửa hồ sơ
                  </span>
                </NavLink>
              )}
            </>
          )}

          {role === 'owner' && (
            <NavLink
              end
              to="/owner/horses"
            >
              <NavIcon kind="owner" />

              <span>
                Ngựa của tôi
              </span>
            </NavLink>
          )}

          {role === 'vet' && <>
            <NavLink to="/vet/overview"><NavIcon kind="vet" /><span>Tổng quan thú y</span></NavLink>
            <NavLink to="/vet/horses-needing-exam"><NavIcon kind="vet" /><span>Hàng chờ khám đầu vào</span></NavLink>
            <NavLink to="/vet/herd"><NavIcon kind="manager" /><span>Sức khỏe toàn đàn</span></NavLink>
            <NavLink to="/vet/stalls"><NavIcon kind="manager" /><span>Sơ đồ chuồng</span></NavLink>
            <NavLink to="/vet/reports"><NavIcon kind="vet" /><span>Báo cáo sức khỏe</span></NavLink>
            <NavLink to="/vet/calendar"><NavIcon kind="manager" /><span>Lịch y tế</span></NavLink>
          </>}
        </nav>

        <div className="sidebar-support">
          <strong>
            Cần hỗ trợ?
          </strong>

          <span>
            Liên hệ quản lý câu
            lạc bộ
          </span>

          <span className="support-link">
            Trung tâm hỗ trợ
          </span>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-workspace">
            <span className="topbar-kicker">
              {roleLabels[role]}
            </span>

            <strong>
              {currentUser.clubId
                ? `Câu lạc bộ #${currentUser.clubId}`
                : 'EquiTrack'}
            </strong>
          </div>

          <div className="topbar-account">
            <div className="topbar-user">
              <span
                className="avatar"
                aria-hidden="true"
              >
                {currentUser.fullName
                  .split(' ')
                  .map(
                    (part) =>
                      part[0],
                  )
                  .slice(0, 2)
                  .join('')
                  .toUpperCase()}
              </span>

              <div className="account-name">
                <strong>
                  {
                    currentUser.fullName
                  }
                </strong>

                <span>
                  <i />

                  {loadingData
                    ? 'Đang tải...'
                    : 'Đang hoạt động'}
                </span>
              </div>
            </div>

            <button
              className="button button-secondary"
              type="button"
              onClick={logout}
            >
              Đăng xuất
            </button>
          </div>
        </header>

        {loadError && (
          <div
            className="alert-banner"
            role="alert"
            style={{
              margin:
                '12px 24px 0',
              background:
                '#fff4f4',
              color: '#7a1d1d',
              border:
                '1px solid #f7c2c2',
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            {loadError}{' '}

            <button
              type="button"
              onClick={
                retryLoad
              }
            >
              Thử lại
            </button>
          </div>
        )}

        {loadingData && (
          <main className="page-content">
            <section
              className="panel"
              role="status"
            >
              Đang tải dữ liệu...
            </section>
          </main>
        )}

        {!loadingData &&
          !loadError && (
          <Routes>
            <Route
              path="/manager/horses"
              element={
                role ===
                'manager' ? (
                  <HorseList
                    owners={
                      ownerList
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route path="/manager/horses/new" element={role === 'manager' && currentUser.permissions.some((permission) => ['HORSE_REGISTER', 'HORSE_REGISTER_REVIEW'].includes(permission))
              ? <CreateHorse /> : <Navigate to={home} replace />} />

            <Route
              path="/manager/profile-change-requests"
              element={
                role ===
                  'manager' &&
                currentUser.permissions.includes(
                  'PROFILE_EDIT_APPROVE',
                ) ? (
                  <ProfileChangeRequests
                    onHorseRefresh={
                      refreshHorse
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/manager/horses/:horseId/intake"
              element={
                role ===
                'manager' ? (
                  <ManagerIntakeRoute
                    horses={horses}
                    permissions={
                      currentUser.permissions
                    }
                    onUpdateHorse={(
                      id,
                      changes,
                    ) =>
                      actionOnHorse(
                        updateHorse(
                          id,
                          changes,
                        ),
                      )
                    }
                    onSubmitHorse={(
                      id,
                    ) =>
                      actionOnHorse(
                        submitHorse(
                          id,
                        ),
                      )
                    }
                    onVerifyHorse={(
                      id,
                    ) =>
                      actionOnHorse(
                        verifyHorse(
                          id,
                        ),
                      )
                    }
                    onRejectHorse={(
                      id,
                      reason,
                    ) =>
                      actionOnHorse(
                        rejectHorse(
                          id,
                          reason,
                        ),
                      )
                    }
                    onApproveHorse={(
                      id,
                      payload,
                    ) =>
                      actionOnHorse(
                        completeHorseIntake(
                          id,
                          payload,
                        ),
                      )
                    }
                    onArchiveHorse={(
                      id,
                      reason,
                    ) =>
                      actionOnHorse(
                        archiveHorse(
                          id,
                          reason,
                        ),
                      )
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/owner/horses"
              element={
                role ===
                'owner' ? (
                  <OwnerHorses
                    horses={horses}
                    currentUser={
                      currentUser
                    }
                    owners={[
                      {
                        ownerId:
                          currentUser.id,

                        fullName:
                          currentUser.fullName,
                      },
                    ]}
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/owner/horses/new"
              element={
                role ===
                  'owner' &&
                currentUser.permissions.includes(
                  'HORSE_REGISTER',
                ) ? (
                  <OwnerHorseForm
                    currentUser={
                      currentUser
                    }
                    onSaved={(
                      horse,
                    ) =>
                      setHorses(
                        (
                          current,
                        ) => [
                          horse,

                          ...current.filter(
                            (
                              item,
                            ) =>
                              String(
                                item.id,
                              ) !==
                              String(
                                horse.id,
                              ),
                          ),
                        ],
                      )
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/owner/horses/:horseId/edit"
              element={
                role ===
                  'owner' &&
                currentUser.permissions.includes(
                  'HORSE_REGISTER',
                ) ? (
                  <OwnerHorseForm
                    currentUser={
                      currentUser
                    }
                    onSaved={
                      syncHorse
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            {['overview', 'herd', 'intake-results', 'stalls', 'reports', 'calendar'].map(mode => <Route key={mode}
              path={`/vet/${mode}`} element={role === 'vet'
                ? <VetWorkspace currentUser={currentUser} mode={mode} initialExams={initialExams} />
                : <Navigate to={home} replace />} />)}

            <Route
              path="/vet/horses-needing-exam"
              element={
                role ===
                'vet' ? (
                  <HorsesNeedingExam
                    currentUser={currentUser}
                    initialExams={
                      initialExams
                    }
                    horses={horses}
                    onRetry={
                      retryLoad
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/vet/horses/:horseId"
              element={
                role ===
                'vet' ? (
                  <VetHorseRoute
                    currentUser={
                      currentUser
                    }
                    initialExams={
                      initialExams
                    }
                    onRefresh={
                      refreshVetData
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/vet/horses/:horseId/examination"
              element={
                role ===
                'vet' ? (
                  <VetHorseRoute
                    currentUser={
                      currentUser
                    }
                    initialExams={
                      initialExams
                    }
                    onRefresh={
                      refreshVetData
                    }
                    examination
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/owner/horses/:horseId"
              element={
                role ===
                'owner' ? (
                  <HorseProfileRoute
                    currentUser={
                      currentUser
                    }
                    horses={
                      horses
                    }
                    onRefresh={
                      refreshHorse
                    }
                    onHorseUpdated={
                      syncHorse
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/owner/horses/:horseId/correction-request"
              element={
                role ===
                'owner' ? (
                  <OwnerCorrectionRoute
                    horses={
                      horses
                    }
                  />
                ) : (
                  <Navigate
                    to={home}
                    replace
                  />
                )
              }
            />

            <Route
              path="/horses/:horseId"
              element={
                <HorseProfileRoute
                  currentUser={
                    currentUser
                  }
                  horses={horses}
                  onRefresh={
                    refreshHorse
                  }
                  onHorseUpdated={
                    syncHorse
                  }
                />
              }
            />

            <Route
              path="*"
              element={
                <main className="page-content">
                  <section className="panel">
                    <h1>
                      Không tìm thấy
                      trang
                    </h1>

                    <Link
                      to={home}
                    >
                      Quay lại
                    </Link>
                  </section>
                </main>
              }
            />
          </Routes>
        )}

        <footer className="app-footer">
          EQUITRACK
        </footer>
      </div>
    </div>
  )
}

const router = createBrowserRouter([{ path: '*', element: <AppContent /> }])

function App() {
  return <RouterProvider router={router} />
}

export default App
