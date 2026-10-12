import { apiGet, apiPatch, apiPost, apiDelete } from './apiClient.js'

const registrationMap = {
  Draft: 'DRAFT', Submitted: 'SUBMITTED', PendingExam: 'PENDING_EXAM', Rejected: 'REJECTED',
  Approved: 'RECEIVED', Archived: 'ARCHIVED',
}
const healthMap = {
  Unknown: 'NOT_ASSESSED', Healthy: 'ELIGIBLE', Monitor: 'MONITORING', Injured: 'INJURED',
  Recovering: 'RECOVERING', Isolated: 'ISOLATION',
}

export function normalizeHorse(record) {
  const status = registrationMap[record.RegistrationStatus] || String(record.RegistrationStatus || '').toUpperCase()
  const healthSummary = record.HealthSummary
  return {
    id: String(record.HorseID),
    clubId: String(record.ClubID ?? ''),
    code: record.HorseCode || '',
    name: record.HorseName || '',
    breed: record.Breed || '',
    dateOfBirth: record.DateOfBirth || '',
    sex: String(record.Gender || '').toUpperCase(),
    coatColor: record.CoatColor || '',
    sexClass: record.SexClass || '',
    registrationNumber: record.PassportNumber || '',
    microchipNumber: record.MicrochipNumber || '',
    sireName: record.SireName || '',
    damName: record.DamName || '',
    sireId: record.SireName || '',
    damId: record.DamName || '',
    ownerUserId: String(record.OwnerID ?? ''),
    owner: record.Owner ? { ownerId: String(record.Owner.UserID), fullName: record.Owner.FullName, email: record.Owner.Email, phone: record.Owner.Phone, address: record.Owner.Address } : undefined,
    profileStatus: status === 'PENDING_EXAM' && record.InitialExamSigned ? 'PENDING_COMPLETION' : status,
    healthStatus: healthMap[record.CurrentHealthStatus] || 'NOT_ASSESSED',
    archiveReason: record.ArchiveReason || '',
    createdAt: record.CreatedAt || '',
    updatedAt: record.UpdatedAt || '',
    healthAssessment: healthSummary ? {
      healthStatus: healthMap[healthSummary.HealthStatus] || 'NOT_ASSESSED',
      conclusion: healthSummary.Conclusion || '',
      exerciseRestrictions: healthSummary.RestrictionNote || '',
      followUpDate: healthSummary.FollowUpDate || '',
      purpose: healthSummary.ExamType || '',
      finalizedAt: healthSummary.ExamDate || '',
      trainingEligibility: healthSummary.TrainingEligibility || '',
    } : undefined,
    intake: { examinationStatus: record.InitialExamSigned ? 'COMPLETED' : 'PENDING' },
    examinations: [],
    documents: [],
    auditLogs: [],
  }
}

export async function getHorses(params = {}) {
  const query = typeof params === 'string' ? params : new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== '')).toString()
  const records = await apiGet(`/horses${query ? `?${query.replace(/^\?/, '')}` : ''}`)
  return records.map(normalizeHorse)
}

export async function getPendingInitialExams() {
  const records = await apiGet('/vet/pending-initial-exams')
  return records.map((item) => normalizeHorse({
    HorseID: item.HorseID,
    HorseCode: item.HorseCode,
    HorseName: item.HorseName,
    ClubID: item.ClubID,
    OwnerID: item.OwnerID,
    Breed: item.Breed,
    Gender: item.Gender,
    DateOfBirth: item.DateOfBirth,
    RegistrationStatus: 'PendingExam',
    CurrentHealthStatus: 'Unknown',
    InitialExamSigned: false,
    CreatedAt: item.RequestDate,
    UpdatedAt: item.RequestDate,
  }))
}

