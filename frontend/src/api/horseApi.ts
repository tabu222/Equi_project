import type { Horse } from '../types';
import { ApiError, apiGet, apiPatch, apiPost } from './apiClient.ts';

type ApiRecord = Record<string, unknown>;

function requiredId(record: ApiRecord, field: string): string {
  const value = record[field];
  if (typeof value !== 'number' && typeof value !== 'string') {
    throw new ApiError(`API trả thiếu hoặc sai trường định danh ${field}.`);
  }
  return String(value);
}

function listResponse<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === 'object' && Array.isArray((value as ApiRecord).results)) {
    return (value as { results: T[] }).results;
  }
  throw new ApiError('API trả danh sách không đúng định dạng.');
}

const profileStatus = (value: unknown): Horse['profileStatus'] => ({
  Draft: 'DRAFT',
  Submitted: 'SUBMITTED',
  PendingExam: 'PENDING_EXAM',
  Approved: 'APPROVED',
  Rejected: 'REJECTED',
  Archived: 'ARCHIVED',
}[String(value)] as Horse['profileStatus'] | undefined) ?? 'UNKNOWN';

const healthStatus = (value: unknown): Horse['healthStatus'] => ({
  Unknown: 'NOT_ASSESSED',
  Healthy: 'ELIGIBLE',
  Monitor: 'MONITORING',
  Injured: 'INJURED',
  Recovering: 'RECOVERING',
  Isolated: 'ISOLATION',
}[String(value)] as Horse['healthStatus'] | undefined) ?? 'NOT_ASSESSED';

export interface Club {
  id: string;
  name: string;
}

export async function getClubs(): Promise<Club[]> {
  return listResponse<ApiRecord>(await apiGet<unknown>('/clubs')).map((club) => {
    const name = club.ClubName;
    if (typeof name !== 'string' || !name.trim()) {
      throw new ApiError('API trả câu lạc bộ thiếu ClubName.');
    }
    return { id: requiredId(club, 'ClubID'), name };
  });
}

function mapHealthSummary(value: unknown): Horse['healthAssessment'] {
  if (!value || typeof value !== 'object') return undefined;
  const summary = value as ApiRecord;
  return {
    examinationId: summary.MedicalRecordID == null ? undefined : String(summary.MedicalRecordID),
    healthStatus: healthStatus(summary.HealthStatus),
    trainingEligibility: typeof summary.TrainingEligibility === 'string' ? summary.TrainingEligibility : undefined,
    conclusion: typeof summary.Conclusion === 'string' ? summary.Conclusion : undefined,
    restrictionNote: typeof summary.RestrictionNote === 'string' ? summary.RestrictionNote : undefined,
    followUpDate: typeof summary.FollowUpDate === 'string' ? summary.FollowUpDate : undefined,
    examDate: typeof summary.ExamDate === 'string' ? summary.ExamDate : undefined,
  };
}

