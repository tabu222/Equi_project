import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import HorseAvatar from '../../components/horse/HorseAvatar.jsx'
import { formatHorseCode, getHorseAge, valueOrMissing } from '../../components/horse/horseDisplay.js'
import { formatHorseGender } from '../../components/horse/horseLabels.js'

const profileStatusFilters = [
  ['DRAFT', 'Bản nháp'],
  ['SUBMITTED', 'Chờ xác minh'],
  ['PENDING_EXAM', 'Chờ khám'],
  ['APPROVED', 'Đã tiếp nhận'],
  ['REJECTED', 'Bị từ chối'],
  ['ARCHIVED', 'Đã lưu trữ'],
]

const healthStatusFilters = [
  ['NOT_ASSESSED', 'Chưa đánh giá'],
  ['ELIGIBLE', 'Đủ điều kiện'],
  ['MONITORING', 'Theo dõi'],
  ['INJURED', 'Chấn thương'],
  ['RECOVERING', 'Đang hồi phục'],
  ['ISOLATION', 'Cách ly'],
]

function OwnerHorses({ horses = [], currentUser, owners = [] }) {
  const [search, setSearch] = useState('')
  const [profileStatus, setProfileStatus] = useState('All')
  const [healthStatus, setHealthStatus] = useState('All')
  const currentOwnerId = currentUser?.id || ''
  const ownedHorses = useMemo(
    () => horses.filter((horse) => String(horse.ownerUserId) === String(currentOwnerId)),
    [currentOwnerId, horses],
  )
  const owner = owners.find((item) => String(item.ownerId) === String(currentOwnerId)) || currentUser
  const canRegister = currentUser?.permissions?.includes('HORSE_REGISTER')

  const filteredHorses = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return ownedHorses.filter((horse) => {
      const matchesSearch = !query
        || horse.name?.toLocaleLowerCase().includes(query)
        || horse.code?.toLocaleLowerCase().includes(query)
      return matchesSearch
        && (profileStatus === 'All' || horse.profileStatus === profileStatus)
        && (healthStatus === 'All' || horse.healthStatus === healthStatus)
    })
  }, [healthStatus, ownedHorses, profileStatus, search])

  const statusCounts = useMemo(() => ({
    awaiting: ownedHorses.filter((horse) => ['SUBMITTED', 'PENDING_EXAM'].includes(horse.profileStatus)).length,
    approved: ownedHorses.filter((horse) => horse.profileStatus === 'APPROVED').length,
    draft: ownedHorses.filter((horse) => horse.profileStatus === 'DRAFT').length,
    needsAttention: ownedHorses.filter((horse) => horse.profileStatus === 'REJECTED').length,
  }), [ownedHorses])

  function clearFilters() {
    setSearch('')
    setProfileStatus('All')
    setHealthStatus('All')
  }

  return (
    <main className="page-content owner-horse-list-page">
      <nav className="breadcrumb" aria-label="Đường dẫn">Ngựa của tôi</nav>
      <header className="page-heading owner-horses-heading">
        <div>
          <p className="eyebrow">CHỦ SỞ HỮU NGỰA · {owner?.fullName || 'CHỦ SỞ HỮU'}</p>
          <h1>Ngựa của tôi</h1>
          <p>Theo dõi hồ sơ đăng ký và thông tin sức khỏe ngựa thuộc sở hữu của bạn.</p>
        </div>
        {canRegister && <Link className="button" to="/owner/horses/new">Đăng ký ngựa</Link>}
      </header>

      <section className="horse-stat-strip owner-horse-stats" aria-label="Tổng quan hồ sơ ngựa">
        <div className="horse-stat-item horse-stat-total"><span>Tổng số ngựa</span><strong>{ownedHorses.length}</strong></div>
        <div className="horse-stat-item"><span>Chờ xử lý</span><strong>{statusCounts.awaiting}</strong></div>
        <div className="horse-stat-item"><span>Đã tiếp nhận</span><strong>{statusCounts.approved}</strong></div>
        <div className="horse-stat-item"><span>Bản nháp</span><strong>{statusCounts.draft}</strong></div>
        <div className="horse-stat-item"><span>Cần cập nhật</span><strong>{statusCounts.needsAttention}</strong></div>
      </section>

      <section className="filter-card owner-horse-filters" aria-label="Tìm kiếm và lọc ngựa">
        <label className="search-field" htmlFor="owner-horse-search">
          <span>Tìm theo tên hoặc mã ngựa</span>
          <input
            id="owner-horse-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nhập tên hoặc mã ngựa..."
          />
        </label>
        <label className="filter-field" htmlFor="owner-profile-status">
          <span>Trạng thái hồ sơ</span>
          <select id="owner-profile-status" value={profileStatus} onChange={(event) => setProfileStatus(event.target.value)}>
            <option value="All">Tất cả trạng thái</option>
            {profileStatusFilters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="filter-field" htmlFor="owner-health-status">
          <span>Tình trạng sức khỏe</span>
          <select id="owner-health-status" value={healthStatus} onChange={(event) => setHealthStatus(event.target.value)}>
            <option value="All">Tất cả tình trạng</option>
            {healthStatusFilters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <button className="clear-filter-button" type="button" onClick={clearFilters}>Xóa bộ lọc</button>
      </section>

      {filteredHorses.length === 0 ? (
        <section className="panel owner-horse-empty">
          <EmptyState
            title={ownedHorses.length === 0 ? 'Bạn chưa có ngựa nào trong hệ thống' : 'Không tìm thấy ngựa phù hợp'}
            description={ownedHorses.length === 0
              ? 'Các hồ sơ ngựa đã đăng ký sẽ hiển thị tại đây.'
              : 'Thử thay đổi từ khóa tìm kiếm hoặc bộ lọc.'}
          />
          {ownedHorses.length > 0 && <button className="clear-filter-button" type="button" onClick={clearFilters}>Xóa bộ lọc</button>}
        </section>
      ) : (
        <section className="owner-horse-grid" aria-label="Danh sách ngựa">
          {filteredHorses.map((horse) => (
            <article className="owner-horse-card" key={horse.id}>
              <HorseAvatar horseId={horse.id} name={horse.name} size="card" />
              <div className="owner-horse-card-body">
                <div className="owner-horse-card-identity">
                  <h2 title={horse.name}>{valueOrMissing(horse.name)}</h2>
                  <span className="profile-id">Mã ngựa {formatHorseCode(horse.code)}</span>
                </div>
                <p className="owner-horse-facts">
                  {valueOrMissing(horse.breed)} <span aria-hidden="true">·</span>{' '}
                  {horse.sex === 'UNKNOWN' ? 'Chưa cập nhật giới tính' : formatHorseGender(horse.sex)}
                  {getHorseAge(horse.dateOfBirth) && <><span aria-hidden="true">·</span> {getHorseAge(horse.dateOfBirth)}</>}
                </p>
                <dl className="card-statuses">
                  <div><dt>Trạng thái hồ sơ</dt><dd><StatusBadge status={horse.profileStatus} type="registration" /></dd></div>
                  <div><dt>Tình trạng sức khỏe</dt><dd><StatusBadge status={horse.healthStatus} type="health" /></dd></div>
                </dl>
                <Link className="owner-horse-view-link" to={`/owner/horses/${horse.id}`}>Xem hồ sơ<span aria-hidden="true">→</span></Link>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  )
}

export default OwnerHorses
