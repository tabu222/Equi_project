import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getVetHerd, getVetHistories, getVetStalls } from '../../api/vetApi.ts'
import HorseAvatar from '../../components/horse/HorseAvatar.jsx'
import { formatHorseCode } from '../../components/horse/horseDisplay.js'
import { clubToday, dueGroup, healthLabels, latestSigned, trainingLabels, vetError } from './vetDomain.js'
import './VetWorkspace.css'

export function Unavailable({ title, children, action }) {
  return <section className="vet-unavailable"><h3>{title}</h3><p>{children}</p>{action && <button className="button button-secondary" type="button" disabled>{action}</button>}</section>
}

export function TrainingBadge({ record }) {
  return <span className={`vet-pill training-${record?.trainingEligibility?.replaceAll(' ', '-') || 'unknown'}`}>
    {record ? trainingLabels[record.trainingEligibility] || 'Chưa kết luận điều kiện tập' : 'Chưa có kết luận điều kiện tập'}
  </span>
}
export function HealthBadge({ status }) {
  return <span className={`vet-pill health-${status}`}>● {healthLabels[status] || 'Chưa đánh giá'}</span>
}

function useVetData(clubId) {
  const [state, setState] = useState({ loading: true, horses: [], records: [], historyLoading: true, historyErrors: [], stalls: null, stallError: false })
  const [version, setVersion] = useState(0)
  useEffect(() => {
    let active = true
    getVetHerd(clubId).then(async horses => {
      if (!active) return
      setState(s => ({ ...s, loading: false, error: '', horses }))
      const history = await getVetHistories(horses.filter(h => h.profileStatus === 'APPROVED' || (h.profileStatus === 'PENDING_EXAM' && h.initialExamSigned)))
      if (active) setState(s => ({ ...s, records: history.records, historyErrors: history.failedHorseIds, historyLoading: false }))
    }).catch(error => { if (active) setState(s => ({ ...s, loading: false, error: vetError(error) })) })
    getVetStalls(clubId).then(stalls => {
      if (active) setState(s => ({ ...s, stalls, stallError: false }))
    }).catch(() => { if (active) setState(s => ({ ...s, stallError: true })) })
    return () => { active = false }
  }, [clubId, version])
  function retry() {
    setState({ loading: true, horses: [], records: [], historyLoading: true, historyErrors: [], stalls: null, stallError: false })
    setVersion(v => v + 1)
  }
  return { ...state, retry }
}

function HorseLink({ horse }) {
  return <Link className="vet-horse-link" to={`/vet/horses/${horse.id}`}><HorseAvatar horseId={horse.id} name={horse.name} size="small" /><span><strong>{horse.name}</strong><small>{formatHorseCode(horse.code)} · Microchip: {horse.microchipNumber || 'Chưa cập nhật'}</small></span></Link>
}

function DueList({ horses, records, filter = 'all', limit }) {
  const today = clubToday()
  const rows = horses.flatMap(horse => {
    const record = latestSigned(records, horse.id)
    return record?.followUpDate ? [{ horse, record, group: dueGroup(record.followUpDate, today) }] : []
  }).filter(row => filter === 'all' || row.group === filter).sort((a, b) => a.record.followUpDate.localeCompare(b.record.followUpDate)).slice(0, limit)
  return rows.length ? <div className="table-wrapper"><table className="horse-table"><thead><tr><th>Ngựa</th><th>Ngày tái khám</th><th>Mốc chỉ định</th><th>Bác sĩ chỉ định</th><th>Thao tác</th></tr></thead><tbody>{rows.map(({ horse, record, group }) => <tr key={horse.id}>
    <td><Link to={`/vet/horses/${horse.id}`}>{horse.name}</Link></td><td>{record.followUpDate}</td>
    <td><span className={`vet-pill due-${group}`}>{({ overdue: 'Đã qua ngày chỉ định', today: 'Hôm nay', upcoming: 'Sắp tới' })[group]}</span></td>
    <td>{record.vetName}</td><td><Link to={`/vet/horses/${horse.id}?tab=calendar`}>Xem chỉ định</Link></td>
  </tr>)}</tbody></table></div> : <p className="vet-empty">Không có chỉ định tái khám phù hợp trong bệnh án gần nhất.</p>
}