export function normalizeHorse(value: unknown): Horse {
  if (!value || typeof value !== 'object') throw new ApiError('API trả hồ sơ ngựa không đúng định dạng.');
  const record = value as ApiRecord;
  const id = requiredId(record, 'HorseID');
  if (typeof record.HorseName !== 'string' || !record.HorseName.trim()) {
    throw new ApiError(`API trả thiếu tên ngựa cho HorseID ${id}.`);
  }
  const owner = record.Owner && typeof record.Owner === 'object' ? record.Owner as ApiRecord : undefined;
  const gender = String(record.Gender ?? '');
  const health = mapHealthSummary(record.HealthSummary);
  return {
    id,
    clubId: record.ClubID == null ? '' : String(record.ClubID),
    code: typeof record.HorseCode === 'string' ? record.HorseCode : '',
    name: record.HorseName,
    breed: typeof record.Breed === 'string' ? record.Breed : '',
    dateOfBirth: typeof record.DateOfBirth === 'string' ? record.DateOfBirth : '',
    sex: ({ Male: 'MALE', Female: 'FEMALE', Gelding: 'GELDING' }[gender] ?? 'UNKNOWN') as Horse['sex'],
    coatColor: typeof record.CoatColor === 'string' ? record.CoatColor : '',
    registrationNumber: typeof record.PassportNumber === 'string' ? record.PassportNumber : '',
    microchipNumber: typeof record.MicrochipNumber === 'string' ? record.MicrochipNumber : '',
    sireName: typeof record.SireName === 'string' ? record.SireName : '',
    damName: typeof record.DamName === 'string' ? record.DamName : '',
    ownerUserId: record.OwnerID == null ? undefined : String(record.OwnerID),
    ownerName: typeof owner?.FullName === 'string' ? owner.FullName : '',
    profileStatus: profileStatus(record.RegistrationStatus),
    rejectionReason: typeof record.ManagerNote === 'string' ? record.ManagerNote : undefined,
    healthStatus: healthStatus(record.CurrentHealthStatus),
    initialExamSigned: typeof record.InitialExamSigned === 'boolean' ? record.InitialExamSigned : undefined,
    healthAssessment: health,
    archiveReason: typeof record.ArchiveReason === 'string' ? record.ArchiveReason : undefined,
    archivedAt: typeof record.ArchivedAt === 'string' ? record.ArchivedAt : undefined,
    currentStall: record.CurrentStall && typeof record.CurrentStall === 'object'
      ? record.CurrentStall as Horse['currentStall']
      : undefined,
    createdAt: typeof record.CreatedAt === 'string' ? record.CreatedAt : '',
    updatedAt: typeof record.UpdatedAt === 'string' ? record.UpdatedAt : '',
    examinations: [],
    documents: [],
  };
}

export interface HorseQuery {
  RegistrationStatus?: string;
  OwnerID?: string;
  search?: string;
}

export async function getHorses(query: HorseQuery = {}): Promise<Horse[]> {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const suffix = params.size ? `?${params.toString()}` : '';
  return listResponse<unknown>(await apiGet<unknown>(`/horses${suffix}`)).map(normalizeHorse);
}

export async function getHorseById(horseId: string): Promise<Horse> {
  return normalizeHorse(await apiGet<unknown>(`/horses/${encodeURIComponent(horseId)}`));
}

export interface HorseProfileInput {
  name: string;
  breed: string;
  dateOfBirth: string;
  sex: Horse['sex'];
  coatColor: string;
  registrationNumber: string;
  microchipNumber: string;
  sireName: string;
  damName: string;
  clubId?: string;
}

function toProfilePayload(input: Partial<HorseProfileInput>, create = false): ApiRecord {
  const fields: Array<[keyof HorseProfileInput, string]> = [
    ['name', 'HorseName'], ['breed', 'Breed'], ['dateOfBirth', 'DateOfBirth'],
    ['coatColor', 'CoatColor'], ['registrationNumber', 'PassportNumber'],
    ['microchipNumber', 'MicrochipNumber'], ['sireName', 'SireName'], ['damName', 'DamName'],
  ];
  const payload: ApiRecord = {};
  fields.forEach(([source, target]) => {
    if (source in input) payload[target] = input[source];
  });
  if ('sex' in input) {
    const gender = input.sex;
    if (gender === 'MALE' || gender === 'FEMALE' || gender === 'GELDING') {
      payload.Gender = ({ MALE: 'Male', FEMALE: 'Female', GELDING: 'Gelding' } as const)[gender];
    }
  }
  if (create && input.clubId) payload.ClubID = Number(input.clubId);
  const passport = payload.PassportNumber;
  if (typeof passport === 'string') payload.PassportNumber = passport.trim().toUpperCase();
  const microchip = payload.MicrochipNumber;
  if (typeof microchip === 'string') payload.MicrochipNumber = microchip.trim();
  return payload;
}

export async function createHorse(input: HorseProfileInput): Promise<Horse> {
  return normalizeHorse(await apiPost<unknown>('/horses', toProfilePayload(input, true)));
}

