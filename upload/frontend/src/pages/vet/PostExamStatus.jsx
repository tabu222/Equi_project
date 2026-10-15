import { Link } from 'react-router-dom'
import StatusBadge from '../../components/common/StatusBadge.jsx'

function PostExamStatus({ horse, owner, exam, viewerRole }) {
  const profilePath = viewerRole === 'owner' ? `/owner/horses/${horse?.id}` : `/horses/${horse?.id}`

  if (!horse) {
    return <main className="page-content"><section className="panel"><h1>{viewerRole === 'owner' ? 'Không tìm thấy hồ sơ thuộc quyền sở hữu của bạn' : 'Không tìm thấy ngựa'}</h1><Link to={viewerRole === 'owner' ? '/owner/horses' : '/manager/horses'}>Quay lại</Link></section></main>
  }

  return (
    <main className="page-content narrow-content">
      <div className="breadcrumb"><Link to={profilePath}>Hồ sơ ngựa</Link><span aria-hidden="true">/</span><span>Trạng thái sức khỏe</span></div>
      <header className="page-heading"><div><p className="eyebrow">{viewerRole === 'owner' ? 'CHỦ SỞ HỮU NGỰA' : 'QUẢN LÝ CÂU LẠC BỘ'} · TRẠNG THÁI SỨC KHỎE</p><h1>{horse.name}</h1><p>Mã ngựa #{horse.code || horse.id} · {horse.breed} · Chủ sở hữu: {owner?.fullName || 'Chưa có thông tin'}</p></div></header>
      <section className="horse-context-card"><div><h2>{horse.name}</h2><p>Mã ngựa #{horse.code || horse.id} · {exam ? `Yêu cầu khám ${exam.examId}` : 'Tóm tắt hồ sơ'}</p></div><StatusBadge status={horse.profileStatus} type="registration" /></section>
      <div className="post-exam-status-grid">
        <section className="panel"><span className="eyebrow">TRẠNG THÁI HỒ SƠ</span><StatusBadge status={horse.profileStatus} type="registration" /></section>
        <section className="panel"><span className="eyebrow">TRẠNG THÁI SỨC KHỎE</span><StatusBadge status={horse.healthStatus} type="health" /></section>
      </div>
      <section className="panel latest-update-panel"><div className="section-title"><h2>Cập nhật gần nhất</h2></div><strong>{horse.updatedAt || 'Chưa có thông tin'}</strong></section>
      <section className="panel role-summary-panel"><div className="section-title"><h2>Thông tin sức khỏe</h2></div><p>{viewerRole === 'owner' ? 'Tình trạng sức khỏe hiện tại của ngựa thuộc sở hữu của bạn.' : 'Thông tin trạng thái phục vụ theo dõi hồ sơ câu lạc bộ.'}</p></section>
      <Link className="button button-secondary" to={profilePath}>Quay lại hồ sơ</Link>
    </main>
  )
}

export default PostExamStatus
