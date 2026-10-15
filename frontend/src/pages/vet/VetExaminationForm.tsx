import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from '../../components/common/StatusBadge.jsx';
import type { ExaminationInput, MedicalRecord } from '../../api/horseApi.ts';
import type { Horse, User } from '../../types';

interface VetExaminationFormProps {
  horse: Horse;
  currentUser: User;
  draft?: MedicalRecord;
  signedRecord?: MedicalRecord;
  onSaveDraft: (horseId: string, input: ExaminationInput, draftId?: string) => Promise<MedicalRecord>;
  onSign: (recordId: string) => Promise<MedicalRecord>;
  onAfterSign: () => Promise<void>;
}

const profileStatusLabels: Partial<Record<Horse['profileStatus'], string>> = {
  PENDING_EXAM: 'Chờ xử lý sau khám',
  APPROVED: 'Đã tiếp nhận',
  REJECTED: 'Bị từ chối',
  SUBMITTED: 'Chờ xác minh',
  DRAFT: 'Nháp',
  ARCHIVED: 'Lưu trữ',
};

function initialInput(draft?: MedicalRecord): ExaminationInput {
  return {
    examDate: draft?.examDate?.slice(0, 10) || new Date().toISOString().slice(0, 10),
    weightKg: draft?.weightKg,
    heightCm: draft?.heightCm,
    symptoms: draft?.symptoms || '',
    diagnosis: draft?.diagnosis || '',
    treatmentPlan: draft?.treatmentPlan || '',
    conclusion: draft?.conclusion || '',
    healthStatus: draft?.healthStatus || '',
    trainingEligibility: draft?.trainingEligibility || '',
    restrictionNote: draft?.restrictionNote || '',
    followUpDate: draft?.followUpDate || '',
  };
}

