# API contract – Equi backend (Flow 1–4)

Documentation for the frontend team. Backend: Django REST, database `sql/horse_v2.sql`.

**Current checkout supports Flow 1, Flow 2 and Flow 3.** Section 7 and the Flow 4 parts of 10 describe the larger system, not available routes in this checkout: diet plans, care tasks and inventory are unavailable; do not show those actions as working features.

### Verified Flow 1 frontend mapping

All paths below use the `/api` prefix, with no trailing slash. Responses use SQL column names; lists currently return arrays (FE also accepts `results` wrappers). Dates use `YYYY-MM-DD`; datetimes use local ISO strings.

| Function | Method/path | Payload → response | Frontend caller |
|---|---|---|---|
| Login / session | `POST /auth/login`, `GET /auth/me`, `POST /auth/refresh` | `Email, Password` → `access, refresh, User`; refresh body `refresh` → `access` | `userApi.ts`, `apiClient.ts` |
| Public signup / clubs | `POST /auth/register`, `GET /clubs` | `FullName, Email, Phone, Address, ClubID, Password` → token pair + Owner `User`; clubs → `ClubID, ClubName` | `registrationApi.js`, `horseApi.ts`, `LoginScreen.jsx` |
| Users | `GET /users?RoleCode=HORSE_OWNER` | array of `UserID, Roles, Status, ...` | `userApi.ts`, `CreateHorse.jsx`, `App.jsx` |
| Horse list/detail/create/edit | `GET, POST /horses`, `GET, PATCH /horses/{id}` | `HorseName, Breed, DateOfBirth, Gender, CoatColor, PassportNumber, MicrochipNumber, SireName, DamName`; Owner create adds `ClubID`, Manager create adds `OwnerID` → horse | `horseApi.ts`, Owner/Manager forms |
| Register / verify / reject | `POST /horses/{id}/submit`, `/verify`, `/reject` | `{}` / `{}` / `{Reason}` → horse | `horseApi.ts`, `App.jsx`, `CompleteIntake.jsx` |
| Intake / stalls / archive | `POST /horses/{id}/approve`, `GET /stalls?Status=Available`, `POST /horses/{id}/archive` | `HorseCode, StallID?, ManagerNote?` → horse; archive `Reason` → horse | `horseApi.ts`, `CompleteIntake.jsx` |
| History / documents | `GET /horses/{id}/registration-requests`, `/documents` | requests with `Status, ManagerNote`; visible documents | `horseApi.ts`, `App.jsx` |
| Vet queue | `GET /vet/pending-initial-exams` | horse/request IDs, `DraftMedicalRecordID, DraftVetID` | `horseApi.ts`, `HorsesNeedingExam.jsx` |
| Exam create/read/update/sign | `GET, POST /horses/{id}/medical-records`, `PATCH /medical-records/{id}`, `POST /medical-records/{id}/sign` | `ExamType="Initial Exam", ExamDate?, WeightKg?, HeightCm?, Symptoms, Diagnosis, TreatmentPlan, Conclusion, HealthStatus, TrainingEligibility, RestrictionNote, FollowUpDate?` → record; sign `{}` | `horseApi.ts`, `VetExaminationForm.tsx` |
| Profile corrections | `POST /horses/{id}/profile-change-requests`, `GET /profile-change-requests?HorseID={id}`, `POST /profile-change-requests/{id}/approve` or `/reject` | create `Changes, Reason, EvidenceDocumentID?`; review `ReviewNote` → request with `ChangedFields, Status` | `horseApi.ts`, Owner/Manager correction pages |

Public signup ignores client roles; the backend grants only `HORSE_OWNER`. JWT/session logic lives exclusively in `apiClient.ts`; logout clears the local tokens (there is no logout/revoke endpoint). A refresh is shared by concurrent 401 responses and retried once. A 403 is shown as a permission error. Roles outside Owner/Manager/Vet can be normalized in lists and receive an explicit unsupported workspace screen at login.

