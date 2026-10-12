import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'

const fields = [['name', 'Tên ngựa'], ['breed', 'Giống'], ['dateOfBirth', 'Ngày sinh'], ['coatColor', 'Màu lông'], ['sex', 'Giới tính']]
const labels = { Pending: 'Chờ xử lý', Approved: 'Đã chấp nhận', Rejected: 'Bị từ chối' }

function OwnerCorrectionRequest({ horses, requests = [], onSubmitRequest, currentUser }) {
  const { horseId } = useParams()
  const horse = horses.find((item) => String(item.id) === String(horseId) && String(item.ownerUserId) === String(currentUser?.id))
  const [field, setField] = useState('')
  const [requestedValue, setRequestedValue] = useState('')
  const [reason, setReason] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const history = requests.filter((item) => String(item.horseId) === String(horseId))
  if (!horse) return <main className="page-content"><section className="panel"><h1>Không tìm thấy ngựa</h1><Link to="/owner/horses">Quay lại danh sách ngựa</Link></section></main>

  async function submit(event) {
    event.preventDefault(); setSaving(true); setError(''); setSubmitted(false)
    try { await onSubmitRequest({ ownerId: currentUser.id, horseId: horse.id, field, requestedValue, reason }); setSubmitted(true) }
    catch (submitError) { setError(submitError.message || 'Không thể gửi yêu cầu.') }
    finally { setSaving(false) }
  }

  return <main className="page-content">
    <div className="breadcrumb"><Link to={`/owner/horses/${horse.id}`}>Hồ sơ và sức khỏe</Link><span aria-hidden="true">/</span><span>Yêu cầu hiệu chỉnh lý lịch</span></div>
    <header className="page-heading"><div><p className="eyebrow">CHỦ SỞ HỮU NGỰA · HIỆU CHỈNH LÝ LỊCH</p><h1>Yêu cầu hiệu chỉnh lý lịch</h1><p>Gửi thông tin cần sửa để câu lạc bộ xem xét.</p></div></header>
    <section className="horse-context-card"><div><h2>{horse.name}</h2><p>Mã ngựa #{horse.code || horse.id} · {horse.breed}</p></div><StatusBadge status={horse.profileStatus} type="registration" /></section>
    <section className="panel form-panel">
      {submitted && <p className="success-message" role="status">Yêu cầu đã được gửi đến câu lạc bộ.</p>}{error && <p className="error-message" role="alert">{error}</p>}
      <form onSubmit={submit}>
        <label className="form-field"><span>Thông tin cần sửa</span><select required value={field} onChange={(event) => setField(event.target.value)}><option value="">Chọn thông tin</option>{fields.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        {field && <div className="current-value"><span>Giá trị hiện tại</span><strong>{horse[field] || 'Chưa có thông tin'}</strong></div>}
        <label className="form-field"><span>Giá trị đề nghị</span><input required maxLength={200} value={requestedValue} onChange={(event) => setRequestedValue(event.target.value)} /></label>
        <label className="form-field"><span>Lý do</span><textarea required rows="3" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <p className="profile-copy">Tải bằng chứng lên chưa được API hiện tại hỗ trợ.</p>
        <div className="form-actions"><button className="button" type="submit" disabled={saving}>{saving ? 'Đang gửi...' : 'Gửi yêu cầu hiệu chỉnh'}</button><Link className="button button-secondary" to={`/owner/horses/${horse.id}`}>Hủy</Link></div>
      </form>
    </section>
    <section className="panel request-history"><div className="section-title"><h2>Trạng thái yêu cầu</h2></div>
      {!history.length ? <EmptyState title="Bạn chưa có yêu cầu hiệu chỉnh nào" description="Các yêu cầu đã gửi sẽ hiển thị tại đây." /> : <div className="request-list">{history.map((request) => <article className="request-item" key={request.requestId}><div className="request-item-heading"><div><strong>{fields.find(([key]) => key === request.field)?.[1] || 'Thông tin hồ sơ'}</strong><small>{request.createdAt}</small></div><StatusBadge status={request.status} type="request" label={labels[request.status] || request.status} /></div><p className="request-value">Giá trị đề nghị: {request.requestedValue}</p>{request.status === 'Rejected' && request.rejectionReason && <p>{request.rejectionReason}</p>}</article>)}</div>}
    </section>
  </main>
}

export default OwnerCorrectionRequest