export async function updateHorse(horseId: string, input: Partial<HorseProfileInput>): Promise<Horse> {
  return normalizeHorse(await apiPatch<unknown>(`/horses/${encodeURIComponent(horseId)}`, toProfilePayload(input)));
}

export async function submitHorse(horseId: string): Promise<Horse> {
  return normalizeHorse(await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/submit`, {}));
}

export async function verifyHorse(horseId: string): Promise<Horse> {
  return normalizeHorse(await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/verify`, {}));
}

export async function rejectHorse(horseId: string, reason: string): Promise<Horse> {
  return normalizeHorse(await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/reject`, { Reason: reason }));
}

export async function completeHorseIntake(
  horseId: string,
  input: { HorseCode: string; StallID?: number; ManagerNote?: string },
): Promise<Horse> {
  return normalizeHorse(await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/approve`, input));
}

export async function archiveHorse(horseId: string, reason: string): Promise<Horse> {
  return normalizeHorse(await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/archive`, { Reason: reason }));
}

export interface HorseDocument {
  documentId: string;
  documentName: string;
  documentType: string;
  uploadedAt: string;
  fileUrl: string;
}

export interface RegistrationHistory {
  id: string;
  requestDate: string;
  status: string;
  managerNote: string;
  reviewedAt?: string;
}

export interface ProfileChangeRequest {
  requestId: string;
  horseId: string;
  horseName: string;
  status: string;
  field: string;
  requestedValue: string;
  reason: string;
  createdAt: string;
  rejectionReason: string;
}

export interface AvailableStall {
  id: string;
  stallNumber: string;
}

export async function getHorseDocuments(horseId: string): Promise<HorseDocument[]> {
  const documents = listResponse<ApiRecord>(await apiGet<unknown>(`/horses/${encodeURIComponent(horseId)}/documents`));
  return documents.map((document) => ({
    documentId: requiredId(document, 'DocumentID'),
    documentName: typeof document.DocumentName === 'string' ? document.DocumentName : '',
    documentType: typeof document.DocumentType === 'string' ? document.DocumentType : '',
    uploadedAt: typeof document.UploadedAt === 'string' ? document.UploadedAt : '',
    fileUrl: typeof document.FileUrl === 'string' ? document.FileUrl : '',
  }));
}

export async function getRegistrationHistory(horseId: string): Promise<RegistrationHistory[]> {
  const requests = listResponse<ApiRecord>(await apiGet<unknown>(`/horses/${encodeURIComponent(horseId)}/registration-requests`));
  return requests.map((request) => ({
    id: requiredId(request, 'RegistrationRequestID'),
    requestDate: typeof request.RequestDate === 'string' ? request.RequestDate : '',
    status: typeof request.Status === 'string' ? request.Status : '',
    managerNote: typeof request.ManagerNote === 'string' ? request.ManagerNote : '',
    reviewedAt: typeof request.ReviewedAt === 'string' ? request.ReviewedAt : undefined,
  }));
}

export async function getAvailableStalls(): Promise<AvailableStall[]> {
  const stalls = listResponse<ApiRecord>(await apiGet<unknown>('/stalls?Status=Available'));
  return stalls.map((stall) => ({
    id: requiredId(stall, 'StallID'),
    stallNumber: typeof stall.StallNumber === 'string' ? stall.StallNumber : '',
  }));
}

const profileColumns: Record<string, string> = {
  name: 'HorseName',
  breed: 'Breed',
  dateOfBirth: 'DateOfBirth',
  coatColor: 'CoatColor',
  sex: 'Gender',
  sireName: 'SireName',
  damName: 'DamName',
  microchipNumber: 'MicrochipNumber',
  registrationNumber: 'PassportNumber',
};

function mapProfileChangeRequest(value: unknown): ProfileChangeRequest {
  if (!value || typeof value !== 'object') throw new ApiError('API trả yêu cầu sửa hồ sơ không đúng định dạng.');
  const record = value as ApiRecord;
  const changes = record.ChangedFields && typeof record.ChangedFields === 'object'
    ? (record.ChangedFields as ApiRecord)
    : {};
  const items = Array.isArray(changes.Changes) ? changes.Changes : [];
  const firstChange = items[0] && typeof items[0] === 'object' ? items[0] as ApiRecord : {};
  const field = Object.keys(profileColumns).find((key) => profileColumns[key] === firstChange.Field) || '';
  return {
    requestId: requiredId(record, 'ProfileChangeRequestID'),
    horseId: requiredId(record, 'HorseID'),
    horseName: typeof record.HorseName === 'string' ? record.HorseName : '',
    status: typeof record.Status === 'string' ? record.Status : '',
    field,
    requestedValue: firstChange.NewValue == null ? '' : String(firstChange.NewValue),
    reason: typeof changes.Reason === 'string' ? changes.Reason : '',
    createdAt: typeof record.RequestedAt === 'string' ? record.RequestedAt : '',
    rejectionReason: typeof record.ReviewNote === 'string' ? record.ReviewNote : '',
  };
}

export async function getProfileChangeRequests(horseId?: string): Promise<ProfileChangeRequest[]> {
  const params = new URLSearchParams();
  if (horseId) params.set('HorseID', horseId);
  const suffix = params.size ? `?${params.toString()}` : '';
  const requests = listResponse<unknown>(await apiGet<unknown>(`/profile-change-requests${suffix}`));
  return requests.map(mapProfileChangeRequest);
}

export async function requestProfileChange(
  horseId: string,
  field: string,
  value: string,
  reason: string,
  evidenceDocumentId?: number,
): Promise<ProfileChangeRequest> {
  const column = profileColumns[field];
  if (!column) throw new ApiError('Trường hồ sơ này không được phép gửi yêu cầu thay đổi.');
  const newValue = column === 'Gender'
    ? ({ MALE: 'Male', FEMALE: 'Female', GELDING: 'Gelding' } as Record<string, string>)[value] ?? value
    : value;
  const result = await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/profile-change-requests`, {
    Changes: { [column]: newValue },
    Reason: reason,
    ...(evidenceDocumentId ? { EvidenceDocumentID: evidenceDocumentId } : {}),
  });
  return mapProfileChangeRequest(result);
}