| Part | Contents |
|---|---|
| [1–3](#1-general-conventions) | General conventions, error codes, horse registration status, roles and permissions |
| [4](#4-flow-1--horse-intake) | **Flow 1** – login, horses, documents, intake examination, profile changes, stalls |
| [5](#5-flow-2--training) | **Flow 2** – assessment, trainer assignment, training plans, training sessions, results, session reviews |
| [6](#6-flow-3--medical) | **Flow 3** – health reports, medical records, Training Lock, treatments, vaccinations, medical schedule |
| [7](#7-flow-4--care-and-nutrition) | **Flow 4** – diet plans, care tasks, inventory |
| [8](#8-notifications) | Notifications (bell) for each role |
| [9](#9-frontend-changes-flow-1) | What the frontend needs to change in the existing Flow 1 |
| [10](#10-frontend-for-flow-24) | Suggested frontend screens for Flow 2–4 |

## 1. General conventions

| Item | Convention |
|---|---|
| Base URL | `http://localhost:8000/api` (the frontend calls `/api/...` through the Vite proxy) |
| Swagger | `http://127.0.0.1:8000/api/docs` to try every API in the browser; OpenAPI schema at `/api/schema` (import into Postman) |
| Trailing `/` | **None**: `/api/horses/5`, not `/api/horses/5/` |
| Format | JSON for both requests and responses |
| JSON key names | **Exactly the database column names**: `HorseID`, `HorseName`, `RegistrationStatus`... |
| Status values | **Exactly the values in the database**: `Draft`, `PendingExam`, `Approved`... |
| Date | `"2021-03-10"` |
| Date-time | `"2026-10-10T08:30:00"` (Vietnam time, no time zone) |
| Decimal numbers | Plain numbers: `"WeightKg": 480.5` |
| Time | `"06:00:00"` (sending `"06:00"` also works) |
| List filtering | Query string by column name: `?HorseID=5&Status=Pending`; on / off flags use `=1` (`?mine=1`, `?open=1`) |
| Login | Header `Authorization: Bearer <access>` for every API (except `auth/login`, `auth/register`, `auth/google`, `clubs`, `health`) |
| Language | Messages (error `detail`, field errors, notification titles) are **Vietnamese by default**. Send header `X-Language: en` (or `?lang=en`) to get **English**. The response header `Content-Language` says which one was used. `code`, JSON keys and status values never change. Messages without a translation stay Vietnamese (add them to `apps/core/i18n.py`) |

### Error codes

| HTTP | When | Body shape |
|---|---|---|
| 400 | Invalid / missing data (including invalid filter parameters, e.g. `?HorseID=abc`) | `{"HorseName": ["This field is required."], "Gender": ["\"Unknown\" is not a valid choice."]}` |
| 401 | Not logged in, token expired, wrong password | `{"detail": "...", "code": "..."}` |
| 403 | Role lacks permission | `{"detail": "You do not have permission to perform this action.", "code": "PERMISSION_DENIED"}` |
| 404 | Does not exist **or is not visible** (horse of another club, horse of another owner) | `{"detail": "...", "code": "NOT_FOUND"}` |
| 409 | Business rule violation | `{"detail": "The horse does not have a signed intake examination record.", "code": "INITIAL_EXAM_REQUIRED"}` |

The frontend shows `detail` to the user; use `code` when special handling is needed.

Errors coming from the database itself are also specific (the backend usually catches them earlier):

| `code` | When | Example `detail` |
|---|---|---|
| name of the CHECK constraint, e.g. `CK_Horse_Gender` | a value breaks a CHECK rule in `horse_v2.sql` | "Giới tính ngựa phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến)." |
| `REQUIRED_VALUE_MISSING` | a required column would be NULL | "Thiếu dữ liệu bắt buộc: câu lạc bộ (ClubID) (bảng Horse) không được để trống." |
| `RELATED_NOT_FOUND` / `IN_USE` | foreign key: the referenced row does not exist / the row is still used elsewhere | "Không tìm thấy dữ liệu liên quan: Owner không tồn tại (FK_Horse_Owner)." |
| unique index name, or `DUPLICATE` | duplicate value | "Số microchip đã tồn tại ở một ngựa khác." |
| `VALUE_TOO_LONG` | text longer than the column allows | "Tên ngựa quá dài so với giới hạn của database." |

409 error `code`s (common and Flow 1; codes specific to Flow 2–4 are listed in each part):

| code | Meaning |
|---|---|
| `INVALID_STATUS` | Action not valid for the current status (e.g. editing a submitted profile) |
| `MISSING_FIELDS` | Submitting a profile / signing a medical record before all fields are filled in (`detail` lists the missing column names) |
| `INITIAL_EXAM_REQUIRED` | Approving a profile before the Vet has signed the intake examination record |
| `INITIAL_EXAM_FAILED` | Intake examination did not pass → can only reject |
| `USER_NO_CLUB` | The Manager's account has no club (`ClubID` is empty), so it cannot create horses. Fix the account, e.g. run `seed_demo` again |
| `DUPLICATE_HORSE_CODE` | Horse code already exists in the club |
| `STALL_NOT_FOUND`, `STALL_NOT_AVAILABLE` | Stall does not belong to the club / is no longer available |
| `INITIAL_EXAM_EXISTS` | This submission already has an intake examination record (it may be another Vet's draft) |
| `RECORD_SIGNED` | Medical record is signed and cannot be edited / deleted |
| `NOT_RECORD_OWNER` | Only the Vet who created the record can edit / sign a draft record |
| `EXAM_TYPE_LOCKED` | Cannot change the exam type of an existing record |
| `RECORD_NOT_SIGNED` | Draft records are edited directly, not through an amendment |
| `PENDING_REQUEST_EXISTS` | The horse already has 1 pending profile change request |
| `FIELD_NOT_EDITABLE` | Requested change to a field that is not allowed |
| `REVIEW_NOTE_REQUIRED` | Rejecting / returning without a reason (profile change request, training plan) |
| `HORSE_NOT_APPROVED` | Flow 2–4 action on a horse that has not been taken in (not yet `Approved`) |
| `DUPLICATE_STALL`, `STALL_OCCUPIED` | Duplicate stall number / stall currently has a horse |
| `TRAINING_LOCK_FULL`, `TRAINING_LOCK_RESTRICTED` | Horse is under a training lock (see Flow 3). The SQL Server trigger returns the same code |
| `UX_...`, `UQ_...`, `DB_INTEGRITY` | Unique index / database constraint violation (translated into Vietnamese) |

## 2. Horse registration status (`RegistrationStatus`)

```
Draft ──submit──> Submitted ──verify──> PendingExam ──(Vet signs exam)──> approve ──> Approved ──archive──> Archived
  ^                   │                      │
  └──── edit ──── Rejected <──── reject ──────┘
```

| Value | Meaning | Who does what next |
|---|---|---|
| `Draft` | Draft | Owner / Manager edits, submits |
| `Submitted` | Submitted | Manager verifies or rejects |
| `PendingExam` + `InitialExamSigned: false` | Waiting for the Vet's intake examination | On-duty Vet examines; Manager can reject |
| `PendingExam` + `InitialExamSigned: true` | Vet has signed the exam (the old screen calls this `PENDING_COMPLETION`) | Manager approves (if passed) or rejects |
| `Approved` | Taken in, has a `HorseCode` | Owner requests profile changes; Manager archives |
| `Rejected` | Rejected (reason in `RegistrationRequest.ManagerNote`) | Owner / Manager edits and resubmits |
| `Archived` | Has left the club | View only |

When resubmitting after `Rejected`, the backend creates a new `RegistrationRequest` and **the Vet must examine again**
(`InitialExamSigned` goes back to `false`).

`CurrentHealthStatus`: `Unknown`, `Healthy`, `Monitor`, `Injured`, `Recovering`, `Isolated`.
`Gender`: `Male`, `Female`, `Gelding`. `SexClass` (computed by the backend): `Foal` (< 1 year old), `Colt`/`Filly` (< 4 years old), `Stallion`/`Mare`, `Gelding`.

## 3. Roles and permissions

Login returns `Roles` and `Permissions`. The frontend uses `Permissions` to hide / show buttons.

| Role (`RoleCode`) | Permissions | Main tasks |
|---|---|---|
| `CLUB_MANAGER` | `CLUB_MANAGE`, `RBAC_MANAGE`, `AUDIT_VIEW`, `HORSE_VIEW`, `HORSE_REGISTER_REVIEW`, `HORSE_ARCHIVE`, `PROFILE_EDIT_APPROVE`, `INVENTORY_MANAGE` | Approve horse profiles, stalls, accounts, inventory, assign care tasks |
| `HEAD_TRAINER` | `HORSE_VIEW`, `HORSE_ASSESS`, `TRAINER_ASSIGN`, `TRAINING_PLAN_APPROVE`, `TRAINING_SESSION_ASSIGN`, `TRAINING_SESSION_SUPERVISE`, `HEALTH_REPORT`, `DIET_MANAGE`, `INVENTORY_REQUEST` | Assess horses, assign trainers, approve training plans, schedule training sessions, create diet plans, assign tasks to Grooms |
| `TRAINER` | `HORSE_VIEW`, `TRAINING_PLAN_MANAGE`, `TRAINING_SESSION_ASSIGN`, `TRAINING_SESSION_SUPERVISE`, `TRAINING_REVIEW`, `HEALTH_REPORT` | Write training plans, schedule sessions **for the horses they are in charge of**, supervise (including as Substitute), review training sessions, close plan stages |
| `WORK_RIDER` | `HORSE_VIEW`, `TRAINING_RESULT_UPDATE`, `HEALTH_REPORT` | Start training sessions, record results |
| `VETERINARIAN` | `HORSE_VIEW`, `MEDICAL_MANAGE`, `MEDICAL_SIGN`, `TRAINING_LOCK_MANAGE`, `DIET_MANAGE` | Examinations, signing records, Training Lock, treatments, vaccinations, approving diet plans |
| `GROOM` | `HORSE_VIEW`, `CARE_MANAGE`, `HEALTH_REPORT`, `INVENTORY_REQUEST` | Care tasks, reporting incidents, requesting inventory items |
| `HORSE_OWNER` | `HORSE_REGISTER`, `PROFILE_EDIT_REQUEST`, `OWNER_VIEW` | Register horses, request profile changes, view own horses and their training results (section 5.7) |

Data scope: staff only see data **within their own club**; horse owners only see **their own horses**
(health summary and training results reviewed by the trainer – section 5.7; not medical records or internal notes).

## 4. Flow 1 – Horse intake

### 4.1 Login, users

| Method | URL | Used by | Body / parameters |
|---|---|---|---|
| GET | `/health` | no login required | → `{"backend": "UP", "database": "UP"}` (503 if the DB fails) |
| POST | `/auth/login` | everyone | `{"Email", "Password"}` → `{access, refresh, User}` |
| POST | `/auth/register` | no login required | Horse owner signs up: `{"FullName", "Email", "Phone", "Address", "Password" (min 6), "ClubID"}` → **201** `{access, refresh, User}` (logged in right away). Role is always `HORSE_OWNER`; max 20 sign-ups per hour per IP |
| POST | `/auth/google` | no login required | Sign in with Google: `{"Credential": "<Google ID token>"}` → existing email: `{access, refresh, User}`; unknown email: `{"SignupRequired": true, "Email", "FullName"}`. Send again with `"Phone", "Address", "ClubID"` (and optional `"FullName"`) to create a **horse owner** account → **201** `{access, refresh, User}`. Needs `GOOGLE_CLIENT_ID` in `.env` (otherwise 409 `GOOGLE_LOGIN_DISABLED`) |
| POST | `/auth/refresh` | everyone | `{"refresh"}` → `{access}` |
| GET | `/auth/me` | logged in | → `User` with `Roles`, `Permissions` |
| GET | `/users?RoleCode=HORSE_OWNER` | Manager, Head Trainer, Trainer | users in the club (`RoleCode` = `TRAINER`, `WORK_RIDER`, `GROOM`... to pick people for assignments). A Trainer only gets `WORK_RIDER` / `TRAINER` / `HEAD_TRAINER` (other `RoleCode` → 403) |
| POST | `/users` | Manager | `{"FullName", "Email", "Phone", "Address", "RoleCode"? (default HORSE_OWNER), "Password"?}`; `Phone` = 10 digits starting with 0 or `+84` + 9 digits |
| GET | `/users/{UserID}` | self / Manager of the same club | |
| GET | `/clubs` | no login required | Active clubs (picked on the sign-up form and when an Owner registers a horse) |

If `POST /users` is sent without `Password`, the backend generates a temporary password and returns `TemporaryPassword` **only once**.

Example `POST /auth/login`:

```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi...",
  "User": {
    "UserID": 7, "ClubID": 1, "FullName": "Demo Horse Owner", "Email": "owner@equi.local",
    "Phone": null, "Address": null, "Status": "Active", "CreatedAt": "2026-10-10T08:00:00",
    "Roles": ["HORSE_OWNER"],
    "Permissions": ["HORSE_REGISTER", "OWNER_VIEW", "PROFILE_EDIT_REQUEST"]
  }
}
```

`access` expires after 60 minutes, `refresh` after 7 days (change in `.env`).

### 4.2 Horses

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/horses?RegistrationStatus=&OwnerID=&search=` | all roles | `search` matches name, code, microchip |
| GET | `/horses/{HorseID}` | all roles | includes `HealthSummary` |
| POST | `/horses` | Owner, Manager | creates a `Draft` |
| PATCH | `/horses/{HorseID}` | Owner (own horse), Manager | only when `Draft` / `Rejected`; send the fields to change |
| POST | `/horses/{HorseID}/submit` | Owner, Manager | `Draft`/`Rejected` → `Submitted` |
| POST | `/horses/{HorseID}/verify` | Manager | `Submitted` → `PendingExam` |
| POST | `/horses/{HorseID}/reject` | Manager | `{"Reason"}`; `Submitted`/`PendingExam` → `Rejected` |
| POST | `/horses/{HorseID}/approve` | Manager | `{"HorseCode", "StallID"?, "ManagerNote"?}`; `PendingExam` → `Approved` |
| POST | `/horses/{HorseID}/archive` | Manager | `{"Reason"}`; `Approved` → `Archived` |
| GET | `/horses/{HorseID}/registration-requests` | can view the horse | history of submissions, rejection reasons |
| GET | `/horses/{HorseID}/audit-logs` | Manager | action history |
| GET | `/stalls?Status=Available` | Manager, staff | pick a stall when approving (see also section 4.6) |

Body of `POST /horses`:

```json
{
  "HorseName": "Thunder", "Breed": "Thoroughbred", "DateOfBirth": "2021-03-10",
  "CoatColor": "Bay", "Gender": "Male", "SireName": "Storm King", "DamName": "Lady Rain",
  "MicrochipNumber": "985000000000001", "PassportNumber": "VN-001",
  "ClubID": 1
}
```

**All profile fields are required** (no `null` / empty string), on `POST /horses` and when changed with `PATCH`
or a profile change request. A 400 error names the exact field and the reason:

| Field | Rule | Example error (`detail` in Vietnamese) |
|---|---|---|
| `HorseName`, `Breed`, `CoatColor`, `SireName`, `DamName` | not empty | `{"Breed": ["Cần nhập giống ngựa (Breed)."]}` |
| `DateOfBirth` | `YYYY-MM-DD`, not in the future, not older than 40 years | `{"DateOfBirth": ["Ngày sinh không được ở tương lai."]}` |
| `Gender` | `Male`, `Female` or `Gelding` | `{"Gender": ["Giới tính phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến)."]}` |
| `MicrochipNumber` | exactly **15 digits** (ISO 11784/11785; the first 3 digits are the country or manufacturer code), spaces are removed; unique | `{"MicrochipNumber": ["Số microchip phải gồm đúng 15 chữ số ..."]}` |
| `PassportNumber` | letters, digits, `-` or `/`, 5–50 characters, saved in upper case; unique | `{"PassportNumber": ["Số hộ chiếu / đăng ký đã được dùng cho một ngựa khác."]}` |
| `SireName`, `DamName` | different from the horse's own name and from each other | `{"SireName": ["Tên ngựa cha không được trùng tên chính con ngựa này."]}` |

- **Owner registers themselves**: send `ClubID`; `OwnerID` = themselves.
- **Manager enters on the owner's behalf**: send `OwnerID` (a `HORSE_OWNER` account); `ClubID` = the Manager's club.

Returned horse (`GET /horses/1`):

```json
{
  "HorseID": 1, "ClubID": 1, "OwnerID": 5,
  "HorseName": "Thunder", "Breed": "Thoroughbred", "DateOfBirth": "2021-03-10", "CoatColor": "Bay",
  "Gender": "Male", "SireName": "Storm King", "DamName": "Lady Rain",
  "MicrochipNumber": "985000000000001", "PassportNumber": "VN-001",
  "HorseCode": "EQ-001", "VerifiedBy": 1, "VerifiedAt": "2026-10-10T09:00:00",
  "RegistrationStatus": "Approved", "CurrentHealthStatus": "Healthy",
  "ArchivedAt": null, "ArchivedBy": null, "ArchiveReason": null,
  "CreatedAt": "2026-10-10T08:00:00", "UpdatedAt": "2026-10-10T10:00:00",
  "SexClass": "Stallion",
  "InitialExamSigned": true,
  "Owner": {"UserID": 5, "FullName": "Hoàng Gia Huy", "Email": "owner@equi.local", "Phone": "0918034567",
            "Address": "86 Nguyễn Văn Trỗi, Phường 8, Quận Phú Nhuận, TP. Hồ Chí Minh"},
  "CurrentStall": {"StallID": 1, "StallNumber": "A01", "StartDate": "2026-10-10"},
  "HealthSummary": {
    "MedicalRecordID": 1, "ExamDate": "2026-10-10T09:30:00", "ExamType": "Initial Exam",
    "HealthStatus": "Healthy", "TrainingEligibility": "Eligible",
    "Conclusion": "Eligible for intake", "RestrictionNote": null, "FollowUpDate": null
  }
}
```

`GET /horses` returns an array of horses in the same shape but **without** `HealthSummary`.
Every action API (`submit`, `verify`, `approve`...) returns the horse after the update; the frontend can use it directly to redraw the screen.

Approval conditions (`approve`): the Vet has signed the intake examination record for the current submission,
`HealthStatus` is `Healthy` or `Monitor`, and `TrainingEligibility` is not `Not Eligible`.

### 4.3 Documents

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/horses/{HorseID}/documents` | can view the horse | Owner only sees documents with `IsVisibleToOwner: true` |
| POST | `/horses/{HorseID}/documents` | Owner (own horse), Manager | **Upload a file**: `multipart/form-data` with `File` (PDF / JPG / PNG / WEBP, max `UPLOAD_MAX_MB` = 10 MB), `DocumentType`, `DocumentName`? (default = file name), `IsVisibleToOwner`? (Manager only). Or JSON link: `{"DocumentName", "DocumentType", "FileUrl", "IsVisibleToOwner"?}`. Response has `IsUploadedFile`; for uploads `FileUrl` = `/api/horse-documents/{DocumentID}/file` |
| GET | `/horse-documents/{DocumentID}/file` | can view the horse | File content (needs the `Authorization` header, so the FE downloads it with `fetch` then opens a blob URL). `?download=1` = save as attachment |
| DELETE | `/horse-documents/{DocumentID}` | Owner (own upload, horse in Draft / Rejected), Manager | **204**. 409 `INVALID_STATUS` after submit (owner), 409 `DOCUMENT_IN_USE` if it is evidence of a profile change request |

`DocumentType`: `Passport`, `Microchip Certificate`, `Ownership Proof`, `Handover Record`, `Contract`, `Other`.
Uploaded files are stored on the backend server (`MEDIA_ROOT`, default `backend/media/`, never committed). A JSON link (`FileUrl`, e.g. a Google Drive link) is still accepted for files kept elsewhere.

### 4.4 Examinations (Vet)

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/vet/pending-initial-exams` | Vet | `PendingExam` horses in the club without a signed intake examination record |
| GET | `/horses/{HorseID}/medical-records` | club staff | The Vet also sees draft records; others only see signed records. Owners view `HealthSummary` |
| POST | `/horses/{HorseID}/medical-records` | Vet | creates a draft record |
| GET | `/medical-records/{MedicalRecordID}` | club staff | |
| PATCH | `/medical-records/{MedicalRecordID}` | Vet who created the record | while still `Draft` |
| DELETE | `/medical-records/{MedicalRecordID}` | Vet who created the record | while still `Draft` |
| POST | `/medical-records/{MedicalRecordID}/sign` | Vet who created the record | signs the record (`Signed`), updates `Horse.CurrentHealthStatus` |
| GET | `/medical-records/{MedicalRecordID}/amendments` | club staff | |
| POST | `/medical-records/{MedicalRecordID}/amendments` | Vet | `{"Reason", "AmendedContent"}`; only for signed records |

Vets examine **on duty**: no Vet is assigned in advance; any Vet in the club can pick up a horse from the queue.
Each submission has only **one** intake examination record; a non-`null` `DraftMedicalRecordID` means a Vet has an examination in progress.

Body for creating a record:

```json
{
  "ExamType": "Initial Exam",
  "WeightKg": 480.5, "HeightCm": 162.0,
  "Symptoms": "No abnormal signs",
  "Diagnosis": "Normal",
  "Conclusion": "Eligible for intake",
  "TreatmentPlan": null,
  "HealthStatus": "Healthy",
  "TrainingEligibility": "Eligible",
  "RestrictionNote": null,
  "FollowUpDate": null,
  "Note": "Purpose of exam: intake into the club"
}
```

- `ExamType`: `Initial Exam` (only when `PendingExam`), `Routine Exam`, `Injury Exam`, `Follow-up`, `Emergency` (only when the horse is `Approved`).
- Leaving `ExamDate` empty = the current time.
- When signing, `HealthStatus` and `TrainingEligibility` are required; if `Restricted`, `RestrictionNote` is required.
- Record `HealthStatus`: `Healthy`, `Monitor`, `Injured`, `Recovering`, `Isolated`.
- `TrainingEligibility`: `Eligible`, `Restricted`, `Not Eligible`.

Returned record:

```json
{
  "MedicalRecordID": 1, "HorseID": 1, "HorseName": "Thunder", "VetID": 2, "VetName": "Demo Veterinarian",
  "RegistrationRequestID": 1, "TrainingSessionID": null,
  "ExamType": "Initial Exam", "ExamDate": "2026-10-10T09:30:00",
  "WeightKg": 480.5, "HeightCm": 162.0,
  "Symptoms": "No abnormal signs", "Diagnosis": "Normal", "Conclusion": "Eligible for intake",
  "InjuryLocation": null, "TreatmentPlan": null,
  "HealthStatus": "Healthy", "TrainingEligibility": "Eligible", "RestrictionNote": null,
  "FollowUpDate": null, "Note": null,
  "RecordStatus": "Signed", "SignedAt": "2026-10-10T09:45:00"
}
```

### 4.5 Profile change requests (after `Approved`)

| Method | URL | Used by | Notes |
|---|---|---|---|
| POST | `/horses/{HorseID}/profile-change-requests` | The horse's Owner | `{"Changes": {"CoatColor": "Dark Bay"}, "Reason", "EvidenceDocumentID"?}` |
| GET | `/profile-change-requests?Status=Pending&HorseID=` | Manager (own club), Owner (own requests) | |
| GET | `/profile-change-requests/{id}` | same as above | |
| POST | `/profile-change-requests/{id}/approve` | Manager | `{"ReviewNote"?}`; the backend applies the changes to the horse |
| POST | `/profile-change-requests/{id}/reject` | Manager | `{"ReviewNote"}` required |

Fields that can be requested for change: `HorseName`, `Breed`, `DateOfBirth`, `CoatColor`, `Gender`, `SireName`, `DamName`, `MicrochipNumber`, `PassportNumber`.
Each horse can have only 1 `Pending` request at a time.

```json
{
  "ProfileChangeRequestID": 1, "HorseID": 1, "HorseName": "Thunder",
  "RequestedBy": 5, "RequestedAt": "2026-10-11T08:00:00",
  "ChangedFields": {
    "Reason": "Coat color changed with age",
    "Changes": [{"Field": "CoatColor", "OldValue": "Bay", "NewValue": "Dark Bay"}]
  },
  "EvidenceDocumentID": 1, "Status": "Pending",
  "ReviewedBy": null, "ReviewedAt": null, "ReviewNote": null
}
```

### 4.6 Stalls

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/stalls?Status=` | Manager, staff | includes `CurrentHorse` (the horse currently in the stall) |
| POST | `/stalls` | Manager | `{"StallNumber": "A05", "StallType": "Standard"}` |
| PATCH | `/stalls/{StallID}` | Manager | `{"StallType"?, "Status": "Maintenance" \| "Available"}`; a stall that currently has a horse cannot change status (`STALL_OCCUPIED`) |
| POST | `/horses/{HorseID}/move-stall` | Manager | `{"StallID": 3}` – move stall (the old stall automatically returns to `Available`) |

`Status = Occupied` is set automatically by the backend when a horse is placed in a stall; the frontend does not send this value.

```json
{"StallID": 1, "ClubID": 1, "StallNumber": "A01", "StallType": "Standard", "Status": "Occupied",
 "CurrentHorse": {"HorseID": 1, "HorseName": "Thunder", "StartDate": "2026-10-10"}}
```

Archiving a horse (`POST /horses/{id}/archive`) now also: ends the trainer assignment (unfinished training plans → `Cancelled`,
`Assigned` training sessions → `Cancelled`), pending care tasks → `Skipped`, active diet plans → `Expired`.

## 5. Flow 2 – Training

```
Head Trainer assesses the horse ──> assigns 1 responsible Trainer ──> Trainer drafts the training plan ──> Head Trainer approves
──> responsible Trainer schedules training sessions (Work Rider, Substitute Trainer if needed; Head Trainer can do it for any horse)
──> Work Rider starts, records the result ──> (Substitute records an observation) ──> responsible Trainer reviews
──> if adjustment is needed, create a new training plan version
──> at the end of each stage the Trainer closes the stage ──> the horse owner receives the stage summary (5.7)
```

Only `Approved` horses can enter training. All Flow 2 APIs require the `HORSE_VIEW` permission to view (club staff).

### 5.1 Specializations, Trainers, trainer profile

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/specializations` | everyone | `Flat Racing`, `Steeplechase / Hurdle Racing`, `Harness Racing`, `Endurance / Long-distance Racing`, `Other` |
| GET | `/trainers?SpecializationID=` | Head Trainer, Manager | trainers in the club: specializations, **profile** (see table below) and number of horses currently assigned |
| GET | `/trainers?HorseID=` | Head Trainer, Manager | **trainer suggestions for a horse** (see below): suitable trainers first |
| GET | `/trainers/{UserID}` | Head Trainer, Manager, the trainer themself | same fields + `ActiveHorses`, `Credentials`, `RecentRaceResults` (last 10) |
| PATCH | `/trainers/{UserID}/profile` | Head Trainer, Manager | `{"CareerStartDate"?, "TrainerRating"?}` |
| GET / POST | `/trainers/{UserID}/credentials` | view: as above · add: Head Trainer, Manager | degrees, certificates, licences, awards |
| DELETE | `/trainer-credentials/{CredentialID}` | Head Trainer, Manager | |
| GET / POST | `/trainers/{UserID}/race-results?From=&To=` | view: as above · add: Head Trainer, Manager | each time a horse prepared by the trainer ran a race |
| DELETE | `/trainer-race-results/{RaceResultID}` | Head Trainer, Manager | remove a wrong entry |
| POST | `/trainers/{UserID}/specializations` | Head Trainer, Manager | `{"SpecializationID": 1}` – assign a specialization to a trainer |
| DELETE | `/trainers/{UserID}/specializations/{SpecializationID}` | Head Trainer, Manager | cannot be deleted if already used in a trainer assignment (`IN_USE`) |

```json
[{"UserID": 4, "FullName": "Phạm Quốc Bảo", "Email": "trainer@equi.local", "Phone": "0938452116",
  "Specializations": [{"SpecializationID": 1, "SpecializationName": "Flat Racing"}],
  "CareerStartDate": "2013-06-01", "YearsOfExperience": 13, "ExperienceLevel": "Expert", "ExperienceLevelName": "Chuyên gia",
  "Seniority": 12, "SenioritySince": "2014-03-10", "QualificationCount": 2, "AwardCount": 2,
  "CareerStarts": 240, "CareerWins": 58, "CareerWinRate": 24.2, "RecentStarts": 40, "RecentWins": 9,
  "WinRate": 22.5, "PlaceRate": 45.0, "WinRateNote": null, "TrainerRating": 4.6, "ActiveHorseCount": 2, "HasProfile": true}]
```

Every number is **computed** from what is recorded, nothing is typed in by hand:

| Field | How it is computed |
|---|---|
| `YearsOfExperience` | full years since `CareerStartDate` (the day the trainer started the profession) – grows by itself every year |
| `ExperienceLevel` | from `YearsOfExperience`: 0–2 `Junior`, 3–5 `Intermediate`, 6–10 `Senior`, more than 10 `Expert` (`ExperienceLevelName` = Vietnamese name) |
| `Seniority` | **proven** professional seniority: full years since the earliest `Degree` / `Certificate` / `License` (`SenioritySince`); `null` if none recorded. `QualificationCount`, `AwardCount` = number of those papers / awards |
| `WinRate` | like the "strike rate" used in racing: wins / starts in the **last 12 months** (`RecentWins` / `RecentStarts`), %. `null` with `WinRateNote` when there are fewer than **10** starts in 12 months (too few to be meaningful) |
| `PlaceRate` | finishes in the top 3 / starts in the last 12 months (same 10-start rule) |
| `CareerStarts`, `CareerWins`, `CareerWinRate` | the whole career (all race results) |
| `TrainerRating` | 0–5 (1 decimal) given by the Head Trainer / Manager, `null` = not rated |
| `HasProfile` | `false` = profile not entered yet |

Example on screen: *Phạm Quốc Bảo – Flat Racing – Kinh nghiệm: 13 năm – Cấp độ: Expert – Đang phụ trách: 2 ngựa*.

Credential body: `{"CredentialType": "Degree" | "Certificate" | "License" | "Award", "Title", "IssuedBy"?, "IssuedDate",
"ExpiryDate"?, "FileUrl"? (link to the scanned paper), "Note"?}`. An award does not count towards `Seniority`.

Race result body: `{"RaceDate", "RaceName", "RaceClass"? ("Group 1", "Group 2", "Group 3", "Listed", "Handicap",
"Maiden", "Other"), "HorseID"? (horse of the club) or "HorseName" (horse from outside), "FinishPosition", "FieldSize", "Note"?}`;
`FinishPosition` must be between 1 and `FieldSize` (at least 2 horses), the date cannot be in the future.

**Trainer suggestions** `GET /trainers?HorseID=5` use the horse's latest `Recommended` assessment (5.2):

- the trainer must have the recommended specialization;
- minimum level by `QualityScore` (a better horse aiming at bigger races needs a more experienced trainer):
  `≥ 85` → `Senior` or higher, `≥ 70` → `Intermediate` or higher, lower / not scored → any level;
- each row gets `IsSuggested`, `MatchesSpecialization`, `MatchesLevel`, `RequiredLevel` and `SuggestionReason`
  (Vietnamese sentence to show); order: suggested first, then higher level, fewer active horses, higher rating.

The trainer must have a specialization (`TrainerSpecialization`) matching the specialization of the assignment (a foreign key constraint in SQL).
The level is only a suggestion: `POST /trainer-assignments` still accepts a lower-level trainer but returns
`LevelWarning` (see 5.3).

### 5.2 Horse assessment

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/horses/{HorseID}/assessments` | staff | newest first |
| POST | `/horses/{HorseID}/assessments` | Head Trainer | `{"SpecializationID", "QualityScore"? (0–100), "FitnessLevel"?, "AssessmentNote"?, "DecisionStatus"?}` |

- `FitnessLevel`: `Excellent`, `Good`, `Average`, `Needs Monitoring`.
- `DecisionStatus`: `Recommended` (default, suitable) or `Rejected` (not suitable). A new `Recommended` assessment
  moves older `Recommended` assessments **of the same specialization** to `Superseded`.

### 5.3 Trainer assignment

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/trainer-assignments?HorseID=&TrainerID=&Status=Active&mine=1` | staff | `mine=1`: a trainer sees the horses assigned to them |
| GET | `/trainer-assignments/{id}` | staff | |
| POST | `/trainer-assignments` | Head Trainer | `{"HorseID", "TrainerID", "SpecializationID", "AssessmentID"?, "StartDate"?, "AssignmentNote"?}` |
| POST | `/trainer-assignments/{id}/end` | Head Trainer | `{"Reason"?}` – ends the assignment; unfinished training plans and `Assigned` training sessions are cancelled |

Each horse has only **1** `Active` responsible trainer (`ALREADY_ASSIGNED` if one exists; to change, `end` it and then assign a new one).

```json
{"TrainerHorseAssignmentID": 1, "HorseID": 1, "HorseName": "Thunder", "TrainerID": 4, "TrainerName": "Demo Trainer",
 "SpecializationID": 1, "SpecializationName": "Flat Racing", "AssignedByHeadTrainerID": 2, "AssignedByName": "Demo Head Trainer",
 "AssessmentID": 1, "StartDate": "2026-10-10", "EndDate": null, "Status": "Active", "AssignmentNote": null}
```

`POST /trainer-assignments` also returns `TrainerExperienceLevel`, `RequiredLevel` and `LevelWarning`
(`null`, or a sentence when the horse should go to a more experienced trainer – the assignment is still created).

### 5.4 Preferred work riders (familiar with the horse)

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/horses/{HorseID}/work-rider-preferences?all=1` | staff | by default returns only preferences still in effect |
| POST | `/horses/{HorseID}/work-rider-preferences` | responsible Trainer, Head Trainer | `{"WorkRiderID", "Priority"? (1 = highest priority), "Note"?}` |
| POST | `/work-rider-preferences/{PreferenceID}/end` | responsible Trainer, Head Trainer | |

Only used as suggestions when scheduling training sessions; each session still selects its own Work Rider.

### 5.5 Training plans

```
Draft ──submit──> Pending Approval ──approve──> Active ──complete──> Completed
  ^                      │ return (ReviewNote required)
  └──────────────────────┘
Draft / Pending Approval / Active ──cancel──> Cancelled
Active ──revise──> new Draft version; when the new version is approved, the old one becomes Completed automatically
```

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/training-plans?HorseID=&TrainerID=&Status=&mine=1` | staff | `Status=Pending Approval` for the Head Trainer's approval screen |
| GET | `/training-plans/{id}` | staff | includes `Stages` |
| POST | `/training-plans` | responsible Trainer | creates a `Draft`, can send `Stages` at the same time |
| PATCH | `/training-plans/{id}` | responsible Trainer | only when `Draft`; `Goal`, `StartDate`, `EndDate`, `OverallIntensity`, `Note` |
| POST | `/training-plans/{id}/stages` | responsible Trainer | add a stage (when `Draft`) |
| PATCH / DELETE | `/training-plan-stages/{TrainingPlanStageID}` | responsible Trainer | when `Draft` |
| POST | `/training-plans/{id}/submit` | responsible Trainer | requires at least 1 stage (`NO_STAGES`) |
| POST | `/training-plans/{id}/approve` | Head Trainer | `{"ReviewNote"?}` → `Active` |
| POST | `/training-plans/{id}/return` | Head Trainer | `{"ReviewNote"}` → back to `Draft` |
| POST | `/training-plans/{id}/complete` | responsible Trainer, Head Trainer | remaining `Assigned` sessions are cancelled |
| POST | `/training-plans/{id}/cancel` | responsible Trainer, Head Trainer | `{"Reason"?}` |
| POST | `/training-plans/{id}/revise` | responsible Trainer | copies an `Active`/`Completed` training plan into a new `Draft` version for adjustment |
| POST | `/training-plan-stages/{TrainingPlanStageID}/close` | responsible Trainer, Head Trainer | `{"SummaryNote"?}` close a stage → stage summary sent to the horse owner (bell + email). Returns the stage summary (5.7) |

Closing a stage: the training plan must be `Active` / `Completed`, the stage must have started (`NOT_STARTED`), not be closed yet
(`ALREADY_CLOSED`) and have no `Assigned` / `In Progress` sessions left (`SESSIONS_PENDING`: finish, cancel or mark them missed).
When the stage end date has passed and it is still open, the Trainer and Head Trainer see `STAGE_TO_CLOSE` in notifications.
Completing a training plan closes its started stages automatically and sends the plan summary to the owner.
Each stage in `Stages` also returns `ClosedAt`, `ClosedByID`, `ClosedByName`, `SummaryNote`.

Body `POST /training-plans`:

```json
{
  "HorseID": 1, "Goal": "Prepare for the December race", "StartDate": "2026-10-12", "EndDate": "2026-12-10",
  "OverallIntensity": "Moderate", "Note": null,
  "Stages": [
    {"StageName": "Foundation", "StartDate": "2026-10-12", "EndDate": "2026-11-01", "Intensity": "Low",
     "TrainingLoad": 30, "DistanceTargetKm": 3, "Surface": "Turf", "Goal": "Familiarization", "Note": null},
    {"StageName": "Speed build-up", "StartDate": "2026-11-02", "Intensity": "High", "TrainingLoad": 70}
  ]
}
```

- `OverallIntensity`, `Intensity`: `Low`, `Moderate`, `High`, `Very High`.
- `StageOrder` left empty = auto-numbered 1, 2, 3...; stages must fall within the training plan's period.
- If the horse has a `Full` lock overlapping the training plan's period, the plan cannot be approved (`TRAINING_LOCK_FULL`).

Returned training plan:

```json
{
  "TrainingPlanID": 1, "TrainerHorseAssignmentID": 1, "HorseID": 1, "HorseName": "Thunder",
  "TrainerID": 4, "TrainerName": "Demo Trainer", "Goal": "Prepare for the December race",
  "StartDate": "2026-10-12", "EndDate": "2026-12-10", "OverallIntensity": "Moderate", "Note": null,
  "Status": "Active", "CreatedAt": "2026-10-10T08:00:00", "SubmittedAt": "2026-10-10T08:05:00",
  "ApprovedByHeadTrainerID": 2, "ApprovedAt": "2026-10-10T09:00:00", "ReviewNote": "Agreed",
  "Stages": [{"TrainingPlanStageID": 1, "TrainingPlanID": 1, "StageName": "Foundation", "StageOrder": 1, "Goal": null,
              "StartDate": "2026-10-12", "EndDate": "2026-11-01", "Intensity": "Low", "TrainingLoad": 30.0,
              "DistanceTargetKm": 3.0, "Surface": "Turf", "Note": null}]
}
```

Specific error codes: `NOT_PLAN_OWNER` (not the currently assigned trainer), `NO_STAGES`, `DRAFT_EXISTS` (a version is already being drafted / pending approval),
`ASSIGNMENT_ENDED`, `IN_USE` (the stage already has training sessions).

### 5.6 Training sessions

```
Assigned ──start (Work Rider, on the session day)──> In Progress ──result (Work Rider)──> Completed
Assigned / In Progress ──stop (supervising trainer, responsible Trainer, Head Trainer) / cancel──> Cancelled
Assigned / In Progress ──missed (from the session day onward)──> Missed
```

Who schedules: the **responsible Trainer** for the horses they are in charge of, the **Head Trainer** for every horse
(exceptions: trainer absent, urgent rider change). Another Trainer gets `403`. `AssignedByHeadTrainerID` stores whoever
scheduled the session (column name kept for compatibility). `stop` = the horse has a problem (the owner is alerted);
`cancel` = ordinary cancellation (weather, schedule change).

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/training-sessions?Date=&From=&To=&HorseID=&TrainingPlanID=&WorkRiderID=&Status=&mine=1` | staff | `mine=1`: Work Rider → sessions they ride; Trainer → sessions they supervise (responsible or Substitute) |
| GET | `/training-sessions/{id}` | staff | |
| POST | `/training-sessions` | responsible Trainer, Head Trainer | schedule a training session (the training plan must be `Active`) |
| PATCH | `/training-sessions/{id}` | responsible Trainer, Head Trainer | when `Assigned`: change Work Rider, Substitute, date/time, intensity... |
| POST | `/training-sessions/{id}/start` | the session's Work Rider | on the session day |
| POST | `/training-sessions/{id}/result` | the session's Work Rider | record the result → `Completed` |
| POST | `/training-sessions/{id}/substitute-observation` | the session's Substitute Trainer | `{"SubstituteObservation"}` (required for substitute-supervised sessions) |
| POST | `/training-sessions/{id}/stop` | supervising trainer, responsible Trainer, Head Trainer | `{"Reason", "ReportHealth"?, "Severity"?, "Description"?}`; the owner gets an urgent alert + email |
| POST | `/training-sessions/{id}/cancel` | responsible Trainer, Head Trainer | `{"Reason"?}` |
| POST | `/training-sessions/{id}/missed` | responsible Trainer, Head Trainer | `{"Reason"?}` |
| POST | `/training-sessions/{id}/review` | responsible Trainer | review a `Completed` session (once per session) |
| GET | `/training-reviews?AdjustmentRequired=1&HorseID=&Days=14` | staff | Head Trainer tracks training plan adjustment requests |
| GET | `/training-dashboard?HorseID=` | staff | overview screen before scheduling (same as the `vw_HorseTrainingDashboard` view) |

Body `POST /training-sessions`:

```json
{
  "TrainingPlanStageID": 1, "WorkRiderID": 5, "SubstituteTrainerID": null,
  "SessionDate": "2026-10-12", "StartTime": "06:00", "EndTime": null, "SequenceNo": null,
  "TrainingType": "Canter", "DurationPlannedMinutes": 45, "DistancePlannedKm": 3.5, "TargetSpeedKmh": 30,
  "TrainingLoad": 30, "Surface": "Turf", "Location": "Track no. 2", "Instructions": "Warm up for 10 minutes"
}
```

- `SubstituteTrainerID`: `null` = the responsible trainer supervises. Choose another Trainer (or the Head Trainer supervises)
  when the responsible trainer is busy. If it is the same as the responsible trainer, the backend treats it as `null`.
- `SequenceNo` left empty = the next slot in the Work Rider's day (`RIDER_SLOT_TAKEN` if it conflicts).
- Cannot schedule on a past date; the session date must fall within the stage.
- **Training Lock**: `Full` → cannot schedule / start (`TRAINING_LOCK_FULL`); `Restricted` → `TrainingLoad` is required
  and must not exceed `MaxIntensity` (`TRAINING_LOCK_RESTRICTED`). The scheduling screen should call `/training-dashboard` to show restrictions.

Body `POST /training-sessions/{id}/result`:

```json
{
  "ActualDurationMinutes": 44, "ActualDistanceKm": 3.4, "AvgSpeedKmh": 28.5, "MaxSpeedKmh": 41,
  "AvgHeartRate": 150, "MaxHeartRate": 190, "RecoveryMinutes": 12, "PerformanceScore": 78,
  "RiderObservation": "Slightly heavy on the right leg at the end of the session", "VideoUrl": null
}
```

Body `POST /training-sessions/{id}/review`:

```json
{"Evaluation": "Good", "TrainerComment": "Fine", "AdjustmentRequired": true, "AdjustmentNote": "Reduce distance next week"}
```

`Evaluation`: `Excellent`, `Good`, `Average`, `Needs Improvement`. If `AdjustmentRequired: true`, `AdjustmentNote` is required
and the Head Trainer sees it in notifications.

Returned training session (same as the `vw_WorkRiderDailySchedule` view, plus result and review):

```json
{
  "TrainingSessionID": 1, "TrainingPlanStageID": 1, "TrainingPlanID": 1, "StageName": "Foundation",
  "HorseID": 1, "HorseName": "Thunder", "HorseCode": "EQ-001",
  "WorkRiderID": 5, "WorkRiderName": "Demo Work Rider", "AssignedByHeadTrainerID": 2,
  "SubstituteTrainerID": 6, "AssignedTrainerID": 4, "AssignedTrainerName": "Demo Trainer",
  "SupervisingTrainerID": 6, "SupervisingTrainerName": "Trainer B", "IsSubstitute": true,
  "SessionDate": "2026-10-12", "StartTime": "06:00:00", "EndTime": "06:45:00", "SequenceNo": 1,
  "TrainingType": "Canter", "DurationPlannedMinutes": 45, "DistancePlannedKm": 3.5, "TargetSpeedKmh": null,
  "TrainingLoad": 30.0, "Surface": "Turf", "Location": "Track no. 2", "Instructions": "Warm up for 10 minutes",
  "Status": "Completed",
  "Result": {"TrainingResultID": 1, "TrainingSessionID": 1, "ActualDurationMinutes": 44, "ActualDistanceKm": 3.4,
             "AvgSpeedKmh": 28.5, "MaxSpeedKmh": 41.0, "AvgHeartRate": 150, "MaxHeartRate": 190, "RecoveryMinutes": 12,
             "PerformanceScore": 78.0, "RiderObservation": "Slightly heavy on the right leg at the end of the session", "VideoUrl": null,
             "SubstituteObservation": "The horse ran steadily", "RecordedAt": "2026-10-12T06:50:00"},
  "Review": null
}
```

Specific error codes: `PLAN_NOT_ACTIVE`, `RIDER_SLOT_TAKEN`, `NOT_SESSION_RIDER`, `WRONG_DAY`, `NOT_SUBSTITUTE`,
`NOT_ASSIGNED_TRAINER`, `ALREADY_REVIEWED`, `NOT_YET` (marking a session as missed before its date).

`GET /training-dashboard`:

```json
[{"HorseID": 1, "HorseCode": "EQ-001", "HorseName": "Thunder", "Gender": "Male", "SexClass": "Stallion",
  "CurrentHealthStatus": "Recovering", "TrainerHorseAssignmentID": 1, "TrainerID": 4, "TrainerName": "Demo Trainer",
  "SpecializationName": "Flat Racing", "ActiveTrainingPlanID": 1,
  "IsTrainingLocked": true, "TrainingLockID": 3, "LockLevel": "Restricted", "MaxIntensity": 25.0, "LockEndDate": null,
  "LatestTrainingDate": "2026-10-12", "LatestPerformanceScore": 78.0, "LatestActualDistanceKm": 3.4,
  "LatestAvgSpeedKmh": 28.5, "LatestAvgHeartRate": 150, "LatestRecoveryMinutes": 12}]
```

### 5.7 Horse owner: training results

The owner (`OWNER_VIEW`) only sees **their own horses**, only training plans that were approved, and:
- `Completed` sessions **after the responsible Trainer reviewed them** (overview + detail);
- `Cancelled` / `Missed` sessions that are due, with the reason (no numbers);
- never: sessions not yet done / in progress / not reviewed, the Substitute Trainer's observation.

Summaries follow the **stages of the training plan** (not weeks / months). A running stage shows numbers "as of today" (`AsOf`);
when the Trainer closes it (5.5) the owner receives the stage summary; when the plan ends, the plan summary.
Result numbers in summaries only count reviewed sessions (what the owner can see).

| Method | URL | Notes |
|---|---|---|
| GET | `/owner/horses/{HorseID}/training-plans` | approved training plans (newest first) with the overall `Summary` |
| GET | `/owner/training-plans/{TrainingPlanID}` | plan summary + `Stages` (each with `Summary`, `ComparedToPreviousStage`, `SummaryNote`) |
| GET | `/owner/horses/{HorseID}/training-sessions?From=&To=&TrainingPlanID=&TrainingPlanStageID=` | session overview list (newest first) |
| GET | `/owner/training-sessions/{TrainingSessionID}` | session detail; `404` if the session is not reviewed yet |

Session overview (list) – detail adds the fields after `Reason`:

```json
{"TrainingSessionID": 1, "SessionDate": "2026-10-17", "StartTime": "06:00:00", "TrainingType": "Canter",
 "TrainingPlanID": 1, "TrainingPlanStageID": 1, "StageName": "Làm quen", "Status": "Completed",
 "DurationMinutes": 47, "DistanceKm": 5.2, "PerformanceScore": 82.0, "Evaluation": "Excellent",
 "IsStopped": false, "Reason": null,
 "HorseID": 3, "HorseName": "Hắc Long", "TrainerName": "Phạm Quốc Bảo", "WorkRiderName": "Võ Thanh Tùng",
 "Surface": "Turf", "Location": "Track no. 2", "DurationPlannedMinutes": 45, "DistancePlannedKm": 5.0, "TargetSpeedKmh": 40.0,
 "AvgSpeedKmh": 41.3, "MaxSpeedKmh": 55.0, "AvgHeartRate": 152, "MaxHeartRate": 205, "RecoveryMinutes": 11,
 "RiderObservation": "Ngựa hơi mệt km cuối", "VideoUrl": "https://...", "TrainerComment": "Thích nghi tốt",
 "AdjustmentRequired": false, "AdjustmentNote": null, "ReviewedBy": "Phạm Quốc Bảo", "ReviewDate": "2026-10-17T09:15:00"}
```

`IsStopped: true` = stopped because the horse had a problem; `Status` is then `Cancelled` and `Reason` explains why.

`GET /owner/training-plans/{id}`:

```json
{"HorseID": 3, "HorseName": "Hắc Long", "HorseCode": "EQ-003",
 "TrainingPlanID": 1, "Goal": "Chuẩn bị giải tháng 12", "StartDate": "2026-10-17", "EndDate": "2026-11-26", "Status": "Active",
 "TrainerName": "Phạm Quốc Bảo", "SpecializationName": "Flat Racing", "ApprovedAt": "2026-10-17T08:00:00",
 "ProgressPercent": 12.5, "StageCount": 2, "CurrentStageName": "Làm quen",
 "Summary": {"From": "2026-10-17", "To": "2026-10-22", "PlannedSessions": 6, "CompletedSessions": 4, "ReviewedSessions": 4,
             "AwaitingReviewSessions": 0, "CancelledSessions": 1, "MissedSessions": 0, "UpcomingSessions": 1,
             "TotalDistanceKm": 20.4, "DistanceTargetKm": 50.0, "DistanceProgressPercent": 40.8, "TotalDurationMinutes": 180,
             "AvgDistancePerSessionKm": 5.1, "AvgSpeedKmh": 40.6, "MaxSpeedKmh": 55.0, "AvgPerformanceScore": 80.5,
             "AvgHeartRate": 151.0, "AvgRecoveryMinutes": 11.5,
             "Evaluations": {"Excellent": 1, "Good": 3, "Average": 0, "Needs Improvement": 0},
             "Health": {"TrainingLockCount": 0, "HealthReportCount": 0, "UrgentHealthReportCount": 0, "IsLockedNow": false,
                        "Text": "Bình thường"}},
 "Stages": [{"TrainingPlanStageID": 1, "StageOrder": 1, "StageName": "Làm quen", "Goal": null,
             "StartDate": "2026-10-17", "EndDate": "2026-10-30", "Intensity": "Low",
             "StageState": "InProgress", "IsOverdue": false, "AsOf": "2026-10-22",
             "ClosedAt": null, "ClosedByName": null, "SummaryNote": null,
             "Summary": {"...": "same fields as above"},
             "ComparedToPreviousStage": null}]}
```

- `StageState`: `NotStarted` (`Summary` = null), `InProgress` (numbers as of `AsOf`), `Closed`.
- `ComparedToPreviousStage`: differences of `AvgSpeedKmh`, `AvgPerformanceScore`, `AvgDistancePerSessionKm`, `AvgRecoveryMinutes`
  against the previous stage (positive = higher).
- `Health` is `null` until Flow 3 is installed.

Emails to the owner (only important events): plan approved, stage closed (stage summary), plan completed (plan summary),
session stopped (urgent); with Flow 3 also Training Lock created (urgent) / released.

## 6. Flow 3 – Medical

```
Groom / Work Rider / Trainer / Head Trainer reports an issue ──> Vet queue (Urgent first)
   (responsible Trainer and Head Trainer see it in notifications)
──> Vet takes the case ──> creates a medical record linked to the report ──> prescribes treatment ──> signs the record (+ Training Lock)
──> resolves the report ──> follow-up examination passes ──> release the lock
```

Medical records (`/horses/{id}/medical-records`, `/medical-records/...`) are shared with Flow 1, see section 4.4. Flow 3 adds:

| Item | Change |
|---|---|
| Create record | adds `"HealthReportID"` (which report the record handles) and `"TrainingSessionID"` (which training session the issue was found in) |
| `TrainingEligibility = Restricted` | must have `RestrictionNote` even when saving a draft (CHECK constraint in SQL) |
| Delete draft record | also deletes the treatments prescribed on the record and unlinks the health report |
| Sign record | optional body `{"TrainingLock": {...}}`; response additionally includes `TrainingLock` (see 6.3) |

### 6.1 Health reports

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/horses/{HorseID}/health-reports?open=1` | staff | **call this first when opening the report form**: if there is an open report, add a note instead of filing a duplicate |
| POST | `/horses/{HorseID}/health-reports` | Groom, Work Rider, Trainer, Head Trainer | `{"Severity": "Urgent" \| "Normal", "Description", "ImageUrl"?, "TrainingSessionID"?}` |
| GET | `/health-reports?open=1&Status=&Severity=&HorseID=&mine=1` | staff | `open=1`: Vet queue, `Urgent` first, then oldest first |
| GET | `/health-reports/{id}` | staff | includes `Notes` |
| POST | `/health-reports/{id}/notes` | anyone allowed to report, Vet | `{"Content"}` |
| POST | `/health-reports/{id}/take` | Vet | the on-duty Vet takes the case: `Reported` → `Reviewing` |
| POST | `/health-reports/{id}/resolve` | Vet | `{"VetNote"?, "MedicalRecordID"?}` (one of the two is required) → `Resolved` |

- An `Urgent` report linked to the `TrainingSessionID` of a session that is `In Progress` → the session stops automatically (`Cancelled`), and the response includes `"StoppedSession": true`.
- The supervising trainer can also stop the session and report at once: `POST /training-sessions/{id}/stop` with `"ReportHealth": true` (section 5.6).
- Vet creates a medical record with `"HealthReportID"` → the report is automatically linked to the record and moves to `Reviewing`. Each report is linked to 1 record (`REPORT_ALREADY_LINKED`).

```json
{
  "HealthReportID": 1, "HorseID": 1, "HorseName": "Thunder", "ReportedBy": 7, "ReportedByName": "Demo Groom",
  "ReportedByRoles": ["GROOM"], "TrainingSessionID": null, "ReportedAt": "2026-10-12T07:30:00",
  "Severity": "Normal", "Description": "Left front leg is slightly warm", "ImageUrl": null,
  "Status": "Reviewing", "VetID": 3, "VetName": "Demo Veterinarian", "MedicalRecordID": 2, "VetNote": null,
  "ResolvedAt": null,
  "Notes": [{"HealthReportNoteID": 1, "HealthReportID": 1, "NoteBy": 5, "NoteByName": "Demo Work Rider",
             "NoteAt": "2026-10-12T07:45:00", "Content": "Gait seemed slightly uneven during warm-up"}]
}
```

Specific error codes: `REPORT_RESOLVED`, `REPORT_ALREADY_LINKED`.

### 6.2 Treatments

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/medical-records/{id}/treatments` | staff | |
| POST | `/medical-records/{id}/treatments` | Vet who created the record (record still `Draft`) | `{"MedicineName", "Dose", "Route", "StartDate", "EndDate"?, "WithdrawalUntil"?, "Note"?}` |
| PATCH | `/treatments/{TreatmentID}` | Vet | draft record: the Vet who created it can edit freely; signed record: only `EndDate`, `WithdrawalUntil` |
| GET | `/horses/{HorseID}/treatments?WithdrawalActive=1` | staff | treatments still within the withdrawal period (doping check) |

`Route`: `Oral`, `Injection`, `Topical`, `Inhalation`, `Other`. Also returns `"WithdrawalActive": true/false`.

### 6.3 Training Lock

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/training-locks?HorseID=&LockStatus=Active` | staff | |
| GET | `/training-locks/{id}` | staff | |
| POST | `/horses/{HorseID}/training-locks` | Vet | `{"Reason", "LockLevel", "MaxIntensity"?, "LockStartDate"?, "LockEndDate"?, "Details"?}` |
| PATCH | `/training-locks/{id}` | Vet | change level, maximum intensity, expected release date |
| POST | `/training-locks/{id}/release` | Vet | `{"Note"?}` – requires a follow-up examination **signed after the lock** with a conclusion other than `Not Eligible` |

- `LockLevel`: `Full` (no training) or `Restricted` (`MaxIntensity` required, compared against the training session's `TrainingLoad`).
- Each horse has at most 1 `Active` lock (`LOCK_EXISTS` → use PATCH).
- Creating / tightening a lock → `Assigned` training sessions within the lock period are cancelled; the response includes `"CancelledSessionIDs": [..]`.
- **Signing a medical record** of a horse that has been taken in:
  - sending `{"TrainingLock": {...}}` → creates a lock (or updates the existing lock) accordingly;
  - not sending it with a `Not Eligible` conclusion → the backend automatically locks `Full` (or raises a `Restricted` lock to `Full`);
  - an `Eligible` conclusion does **not** release the lock automatically: the Vet releases it after the follow-up examination.

```json
{"TrainingLockID": 3, "HorseID": 1, "HorseName": "Thunder", "CreatedByVetID": 3, "CreatedByName": "Demo Veterinarian",
 "Reason": "Mild tendinitis", "LockLevel": "Restricted", "MaxIntensity": 25.0, "LockStartDate": "2026-10-12T09:00:00",
 "LockEndDate": null, "LockStatus": "Active", "Details": null, "ReleasedByVetID": null, "ReleasedAt": null,
 "CancelledSessionIDs": [12]}
```

Specific error codes: `LOCK_EXISTS`, `FOLLOW_UP_EXAM_REQUIRED`.

### 6.4 Vaccinations, medical schedules

| Method | URL | Used by | Notes |
|---|---|---|---|
| GET | `/vaccinations?HorseID=&Status=&DueWithinDays=14` | staff | `DueWithinDays`: upcoming / overdue vaccinations and upcoming boosters |
| GET / POST | `/horses/{HorseID}/vaccinations` | view: staff; create: Vet | `{"VaccineName", "VaccinationDate", "NextDueDate"?, "Status"?, "Note"?, "ExternalVet"?}` |
| PATCH | `/vaccinations/{id}` | Vet | e.g. `{"Status": "Completed", "NextDueDate": "2027-04-01"}` |
| GET | `/medical-schedules?From=&To=&HorseID=&Status=&ScheduleType=` | staff | |
| GET / POST | `/horses/{HorseID}/medical-schedules` | view: staff; create: Vet | `{"ScheduleType", "ScheduledDate", "Status"?, "Note"?, "ExternalVet"?}` |
| PATCH | `/medical-schedules/{id}` | Vet | |

- Vaccination `Status`: `Scheduled`, `Completed`, `Overdue`, `Cancelled`. Also returns `IsOverdue` (past the date but still `Scheduled`).
- `ScheduleType`: `Vaccination`, `Deworming`, `Farrier`, `Routine Examination`. `Status`: `Scheduled`, `Completed`, `Cancelled`, `Overdue`.
- `"ExternalVet": true` → external vet (no account), `VetID = null`. By default `VetID` = the currently logged-in Vet.

## 7. Flow 4 – Care and nutrition

### 7.1 Diet plans

```
Head Trainer creates (Pending) ──Vet approve──> Approved ──Vet adjust──> Adjusted
     ^                          │ Vet reject (VetNote required)
     └── Head Trainer edits ── Rejected
```

| Method | URL | Who uses it | Notes |
|---|---|---|---|
| GET | `/horses/{HorseID}/diet-plans` | staff | |
| POST | `/horses/{HorseID}/diet-plans` | Head Trainer | `{"DietDescription"?, "StartDate", "EndDate"?, "Meals": [...]}` (at least 1 meal) |
| GET | `/horses/{HorseID}/current-diet` | staff | diet plan in effect today (`null` if none) – the Groom's screen |
| GET | `/diet-plans?Status=Pending&HorseID=` | staff | Vet views diet plans awaiting approval |
| GET | `/diet-plans/{id}` | staff | |
| PATCH | `/diet-plans/{id}` | Head Trainer | when `Pending`/`Rejected`; sending `Meals` replaces all meals; after editing → `Pending` |
| POST | `/diet-plans/{id}/approve` | Vet | `{"VetNote"?}` (the creator cannot approve their own plan) |
| POST | `/diet-plans/{id}/reject` | Vet | `{"VetNote"}` |
| POST | `/diet-plans/{id}/adjust` | Vet | `{"VetNote", "Meals"?, "EndDate"?...}` – adjust the diet plan currently in effect |

```json
{"MealTime": "06:00", "FeedType": "Oats", "Quantity": 3, "Unit": "kg", "Note": null}
```

When a new diet plan is approved: an overlapping old plan that started earlier ends on the day before the new plan's start date;
one that starts on the same day / later becomes `Expired`. If the new plan starts in the future, the current plan stays in use until that day.

```json
{"DietPlanID": 1, "HorseID": 1, "HorseName": "Thunder", "CreatedByHeadTrainerID": 2, "CreatedByName": "Demo Head Trainer",
 "ReviewedByVetID": 3, "ReviewedByName": "Demo Veterinarian", "DietDescription": "Recovery diet",
 "StartDate": "2026-10-12", "EndDate": null, "Status": "Approved", "VetNote": null,
 "CreatedAt": "2026-10-10T08:00:00", "ApprovedAt": "2026-10-10T10:00:00",
 "Meals": [{"DietMealID": 1, "MealTime": "06:00:00", "FeedType": "Oats", "Quantity": 3.0, "Unit": "kg", "Note": null}]}
```

Specific error codes: `SELF_APPROVAL`.

### 7.2 Care tasks

| Method | URL | Who uses it | Notes |
|---|---|---|---|
| GET | `/care-tasks?Date=&From=&To=&HorseID=&GroomID=&Status=&mine=1` | staff | `mine=1`: tasks of the logged-in Groom |
| GET | `/care-tasks/{id}` | staff | |
| POST | `/care-tasks` | Head Trainer, Manager (assign); Groom (self-created) | `{"HorseID", "GroomID", "TaskType", "ScheduledAt", "Note"?}` – a Groom creating their own task omits `GroomID` |
| PATCH | `/care-tasks/{id}` | assigner / Groom who created it | when `Pending`; only Head Trainer / Manager can change `GroomID` |
| POST | `/care-tasks/{id}/complete` | assigned Groom | `{"Note"?}` → `Completed` |
| POST | `/care-tasks/{id}/skip` | Groom, assigner | `{"Reason"}` → `Skipped` |

`TaskType`: `Feeding`, `Cleaning`, `Bathing`, `Ice Leg Soak`. `AssignedBy = null` means the Groom created the task themselves.
If the horse looks abnormal during care → report it via section 6.1.

```json
{"CareTaskID": 1, "HorseID": 1, "HorseName": "Thunder", "GroomID": 7, "GroomName": "Demo Groom", "AssignedBy": 2,
 "AssignedByName": "Demo Head Trainer", "TaskType": "Ice Leg Soak", "ScheduledAt": "2026-10-12T15:00:00",
 "Status": "Pending", "CompletedAt": null, "Note": "20 minutes"}
```

Specific error codes: `NOT_TASK_OWNER`, `NOT_TASK_GROOM`.

### 7.3 Inventory

| Method | URL | Who uses it | Notes |
|---|---|---|---|
| GET | `/inventory-items?ItemType=&Status=&LowStock=1` | Manager, Groom, Head Trainer | |
| POST | `/inventory-items` | Manager | `{"ItemName", "ItemType", "Unit", "Quantity"?, "MinimumQuantity"?}` |
| PATCH | `/inventory-items/{id}` | Manager | `ItemName`, `ItemType`, `Unit`, `MinimumQuantity`; `"Status": "Inactive"` to discontinue, `"Reactivate": true` to reactivate |
| POST | `/inventory-items/{id}/stock` | Manager | `{"Change": 50, "Note"?}` – stock in (positive number) / adjust down (negative number) |
| GET | `/inventory-requests?Status=&mine=1` | Manager (whole club), Groom / Head Trainer (their own) | |
| POST | `/inventory-requests` | Groom, Head Trainer | `{"Reason"?, "Items": [{"InventoryItemID", "RequestedQuantity", "Note"?}]}` |
| POST | `/inventory-requests/{id}/approve` | Manager | `{"Items"?: [{"InventoryItemID", "ApprovedQuantity"}]}` – empty = approve in full; deducts stock |
| POST | `/inventory-requests/{id}/reject` | Manager | `{"Note"}` |
| POST | `/inventory-requests/{id}/cancel` | requester | while still `Pending` |

- `ItemType`: `Food`, `Medicine`, `Care Equipment`.
- Inventory item `Status` is computed automatically: `Out of Stock` (none left), `Low Stock` (≤ `MinimumQuantity`), `Available`; `Inactive` is set by the Manager.
- The `InventoryRequest` table has no Manager note column: the rejection reason is returned in `RejectNote` (taken from the Audit Log).
  `ApprovedBy` / `ApprovedAt` are the person / time that processed the request (approved or rejected).
- Inventory has no stock-movement history table; every stock in / stock out is recorded in the Audit Log.

```json
{"InventoryRequestID": 1, "ClubID": 1, "RequestedBy": 7, "RequestedByName": "Demo Groom", "ApprovedBy": 1,
 "ApprovedByName": "Demo Club Manager", "RequestDate": "2026-10-12T08:00:00", "Status": "Approved", "Reason": "Out of bran",
 "ApprovedAt": "2026-10-12T09:00:00", "RejectNote": null,
 "Items": [{"InventoryRequestItemID": 1, "InventoryItemID": 1, "ItemName": "Bran pellets", "Unit": "kg",
            "RequestedQuantity": 20.0, "ApprovedQuantity": 20.0, "Note": null}]}
```

Specific error codes: `INSUFFICIENT_STOCK`, `NOT_REQUESTER`.

## 8. Notifications

`GET /notifications` – items needing the logged-in user's attention. The database has no notifications table, so the list is
**recomputed on every call** from current data (there is no "read" state). The frontend calls it on page load or every 1–2 minutes to show the bell.

```json
[{"Type": "HEALTH_REPORT", "Priority": "High", "Title": "Health report (Urgent) - Reported",
  "Message": "Demo Work Rider: Horse lame in the right hind leg when cantering", "EntityName": "HealthReport", "EntityID": 4,
  "HorseID": 1, "HorseName": "Thunder", "At": "2026-10-12T06:20:00"}]
```

Sorting: `Priority = High` first, newest first. `EntityName` + `EntityID` tell which screen to open when clicked.

| Role | `Type` |
|---|---|
| Club Manager | `HORSE_TO_VERIFY`, `HORSE_TO_APPROVE`, `PROFILE_CHANGE`, `INVENTORY_REQUEST`, `LOW_STOCK` |
| Vet | `HEALTH_REPORT`, `INITIAL_EXAM`, `VACCINATION_DUE`, `MEDICAL_SCHEDULE`, `DRAFT_RECORD`, `DIET_TO_REVIEW` |
| Head Trainer | `HEALTH_REPORT` (all horses in the club), `PLAN_TO_APPROVE`, `ADJUSTMENT_REQUIRED`, `STAGE_TO_CLOSE`, `DIET_RETURNED` |
| Trainer | `HEALTH_REPORT` (horses they are in charge of), `PLAN_RETURNED`, `SUPERVISE_TODAY`, `SUBSTITUTE_OBSERVATION`, `SESSION_TO_REVIEW`, `STAGE_TO_CLOSE` |
| Work Rider | `RIDE_TODAY` |
| Groom | `CARE_TASK` |
| Horse Owner | `HORSE_REJECTED`, `PROFILE_CHANGE_DONE`, `OWNER_SESSIONS_REVIEWED` (new reviewed sessions, grouped per horse), `OWNER_STAGE_SUMMARY`, `OWNER_PLAN_SUMMARY`, `OWNER_PLAN_APPROVED`, `OWNER_SESSION_STOPPED` (High); Flow 3: `OWNER_TRAINING_LOCKED` (High), `OWNER_TRAINING_UNLOCKED` |

## 9. Frontend changes (Flow 1)

### 9.0 Connect the frontend to the backend (do this first)

| # | Task | Reason |
|---|---|---|
| 1 | `vite.config.js`: change `'http://localhost:8080'` to `'http://127.0.0.1:8000'` | The Django backend runs on port 8000 (8080 was the old Java backend). Use `127.0.0.1` because on some machines `localhost` does not reach Django |
| 2 | `src/api/apiClient.ts`: change the default base URL from MockAPI to `/api` | Call the real backend through the Vite proxy instead of MockAPI |
| 3 | `apiClient.ts`: attach the `Authorization: Bearer <access>` header to every request | Every API (except `auth/login`, `auth/register`, `auth/google`, `clubs`, `health`) requires login; a missing token returns **401** |
| 4 | `apiClient.ts`: on 401, call `POST /auth/refresh` with `refresh` to get a new `access`, then retry | `access` expires after 60 minutes |
| 5 | `apiClient.ts`: on errors read `detail` (show to the user) and `code` (special handling); a 400 error is an object keyed by field | See section 1, error codes part |
| 6 | `apiClient.ts`: add `apiPatch`, `apiDelete` | Partial updates use `PATCH`, not `PUT` of the whole horse |
| 7 | **Login** screen (Email + Password → `POST /auth/login`), store `access` / `refresh`; remove the demo role picker `DemoPicker` | Route by `Roles`: `CLUB_MANAGER` → `/manager`, `VETERINARIAN` → `/vet`, `HORSE_OWNER` → `/owner` |
| 8 | `src/types/index.ts`: redeclare data types using database column names | Per tables 9.2–9.6 and the JSON examples in section 4 |

To override the addresses on your own machine, create `.env.local` (do not commit it):

```
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

### 9.1 Functions in `horseApi.ts` (rewrite per this table)

| Old function (MockAPI) | Replace with |
|---|---|
| `getHorses()` | `getHorses({RegistrationStatus?, OwnerID?, search?})` → `GET /horses` |
| `getHorseById(id)` | keep the name → `GET /horses/{id}` |
| `createHorse(payload)` | keep the name, body uses column names + `ClubID` (Owner) or `OwnerID` (Manager) |
| `updateHorse(id, payload)` (PUT of the whole horse) | `PATCH /horses/{id}`, send only the fields to change, only when `Draft`/`Rejected` |
| *(not yet)* | `submitHorse`, `verifyHorse`, `rejectHorse`, `archiveHorse` |
| `saveExaminationDraft(horseId, vet, input)` | `saveExaminationDraft(horseId, input, draftId?)` → POST the first time, PATCH afterwards |
| `finalizeExamination(horseId, vet, input)` | `finalizeExamination(horseId, input, draftId?)` → save then `POST /medical-records/{id}/sign` |
| `completeHorseIntake(horseId, managerId)` | `completeHorseIntake(horseId, HorseCode, StallID?, ManagerNote?)` → `POST /horses/{id}/approve` |
| `isHorseAssignedToVet(horse, user)` | **remove**: Vets are on duty, not assigned |
| `getLatestHorse`, `putHorsePreservingData`, `toExamination` | **remove**: the backend handles status and audit log |
| `normalizeHorse`, `normalizeUser` | **remove**: use the backend JSON directly |
| *(not yet)* | `getPendingInitialExams`, `getMedicalRecords`, `addAmendment`, `getHorseDocuments`, `addHorseDocument`, `requestProfileChange`, `getProfileChangeRequests`, `approveProfileChange`, `rejectProfileChange`, `getStalls`, `getClubs`, `getRegistrationRequests`, `getHorseAuditLogs` |

### 9.2 Horse field renames

| Old frontend | Backend | Notes |
|---|---|---|
| `id` | `HorseID` | number, not string |
| `clubId` | `ClubID` | |
| `code` | `HorseCode` | `null` until `Approved` |
| `name` | `HorseName` | |
| `breed`, `dateOfBirth`, `coatColor`, `microchipNumber` | `Breed`, `DateOfBirth`, `CoatColor`, `MicrochipNumber` | |
| `sex`: `MALE`/`FEMALE`/`GELDING` | `Gender`: `Male`/`Female`/`Gelding` | plus `SexClass` for display |
| `registrationNumber` | `PassportNumber` | |
| `sireId`, `damId` | `SireName`, `DamName` | enter the parents' **names**, not select horses |
| `ownerUserId` | `OwnerID` | contact info is in `Owner` |
| `profileStatus` | `RegistrationStatus` | see table 5.3 |
| `healthStatus` | `CurrentHealthStatus` | see table 5.4 |
| `archiveReason` | `ArchiveReason` | |
| `createdAt`, `updatedAt` | `CreatedAt`, `UpdatedAt` | |
| `intake.assignedVetId` | **remove** | Vets are on duty |
| `intake.completedAt`, `completedBy` | `RegistrationRequest.ReviewedAt`, `ReviewedByClubManagerID` | `GET /horses/{id}/registration-requests` |
| `intake.handoverNotes`, `intakeNotes` | `RegistrationRequest.ManagerNote` | sent with `approve` |
| `intake.handoverDocuments` | documents of type `Handover Record` | `/horses/{id}/documents` |
| `healthAssessment` | `HealthSummary` | only in `GET /horses/{id}` |
| `examinations[]` | `GET /horses/{id}/medical-records` | |
| `documents[]` | `GET /horses/{id}/documents` | |
| `correctionRequests[]` | `GET /profile-change-requests?HorseID={id}` | |
| `auditLogs[]` | `GET /horses/{id}/audit-logs` | |
| `ownershipHistory[]` | **remove** | the team decided not to store ownership history |
| `medicalRecords[]`, `vaccinations[]` | Flow 3 APIs | see section 6 |

### 9.3 Profile status

| Old `profileStatus` | New `RegistrationStatus` |
|---|---|
| `DRAFT` | `Draft` |
| *(not yet)* | `Submitted` (Manager must click **Verify**) |
| `PENDING_EXAM` | `PendingExam` and `InitialExamSigned === false` |
| `PENDING_COMPLETION` | `PendingExam` and `InitialExamSigned === true` |
| `RECEIVED` | `Approved` |
| *(not yet)* | `Rejected` |
| `ARCHIVED` | `Archived` |

### 9.4 Health status

The database separates **health** (`HealthStatus`) from **whether the horse may train** (`TrainingEligibility`).

| Old `healthStatus` | New |
|---|---|
| `NOT_ASSESSED` | `CurrentHealthStatus: "Unknown"` |
| `ELIGIBLE` | `HealthStatus: "Healthy"` + `TrainingEligibility: "Eligible"` |
| `MONITORING` | `"Monitor"` |
| `INJURED` | `"Injured"` |
| `ISOLATION` | `"Isolated"` |
| *(not yet)* | `"Recovering"` |

The examination form needs an extra `TrainingEligibility` selector. The old approval condition `healthStatus === 'ELIGIBLE'`
becomes: `HealthStatus` is `Healthy`/`Monitor` **and** `TrainingEligibility !== 'Not Eligible'` (the backend checks this itself).

### 9.5 Examination form (old `ExaminationInput` → medical record body in section 4.4)

| Old | New |
|---|---|
| `examinedAt` | `ExamDate` |
| `weightKg`, `heightCm` | `WeightKg`, `HeightCm` |
| `symptoms` | `Symptoms` |
| `diagnosis` | `Diagnosis` |
| `treatmentPlan` | `TreatmentPlan` |
| `conclusion` | `Conclusion` |
| `healthStatus` | `HealthStatus` + `TrainingEligibility` |
| `exerciseRestrictions` | `RestrictionNote` |
| `followUpDate` | `FollowUpDate` |
| `purpose` | `ExamType` (`Initial Exam` at intake); extra notes go in `Note` |
| `status: DRAFT/FINALIZED` | `RecordStatus: Draft/Signed` |

### 9.6 Users, login

| Old | New |
|---|---|
| demo role picker screen | login screen → `POST /auth/login` (section 4.1) |
| `user.id` | `UserID` |
| `user.clubId` | `ClubID` |
| `user.role`: `CLUB_MANAGER`/`OWNER`/`VET` | `user.Roles`: `CLUB_MANAGER`/`HORSE_OWNER`/`VETERINARIAN` (array) |
| `user.isActive` | `Status === "Active"` |
| `fullName`, `email`, `phone`, `address`, `createdAt` | `FullName`, `Email`, `Phone`, `Address`, `CreatedAt` |

### 9.7 Screens

| Route | API calls |
|---|---|
| `/manager/horses` | `getHorses({RegistrationStatus})` |
| `/manager/horses/new` | `getUsers('HORSE_OWNER')` to pick the owner, then `createHorse({... , OwnerID})` |
| `/horses/:id` | `getHorseById`, `getHorseDocuments`, `getRegistrationRequests` |
| `/manager/horses/:id/intake` | `verifyHorse` / `rejectHorse` |
| `/manager/horses/:id/post-exam` | `getHorseById` (view `HealthSummary`), `getStalls('Available')`, `completeHorseIntake` or `rejectHorse` |
| `/owner/horses` | `getHorses()` (the backend filters to the owner's own horses) |
| `/owner/horses/:id` | `getHorseById`, `getHorseDocuments` |
| `/owner/horses/:id/correction-request` | `submitProfileProposal` (multipart), `getChangeRequestOptions`, `withdrawProfileProposal` |
| `/vet/horses-needing-exam` | `getPendingInitialExams` |
| `/vet/horses/:id` | `getHorseById`, `getMedicalRecords` |
| `/vet/horses/:id/examination` | `saveExaminationDraft`, `finalizeExamination` (pass `DraftMedicalRecordID`) |
| `/manager/profile-change-requests` | `getProfileChangeRequests`, `reviewProfileChangeRequest` |

## 10. Frontend for Flow 2–4

The frontend has no Flow 2–4 screens yet. When building them, add API files per sections 5–8
(e.g. `src/api/trainingApi.ts`, `medicalApi.ts`, `careApi.ts`) in the same style as `horseApi.ts`.

Suggested screens by role:

| Role | Screen | Main APIs |
|---|---|---|
| Head Trainer | Horse overview (training lock, trainer, latest session) | `GET /training-dashboard` |
| Head Trainer | Horse assessment, trainer assignment | `POST /horses/{id}/assessments`, `GET /trainers`, `POST /trainer-assignments`, `POST /trainer-assignments/{id}/end` |
| Head Trainer | Approve training plans | `GET /training-plans?Status=Pending Approval`, `POST /training-plans/{id}/approve`, `.../return` |
| Head Trainer | Training schedule (all horses; exceptions) | `GET /training-sessions?From=&To=`, `POST /training-sessions`, `PATCH /training-sessions/{id}`, `GET /users?RoleCode=WORK_RIDER` |
| Head Trainer | Diet plans, assign Groom tasks | `POST /horses/{id}/diet-plans`, `POST /care-tasks` |
| Trainer | Assigned horses, write training plans | `GET /trainer-assignments?mine=1`, `POST /training-plans`, `.../stages`, `.../submit`, `.../revise` |
| Trainer | Schedule sessions for own horses, close stages | `POST /training-sessions`, `PATCH /training-sessions/{id}`, `.../cancel`, `GET /users?RoleCode=WORK_RIDER`, `POST /training-plan-stages/{id}/close` |
| Trainer | Today's supervised sessions, session review | `GET /training-sessions?mine=1&Date=`, `.../stop`, `.../substitute-observation`, `.../review` |
| Work Rider | Today's rides, record results | `GET /training-sessions?mine=1&Date=`, `.../start`, `.../result` |
| Vet | Health report queue | `GET /health-reports?open=1`, `.../take`, `.../resolve` |
| Vet | Examination, prescribe treatments, sign, Training Lock | `POST /horses/{id}/medical-records`, `.../treatments`, `POST /medical-records/{id}/sign`, `POST /training-locks/{id}/release` |
| Vet | Vaccinations, medical schedule, approve diet plans | `GET /vaccinations?DueWithinDays=14`, `POST /diet-plans/{id}/approve` |
| Groom | Today's tasks, diet plan, report incidents, request inventory | `GET /care-tasks?mine=1&Date=`, `GET /horses/{id}/current-diet`, `POST /horses/{id}/health-reports`, `POST /inventory-requests` |
| Manager | Inventory, approve requests | `GET /inventory-items`, `POST /inventory-items/{id}/stock`, `POST /inventory-requests/{id}/approve` |
| Horse Owner | Training tab of a horse: plan + stage summaries, session list, session detail | `GET /owner/horses/{id}/training-plans`, `GET /owner/training-plans/{id}`, `GET /owner/horses/{id}/training-sessions`, `GET /owner/training-sessions/{id}` |
| All roles | Notification bell | `GET /notifications` |

## 11. Profile update proposals (2026-10-16)

The Owner correction screen and Manager review screen now use the same complete proposal.
The old JSON creation contract and existing request IDs remain supported. All paths below
have the `/api` prefix.

| Method / route | Contract / access |
|---|---|
| `GET /horses/{id}/profile-change-options` | Owner + `PROFILE_EDIT_REQUEST`: `MaxFileMB`, `MaxFiles`, `DocumentTypes`, `ClearableFields` |
| `POST /horses/{id}/profile-change-requests` | Owner's approved horse, `PROFILE_EDIT_REQUEST`; JSON for fields/existing media, multipart for new files |
| `GET /profile-change-requests[?HorseID=…&Status=…]` | Owner's horses or Manager's club, with the corresponding profile permission |
| `GET /profile-change-requests/{id}` | Same scope as list; immutable proposal with all changes and attachments |
| `GET /profile-change-requests/{id}/attachments/{index}[?download=1]` | Same request scope; authenticated file response, private/no-store, no public media URLs |
| `POST /profile-change-requests/{id}/approve` | Club Manager + `PROFILE_EDIT_APPROVE`, optional `ReviewNote` |
| `POST /profile-change-requests/{id}/reject` | Club Manager + `PROFILE_EDIT_APPROVE`, nonblank `ReviewNote` required |
| `POST /profile-change-requests/{id}/withdraw` | Original requester who still owns the horse + `PROFILE_EDIT_REQUEST`; pending only |

For multipart creation, send `Payload` containing JSON and files under `file0`, `file1`, etc.:

```json
{
  "Changes": {"HorseName": "Thunder II", "CoatColor": "Grey"},
  "Reason": "Correct the name using the certificate",
  "EvidenceDocumentIDs": [12],
  "RemoveImageIDs": [8],
  "AvatarDocumentID": 10,
  "Attachments": [
    {"FileKey": "file0", "Purpose": "replace", "DocumentName": "Corrected certificate",
     "DocumentType": "Passport", "ReplacesDocumentID": 11, "Note": "Corrected spelling"},
    {"FileKey": "file1", "Purpose": "add", "DocumentName": "Owner supporting record", "DocumentType": "Other"}
  ]
}
```

`Purpose` is `avatar`, `image`, `evidence`, `add`, or `replace`. Choose one uploaded avatar
or one `AvatarDocumentID`, never both. Image purposes accept JPG/JPEG/PNG/WebP; documents
use the existing PDF/image upload validator. Extension and file signature must agree;
empty/oversized/disallowed files are rejected. Defaults: `UPLOAD_MAX_MB=10`,
`CHANGE_REQUEST_MAX_FILES=12`. The UI reads these limits from the server. There is no
pre-upload step: failed request creation removes its staged files, including partial disk writes.

The server reads old values, ownership, club, and media from the database. It normalizes
values, omits unchanged fields, and rejects a proposal without an actual change (evidence
alone is not a profile change). Existing `EvidenceDocumentID` is also supported. Owner
may only reference visible, active documents on the same horse. Replacement is restricted
to the Owner's own documents, excluding profile photos, contracts, and handover records.
Only the Owner's own profile photos may be proposed for removal. Removing the current
avatar requires a replacement. Scanned documents remain documents, distinct from profile photos.

The existing stricter rule remains: **one pending request per horse**. A conflict returns
HTTP 409 with `code=PENDING_REQUEST_EXISTS` and `RequestID`; the UI links to that request.
Fields in the current write serializer are all required, so `ClearableFields=[]`; blank and
null values are invalid rather than interpreted as deletion. There are no model fields for
origin, identification description, Owner health notes, document issue date, or expiry date.
Those fields have not been added. Owner can attach supporting health documents without
changing Vet conclusions or records.

`ChangedFields` now includes `Changes` (all old/new values), `Attachments`, `EvidenceDocuments`,
`CurrentAvatar`, `AvatarDocument`, and `RemovedImages`. File records include name, size,
content type, purpose, optional note, and previous-document metadata. Internal disk paths
and the server snapshot are omitted from API responses. Review responses also expose
`ReviewedAt`, `ReviewedBy`, `ReviewedByName`, and `ReviewNote`. Status values are `Pending`,
`Approved`, `Rejected`, `Withdrawn`. Resolved requests cannot be edited or processed again.
Creating a new proposal from a rejection re-fetches the horse/documents and revalidates;
the Owner explicitly reselects files for the new request.

Approval locks the horse then the request, checks club/permission/status, compares the full
profile/ownership/active and historical document snapshot, and revalidates proposed values
and file availability. A stale snapshot returns HTTP 409 `STALE_PROFILE`. All field updates,
document versions, photo flags, reviewer information, and audit records commit together or
roll back together. Legacy requests without a snapshot compare their changed fields' old values.
Pending/rejected/withdrawn uploads never enter `HorseDocument`. Evidence stays request-only
even after approval. Replaced/removed records and physical files remain available to authorized
history viewers. Documents referenced by request history cannot be permanently deleted.
Owner direct upload to the approved profile now returns `APPROVAL_REQUIRED`; draft/rejected
registration editing and upload continue through the existing endpoints.

Changed implementation files:

- Backend: `apps/horses/change_requests.py`, `models.py`, `serializers.py`, `services.py`,
  `views.py`, `documents.py`; `config/settings.py`, `.env.example`.
- Frontend: `pages/owner/OwnerCorrectionRequest.jsx` and `.css`,
  `pages/manager/ProfileChangeRequests.jsx`, `api/horseApi.ts`, `App.jsx` (navigation blocking),
  `components/horse/ProfileProposalDetails.jsx`, `proposalLabels.js`, `HorseAvatar.jsx`, `HorseDocuments.jsx`.
- Schema: `sql/migrations/20261016_profile_change_media.sql` is the additive, re-runnable
  existing-database migration. `sql/horse_v2.sql` reflects the same schema for new demo databases.
  The additive migration was applied to local SQL Server on 2026-10-16 to correct the initial
  missing-column regression; original document/request values were verified unchanged.
  No database reset was run. `python manage.py upgrade_profile_media` checks another database;
  use `--apply` to perform the additive upgrade explicitly.
- Tests: `apps/core/tests/test_profile_proposals.py`, `browser_fixture.py`,
  `frontend/tests/api.test.mjs`, `frontend/tests/profile-proposal.browser.mjs`.

Validation uses the actual Django services with temporary SQLite, FE adapter HTTP contract
tests, and a real Chromium browser against the isolated Django fixture API. The browser
exercises desktop/mobile, unsaved navigation, failed-network retry retaining fields/files,
combined proposals, unchanged live profiles while pending, Manager approval and Owner withdrawal.
Run commands are in the backend/frontend READMEs. Local SQL Server schema deployment and live
read APIs for horse 8 were subsequently verified after fixing the initial deployment mismatch.
SQL Server locking under simultaneous requests and production storage deployment still require
verification in the target environment; SQLite tests cannot verify those database-specific behaviors.

