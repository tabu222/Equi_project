import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getProfileChangeRequests, reviewProfileChangeRequest } from '../../api/horseApi.ts'

const fieldLabels = {
  name: 'Horse name',
  breed: 'Breed',
  dateOfBirth: 'Date of birth',
  coatColor: 'Coat color',
  sex: 'Gender',
  sireName: 'Sire name',
  damName: 'Dam name',
  microchipNumber: 'Microchip number',
  registrationNumber: 'Passport number',
}

const statusLabels = {
  Pending: 'Chờ duyệt',
  Approved: 'Đã duyệt',
  Rejected: 'Đã từ chối',
}

function ProfileChangeRequests({ onHorseRefresh }) {
  const [requests, setRequests] = useState([])
  const [reviewNotes, setReviewNotes] = useState({})
  const [busyId, setBusyId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)

  const load = useCallback(async () => {
    try {
      const result = await getProfileChangeRequests()
      setRequests(result)
      setError('')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không thể tải yêu cầu sửa hồ sơ.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load, reloadCount])

  async function review(request, decision) {
    setBusyId(request.requestId)
    setError('')
    try {
      const saved = await reviewProfileChangeRequest(
        request.requestId,
        decision,
        reviewNotes[request.requestId] || '',
      )
      setRequests((current) => current.map((item) => item.requestId === saved.requestId ? saved : item))
      setReviewNotes((current) => ({ ...current, [request.requestId]: '' }))
      try {
        await onHorseRefresh(saved.horseId)
      } catch {
        setError('Đã xử lý yêu cầu nhưng không tải lại được hồ sơ ngựa. Hãy tải lại trang để xác nhận dữ liệu mới nhất.')
      }
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : 'Không thể xử lý yêu cầu.')
    } finally {
      setBusyId('')
    }
  }

  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải yêu cầu sửa hồ sơ...</section></main>

  return (
    <main className="page-content">
      <header className="page-heading">
        <div>
          <p className="eyebrow">ĐĂNG KÝ NGỰA</p>
          <h1>Yêu cầu sửa hồ sơ</h1>
          <p>Xem xét nội dung chủ ngựa đề nghị. Khi duyệt, trường được yêu cầu sẽ cập nhật vào hồ sơ.</p>
        </div>
      </header>
      {error && <section className="panel" role="alert"><p>{error}</p>{requests.length === 0 && <button className="button" type="button" onClick={() => { setLoading(true); setReloadCount((count) => count + 1) }}>Thử lại</button>}</section>}
      {requests.length === 0 ? (
        <section className="panel"><p>Chưa có yêu cầu sửa hồ sơ.</p></section>
      ) : (
        <div className="card-grid">
          {requests.map((request) => (
            <article className="panel" key={request.requestId}>
              <p className="profile-id">Request #{request.requestId} · {statusLabels[request.status] || request.status}</p>
              <h2>{request.horseName || `Horse #${request.horseId}`}</h2>
              <p>{fieldLabels[request.field] || 'Trường hồ sơ'}: <strong>{request.requestedValue || '—'}</strong></p>
              <p>Lý do của chủ ngựa: {request.reason || '—'}</p>
              {request.rejectionReason && <p>Ghi chú xử lý: {request.rejectionReason}</p>}
              {request.createdAt && <p><small>Gửi lúc {new Date(request.createdAt).toLocaleString()}</small></p>}
              <p><Link to={`/manager/horses/${request.horseId}/intake`}>Mở hồ sơ tiếp nhận</Link></p>
              {request.status === 'Pending' && (
                <>
                  <label className="form-field">
                    <span>Ghi chú xử lý (bắt buộc khi từ chối)</span>
                    <textarea
                      rows="3"
                      value={reviewNotes[request.requestId] || ''}
                      onChange={(event) => setReviewNotes((current) => ({ ...current, [request.requestId]: event.target.value }))}
                    />
                  </label>
                  <div className="form-actions-inline">
                    <button className="button" type="button" disabled={busyId !== ''} onClick={() => void review(request, 'approve')}>
                      {busyId === request.requestId ? 'Đang lưu...' : 'Duyệt'}
                    </button>
                    <button
                      className="button button-secondary"
                      type="button"
                      disabled={busyId !== '' || !reviewNotes[request.requestId]?.trim()}
                      onClick={() => void review(request, 'reject')}
                    >
                      Từ chối
                    </button>
                  </div>
                </>
              )}
            </article>
          ))}
        </div>
      )}
    </main>
  )
}

export default ProfileChangeRequests