export async function getHorseById(id, { role } = {}) {
  const record = await apiGet(`/horses/${id}`)
  const horse = normalizeHorse(record)
  const [documents, medicalRecords] = await Promise.all([
    apiGet(`/horses/${id}/documents`),
    role === 'OWNER' ? Promise.resolve([]) : apiGet(`/horses/${id}/medical-records`),
  ])
  horse.documents = documents.map((item) => ({
    documentId: item.DocumentID,
    documentName: item.DocumentName,
    documentType: item.DocumentType,
    fileUrl: item.FileUrl,
    isVisibleToOwner: item.IsVisibleToOwner,
    uploadedAt: item.UploadedAt,
  }))
  horse.examinations = medicalRecords.map((item) => ({
    id: String(item.MedicalRecordID),
    examinedAt: item.ExamDate,
    weightKg: item.WeightKg,
    heightCm: item.HeightCm,
    symptoms: item.Symptoms,
    diagnosis: item.Diagnosis,
    treatmentPlan: item.TreatmentPlan,
    conclusion: item.Conclusion,
    healthStatus: healthMap[item.HealthStatus] || 'NOT_ASSESSED',
    exerciseRestrictions: item.RestrictionNote,
    trainingEligibility: item.TrainingEligibility || '',
    followUpDate: item.FollowUpDate,
    status: item.RecordStatus === 'Signed' ? 'FINALIZED' : 'DRAFT',
    examType: item.ExamType,
    note: item.Note,
  }))
  return horse
}

export async function createHorse(values) {
  const payload = {
    HorseName: values.name,
    Breed: values.breed,
    DateOfBirth: values.dateOfBirth,
    Gender: values.sex[0] + values.sex.slice(1).toLowerCase(),
    CoatColor: values.coatColor || null,
    SireName: values.sireId || null,
    DamName: values.damId || null,
    MicrochipNumber: values.microchipNumber || null,
    PassportNumber: values.registrationNumber || null,
  }
  if (values.ownerUserId) payload.OwnerID = Number(values.ownerUserId)
  if (values.clubId) payload.ClubID = Number(values.clubId)
  const result = await apiPost('/horses', payload)
  return normalizeHorse(result)
}

export async function createUser(values) {
  const user = await apiPost('/users', {
    FullName: values.fullName,
    Email: values.email,
    Phone: values.phone,
    Address: values.address,
    RoleCode: 'HORSE_OWNER',
  })
  return normalizeUser(user)
}

export async function getHorseDocuments(id) {
  const documents = await apiGet(`/horses/${id}/documents`)
  return documents.map((item) => ({ documentId: item.DocumentID, documentName: item.DocumentName, documentType: item.DocumentType, fileUrl: item.FileUrl, isVisibleToOwner: item.IsVisibleToOwner, uploadedAt: item.UploadedAt }))
}

export async function addHorseDocument(id, values) {
  return apiPost(`/horses/${id}/documents`, {
    DocumentName: values.documentName,
    DocumentType: values.documentType,
    FileUrl: values.fileUrl,
    IsVisibleToOwner: Boolean(values.isVisibleToOwner),
  })
}

export const submitHorse = (id) => apiPost(`/horses/${id}/submit`, {})
export const verifyHorse = (id) => apiPost(`/horses/${id}/verify`, {})
export const rejectHorse = (id, reason) => apiPost(`/horses/${id}/reject`, { Reason: reason })
export const deleteMedicalRecord = (id) => apiDelete(`/medical-records/${id}`)

export async function getProfileChangeRequests(horseId) {
  const items = await apiGet(`/profile-change-requests?HorseID=${encodeURIComponent(horseId)}`)
  return items.map((item) => {
    const changes = item.ChangedFields?.Changes || []
    const first = changes[0]
    const fieldMap = { HorseName: 'name', Breed: 'breed', DateOfBirth: 'dateOfBirth', CoatColor: 'coatColor', Gender: 'sex', SireName: 'sireName', DamName: 'damName', MicrochipNumber: 'microchipNumber', PassportNumber: 'registrationNumber' }
    return {
      requestId: String(item.ProfileChangeRequestID),
      ownerId: String(item.RequestedBy),
      horseId: String(item.HorseID),
      status: item.Status,
      field: fieldMap[first?.Field] || first?.Field,
      requestedValue: first?.NewValue || '',
      reason: item.ChangedFields?.Reason || '',
      createdAt: item.RequestedAt,
      rejectionReason: item.ReviewNote || '',
      evidenceFiles: [],
    }
  })
}

export async function submitProfileChangeRequest({ horseId, field, requestedValue, reason }) {
  return createProfileChangeRequest(horseId, field, requestedValue, reason)
}

export async function approveHorse(id, values) {
  const body = { HorseCode: values.HorseCode }
  if (values.StallID) body.StallID = Number(values.StallID)
  if (values.ManagerNote) body.ManagerNote = values.ManagerNote
  return normalizeHorse(await apiPost(`/horses/${id}/approve`, body))
}

