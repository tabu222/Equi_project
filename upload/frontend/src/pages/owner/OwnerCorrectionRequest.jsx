import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { requestProfileChange } from '../../api/horseApi';
import './OwnerCorrectionRequest.css';

const editableFields = [
  ['name', 'Tên ngựa', 'text'],
  ['breed', 'Giống', 'text'],
  ['dateOfBirth', 'Ngày sinh', 'date'],
  ['coatColor', 'Màu lông', 'text'],
  ['sex', 'Giới tính', 'select'],
  ['sireName', 'Tên ngựa cha', 'text'],
  ['damName', 'Tên ngựa mẹ', 'text'],
  ['microchipNumber', 'Số microchip', 'text'],
  ['registrationNumber', 'Số hộ chiếu', 'text'],
];

const statusLabels = {
  Pending: 'Chờ duyệt',
  Approved: 'Đã duyệt',
  Rejected: 'Đã từ chối',
};

function currentFieldValue(horse, field) {
  const value = horse[field];
  if (field === 'sex') {
    return ({ Male: 'MALE', Female: 'FEMALE', Gelding: 'GELDING' })[value] || value || '';
  }
  return value == null ? '' : String(value).slice(0, field === 'dateOfBirth' ? 10 : undefined);
}

export default function OwnerCorrectionRequest({ horse, requests = [], onSubmitted }) {
  const { horseId } = useParams();
  const navigate = useNavigate();
  const [field, setField] = useState(editableFields[0][0]);
  const [requestedValue, setRequestedValue] = useState('');
  const [reason, setReason] = useState('');
  const [evidenceDocumentId, setEvidenceDocumentId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!horse) return <p className="correction-page__error">Không tìm thấy hồ sơ ngựa.</p>;

  const isApproved = horse.profileStatus === 'APPROVED';
  const pendingRequest = requests.some((request) => request.status === 'Pending');

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      const saved = await requestProfileChange(
        horseId,
        field,
        requestedValue,
        reason,
        evidenceDocumentId ? Number(evidenceDocumentId) : undefined,
      );
      onSubmitted?.(saved);
      setSuccess('Yêu cầu sửa hồ sơ đã được gửi.');
      setRequestedValue('');
      setReason('');
      setEvidenceDocumentId('');
    } catch (requestError) {
      setError(requestError.message || 'Không thể gửi yêu cầu sửa hồ sơ.');
    } finally {
      setSubmitting(false);
    }
  }

  const selectedField = editableFields.find(([key]) => key === field);

  return (
    <section className="correction-page">
      <header className="correction-page__header">
        <button type="button" className="correction-page__back" onClick={() => navigate(-1)}>
          ← Quay lại
        </button>
        <div>
          <p className="correction-page__eyebrow">Hồ sơ ngựa</p>
          <h1>Yêu cầu sửa hồ sơ</h1>
          <p className="correction-page__subtitle">
            Gửi yêu cầu thay đổi thông tin của {horse.name}. Quản lý cần duyệt trước khi hồ sơ được cập nhật.
          </p>
        </div>
      </header>

      {!isApproved && (
        <p className="correction-page__notice">
          Chỉ có thể yêu cầu sửa hồ sơ ngựa đã được tiếp nhận.
        </p>
      )}
      {pendingRequest && (
        <p className="correction-page__notice">
          Ngựa này đã có yêu cầu đang chờ duyệt.
        </p>
      )}
      {error && <p className="correction-page__error" role="alert">{error}</p>}
      {success && <p className="correction-page__success" role="status">{success}</p>}

      <form className="correction-form" onSubmit={handleSubmit}>
        <label>
          Trường cần thay đổi
          <select value={field} onChange={(event) => setField(event.target.value)}>
            {editableFields.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>
        <label>
          Giá trị hiện tại
          <input readOnly value={currentFieldValue(horse, field)} />
        </label>
        <label>
          Giá trị đề nghị
          {selectedField?.[2] === 'select' ? (
            <select required value={requestedValue} onChange={(event) => setRequestedValue(event.target.value)}>
              <option value="">Chọn giới tính</option>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
              <option value="GELDING">Gelding</option>
            </select>
          ) : (
            <input
              required
              type={selectedField?.[2] || 'text'}
              value={requestedValue}
              onChange={(event) => setRequestedValue(event.target.value)}
            />
          )}
        </label>
        <label>
          Lý do thay đổi
          <textarea required rows="4" value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        <label>
          Mã tài liệu bằng chứng (không bắt buộc)
          <input
            type="number"
            min="1"
            value={evidenceDocumentId}
            onChange={(event) => setEvidenceDocumentId(event.target.value)}
          />
        </label>
        <div className="correction-form__actions">
          <Link to={`/owner/horses/${horseId}`}>Hủy</Link>
          <button type="submit" disabled={!isApproved || pendingRequest || submitting}>
            {submitting ? 'Đang gửi...' : 'Gửi yêu cầu'}
          </button>
        </div>
      </form>

      <section className="correction-history">
        <h2>Lịch sử yêu cầu</h2>
        {!requests.length ? (
          <p>Chưa có yêu cầu sửa hồ sơ.</p>
        ) : requests.map((request) => (
          <article className="correction-history__item" key={request.requestId}>
            <div className="correction-history__top">
              <strong>{editableFields.find(([key]) => key === request.field)?.[1] || 'Trường hồ sơ'}</strong>
              <span className={`correction-history__status correction-history__status--${request.status.toLowerCase()}`}>
                {statusLabels[request.status] || request.status}
              </span>
            </div>
            <p>Giá trị đề nghị: {request.requestedValue || '—'}</p>
            <p>Lý do: {request.reason || '—'}</p>
            {request.rejectionReason && <p>Ghi chú xử lý: {request.rejectionReason}</p>}
            {request.createdAt && <small>{new Date(request.createdAt).toLocaleString()}</small>}
          </article>
        ))}
      </section>
    </section>
  );
}
