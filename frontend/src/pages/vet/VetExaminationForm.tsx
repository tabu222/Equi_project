import { vetDateTime } from './vetDomain.js'
import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from '../../components/common/StatusBadge.jsx';
import type { ExaminationInput, MedicalRecord } from '../../api/horseApi.ts';
import type { Horse, User } from '../../types';
import { ApiError } from '../../api/apiClient.ts';
import { clubDateTimeInput, healthLabels, recordHealthLabels, trainingLabels, vetError } from './vetDomain.js';
import { formatHorseCode } from '../../components/horse/horseDisplay.js';

interface VetExaminationFormProps {
  horse: Horse;
  currentUser: User;
  draft?: MedicalRecord;
  signedRecord?: MedicalRecord;
  onSaveDraft: (horseId: string, input: ExaminationInput, draftId?: string) => Promise<MedicalRecord>;
  onSign: (recordId: string) => Promise<MedicalRecord>;
  onAfterSign: () => Promise<void>;
  onConflict: () => Promise<void>;
  conflictNotice?: string;
}

const profileStatusLabels: Partial<Record<Horse['profileStatus'], string>> = {
  PENDING_EXAM: 'Chờ khám / xử lý tiếp nhận',
  APPROVED: 'Đã tiếp nhận',
  REJECTED: 'Bị từ chối',
  SUBMITTED: 'Chờ xác minh',
  DRAFT: 'Nháp',
  ARCHIVED: 'Lưu trữ',
};

function initialInput(draft?: MedicalRecord): ExaminationInput {
  return {
    examDate: clubDateTimeInput(draft?.examDate),
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
    injuryLocation: draft?.injuryLocation || '',
    note: draft?.note || '',
  };
}

