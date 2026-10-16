import { useState } from 'react'
import EmptyState from '../common/EmptyState.jsx'
import StatusBadge from '../common/StatusBadge.jsx'
import HorseBasicInfo from './HorseBasicInfo.jsx'
import HorsePedigree from './HorsePedigree.jsx'
import HorseOwnerInfo from './HorseOwnerInfo.jsx'
import HorseDocuments from './HorseDocuments.jsx'
import HorseHealthSummary from './HorseHealthSummary.jsx'
import { formatHorseGender } from './horseLabels.js'
import HorseAvatar from './HorseAvatar.jsx'
import { formatHorseDate, formatHorseDateTime, formatHorseCode, getHorseAge } from './horseDisplay.js'

function HorseProfile({ horse, owner, clubName, documents, healthContent, registrationLabel, registrationHistory = [], medicalRecords = [] }) {
  const [activeTab, setActiveTab] = useState('profile')
  const tabs = [
    { id: 'profile', label: 'Tổng quan' },
    { id: 'health', label: 'Sức khỏe' },
    { id: 'documents', label: 'Hình ảnh & tài liệu' },
    ...(registrationHistory.length ? [{ id: 'history', label: 'Lịch sử' }] : []),
  ]

  function handleTabKeyDown(event) {
    const tabs = Array.from(event.currentTarget.parentElement.querySelectorAll('[role="tab"]'))
    const currentIndex = tabs.indexOf(event.currentTarget)
    let nextIndex
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % tabs.length
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = tabs.length - 1
    if (nextIndex == null) return
    event.preventDefault()
    const nextTab = tabs[nextIndex]
    nextTab.focus()
    setActiveTab(nextTab.id.replace('horse-', '').replace('-tab', ''))
  }

  if (!horse) return <EmptyState title="Không tìm thấy ngựa" description="Hồ sơ này không có trong dữ liệu hiện tại." />

  return (
    <div className="horse-profile">
      <header className="profile-header panel">
        <HorseAvatar horseId={horse.id} documents={horse.documents} name={horse.name} size="profile" />
        <div className="profile-identity">
          <span className="profile-id">Mã ngựa {formatHorseCode(horse.code)}</span>
          <h1>{horse.name || 'Chưa có tên'}</h1>
          <p>{[horse.breed || 'Chưa cập nhật giống', horse.sex === 'UNKNOWN' ? '' : formatHorseGender(horse.sex), getHorseAge(horse.dateOfBirth)].filter(Boolean).join(' · ')}</p>
        </div>
        <div className="profile-statuses">
          <div><span>Trạng thái hồ sơ</span><StatusBadge status={horse.profileStatus} label={registrationLabel} type="registration" /></div>
          <div><span>Tình trạng sức khỏe</span><StatusBadge status={horse.healthStatus} type="health" /></div>
        </div>
      </header>
      <div className="profile-tabs" role="tablist" aria-label="Các mục hồ sơ ngựa">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`horse-${tab.id}-tab`}
            className="profile-tab"
            type="button"
            role="tab"
            tabIndex={activeTab === tab.id ? 0 : -1}
            aria-selected={activeTab === tab.id}
            aria-controls={`horse-${tab.id}-panel`}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={handleTabKeyDown}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <section id="horse-profile-panel" className="profile-tab-panel" role="tabpanel" aria-labelledby="horse-profile-tab" hidden={activeTab !== 'profile'}>
        <div className="profile-overview-grid">
          <div className="profile-primary-column">
            <HorseBasicInfo horse={horse} />
            <HorsePedigree horse={horse} />
          </div>
          <div className="profile-secondary-column">
            <HorseOwnerInfo owner={owner} clubName={clubName} updatedAt={formatHorseDateTime(horse.updatedAt)} />
          </div>
        </div>
      </section>
      <section id="horse-health-panel" className="profile-tab-panel health-tab-panel" role="tabpanel" aria-labelledby="horse-health-tab" hidden={activeTab !== 'health'}>
        <HorseHealthSummary>
          {healthContent}
          {medicalRecords.length > 0 && (
            <section className="health-history">
              <div className="section-title"><h2>Lịch sử khám</h2></div>
              <div className="health-record-list">
                {medicalRecords.map((record) => (
                  <article className="health-record-item" key={record.id}>
                    <div className="health-record-heading">
                      <strong>{record.examType || 'Khám sức khỏe'}</strong>
                      <StatusBadge status={record.recordStatus} />
                    </div>
                    <p>{formatHorseDateTime(record.examDate)}</p>
                    {record.healthStatus && <p>Tình trạng: {record.healthStatus}</p>}
                    {record.conclusion && <p>Kết luận: {record.conclusion}</p>}
                    {record.trainingEligibility && <p>Điều kiện tập luyện: {record.trainingEligibility}</p>}
                    {record.followUpDate && <p>Tái khám: {formatHorseDate(record.followUpDate)}</p>}
                  </article>
                ))}
              </div>
            </section>
          )}
        </HorseHealthSummary>
      </section>
      <section id="horse-documents-panel" className="profile-tab-panel" role="tabpanel" aria-labelledby="horse-documents-tab" hidden={activeTab !== 'documents'}>
        <HorseDocuments documents={documents} />
      </section>
      {registrationHistory.length > 0 && (
        <section id="horse-history-panel" className="profile-tab-panel" role="tabpanel" aria-labelledby="horse-history-tab" hidden={activeTab !== 'history'}>
          <div className="profile-section profile-info-card">
            <div className="section-title"><h2>Lịch sử đăng ký</h2></div>
            <div className="request-list">
              {registrationHistory.map((item) => (
                <article className="request-item" key={item.id}>
                  <div className="request-item-heading">
                    <strong>Yêu cầu đăng ký</strong>
                    <StatusBadge status={item.status} />
                  </div>
                  <p>Ngày gửi: {formatHorseDateTime(item.requestDate)}</p>
                  {item.reviewedAt && <p>Ngày xử lý: {formatHorseDateTime(item.reviewedAt)}</p>}
                  {item.managerNote && <p>Ghi chú: {item.managerNote}</p>}
                </article>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

export default HorseProfile
