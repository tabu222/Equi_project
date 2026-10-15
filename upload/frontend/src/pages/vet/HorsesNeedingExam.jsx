import { Link } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'

function HorsesNeedingExam({ initialExams = [], loadError, onRetry }) {
  return (
    <main className="page-content">
      <nav className="breadcrumb" aria-label="Đường dẫn">Hồ sơ khám <span aria-hidden="true">/</span> Ngựa cần khám</nav>
      <header className="page-heading"><div><p className="eyebrow">BÁC SĨ THÚ Y · HỒ SƠ KHÁM</p><h1>Hàng đợi khám đầu vào</h1></div></header>
      {loadError && <section className="panel" role="alert"><p>{loadError}</p><button className="button" type="button" onClick={onRetry}>Tải lại</button></section>}
      {!loadError && initialExams.length === 0 ? (
        <EmptyState title="Không có hồ sơ chờ khám" description="Các hồ sơ cần khám sẽ hiển thị tại đây." />
      ) : !loadError && (
        <div className="table-card"><div className="table-wrap"><table className="data-table"><thead><tr><th scope="col">Mã hồ sơ</th><th scope="col">Tên ngựa</th><th scope="col">Giống</th><th scope="col">Microchip</th><th scope="col">Thời gian chờ</th><th scope="col">Phiếu nháp</th><th scope="col">Thao tác</th></tr></thead>
          <tbody>{initialExams.map(({ horse, requestDate, waitingHours, draftMedicalRecordId }) => <tr key={horse.id}>
            <td>#{horse.id}</td><td><strong>{horse.name}</strong></td><td>{horse.breed || '—'}</td><td>{horse.microchipNumber || '—'}</td>
            <td>{requestDate || '—'}{typeof waitingHours === 'number' && ` · ${waitingHours} giờ`}</td>
            <td>{draftMedicalRecordId ? <StatusBadge status="DRAFT" label={`Nháp #${draftMedicalRecordId}`} /> : 'Chưa lập'}</td>
            <td className="row-actions"><Link to={`/vet/horses/${horse.id}/examination`}>{draftMedicalRecordId ? 'Mở phiếu khám' : 'Bắt đầu khám'}</Link></td>
          </tr>)}</tbody>
        </table></div></div>
      )}
    </main>
  )
}

export default HorsesNeedingExam