export async function reviewProfileChangeRequest(
  requestId: string,
  decision: 'approve' | 'reject',
  reviewNote: string,
): Promise<ProfileChangeRequest> {
  const result = await apiPost<unknown>(
    `/profile-change-requests/${encodeURIComponent(requestId)}/${decision}`,
    { ReviewNote: reviewNote },
  );
  return mapProfileChangeRequest(result);
}

export interface ExaminationInput {
  examDate: string;
  weightKg?: number;
  heightCm?: number;
  symptoms: string;
  diagnosis: string;
  treatmentPlan: string;
  conclusion: string;
  healthStatus: string;
  trainingEligibility: string;
  restrictionNote: string;
  followUpDate: string;
}

export interface MedicalRecord extends ExaminationInput {
  id: string;
  horseId: string;
  horseName: string;
  vetId: string;
  vetName: string;
  registrationRequestId?: string;
  examType: string;
  recordStatus: 'Draft' | 'Signed';
  signedAt?: string;
}

export interface PendingInitialExam {
  horse: Horse;
  requestId: string;
  requestDate: string;
  waitingHours: number;
  draftMedicalRecordId?: string;
  draftVetId?: string;
}

function mapMedicalRecord(value: unknown): MedicalRecord {
  if (!value || typeof value !== 'object') throw new ApiError('API trả phiếu khám không đúng định dạng.');
  const record = value as ApiRecord;
  return {
    id: requiredId(record, 'MedicalRecordID'),
    horseId: requiredId(record, 'HorseID'),
    horseName: typeof record.HorseName === 'string' ? record.HorseName : '',
    vetId: requiredId(record, 'VetID'),
    vetName: typeof record.VetName === 'string' ? record.VetName : '',
    registrationRequestId: record.RegistrationRequestID == null
      ? undefined
      : String(record.RegistrationRequestID),
    examType: typeof record.ExamType === 'string' ? record.ExamType : '',
    examDate: typeof record.ExamDate === 'string' ? record.ExamDate : '',
    weightKg: typeof record.WeightKg === 'number' ? record.WeightKg : undefined,
    heightCm: typeof record.HeightCm === 'number' ? record.HeightCm : undefined,
    symptoms: typeof record.Symptoms === 'string' ? record.Symptoms : '',
    diagnosis: typeof record.Diagnosis === 'string' ? record.Diagnosis : '',
    treatmentPlan: typeof record.TreatmentPlan === 'string' ? record.TreatmentPlan : '',
    conclusion: typeof record.Conclusion === 'string' ? record.Conclusion : '',
    healthStatus: typeof record.HealthStatus === 'string' ? record.HealthStatus : '',
    trainingEligibility: typeof record.TrainingEligibility === 'string' ? record.TrainingEligibility : '',
    restrictionNote: typeof record.RestrictionNote === 'string' ? record.RestrictionNote : '',
    followUpDate: typeof record.FollowUpDate === 'string' ? record.FollowUpDate : '',
    recordStatus: record.RecordStatus === 'Signed' ? 'Signed' : 'Draft',
    signedAt: typeof record.SignedAt === 'string' ? record.SignedAt : undefined,
  };
}