export async function getStalls() {
  return apiGet('/stalls?Status=Available')
}

function medicalPayload(horse, input) {
  const healthStatus = {
    ELIGIBLE: 'Healthy', MONITORING: 'Monitor', RECOVERING: 'Recovering', INJURED: 'Injured', ISOLATION: 'Isolated',
  }[input.healthStatus]
  const examType = horse.profileStatus === 'PENDING_EXAM' || horse.profileStatus === 'PENDING_COMPLETION'
    ? 'Initial Exam'
    : /follow/i.test(input.purpose || '') ? 'Follow-up' : 'Routine Exam'
  const trainingEligibility = input.trainingEligibility
  return {
    ExamType: examType,
    ExamDate: input.examinedAt ? `${input.examinedAt}T12:00:00` : undefined,
    WeightKg: input.weightKg,
    HeightCm: input.heightCm,
    Symptoms: input.symptoms,
    Diagnosis: input.diagnosis,
    TreatmentPlan: input.treatmentPlan,
    Conclusion: input.conclusion,
    HealthStatus: healthStatus,
    TrainingEligibility: trainingEligibility,
    RestrictionNote: trainingEligibility === 'Restricted' ? input.exerciseRestrictions : undefined,
    FollowUpDate: input.followUpDate || null,
    Note: input.note || null,
  }
}

async function saveMedicalRecord(horseId, vet, input, sign) {
  const horse = await getHorseById(horseId)
  const draft = [...horse.examinations].reverse().find((item) => item.status === 'DRAFT')
  const payload = medicalPayload(horse, input)
  let record
  if (draft) record = await apiPatch(`/medical-records/${draft.id}`, payload)
  else record = await apiPost(`/horses/${horseId}/medical-records`, payload)
  if (sign) await apiPost(`/medical-records/${record.MedicalRecordID}/sign`, {})
  return getHorseById(horseId)
}

export function saveExaminationDraft(horseId, vet, input) {
  return saveMedicalRecord(horseId, vet, input, false)
}

export function finalizeExamination(horseId, vet, input) {
  return saveMedicalRecord(horseId, vet, input, true)
}

export async function completeHorseIntake(horseId, values) {
  return approveHorse(horseId, values)
}

export async function updateHorse(id, values) {
  const result = await apiPatch(`/horses/${id}`, {
    HorseName: values.name,
    Breed: values.breed,
    DateOfBirth: values.dateOfBirth,
    Gender: values.sex,
    CoatColor: values.coatColor,
    SireName: values.sireId,
    DamName: values.damId,
    MicrochipNumber: values.microchipNumber,
    PassportNumber: values.registrationNumber,
  })
  return normalizeHorse(result)
}

export async function archiveHorse(id, reason) {
  return normalizeHorse(await apiPost(`/horses/${id}/archive`, { Reason: reason }))
}

export async function createProfileChangeRequest(id, field, value, reason) {
  const fieldMap = { name: 'HorseName', breed: 'Breed', dateOfBirth: 'DateOfBirth', coatColor: 'CoatColor', sex: 'Gender', sireName: 'SireName', damName: 'DamName', microchipNumber: 'MicrochipNumber', registrationNumber: 'PassportNumber' }
  return apiPost(`/horses/${id}/profile-change-requests`, { Changes: { [fieldMap[field]]: value }, Reason: reason })
}

export function isHorseAssignedToVet() {
  // The Django queue is club-wide and contains only unsigned intake exams.
  return true
}

export function normalizeUser(record) {
  const roles = record.Roles || record.roles || (record.role ? [record.role] : [])
  const roleMap = { CLUB_MANAGER: 'CLUB_MANAGER', HORSE_OWNER: 'OWNER', VETERINARIAN: 'VET', HEAD_TRAINER: 'HEAD_TRAINER' }
  return {
    id: String(record.UserID ?? record.id ?? ''),
    clubId: String(record.ClubID ?? record.clubId ?? ''),
    fullName: record.FullName || record.fullName || '',
    email: record.Email || record.email || '',
    phone: record.Phone || record.phone || '',
    address: record.Address || record.address || '',
    role: roleMap[roles[0]] || roles[0] || '',
    roles,
    permissions: record.Permissions || [],
    isActive: record.Status === 'Active',
    createdAt: record.CreatedAt || '',
  }
}

