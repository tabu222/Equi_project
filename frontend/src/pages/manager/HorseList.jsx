import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'

const pageSize = 5
const registrationLabels = {
  DRAFT: 'Bản nháp',
  PENDING_EXAM: 'Chờ khám',
  PENDING_COMPLETION: 'Chờ hoàn tất',
  RECEIVED: 'Đã nhận',
  ARCHIVED: 'Đã lưu trữ',
}
const healthLabels = {
  NOT_ASSESSED: 'Chưa đánh giá',
  ELIGIBLE: 'Đủ điều kiện',
  MONITORING: 'Theo dõi',
  INJURED: 'Chấn thương',
  ISOLATION: 'Cách ly',
}

function HorseList({ horses, owners = [], currentUser }) {
  const [search, setSearch] = useState('')
  const [selectedOwnerId, setSelectedOwnerId] = useState('All')
  const [profileStatus, setProfileStatus] = useState('All')
  const [page, setPage] = useState(1)

  const clubHorses = useMemo(
    () => horses.filter((horse) => String(horse.clubId ?? '1') === String(currentUser?.clubId ?? '1')),
    [horses, currentUser],
  )
  const clubOwners = useMemo(
    () => owners.filter((owner) => clubHorses.some((horse) => String(horse.ownerUserId ?? horse.ownerId) === String(owner.ownerId))),
    [clubHorses, owners],
  )

  const filteredHorses = useMemo(() => {
    const query = search.trim().toLowerCase()
    return clubHorses.filter((horse) => {
      const matchesSearch = !query || String(horse.code ?? horse.id).toLowerCase().includes(query) || String(horse.name ?? horse.horseName).toLowerCase().includes(query)
      const matchesOwner = selectedOwnerId === 'All' || String(horse.ownerUserId ?? horse.ownerId) === selectedOwnerId
      const matchesStatus = profileStatus === 'All' || String(horse.profileStatus) === profileStatus
      return matchesSearch && matchesOwner && matchesStatus
    })
  }, [clubHorses, search, selectedOwnerId, profileStatus])

  const pageCount = Math.max(1, Math.ceil(filteredHorses.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const pageHorses = filteredHorses.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const firstResult = filteredHorses.length === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const lastResult = Math.min(currentPage * pageSize, filteredHorses.length)

  function clearFilters() {
    setSearch('')
    setSelectedOwnerId('All')
    setProfileStatus('All')
    setPage(1)
  }

  return (
    <main className="page-content horse-list-page">
      <nav className="breadcrumb" aria-label="Đường dẫn">Danh sách ngựa <span aria-hidden="true">/</span> Danh sách chiến mã</nav>
      <header className="page-heading list-heading">
        <div><p className="eyebrow">QUẢN LÝ CÂU LẠC BỘ</p><h1>Danh sách chiến mã</h1><p>Quản lý hồ sơ, người phụ trách và chủ sở hữu.</p></div>
        <div className="horse-count"><strong>{filteredHorses.length}</strong><span>ngựa phù hợp</span></div>
      </header>
      <section className="filter-card" aria-label="Tìm kiếm và lọc danh sách ngựa">
        <div className="filter-row">
          <label className="search-field" htmlFor="horse-search"><span>Tìm kiếm</span><input id="horse-search" placeholder="Tên hoặc mã ngựa..." value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /></label>
          <label className="filter-field" htmlFor="owner-filter"><span>Chủ sở hữu</span><select id="owner-filter" value={selectedOwnerId} onChange={(event) => { setSelectedOwnerId(event.target.value); setPage(1) }}><option value="All">Tất cả chủ sở hữu</option>{clubOwners.map((owner) => <option key={owner.ownerId} value={owner.ownerId}>{owner.fullName}</option>)}</select></label>
          <label className="filter-field" htmlFor="status-filter"><span>Trạng thái hồ sơ</span><select id="status-filter" value={profileStatus} onChange={(event) => { setProfileStatus(event.target.value); setPage(1) }}><option value="All">Tất cả trạng thái</option>{Object.entries(registrationLabels).map(([status, label]) => <option key={status} value={status}>{label}</option>)}</select></label>
          <button className="clear-filter-button" type="button" onClick={clearFilters}>Xóa bộ lọc</button>
          <Link className="button" to="/manager/horses/new">Thêm ngựa</Link>
        </div>
      </section>
      <section className="table-card" aria-label="Danh sách ngựa">
        <div className="table-header"><div><h2>Danh sách ngựa</h2><p>Đang hiển thị {firstResult}–{lastResult} trong {filteredHorses.length} ngựa</p></div></div>
        {filteredHorses.length === 0 ? (
          <div className="horse-list-empty"><EmptyState title="Không tìm thấy ngựa" description="Không có ngựa phù hợp với điều kiện tìm kiếm hoặc bộ lọc hiện tại." /><button className="clear-filter-button" type="button" onClick={clearFilters}>Xóa bộ lọc</button></div>
        ) : (
          <div className="table-wrapper"><table className="horse-table"><thead><tr><th scope="col">Mã ngựa</th><th scope="col">Tên ngựa</th><th scope="col">Giống</th><th scope="col">Chủ sở hữu</th><th scope="col">Trạng thái hồ sơ</th><th scope="col">Sức khỏe</th><th scope="col">Thao tác</th></tr></thead>
            <tbody>{pageHorses.map((horse) => <tr key={horse.id}>
              <td className="horse-id">#{horse.code || horse.id}</td><td><strong>{horse.name || 'Chưa có tên'}</strong></td>
              <td>{horse.breed || '—'}</td><td>{owners.find((owner) => String(owner.ownerId) === String(horse.ownerUserId ?? horse.ownerId))?.fullName || 'Chưa có thông tin'}</td>
              <td><StatusBadge status={horse.profileStatus} label={registrationLabels[horse.profileStatus] || horse.profileStatus} type="registration" /></td><td><StatusBadge status={horse.healthStatus} label={healthLabels[horse.healthStatus] || horse.healthStatus} type="health" /></td>
              <td><Link className="view-button" to={`/horses/${horse.id}`}>Xem chi tiết</Link></td>
            </tr>)}</tbody>
          </table></div>
        )}
        {filteredHorses.length > 0 && pageCount > 1 && <nav className="pagination" aria-label="Phân trang danh sách ngựa">
          <button type="button" className="page-button" onClick={() => setPage(Math.max(1, currentPage - 1))} disabled={currentPage === 1}>Trước</button>
          {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => <button key={pageNumber} type="button" className={`page-button${pageNumber === currentPage ? ' selected' : ''}`} aria-current={pageNumber === currentPage ? 'page' : undefined} onClick={() => setPage(pageNumber)}>{pageNumber}</button>)}
          <button type="button" className="page-button" onClick={() => setPage(Math.min(pageCount, currentPage + 1))} disabled={currentPage === pageCount}>Tiếp</button>
        </nav>}
      </section>
    </main>
  )
}

export default HorseList