export async function getPendingInitialExams(): Promise<PendingInitialExam[]> {
  const records = listResponse<ApiRecord>(await apiGet<unknown>('/vet/pending-initial-exams'));
  return records.map((record) => ({
    horse: { ...normalizeHorse(record), initialExamSigned: false },
    requestId: requiredId(record, 'RegistrationRequestID'),
    requestDate: typeof record.RequestDate === 'string' ? record.RequestDate : '',
    waitingHours: typeof record.WaitingHours === 'number' ? record.WaitingHours : 0,
    draftMedicalRecordId: record.DraftMedicalRecordID == null ? undefined : String(record.DraftMedicalRecordID),
    draftVetId: record.DraftVetID == null ? undefined : String(record.DraftVetID),
  }));
}

export async function getMedicalRecords(horseId: string): Promise<MedicalRecord[]> {
  return listResponse<unknown>(await apiGet<unknown>(`/horses/${encodeURIComponent(horseId)}/medical-records`)).map(mapMedicalRecord);
}

function examinationPayload(input: ExaminationInput): ApiRecord {
  return {
    ExamType: 'Initial Exam',
    ...(input.examDate ? { ExamDate: input.examDate } : {}),
    WeightKg: input.weightKg ?? null,
    HeightCm: input.heightCm ?? null,
    Symptoms: input.symptoms,
    Diagnosis: input.diagnosis,
    TreatmentPlan: input.treatmentPlan,
    Conclusion: input.conclusion,
    ...(input.healthStatus ? { HealthStatus: input.healthStatus } : {}),
    ...(input.trainingEligibility ? { TrainingEligibility: input.trainingEligibility } : {}),
    ...(input.restrictionNote !== undefined ? { RestrictionNote: input.restrictionNote } : {}),
    FollowUpDate: input.followUpDate || null,
  };
}

export async function saveExaminationDraft(
  horseId: string,
  input: ExaminationInput,
  draftMedicalRecordId?: string,
): Promise<MedicalRecord> {
  const payload = examinationPayload(input);
  const result = draftMedicalRecordId
    ? await apiPatch<unknown>(`/medical-records/${encodeURIComponent(draftMedicalRecordId)}`, payload)
    : await apiPost<unknown>(`/horses/${encodeURIComponent(horseId)}/medical-records`, payload);
  return mapMedicalRecord(result);
}

export async function signMedicalRecord(recordId: string): Promise<MedicalRecord> {
  return mapMedicalRecord(await apiPost<unknown>(`/medical-records/${encodeURIComponent(recordId)}/sign`, {}));
}
