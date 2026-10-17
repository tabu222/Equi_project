import { vetDateTime } from './vetDomain.js'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import HorseAvatar from '../../components/horse/HorseAvatar.jsx'
import { formatHorseCode, valueOrMissing } from '../../components/horse/horseDisplay.js'
import { formatHorseGender } from '../../components/horse/horseLabels.js'

const pageSize = 10

function HorsesNeedingExam({ initialExams = [], horses = [], currentUser, loadError, onRetry }) {
  const [search, setSearch] = useState('')
  const [examStatus, setExamStatus] = useState('All')
  const [page, setPage] = useState(1)
  const horseById = useMemo(
    () => new Map(horses.map((horse) => [String(horse.id), horse])),
    [horses],
  )

  const filteredExams = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return initialExams.filter(({ horse, draftMedicalRecordId }) => {
      const code = horse.code || horseById.get(String(horse.id))?.code || ''
      const matchesSearch = !query
        || horse.name?.toLocaleLowerCase().includes(query)
        || code.toLocaleLowerCase().includes(query)
        || horse.microchipNumber?.toLocaleLowerCase().includes(query)
      const matchesStatus = examStatus === 'All'
        || (examStatus === 'Draft' && Boolean(draftMedicalRecordId))
        || (examStatus === 'NotStarted' && !draftMedicalRecordId)
      return matchesSearch && matchesStatus
    })
  }, [examStatus, horseById, initialExams, search])

  const pageCount = Math.max(1, Math.ceil(filteredExams.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const pageExams = filteredExams.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const firstResult = filteredExams.length ? (currentPage - 1) * pageSize + 1 : 0
  const lastResult = Math.min(currentPage * pageSize, filteredExams.length)
  const draftCount = initialExams.filter((exam) => Boolean(exam.draftMedicalRecordId)).length

  return (
    <main className="page-content vet-exam-queue-page">
      <nav className="breadcrumb" aria-label="Đường dẫn">Hồ sơ khám <span aria-hidden="true">/</span> Hàng chờ khám</nav>
      <header className="page-heading">
        <div>
          <p className="eyebrow">BÁC SĨ THÚ Y · HỒ SƠ KHÁM</p>
          <h1>Hàng chờ khám đầu vào</h1>
          <p>Vet trực tiếp nhận khám, không cần Manager chỉ định. <Link to="/vet/intake-results">Xem kết quả khám đầu vào →</Link></p>
        </div>
        <button className="button button-secondary" type="button" onClick={onRetry}>Làm mới hàng chờ</button>
      </header>
      <p className="vet-caption">Thời gian chờ hiện tính từ lúc gửi hồ sơ tiếp nhận. Chưa có mốc riêng cho lúc chuyển sang chờ khám.</p>

      {loadError && (
        <section className="panel" role="alert">
          <p>{loadError}</p>
          <button className="button" type="button" onClick={onRetry}>Thử lại</button>
        </section>
      )}

      {!loadError && (
        <>
          <section className="horse-stat-strip vet-queue-stats" aria-label="Tổng quan hàng chờ khám">
            <div className="horse-stat-item horse-stat-total"><span>Đang chờ khám</span><strong>{initialExams.length}</strong></div>
            <div className="horse-stat-item"><span>Đã có phiếu nháp</span><strong>{draftCount}</strong></div>
            <div className="horse-stat-item"><span>Chưa bắt đầu</span><strong>{initialExams.length - draftCount}</strong></div>
          </section>

          <section className="filter-card vet-queue-filters" aria-label="Tìm kiếm và lọc hàng chờ">
            <label className="search-field" htmlFor="vet-horse-search">
              <span>Tìm theo tên, mã hoặc microchip</span>
              <input
                id="vet-horse-search"
                type="search"
                placeholder="Nhập thông tin ngựa..."
                value={search}
                onChange={(event) => { setSearch(event.target.value); setPage(1) }}
              />
            </label>
            <label className="filter-field" htmlFor="vet-exam-status">
              <span>Tiến độ khám</span>
              <select id="vet-exam-status" value={examStatus} onChange={(event) => { setExamStatus(event.target.value); setPage(1) }}>
                <option value="All">Tất cả tiến độ</option>
                <option value="NotStarted">Chưa bắt đầu</option>
                <option value="Draft">Đang có phiếu nháp</option>
              </select>
            </label>
            <button className="clear-filter-button" type="button" onClick={() => { setSearch(''); setExamStatus('All'); setPage(1) }}>Xóa bộ lọc</button>
          </section>

          {filteredExams.length === 0 ? (
            <section className="panel">
              <EmptyState
                title={initialExams.length === 0 ? 'Không có hồ sơ chờ khám' : 'Không tìm thấy hồ sơ phù hợp'}
                description={initialExams.length === 0
                  ? 'Khi hồ sơ được xác minh và chuyển sang chờ khám, hồ sơ sẽ hiển thị tại đây.'
                  : 'Thử thay đổi từ khóa hoặc tiến độ khám.'}
              />
            </section>
          ) : (
            <section className="table-card vet-queue-table-card" aria-label="Danh sách hồ sơ cần khám">
              <div className="table-header">
                <div><h2>Hồ sơ khám đầu vào</h2><p>Đang hiển thị {firstResult}–{lastResult} trong {filteredExams.length} hồ sơ phù hợp.</p></div>
              </div>
              <div className="table-wrapper">
                <table className="horse-table vet-queue-table">
                  <thead>
                    <tr>
                      <th scope="col">Ngựa</th>
                      <th scope="col">Nhận diện</th>
                      <th scope="col">Trạng thái hồ sơ</th>
                      <th scope="col">Tiến độ khám</th>
                      <th scope="col">Gửi vào hàng chờ tiếp nhận</th>
                      <th scope="col">Thời gian chờ</th>
                      <th scope="col">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageExams.map(({ horse, requestDate, waitingHours, draftMedicalRecordId, draftVetId }) => {
                      const code = horse.code || horseById.get(String(horse.id))?.code || ''
                      return (
                      <tr key={horse.id} className={waitingHours >= 24 ? 'vet-wait-long' : undefined}>
                        <td>
                          <div className="horse-table-identity">
                            <HorseAvatar horseId={horse.id} name={horse.name} size="small" />
                            <div><strong>{valueOrMissing(horse.name)}</strong><small>{formatHorseCode(code)}</small></div>
                          </div>
                        </td>
                        <td>{valueOrMissing(horse.breed)}<small>{horse.sex === 'UNKNOWN' ? 'Chưa cập nhật giới tính' : formatHorseGender(horse.sex)}</small><small>Microchip: {valueOrMissing(horse.microchipNumber)}</small></td>
                        <td><StatusBadge status={horse.profileStatus} type="registration" /></td>
                        <td><StatusBadge status={draftMedicalRecordId ? 'DRAFT' : 'PENDING'} type="exam" label={draftMedicalRecordId ? `Đang khám · phiếu #${draftMedicalRecordId}` : 'Chưa bắt đầu'} /></td>
                        <td>{vetDateTime(requestDate)}</td>
                        <td>{typeof waitingHours === 'number' && Number.isFinite(waitingHours) ? `${waitingHours} giờ${waitingHours >= 24 ? ' · Chờ lâu' : ''}` : 'Chưa cập nhật'}</td>
                        <td>
                          {!currentUser?.permissions.includes('MEDICAL_MANAGE') ? <span>Không có quyền nhận khám</span>
                            : draftMedicalRecordId && draftVetId !== currentUser.id
                              ? <><span>Vet khác đang xử lý</span><Link className="view-button" to={`/vet/horses/${horse.id}`}>Xem hồ sơ</Link></>
                              : <Link className="view-button vet-queue-action" to={`/vet/horses/${horse.id}/examination`}>
                                {draftMedicalRecordId ? 'Tiếp tục phiếu nháp' : 'Bắt đầu khám'}
                              </Link>}
                        </td>
                      </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {pageCount > 1 && (
                <nav className="pagination" aria-label="Phân trang hàng chờ khám">
                  <button type="button" className="page-button" onClick={() => setPage(Math.max(1, currentPage - 1))} disabled={currentPage === 1}>Trước</button>
                  {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => (
                    <button key={pageNumber} type="button" className={`page-button${pageNumber === currentPage ? ' selected' : ''}`} aria-current={pageNumber === currentPage ? 'page' : undefined} onClick={() => setPage(pageNumber)}>{pageNumber}</button>
                  ))}
                  <button type="button" className="page-button" onClick={() => setPage(Math.min(pageCount, currentPage + 1))} disabled={currentPage === pageCount}>Tiếp</button>
                </nav>
              )}
            </section>
          )}
        </>
      )}
    </main>
  )
}

export default HorsesNeedingExam