export default function VetWorkspace({ currentUser, mode = 'overview', initialExams = [] }) {
  const data = useVetData(currentUser.clubId)
  const [params, setParams] = useSearchParams()
  const search = params.get('q') || ''
  const health = params.get('health') || ''
  const training = params.get('training') || ''
  const due = params.get('due') || 'all'
  const [page, setPage] = useState(1)
  const herd = data.horses.filter(h => mode === 'intake-results'
    ? h.initialExamSigned && ['APPROVED', 'PENDING_EXAM'].includes(h.profileStatus)
    : h.profileStatus === 'APPROVED')
  const historyComplete = !data.historyLoading && !data.historyErrors.length
  const waitingForTrainingFilter = training && !historyComplete && ['herd', 'stalls', 'intake-results'].includes(mode)
  function filter(key, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
    setPage(1)
  }
  const filtered = herd.filter(h => (!health || h.healthStatus === health)
    && (!search || [h.name, h.code, h.microchipNumber].some(v => v?.toLocaleLowerCase().includes(search.toLocaleLowerCase().trim())))
    && (!training || (!data.historyErrors.includes(h.id) && !data.historyLoading && (training === 'limited'
      ? ['Restricted', 'Not Eligible'].includes(latestSigned(data.records, h.id)?.trainingEligibility)
      : latestSigned(data.records, h.id)?.trainingEligibility === training))))
  const titles = { overview: 'Tổng quan thú y', herd: 'Sức khỏe toàn đàn', 'intake-results': 'Kết quả khám đầu vào', stalls: 'Sơ đồ sức khỏe theo chuồng', calendar: 'Lịch y tế', reports: 'Báo cáo sức khỏe' }
  const currentPage = Math.min(page, Math.max(1, Math.ceil(filtered.length / 20)))
  const visible = filtered.slice((currentPage - 1) * 20, currentPage * 20)
  const healthFilters = <div className="filter-card vet-filters">
    <label className="search-field"><span>Tên, mã hoặc microchip</span><input type="search" value={search} onChange={e => filter('q', e.target.value)} placeholder="Tìm ngựa trong CLB…" /></label>
    <label className="filter-field"><span>Sức khỏe</span><select value={health} onChange={e => filter('health', e.target.value)}><option value="">Tất cả sức khỏe</option>{Object.entries(healthLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    <label className="filter-field"><span>Kết luận điều kiện tập</span><select value={training} disabled={!historyComplete} onChange={e => filter('training', e.target.value)}><option value="">Tất cả</option><option value="limited">Cấm hoặc hạn chế tập</option>{Object.entries(trainingLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    {mode === 'stalls' && <label className="filter-field"><span>Khu chuồng</span><select disabled><option>Chưa có thông tin phân khu</option></select></label>}
    <button className="clear-filter-button" type="button" onClick={() => { setParams({}); setPage(1) }}>Xóa bộ lọc</button>
  </div>
  return <main className="page-content vet-workspace">
    <header className="page-heading"><div><p className="eyebrow">EQUI · KHÔNG GIAN THÚ Y</p><h1>{titles[mode]}</h1><p>{mode === 'intake-results' ? 'Phiếu đã chốt cho lần đăng ký hiện tại · Bao gồm hồ sơ chờ Manager tiếp nhận' : 'Đàn ngựa đã tiếp nhận trong CLB'} · Giờ CLB: UTC+07:00</p></div><button className="button button-secondary" onClick={data.retry} disabled={data.loading}>Làm mới</button></header>
    {data.loading ? <section className="panel" role="status">Đang tải sức khỏe đàn ngựa…</section> : data.error ? <section className="panel" role="alert"><p>{data.error}</p><button className="button" onClick={data.retry}>Thử lại</button></section> : <>
      {data.historyErrors.length > 0 && <p className="error-message" role="alert">Không tải được bệnh án của {data.historyErrors.length} ngựa. Chưa thể tổng hợp điều kiện tập và tái khám. <button onClick={data.retry}>Thử lại</button></p>}
      {waitingForTrainingFilter ? <section className="panel" role="status"><p>{data.historyLoading ? 'Đang tải kết luận để lọc theo điều kiện tập…' : 'Chưa thể xác định danh sách phù hợp vì chưa tải đủ kết luận điều kiện tập.'}</p><button className="button button-secondary" onClick={() => filter('training', '')}>Bỏ lọc điều kiện tập</button></section> : <>
      {mode === 'overview' && <>
        <section className="vet-stats" aria-label="Bốn nhóm sức khỏe">{['ELIGIBLE', 'MONITORING', 'INJURED', 'ISOLATION'].map(key => <Link key={key} to={`/vet/herd?health=${key}`} className={`vet-stat health-${key}`}><span>{healthLabels[key]}</span><strong>{herd.filter(h => h.healthStatus === key).length}</strong><small>Xem danh sách →</small></Link>)}</section>
        <p className="vet-caption">“Đủ điều kiện” ở đây là sức khỏe Healthy; điều kiện tập được kết luận riêng. <Link to="/vet/herd">Toàn đàn: {herd.length}</Link> · <Link to="/vet/herd?health=RECOVERING">Hồi phục: {herd.filter(h => h.healthStatus === 'RECOVERING').length}</Link> · <Link to="/vet/herd?health=NOT_ASSESSED">Chưa đánh giá: {herd.filter(h => h.healthStatus === 'NOT_ASSESSED').length}</Link></p>
        <div className="vet-two-columns"><section className="panel"><h2>Cần xử lý</h2>
          <Link className="vet-task" to="/vet/horses-needing-exam"><span>Khám đầu vào<small>Vet trực tiếp nhận khám</small></span><strong>{initialExams.length} →</strong></Link>
          <Link className="vet-task" to="/vet/calendar?due=today"><span>Tái khám theo chỉ định hôm nay<small>Đối chiếu bệnh án trước khi xử lý</small></span><strong>{historyComplete ? herd.filter(h => latestSigned(data.records, h.id)?.followUpDate === clubToday()).length : 'Chưa có số liệu'} →</strong></Link>
          <Link className="vet-task" to="/vet/reports"><span>Báo cáo khẩn<small>Chưa khả dụng</small></span><span>→</span></Link>
          <Link className="vet-task" to="/vet/calendar?due=overdue"><span>Lịch y tế quá hạn<small>Chưa có dữ liệu lịch; xem mốc tái khám trên bệnh án</small></span><span>→</span></Link>
        </section><section className="panel"><h2>Điều kiện huấn luyện</h2><p>Kết luận từ bệnh án đã chốt gần nhất; chưa xác nhận khóa tập hiện hành.</p>
          {data.historyLoading ? <p role="status">Đang tải kết luận…</p> : historyComplete ? <><Link className="vet-task" to="/vet/herd?training=Not+Eligible">Không được tập <strong>{herd.filter(h => latestSigned(data.records, h.id)?.trainingEligibility === 'Not Eligible').length} →</strong></Link><Link className="vet-task" to="/vet/herd?training=Restricted">Hạn chế tập <strong>{herd.filter(h => latestSigned(data.records, h.id)?.trainingEligibility === 'Restricted').length} →</strong></Link></> : <p>Chưa có số liệu đầy đủ.</p>}
          <Unavailable title="Khóa tập hiện hành">Chưa thể tra cứu hoặc áp dụng khóa tập tại đây.</Unavailable>
        </section></div>
        <section className="panel"><h2>Hôm nay và sắp tới</h2><p>Ngày tái khám trên bệnh án gần nhất, chưa phải lịch đã đặt và chưa có trạng thái hoàn thành.</p>{historyComplete ? <><h3>Hôm nay</h3><DueList horses={herd} records={data.records} filter="today" limit={5} /><h3>Sắp tới · tối đa 5 mốc gần nhất</h3><DueList horses={herd} records={data.records} filter="upcoming" limit={5} /></> : <p>{data.historyLoading ? 'Đang tải chỉ định…' : 'Chưa có số liệu đầy đủ.'}</p>}<Link to="/vet/calendar">Xem các mốc tái khám →</Link></section>
      </>}
      {['herd', 'intake-results'].includes(mode) && <>{healthFilters}<section className="table-card"><div className="table-header"><h2>{filtered.length} ngựa phù hợp</h2></div><div className="table-wrapper"><table className="horse-table"><thead><tr><th>Ngựa</th><th>Sức khỏe</th><th>Điều kiện tập theo bệnh án</th><th>Ô chuồng</th>{mode === 'intake-results' && <th>Trạng thái tiếp nhận</th>}<th>Hồ sơ</th></tr></thead><tbody>{visible.map(h => <tr key={h.id}><td><HorseLink horse={h} /></td><td><HealthBadge status={h.healthStatus} /></td><td>{data.historyLoading ? 'Đang tải…' : data.historyErrors.includes(h.id) ? 'Không tải được kết luận' : <TrainingBadge record={latestSigned(data.records, h.id)} />}</td><td>{h.currentStall?.StallNumber || 'Chưa xếp chuồng'}</td>{mode === 'intake-results' && <td>{h.profileStatus === 'APPROVED' ? 'Đã tiếp nhận' : 'Chờ Manager xử lý'}</td>}<td><Link to={mode === 'intake-results' ? `/vet/horses/${h.id}/examination` : `/vet/horses/${h.id}`}>{mode === 'intake-results' ? 'Xem kết quả →' : 'Hồ sơ y tế →'}</Link></td></tr>)}</tbody></table></div>{!filtered.length && <p className="vet-empty">Không có ngựa phù hợp.</p>}
        {filtered.length > 20 && <nav className="pagination" aria-label="Phân trang đàn ngựa"><button className="page-button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Trước</button><span>Trang {currentPage} / {Math.ceil(filtered.length / 20)}</span><button className="page-button" disabled={currentPage * 20 >= filtered.length} onClick={() => setPage(currentPage + 1)}>Tiếp</button></nav>}</section></>}
      {mode === 'stalls' && <>{healthFilters}<p className="vet-caption">Lưới các ô chuồng, chưa có vị trí thực địa hoặc dữ liệu phân khu. Sức khỏe và điều kiện tập là hai thông tin riêng.</p><div className="vet-legend" aria-label="Chú giải sức khỏe">{Object.keys(healthLabels).map(key => <HealthBadge key={key} status={key} />)}</div>
        {data.stallError ? <section className="panel" role="alert"><p>Không tải được chuồng. Chưa thể xác định ô trống hoặc ngựa chưa xếp chuồng.</p><button className="button" onClick={data.retry}>Thử lại</button></section> : data.stalls === null ? <p role="status">Đang tải chuồng…</p> : <>
          <section className="panel"><h2>Các ô chuồng · Chưa phân khu</h2><div className="vet-stall-grid">{data.stalls.filter(stall => !stall.horseId ? !search && !health && !training : filtered.some(h => h.id === stall.horseId) || (!herd.some(h => h.id === stall.horseId) && !search && !health && !training)).map(stall => {
            const horse = data.horses.find(h => h.id === stall.horseId)
            return <article className="vet-stall" key={stall.id}><h3>Ô {stall.number}</h3><small>{stall.type}</small>{horse ? <><Link to={`/vet/horses/${horse.id}`}><strong>{horse.name}</strong><small>{formatHorseCode(horse.code)}</small></Link><HealthBadge status={horse.healthStatus} />{data.historyErrors.includes(horse.id) ? <small>Không tải được điều kiện tập</small> : <TrainingBadge record={latestSigned(data.records, horse.id)} />}</> : <p>{stall.horseId || stall.status === 'Occupied' ? 'Ô có ngựa · chưa đối chiếu được hồ sơ' : stall.status === 'Maintenance' ? 'Đang bảo trì' : stall.status === 'Available' ? 'Ô trống' : 'Chưa rõ trạng thái ô'}</p>}</article>
          })}</div>{!data.stalls.length && <p>Chưa có ô chuồng.</p>}</section>
          <section className="panel"><h2>Chưa xếp chuồng</h2><div className="vet-stall-grid">{filtered.filter(h => !h.currentStall && !data.stalls.some(s => s.horseId === h.id)).map(h => <article className="vet-stall" key={h.id}><HorseLink horse={h} /><HealthBadge status={h.healthStatus} /><TrainingBadge record={latestSigned(data.records, h.id)} /></article>)}</div>{!filtered.some(h => !h.currentStall && !data.stalls.some(s => s.horseId === h.id)) && <p>Không có ngựa chưa xếp chuồng phù hợp.</p>}</section>
        </>}
      </>}
      {mode === 'calendar' && <><Unavailable title="Lịch chăm sóc và nhắc việc" action="Đặt lịch y tế">Tiêm phòng, tẩy giun, chăm sóc móng và khám định kỳ chưa khả dụng. Chưa có nhắc việc tự động hoặc thao tác hoàn thành lịch.</Unavailable><section className="panel"><h2>Chỉ định tái khám từ bệnh án</h2><p>Chỉ lấy bệnh án đã chốt gần nhất của mỗi ngựa. Mốc ngày chưa xác nhận đã tái khám hay chưa; không tự tính chu kỳ tiếp theo.</p><label className="form-field"><span>Lọc ngày chỉ định</span><select value={due} onChange={e => filter('due', e.target.value)}><option value="all">Tất cả</option><option value="overdue">Đã qua ngày chỉ định</option><option value="today">Hôm nay</option><option value="upcoming">Sắp tới</option></select></label>{historyComplete ? <DueList horses={herd} records={data.records} filter={due} /> : <p>{data.historyLoading ? 'Đang tải…' : 'Chưa có số liệu đầy đủ.'}</p>}</section></>}
      {mode === 'reports' && <Unavailable title="Tiếp nhận báo cáo sức khỏe" action="Nhận xử lý báo cáo">Chưa thể tải báo cáo từ nhân sự chăm sóc và huấn luyện. Khi được hỗ trợ, báo cáo khẩn sẽ đến Vet trực tiếp, kèm ngựa, người báo, thời gian, ảnh và buổi tập liên quan. Hiện chưa thể nhận xử lý hoặc đóng báo cáo tại đây.</Unavailable>}
      </>}
    </>}
  </main>
}
