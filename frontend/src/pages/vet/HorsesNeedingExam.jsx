import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import { isHorseAssignedToVet } from '../../api/horseApi'

const examStatusLabels = { PENDING: 'Chờ khám', COMPLETED: 'Đã khám' }

function HorsesNeedingExam({ horses, currentUser, owners = [] }) {
  const [statusFilter, setStatusFilter] = useState('All')
  const assignedHorses = useMemo(
    () => horses.filter((horse) => isHorseAssignedToVet(horse, currentUser)),
    [horses, currentUser],
  )

  const tableRows = useMemo(
    () => assignedHorses.filter((horse) => statusFilter === 'All' || String(horse.intake?.examinationStatus ?? 'PENDING') === statusFilter),
    [assignedHorses, statusFilter],
  )

  return (
    <main className="page-content">
      <nav className="breadcrumb" aria-label="Đường dẫn">Hồ sơ khám <span aria-hidden="true">/</span> Ngựa cần khám</nav>
      <header className="page-heading"><div><p className="eyebrow">BÁC SĨ THÚ Y · HỒ SƠ KHÁM</p><h1>Ngựa cần khám</h1><p>Theo dõi ngựa và yêu cầu khám được phân công.</p></div></header>
      <section className="filter-card exam-filter-card"><label className="filter-field" htmlFor="exam-status-filter"><span>Trạng thái khám</span><select id="exam-status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="All">Tất cả</option><option value="PENDING">Chờ khám</option><option value="COMPLETED">Đã khám</option></select></label></section>
      {tableRows.length === 0 ? <EmptyState title="Không có ngựa cần khám trong trạng thái đã chọn" description="Chọn trạng thái khác để xem các hồ sơ được phân công." /> : (
        <div className="table-card"><div className="table-wrap"><table className="data-table"><thead><tr><th scope="col">Mã ngựa</th><th scope="col">Tên ngựa</th><th scope="col">Chủ sở hữu</th><th scope="col">Trạng thái khám</th><th scope="col">Cập nhật</th><th scope="col">Thao tác</th></tr></thead>
          <tbody>{tableRows.map((horse) => <tr key={horse.id}><td>#{horse.code || horse.id}</td><td><strong>{horse.name}</strong><small>{horse.breed}</small></td><td>{owners.find((owner) => String(owner.ownerId) === String(horse.ownerUserId))?.fullName || `#${horse.ownerUserId}`}</td><td><StatusBadge status={horse.intake?.examinationStatus || 'PENDING'} label={examStatusLabels[horse.intake?.examinationStatus || 'PENDING']} type="exam" /></td><td>{horse.updatedAt}</td><td className="row-actions"><Link to={`/vet/horses/${horse.id}`}>Mở hồ sơ</Link></td></tr>)}</tbody>
        </table></div></div>
      )}
    </main>
  )
}

export default HorsesNeedingExam