function VetExaminationForm({ horse, currentUser, draft, signedRecord, onSaveDraft, onSign, onAfterSign, onConflict, conflictNotice }: VetExaminationFormProps) {
  const [form, setForm] = useState<ExaminationInput>(() => initialInput(draft));
  const [draftId, setDraftId] = useState(draft?.id);
  const [justSignedRecord, setJustSignedRecord] = useState<MedicalRecord>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [refreshWarning, setRefreshWarning] = useState('');
  const submitting = useRef(false);
  const [blocked, setBlocked] = useState(false);
  const ownsDraft = !draft || draft.vetId === currentUser.id;
  const profilePath = `/vet/horses/${horse.id}`;
  const currentSignedRecord = signedRecord || justSignedRecord;

  function updateField<K extends keyof ExaminationInput>(key: K, value: ExaminationInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  if (currentSignedRecord) {
    const managerStatus = horse.profileStatus === 'PENDING_EXAM'
      ? 'Đã chốt phiếu khám, chờ Manager xử lý.'
      : `Phiếu đã chốt. Trạng thái hồ sơ hiện tại: ${profileStatusLabels[horse.profileStatus] || horse.profileStatus}.`;
    return <main className="page-content narrow-content">
      <div className="breadcrumb"><Link to="/vet/horses-needing-exam">Hàng đợi khám</Link><span aria-hidden="true">/</span><span>Phiếu khám đã chốt</span></div>
      <section className="panel">
        <p className="eyebrow">BÁC SĨ THÚ Y · KHÁM ĐẦU VÀO</p>
        <h1>{horse.name}</h1>
        <p className="success-message" role="status">{managerStatus}</p>
        {conflictNotice && <p className="error-message" role="alert">{conflictNotice}</p>}
        {refreshWarning && <p className="profile-copy" role="note">{refreshWarning}</p>}
        <div className="intake-vet-conclusion">
          <h2>Phiếu khám #{currentSignedRecord.id} · Đã chốt</h2>
          <p>Trạng thái hồ sơ: {profileStatusLabels[horse.profileStatus] || horse.profileStatus} ({horse.profileStatus})</p>
          <p>Kết luận: {currentSignedRecord.conclusion || '—'}</p>
          <p>Sức khỏe: {recordHealthLabels[currentSignedRecord.healthStatus as keyof typeof recordHealthLabels] || 'Chưa ghi'} · Điều kiện tập: {trainingLabels[currentSignedRecord.trainingEligibility as keyof typeof trainingLabels] || 'Chưa ghi'}</p>
          {currentSignedRecord.signedAt && <p>Thời điểm chốt: {vetDateTime(currentSignedRecord.signedAt)}</p>}
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
    if (submitting.current || blocked) return;
    if (form.trainingEligibility === 'Restricted' && !form.restrictionNote.trim()) {
      setError('Cần ghi rõ hạn chế tập trước khi lưu.'); return;
    }
    submitting.current = true;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await saveDraft();
      setMessage('Đã lưu phiếu khám nháp.');
    } catch (saveError) {
      await handleFailure(saveError);
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  }

  async function handleSign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current || blocked || !currentUser.permissions.includes('MEDICAL_SIGN')) return;
    if (!form.healthStatus || !form.trainingEligibility) {
      setError('Cần chọn tình trạng sức khỏe và điều kiện tập trước khi chốt phiếu.');
      return;
    }
    if (form.trainingEligibility === 'Restricted' && !form.restrictionNote.trim()) {
      setError('Cần ghi rõ hạn chế tập khi chọn mức Hạn chế.');
      return;
    }
    submitting.current = true;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const savedDraft = await saveDraft();
      const signed = await onSign(savedDraft.id);
      setJustSignedRecord(signed);
      setMessage('Đã chốt phiếu khám, chờ Manager xử lý.');
    } catch (signError) {
      await handleFailure(signError);
      submitting.current = false;
      setSaving(false);
      return;
    }
    try {
      await onAfterSign();
    } catch (refreshError) {
      setRefreshWarning(refreshError instanceof Error ? refreshError.message : 'Phiếu đã chốt nhưng không thể tải lại dữ liệu mới nhất.')
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  }

  async function handleFailure(failure: unknown) {
    if (!(failure instanceof ApiError) || !failure.status || failure.status >= 500 || failure.status === 409) {
      setBlocked(true);
      setError('Chưa thể xác nhận lưu. Hồ sơ có thể đã được Vet khác nhận hoặc chốt; đang tải lại dữ liệu.');
      try { await onConflict(); }
      catch { setError('Không thể xác nhận trạng thái mới nhất. Vui lòng quay lại hàng chờ và tải lại trước khi tiếp tục.'); }
    } else if (failure instanceof ApiError && failure.status === 400) {
      // Only expose known clinical validation fields, never raw endpoint/database messages.
      const labels: Record<string, string> = { ExamDate: 'Thời điểm khám', WeightKg: 'Cân nặng', HeightCm: 'Chiều cao', FollowUpDate: 'Ngày tái khám', Symptoms: 'Triệu chứng', Diagnosis: 'Chẩn đoán', Conclusion: 'Kết luận', TreatmentPlan: 'Hướng điều trị', RestrictionNote: 'Hạn chế tập', Note: 'Ghi chú', InjuryLocation: 'Vị trí chấn thương' };
      const fields = Object.keys(failure.fieldErrors).filter(key => labels[key]).map(key => labels[key]);
      setError(fields.length ? `Vui lòng kiểm tra: ${fields.join(', ')}. Nội dung phải đúng định dạng và giới hạn cho phép.` : 'Thông tin khám chưa hợp lệ. Vui lòng kiểm tra lại.');
    } else setError(vetError(failure, 'Không thể lưu phiếu khám. Vui lòng tải lại và thử lại.'));
  }

  if (!currentUser.permissions.includes('MEDICAL_MANAGE')) return <main className="page-content"><section className="panel">Bạn không có quyền lập phiếu khám.</section></main>;

  if (!ownsDraft) {
    return <main className="page-content"><section className="panel">
      <h1>Phiếu khám đang do Vet khác xử lý</h1>
      {conflictNotice && <p className="error-message" role="alert">{conflictNotice}</p>}
      <p>Phiếu nháp #{draft?.id} do {draft?.vetName || `Vet #${draft?.vetId}`} lập. Chỉ người lập phiếu mới có thể tiếp tục chỉnh sửa hoặc chốt phiếu.</p>
      <Link className="button" to="/vet/horses-needing-exam">Quay lại hàng đợi</Link>
    </section></main>;
  }

  return (
    <main className="page-content narrow-content">
      <div className="breadcrumb"><Link to={profilePath}>Hồ sơ ngựa</Link><span aria-hidden="true">/</span><span>Khám đầu vào</span></div>
      <header className="page-heading">
        <div><p className="eyebrow">BÁC SĨ THÚ Y · KHÁM ĐẦU VÀO</p><h1>{horse.name}</h1><p>{formatHorseCode(horse.code)} · Microchip: {horse.microchipNumber || 'Chưa cập nhật'} · Bác sĩ: {currentUser.fullName}</p></div>
      </header>
      <section className="horse-context-card">
        <div><h2>{horse.name}</h2><p>Trạng thái hồ sơ: {profileStatusLabels[horse.profileStatus] || 'Chưa xác định'}</p></div>
        <StatusBadge status={horse.healthStatus} label={healthLabels[horse.healthStatus]} type="health" />
      </section>
      {draft && <p className="profile-copy">Đang tiếp tục phiếu nháp #{draft.id} do bạn lập.</p>}
      {!draft && !draftId && <p className="profile-copy">Chưa ghi nhận nhận khám. Lưu phiếu nháp để ghi nhận bác sĩ đang xử lý.</p>}
      {conflictNotice && <p className="error-message" role="alert">{conflictNotice}</p>}
      {error && <div className="alert-banner" role="alert" style={{ marginTop: 16, background: '#fff4f4', color: '#7a1d1d', border: '1px solid #f7c2c2', borderRadius: 8, padding: '10px 12px' }}>{error}</div>}
      {message && <p className="success-message" role="status">{message}</p>}
      <section className="panel form-panel post-exam-form-panel">
        <h2>Phiếu khám đầu vào</h2>
        <p>Chốt phiếu xác nhận kết luận trong hệ thống, chưa phải chữ ký số. Manager quyết định tiếp nhận.</p>
        <p>Khóa tập khẩn cấp chưa khả dụng. Kết luận điều kiện tập chưa xác nhận đã áp dụng khóa tập.</p>
        <button className="button vet-emergency" type="button" disabled>Khóa tập khẩn cấp</button>
        <form onSubmit={handleSign}>
          <fieldset disabled={saving || blocked} className="vet-form-fields">
          <label className="form-field"><span>Thời điểm khám (giờ CLB UTC+07:00)</span><input type="datetime-local" step="1" required value={form.examDate} onChange={(event) => updateField('examDate', event.target.value)} /></label>
          <div className="horse-form-grid">
            <label className="form-field"><span>Cân nặng (kg)</span><input type="number" min="0.1" step="0.1" value={form.weightKg ?? ''} onChange={(event) => updateField('weightKg', event.target.value ? Number(event.target.value) : undefined)} /></label>
            <label className="form-field"><span>Chiều cao (cm)</span><input type="number" min="0.1" step="0.1" value={form.heightCm ?? ''} onChange={(event) => updateField('heightCm', event.target.value ? Number(event.target.value) : undefined)} /></label>
          </div>
          <label className="form-field"><span>Triệu chứng / lý do khám</span><textarea maxLength={1500} rows={3} value={form.symptoms} onChange={(event) => updateField('symptoms', event.target.value)} /></label>
          <label className="form-field"><span>Chẩn đoán</span><textarea maxLength={1500} rows={3} value={form.diagnosis} onChange={(event) => updateField('diagnosis', event.target.value)} /></label>
          <label className="form-field"><span>Vị trí chấn thương (ghi bằng chữ)</span><input maxLength={500} value={form.injuryLocation || ''} onChange={(event) => updateField('injuryLocation', event.target.value)} /></label>
          <label className="form-field"><span>Hướng điều trị / xử trí</span><textarea maxLength={3000} rows={3} value={form.treatmentPlan} onChange={(event) => updateField('treatmentPlan', event.target.value)} /></label>
          <label className="form-field"><span>Kết luận</span><textarea maxLength={1500} rows={3} required value={form.conclusion} onChange={(event) => updateField('conclusion', event.target.value)} /></label>
          <div className="horse-form-grid">
            <label className="form-field"><span>Tình trạng sức khỏe</span><select required value={form.healthStatus} onChange={(event) => updateField('healthStatus', event.target.value)}><option value="">Chọn tình trạng sức khỏe</option><option value="Healthy">Khỏe mạnh</option><option value="Monitor">Theo dõi</option><option value="Injured">Chấn thương</option><option value="Recovering">Đang hồi phục</option><option value="Isolated">Cách ly</option></select></label>
            <label className="form-field"><span>Điều kiện tập</span><select required value={form.trainingEligibility} onChange={(event) => updateField('trainingEligibility', event.target.value)}><option value="">Chọn điều kiện tập</option><option value="Eligible">Đủ điều kiện</option><option value="Restricted">Hạn chế</option><option value="Not Eligible">Không được tập</option></select></label>
          </div>
          <label className="form-field"><span>Hạn chế tập (bắt buộc nếu chọn Hạn chế)</span><textarea maxLength={1000} rows={2} value={form.restrictionNote} onChange={(event) => updateField('restrictionNote', event.target.value)} /></label>
          <label className="form-field"><span>Ngày tái khám</span><input type="date" min={form.examDate.slice(0, 10)} value={form.followUpDate} onChange={(event) => updateField('followUpDate', event.target.value)} /></label>
          <label className="form-field"><span>Kết quả kiểm tra / ghi chú</span><textarea rows={3} maxLength={1500} value={form.note || ''} onChange={(event) => updateField('note', event.target.value)} /></label>
          <div className="form-actions">
            <button className="button button-secondary" type="button" disabled={saving} onClick={() => void handleSaveDraft()}>{saving ? 'Đang lưu...' : 'Lưu nháp'}</button>
            <button className="button" type="submit" disabled={saving || !currentUser.permissions.includes('MEDICAL_SIGN')}>{saving ? 'Đang chốt...' : 'Chốt phiếu khám'}</button>
            <Link className="button button-secondary" to={profilePath}>Quay lại hồ sơ</Link>
          </div>
          </fieldset>
        </form>
      </section>
    </main>
  );
}

export default VetExaminationForm;
