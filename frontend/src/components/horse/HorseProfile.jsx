import { useState } from 'react'
import EmptyState from '../common/EmptyState.jsx'
import StatusBadge from '../common/StatusBadge.jsx'
import HorseBasicInfo from './HorseBasicInfo.jsx'
import HorsePedigree from './HorsePedigree.jsx'
import HorseOwnerInfo from './HorseOwnerInfo.jsx'
import HorseDocuments from './HorseDocuments.jsx'
import HorseHealthSummary from './HorseHealthSummary.jsx'
import { formatHorseGender } from './horseLabels.js'

function HorseProfile({ horse, owner, documents, healthContent }) {
  const [activeTab, setActiveTab] = useState('profile')

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
    setActiveTab(nextTab.id === 'horse-health-tab' ? 'health' : 'profile')
  }

  if (!horse) return <EmptyState title="Không tìm thấy ngựa" description="Hồ sơ này không có trong dữ liệu hiện tại." />

  return (
    <div className="horse-profile">
      <header className="profile-header panel">
        <div><span className="profile-id">Mã ngựa #{horse.id}</span><h1>{horse.name || 'Chưa có tên'}</h1><p>{[horse.breed, formatHorseGender(horse.sex)].filter(Boolean).join(' · ')}</p></div>
        <div className="profile-statuses">
          <div><span>Trạng thái hồ sơ</span><StatusBadge status={horse.profileStatus} type="registration" /></div>
          <div><span>Sức khỏe</span><StatusBadge status={horse.healthStatus} type="health" /></div>
        </div>
      </header>
      <div className="profile-tabs" role="tablist" aria-label="Các mục hồ sơ ngựa">
        <button id="horse-profile-tab" className="profile-tab" type="button" role="tab" tabIndex={activeTab === 'profile' ? 0 : -1} aria-selected={activeTab === 'profile'} aria-controls="horse-profile-panel" onClick={() => setActiveTab('profile')} onKeyDown={handleTabKeyDown}>Hồ sơ</button>
        <button id="horse-health-tab" className="profile-tab" type="button" role="tab" tabIndex={activeTab === 'health' ? 0 : -1} aria-selected={activeTab === 'health'} aria-controls="horse-health-panel" onClick={() => setActiveTab('health')} onKeyDown={handleTabKeyDown}>Sức khỏe</button>
      </div>
      <section id="horse-profile-panel" className="profile-tab-panel" role="tabpanel" aria-labelledby="horse-profile-tab" hidden={activeTab !== 'profile'}>
        <HorseBasicInfo horse={horse} />
        <HorsePedigree horse={horse} />
        <HorseOwnerInfo owner={owner} ownerId={horse.ownerUserId} />
        <HorseDocuments documents={documents} />
      </section>
      <section id="horse-health-panel" className="profile-tab-panel health-tab-panel" role="tabpanel" aria-labelledby="horse-health-tab" hidden={activeTab !== 'health'}>
        <HorseHealthSummary>{healthContent}</HorseHealthSummary>
      </section>
    </div>
  )
}

export default HorseProfile