function VetExaminationForm({ horse, currentUser, draft, signedRecord, onSaveDraft, onSign, onAfterSign }: VetExaminationFormProps) {
  const [form, setForm] = useState<ExaminationInput>(() => initialInput(draft));
  const [draftId, setDraftId] = useState(draft?.id);
  const [justSignedRecord, setJustSignedRecord] = useState<MedicalRecord>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [refreshWarning, setRefreshWarning] = useState('');
  const ownsDraft = !draft || draft.vetId === currentUser.id;
  const profilePath = `/vet/horses/${horse.id}`;
  const currentSignedRecord = signedRecord || justSignedRecord;

  function updateField<K extends keyof ExaminationInput>(key: K, value: ExaminationInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  if (currentSignedRecord) {
    const managerStatus = horse.profileStatus === 'PENDING_EXAM'
      ? 'Đã chốt phiếu khám, chờ Manager xử lý.'
      : `Phiếu đã ký. Trạng thái hồ sơ hiện tại: ${profileStatusLabels[horse.profileStatus] || horse.profileStatus}.`;
    return <main className="page-content narrow-content">
      <div className="breadcrumb"><Link to="/vet/horses-needing-exam">Hàng đợi khám</Link><span aria-hidden="true">/</span><span>Phiếu khám đã ký</span></div>
      <section className="panel">
        <p className="eyebrow">BÁC SĨ THÚ Y · KHÁM ĐẦU VÀO</p>
        <h1>{horse.name}</h1>
        <p className="success-message" role="status">{managerStatus}</p>
        {refreshWarning && <p className="profile-copy" role="note">{refreshWarning}</p>}
        <div className="intake-vet-conclusion">
          <h2>Phiếu khám #{currentSignedRecord.id} · Đã ký</h2>
          <p>Trạng thái hồ sơ: {profileStatusLabels[horse.profileStatus] || horse.profileStatus} ({horse.profileStatus})</p>
          <p>Kết luận: {currentSignedRecord.conclusion || '—'}</p>
          <p>HealthStatus: {currentSignedRecord.healthStatus || '—'} · TrainingEligibility: {currentSignedRecord.trainingEligibility || '—'}</p>
          {currentSignedRecord.signedAt && <p>Thời điểm ký: {currentSignedRecord.signedAt}</p>}
        </div>
        <div className="form-actions"><Link className="button" to="/vet/horses-needing-exam">Quay về danh sách khám</Link><Link className="button button-secondary" to={profilePath}>Xem hồ sơ ngựa</Link></div>
      </section>
    </main>;
  }

  if (horse.profileStatus !== 'PENDING_EXAM' || horse.initialExamSigned !== false) {
    return <main className="page-content"><section className="panel">
      <h1>{horse.profileStatus === 'PENDING_EXAM' ? 'Chưa xác định được phiếu khám hiện tại' : 'Hồ sơ không còn chờ khám đầu vào'}</h1>
      <p>{horse.profileStatus !== 'PENDING_EXAM'
        ? `Trạng thái hồ sơ hiện tại là ${horse.profileStatus}; không thể tiếp tục khám đầu vào.`
        : horse.initialExamSigned === true
          ? 'Lần đăng ký hiện tại đã có phiếu khám được ký nhưng không tìm thấy phiếu phù hợp. Không thể tạo hoặc ký thêm phiếu.'
          : 'Không xác định được trạng thái phiếu khám hiện tại. Không thể tiếp tục khám đầu vào.'}</p>
      <Link className="button" to="/vet/horses-needing-exam">Quay lại hàng đợi</Link>
    </section></main>;
  }

  async function saveDraft(): Promise<MedicalRecord> {
    const result = await onSaveDraft(horse.id, {
      ...form,
      symptoms: form.symptoms.trim(),
      diagnosis: form.diagnosis.trim(),
      treatmentPlan: form.treatmentPlan.trim(),
      conclusion: form.conclusion.trim(),
      restrictionNote: form.restrictionNote.trim(),
    }, draftId);
    setDraftId(result.id);
    return result;
  }

  async function handleSaveDraft() {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await saveDraft();
      setMessage('Đã lưu phiếu khám nháp.');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Không thể lưu phiếu khám nháp.');
    } finally {
      setSaving(false);
    }
  }

  async function handleSign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.healthStatus || !form.trainingEligibility) {
      setError('Cần chọn HealthStatus và TrainingEligibility trước khi chốt phiếu.');
      return;
    }
    if (form.trainingEligibility === 'Restricted' && !form.restrictionNote.trim()) {
      setError('Cần ghi rõ RestrictionNote khi TrainingEligibility là Restricted.');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const savedDraft = await saveDraft();
      const signed = await onSign(savedDraft.id);
      setJustSignedRecord(signed);
      setMessage('Đã chốt phiếu khám, chờ Manager xử lý.');
    } catch (signError) {
      setError(signError instanceof Error ? signError.message : 'Không thể chốt phiếu khám.');
      setSaving(false);
      return;
    }
    try {
      await onAfterSign();
    } catch (refreshError) {
      setRefreshWarning(refreshError instanceof Error ? refreshError.message : 'Phiếu đã chốt nhưng không thể tải lại dữ liệu mới nhất.')
    } finally {
      setSaving(false);
    }
  }

  if (!ownsDraft) {
    return <main className="page-content"><section className="panel">
      <h1>Phiếu khám đang do Vet khác xử lý</h1>
      <p>Phiếu nháp #{draft?.id} do {draft?.vetName || `Vet #${draft?.vetId}`} lập. Chỉ người lập phiếu mới có thể tiếp tục chỉnh sửa hoặc chốt phiếu.</p>
      <Link className="button" to="/vet/horses-needing-exam">Quay lại hàng đợi</Link>
    </section></main>;
  }

  return (
    <main className="page-content narrow-content">
      <div className="breadcrumb"><Link to={profilePath}>Hồ sơ ngựa</Link><span aria-hidden="true">/</span><span>Khám đầu vào</span></div>
      <header className="page-heading">
        <div><p className="eyebrow">BÁC SĨ THÚ Y · KHÁM ĐẦU VÀO</p><h1>{horse.name}</h1><p>Mã ngựa #{horse.id} · {horse.breed} · Chủ sở hữu: {horse.ownerName || 'Chưa có thông tin'}</p></div>
      </header>
      <section className="horse-context-card">
        <div><h2>{horse.name}</h2><p>Trạng thái hồ sơ: {horse.profileStatus === 'PENDING_EXAM' ? 'PendingExam' : horse.profileStatus}</p></div>
        <StatusBadge status={horse.healthStatus} label={horse.healthStatus} type="health" />
      </section>
      {draft && <p className="profile-copy">Đang tiếp tục phiếu nháp #{draft.id} do bạn lập.</p>}
      {error && <div className="alert-banner" role="alert" style={{ marginTop: 16, background: '#fff4f4', color: '#7a1d1d', border: '1px solid #f7c2c2', borderRadius: 8, padding: '10px 12px' }}>{error}</div>}
      {message && <p className="success-message" role="status">{message}</p>}
      <section className="panel form-panel post-exam-form-panel">
        <h2>Phiếu khám đầu vào</h2>
        <form onSubmit={handleSign}>
          <label className="form-field"><span>Ngày khám</span><input type="date" value={form.examDate} onChange={(event) => updateField('examDate', event.target.value)} /></label>
          <div className="horse-form-grid">
            <label className="form-field"><span>Cân nặng (kg)</span><input type="number" min="0.1" step="0.1" value={form.weightKg ?? ''} onChange={(event) => updateField('weightKg', event.target.value ? Number(event.target.value) : undefined)} /></label>
            <label className="form-field"><span>Chiều cao (cm)</span><input type="number" min="0.1" step="0.1" value={form.heightCm ?? ''} onChange={(event) => updateField('heightCm', event.target.value ? Number(event.target.value) : undefined)} /></label>
          </div>
          <label className="form-field"><span>Triệu chứng</span><textarea rows={3} value={form.symptoms} onChange={(event) => updateField('symptoms', event.target.value)} /></label>
          <label className="form-field"><span>Chẩn đoán</span><textarea rows={3} value={form.diagnosis} onChange={(event) => updateField('diagnosis', event.target.value)} /></label>
          <label className="form-field"><span>Xử trí</span><textarea rows={3} value={form.treatmentPlan} onChange={(event) => updateField('treatmentPlan', event.target.value)} /></label>
          <label className="form-field"><span>Kết luận</span><textarea rows={3} required value={form.conclusion} onChange={(event) => updateField('conclusion', event.target.value)} /></label>
          <div className="horse-form-grid">
            <label className="form-field"><span>HealthStatus</span><select required value={form.healthStatus} onChange={(event) => updateField('healthStatus', event.target.value)}><option value="">Chọn tình trạng sức khỏe</option><option value="Healthy">Khỏe mạnh</option><option value="Monitor">Theo dõi</option><option value="Injured">Chấn thương</option><option value="Recovering">Đang hồi phục</option><option value="Isolated">Cách ly</option></select></label>
            <label className="form-field"><span>TrainingEligibility</span><select required value={form.trainingEligibility} onChange={(event) => updateField('trainingEligibility', event.target.value)}><option value="">Chọn điều kiện tập</option><option value="Eligible">Đủ điều kiện</option><option value="Restricted">Hạn chế</option><option value="Not Eligible">Không đủ điều kiện</option></select></label>
          </div>
          <label className="form-field"><span>Hạn chế tập (bắt buộc nếu chọn Restricted)</span><textarea rows={2} value={form.restrictionNote} onChange={(event) => updateField('restrictionNote', event.target.value)} /></label>
          <label className="form-field"><span>Ngày tái khám</span><input type="date" value={form.followUpDate} onChange={(event) => updateField('followUpDate', event.target.value)} /></label>
          <div className="form-actions">
            <button className="button button-secondary" type="button" disabled={saving} onClick={() => void handleSaveDraft()}>{saving ? 'Đang lưu...' : 'Lưu nháp'}</button>
            <button className="button" type="submit" disabled={saving}>{saving ? 'Đang chốt...' : 'Chốt phiếu khám'}</button>
            <Link className="button button-secondary" to={profilePath}>Quay lại hồ sơ</Link>
          </div>
        </form>
      </section>
    </main>
  );
}

export default VetExaminationForm;
