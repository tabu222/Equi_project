import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getHorses } from '../../api/horseApi'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import { matchesRegistrationFilter, registrationFilters, registrationGroup } from '../../components/horse/registrationGroups.js'

const pageSize = 5
const validFilters = new Set(registrationFilters.map(([value]) => value))
const healthLabels = {
  NOT_ASSESSED: 'Chưa đánh giá',
  ELIGIBLE: 'Đủ điều kiện',
  MONITORING: 'Theo dõi',
  INJURED: 'Chấn thương',
  RECOVERING: 'Đang hồi phục',
  ISOLATION: 'Cách ly',
}

function HorseList({ owners = [], canCreate = false }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlFilter = searchParams.get('status')
  const selectedFilter = validFilters.has(urlFilter) ? urlFilter : 'NeedsAction'
  const [horses, setHorses] = useState([])
  const [search, setSearch] = useState('')
  const [selectedOwnerId, setSelectedOwnerId] = useState('All')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)
  const requestInFlight = useRef(false)
  const mounted = useRef(false)

  const loadHorses = useCallback(async () => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    setLoading(true)
    setError('')
    try {
      const result = await getHorses()
      if (mounted.current) setHorses([...new Map(result.map((horse) => [String(horse.id), horse])).values()])
    } catch (loadError) {
      if (mounted.current) setError(loadError instanceof Error ? loadError.message : 'Không thể tải danh sách ngựa.')
    } finally {
      requestInFlight.current = false
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void loadHorses()
    }
    window.addEventListener('focus', refreshWhenVisible)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      mounted.current = false
      window.removeEventListener('focus', refreshWhenVisible)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [loadHorses])
  useEffect(() => { void loadHorses() }, [loadHorses, reloadCount])

  const baseHorses = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return horses.filter((horse) => {
      const matchesSearch = !query
        || String(horse.code || horse.id).toLocaleLowerCase().includes(query)
        || String(horse.name).toLocaleLowerCase().includes(query)
        || String(horse.microchipNumber).toLocaleLowerCase().includes(query)
      const matchesOwner = selectedOwnerId === 'All' || String(horse.ownerUserId) === selectedOwnerId
      return matchesSearch && matchesOwner
    })
  }, [horses, search, selectedOwnerId])

  const groupCounts = useMemo(() => {
    const counts = {
      NeedsAction: 0,
      Submitted: 0,
      WaitingExam: 0,
      Examined: 0,
      Approved: 0,
      Draft: 0,
      Rejected: 0,
      Archived: 0,
      All: baseHorses.length,
    }
    baseHorses.forEach((horse) => {
      const group = registrationGroup(horse)
      if (group in counts) counts[group] += 1
      if (group === 'Submitted' || group === 'Examined') counts.NeedsAction += 1
    })
    return counts
  }, [baseHorses])

  const filteredHorses = useMemo(
    () => baseHorses.filter((horse) => matchesRegistrationFilter(horse, selectedFilter)),
    [baseHorses, selectedFilter],
  )
  const pageCount = Math.max(1, Math.ceil(filteredHorses.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const pageHorses = filteredHorses.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const firstResult = filteredHorses.length === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const lastResult = Math.min(currentPage * pageSize, filteredHorses.length)
  const clubOwners = useMemo(
    () => owners.filter((owner) => horses.some((horse) => String(horse.ownerUserId) === String(owner.ownerId))),
    [horses, owners],
  )

  function selectFilter(value) {
    setPage(1)
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('status', value)
      return next
    })
  }

  function refresh() {
    setLoading(true)
    setError('')
    setPage(1)
    setReloadCount((count) => count + 1)
  }

  function clearFilters() {
    setSearch('')
    setSelectedOwnerId('All')
    selectFilter('All')
  }

  const filterLabel = registrationFilters.find(([value]) => value === selectedFilter)?.[1] || 'Cần xử lý'

  return (
    <main className="page-content horse-list-page">
      <nav className="breadcrumb" aria-label="Đường dẫn">Danh sách ngựa <span aria-hidden="true">/</span> Danh sách chiến mã</nav>
      <header className="page-heading list-heading">
        <div><p className="eyebrow">QUẢN LÝ CÂU LẠC BỘ</p><h1>Danh sách chiến mã</h1><p>Hồ sơ do Manager lập hoặc Owner gửi đến CLB, tình trạng khám và hồ sơ đã tiếp nhận.</p></div>
        <div className="horse-count"><strong>{filteredHorses.length}</strong><span>ngựa phù hợp</span></div>
        {canCreate && <Link className="button" to="/manager/horses/new">+ Thêm ngựa</Link>}
      </header>
      <section className="filter-card" aria-label="Tìm kiếm và lọc danh sách ngựa">
        <div className="filter-row">
          <label className="search-field" htmlFor="horse-search"><span>Tìm kiếm</span><input id="horse-search" placeholder="Tên, mã hoặc microchip..." value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /></label>
          <label className="filter-field" htmlFor="owner-filter"><span>Chủ sở hữu</span><select id="owner-filter" value={selectedOwnerId} onChange={(event) => { setSelectedOwnerId(event.target.value); setPage(1) }}><option value="All">Tất cả chủ sở hữu</option>{clubOwners.map((owner) => <option key={owner.ownerId} value={owner.ownerId}>{owner.fullName}</option>)}</select></label>
          <label className="filter-field" htmlFor="status-filter"><span>Trạng thái hồ sơ</span><select id="status-filter" value={selectedFilter} onChange={(event) => selectFilter(event.target.value)}>{registrationFilters.map(([value, label]) => <option key={value} value={value}>{label} ({groupCounts[value]})</option>)}</select></label>
          <button className="clear-filter-button" type="button" onClick={clearFilters}>Xóa bộ lọc</button>
          <button className="button button-secondary" type="button" onClick={refresh} disabled={loading}>{loading ? 'Đang tải...' : 'Làm mới'}</button>
        </div>
        <div className="horse-group-counts" aria-label="Số hồ sơ theo trạng thái">
          {registrationFilters.filter(([value]) => value !== 'All').map(([value, label]) => (
            <button key={value} type="button" className={`horse-group-count${selectedFilter === value ? ' selected' : ''}`} onClick={() => selectFilter(value)} aria-pressed={selectedFilter === value}>
              {label}<strong>{groupCounts[value]}</strong>
            </button>
          ))}
        </div>
      </section>
      <section className="table-card" aria-label="Danh sách ngựa">
        <div className="table-header"><div><h2>{filterLabel}</h2><p>Đang hiển thị {firstResult}–{lastResult} trong {filteredHorses.length} ngựa</p></div></div>
        {error ? <div className="horse-list-empty" role="alert"><p className="error-message">{error}</p><button className="button" type="button" onClick={refresh}>Thử lại</button></div>
          : loading ? <p className="table-loading" role="status">Đang tải danh sách ngựa...</p>
            : filteredHorses.length === 0 ? (
              <div className="horse-list-empty"><EmptyState title="Không tìm thấy ngựa" description={selectedFilter === 'NeedsAction' ? 'Không có hồ sơ nào cần Manager xử lý theo điều kiện hiện tại.' : 'Không có ngựa phù hợp với tìm kiếm và bộ lọc hiện tại.'} /><button className="clear-filter-button" type="button" onClick={clearFilters}>Xóa bộ lọc</button></div>
            ) : (
              <div className="table-wrapper"><table className="horse-table"><thead><tr><th scope="col">Mã ngựa</th><th scope="col">Tên ngựa</th><th scope="col">Giống</th><th scope="col">Chủ sở hữu</th><th scope="col">Trạng thái hồ sơ</th><th scope="col">Sức khỏe</th><th scope="col">Thao tác</th></tr></thead>
                <tbody>{pageHorses.map((horse) => <tr key={horse.id}>
                  <td className="horse-id">#{horse.code || horse.id}</td><td><strong>{horse.name || 'Chưa có tên'}</strong></td>
                  <td>{horse.breed || '—'}</td><td>{horse.ownerName || owners.find((owner) => String(owner.ownerId) === String(horse.ownerUserId))?.fullName || 'Chưa có thông tin'}</td>
                  <td><StatusBadge status={horse.profileStatus} label={registrationGroup(horse) === 'Unknown' ? horse.profileStatus : registrationFilters.find(([value]) => value === registrationGroup(horse))?.[1]} type="registration" /></td>
                  <td><StatusBadge status={horse.healthStatus} label={healthLabels[horse.healthStatus] || horse.healthStatus} type="health" /></td>
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
