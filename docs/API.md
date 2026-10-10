# Hợp đồng API – Equi backend (Flow 1–4)

Tài liệu cho nhóm frontend. Backend: Django REST, database `sql/horse_v2.sql`.

| Phần | Nội dung |
|---|---|
| [1–3](#1-quy-ước-chung) | Quy ước chung, mã lỗi, trạng thái hồ sơ ngựa, vai trò và quyền |
| [4](#4-flow-1--tiếp-nhận-ngựa) | **Flow 1** – đăng nhập, ngựa, giấy tờ, khám đầu vào, sửa lý lịch, chuồng |
| [5](#5-flow-2--huấn-luyện) | **Flow 2** – đánh giá, phân công Trainer, giáo án, buổi tập, kết quả, đánh giá buổi tập |
| [6](#6-flow-3--y-tế) | **Flow 3** – báo cáo sức khỏe, phiếu khám, Training Lock, thuốc, tiêm phòng, lịch y tế |
| [7](#7-flow-4--chăm-sóc-và-dinh-dưỡng) | **Flow 4** – khẩu phần, việc chăm sóc, kho vật tư |
| [8](#8-thông-báo) | Thông báo (chuông) cho từng vai trò |
| [9](#9-frontend-cần-sửa-gì-flow-1) | Frontend cần sửa gì ở Flow 1 đang có |
| [10](#10-frontend-flow-24) | Code mẫu frontend cho Flow 2–4 |

## 1. Quy ước chung

| Mục | Quy ước |
|---|---|
| Địa chỉ gốc | `http://localhost:8000/api` (frontend gọi `/api/...` qua Vite proxy) |
| Dấu `/` cuối | **Không có**: `/api/horses/5`, không phải `/api/horses/5/` |
| Định dạng | JSON cả chiều gửi lẫn chiều nhận |
| Tên khóa JSON | **Đúng tên cột database**: `HorseID`, `HorseName`, `RegistrationStatus`... |
| Giá trị trạng thái | **Đúng giá trị trong database**: `Draft`, `PendingExam`, `Approved`... |
| Ngày | `"2021-03-10"` |
| Ngày giờ | `"2026-10-10T08:30:00"` (giờ Việt Nam, không có múi giờ) |
| Số thập phân | Số thường: `"WeightKg": 480.5` |
| Giờ | `"06:00:00"` (gửi `"06:00"` cũng được) |
| Lọc danh sách | Query string theo tên cột: `?HorseID=5&Status=Pending`; cờ bật / tắt dùng `=1` (`?mine=1`, `?open=1`) |
| Đăng nhập | Header `Authorization: Bearer <access>` cho mọi API (trừ `auth/login`, `health`) |

### Mã lỗi

| HTTP | Khi nào | Dạng body |
|---|---|---|
| 400 | Dữ liệu sai / thiếu (cả tham số lọc sai, vd `?HorseID=abc`) | `{"HorseName": ["Trường này là bắt buộc."], "Gender": ["\"Unknown\" is not a valid choice."]}` |
| 401 | Chưa đăng nhập, token hết hạn, sai mật khẩu | `{"detail": "...", "code": "..."}` |
| 403 | Vai trò không có quyền | `{"detail": "Bạn không có quyền thực hiện thao tác này.", "code": "PERMISSION_DENIED"}` |
| 404 | Không tồn tại **hoặc không được thấy** (ngựa của CLB khác, ngựa của chủ khác) | `{"detail": "...", "code": "NOT_FOUND"}` |
| 409 | Sai luật nghiệp vụ | `{"detail": "Ngựa chưa có phiếu khám đầu vào đã chốt.", "code": "INITIAL_EXAM_REQUIRED"}` |

Frontend hiển thị `detail` cho người dùng; dùng `code` khi cần xử lý riêng.

Các `code` của lỗi 409 (chung và Flow 1; mã riêng của Flow 2–4 ghi ở từng phần):

| code | Ý nghĩa |
|---|---|
| `INVALID_STATUS` | Thao tác không hợp lệ với trạng thái hiện tại (vd: sửa hồ sơ đã gửi) |
| `MISSING_FIELDS` | Gửi hồ sơ / chốt phiếu khám khi chưa nhập đủ (`detail` liệt kê tên cột còn thiếu) |
| `INITIAL_EXAM_REQUIRED` | Duyệt hồ sơ khi Vet chưa chốt phiếu khám đầu vào |
| `INITIAL_EXAM_FAILED` | Phiếu khám đầu vào không đạt → chỉ có thể từ chối |
| `DUPLICATE_HORSE_CODE` | Mã ngựa đã có trong CLB |
| `STALL_NOT_FOUND`, `STALL_NOT_AVAILABLE` | Chuồng không thuộc CLB / không còn trống |
| `INITIAL_EXAM_EXISTS` | Lần nộp này đã có phiếu khám đầu vào (có thể đang là nháp của Vet khác) |
| `RECORD_SIGNED` | Phiếu khám đã chốt, không sửa / xóa được |
| `NOT_RECORD_OWNER` | Chỉ Vet lập phiếu mới sửa / chốt được phiếu nháp |
| `EXAM_TYPE_LOCKED` | Không đổi loại khám của phiếu đã tạo |
| `RECORD_NOT_SIGNED` | Phiếu nháp thì sửa trực tiếp, không thêm đính chính |
| `PENDING_REQUEST_EXISTS` | Ngựa đã có 1 yêu cầu sửa lý lịch đang chờ |
| `FIELD_NOT_EDITABLE` | Xin sửa trường không được phép |
| `REVIEW_NOTE_REQUIRED` | Từ chối / trả về mà thiếu lý do (yêu cầu sửa lý lịch, giáo án) |
| `HORSE_NOT_APPROVED` | Thao tác Flow 2–4 trên ngựa chưa tiếp nhận (chưa `Approved`) |
| `DUPLICATE_STALL`, `STALL_OCCUPIED` | Số chuồng trùng / chuồng đang có ngựa |
| `TRAINING_LOCK_FULL`, `TRAINING_LOCK_RESTRICTED` | Ngựa đang bị khóa tập (xem Flow 3). Trigger SQL Server trả cùng mã này |
| `UX_...`, `UQ_...`, `DB_INTEGRITY` | Vi phạm unique index / ràng buộc database (đã dịch sang tiếng Việt) |

## 2. Trạng thái hồ sơ ngựa (`RegistrationStatus`)

```
Draft ──submit──> Submitted ──verify──> PendingExam ──(Vet chốt khám)──> approve ──> Approved ──archive──> Archived
  ^                   │                      │
  └──── sửa ──── Rejected <──── reject ──────┘
```

| Giá trị | Nghĩa | Ai làm gì tiếp |
|---|---|---|
| `Draft` | Nháp | Owner / Manager sửa, gửi |
| `Submitted` | Đã gửi | Manager xác minh hoặc từ chối |
| `PendingExam` + `InitialExamSigned: false` | Chờ Vet khám đầu vào | Vet trực khám; Manager có thể từ chối |
| `PendingExam` + `InitialExamSigned: true` | Vet đã chốt khám (màn cũ gọi là `PENDING_COMPLETION`) | Manager duyệt (nếu đạt) hoặc từ chối |
| `Approved` | Đã tiếp nhận, có `HorseCode` | Owner xin sửa lý lịch; Manager lưu trữ |
| `Rejected` | Bị từ chối (lý do ở `RegistrationRequest.ManagerNote`) | Owner / Manager sửa rồi gửi lại |
| `Archived` | Đã rời CLB | Chỉ xem |

Khi gửi lại sau `Rejected`, backend tạo một `RegistrationRequest` mới và **Vet phải khám lại**
(`InitialExamSigned` quay về `false`).

`CurrentHealthStatus`: `Unknown`, `Healthy`, `Monitor`, `Injured`, `Recovering`, `Isolated`.
`Gender`: `Male`, `Female`, `Gelding`. `SexClass` (backend tự tính): `Foal` (< 1 tuổi), `Colt`/`Filly` (< 4 tuổi), `Stallion`/`Mare`, `Gelding`.

## 3. Vai trò và quyền

Đăng nhập trả về `Roles` và `Permissions`. Frontend dùng `Permissions` để ẩn / hiện nút.

| Vai trò (`RoleCode`) | Quyền | Việc chính |
|---|---|---|
| `CLUB_MANAGER` | `CLUB_MANAGE`, `RBAC_MANAGE`, `AUDIT_VIEW`, `HORSE_VIEW`, `HORSE_REGISTER_REVIEW`, `HORSE_ARCHIVE`, `PROFILE_EDIT_APPROVE`, `INVENTORY_MANAGE` | Duyệt hồ sơ ngựa, chuồng, tài khoản, kho vật tư, giao việc chăm sóc |
| `HEAD_TRAINER` | `HORSE_VIEW`, `HORSE_ASSESS`, `TRAINER_ASSIGN`, `TRAINING_PLAN_APPROVE`, `TRAINING_SESSION_ASSIGN`, `TRAINING_SESSION_SUPERVISE`, `HEALTH_REPORT`, `DIET_MANAGE`, `INVENTORY_REQUEST` | Đánh giá ngựa, phân công Trainer, duyệt giáo án, xếp buổi tập, lập khẩu phần, giao việc Groom |
| `TRAINER` | `HORSE_VIEW`, `TRAINING_PLAN_MANAGE`, `TRAINING_SESSION_SUPERVISE`, `TRAINING_REVIEW`, `HEALTH_REPORT` | Soạn giáo án, giám sát (kể cả làm Substitute), đánh giá buổi tập |
| `WORK_RIDER` | `HORSE_VIEW`, `TRAINING_RESULT_UPDATE`, `HEALTH_REPORT` | Bắt đầu buổi tập, ghi kết quả |
| `VETERINARIAN` | `HORSE_VIEW`, `MEDICAL_MANAGE`, `MEDICAL_SIGN`, `TRAINING_LOCK_MANAGE`, `DIET_MANAGE` | Khám, chốt phiếu, Training Lock, thuốc, tiêm phòng, duyệt khẩu phần |
| `GROOM` | `HORSE_VIEW`, `CARE_MANAGE`, `HEALTH_REPORT`, `INVENTORY_REQUEST` | Việc chăm sóc, báo sự cố, xin vật tư |
| `HORSE_OWNER` | `HORSE_REGISTER`, `PROFILE_EDIT_REQUEST`, `OWNER_VIEW` | Đăng ký ngựa, xin sửa lý lịch, xem ngựa của mình |

Phạm vi dữ liệu: nhân sự chỉ thấy dữ liệu **trong CLB của mình**; chủ ngựa chỉ thấy **ngựa của mình**
(chỉ phần tóm tắt sức khỏe, không xem huấn luyện / bệnh án chi tiết).

## 4. Flow 1 – tiếp nhận ngựa

### 4.1 Đăng nhập, người dùng

| Method | URL | Ai dùng | Body / tham số |
|---|---|---|---|
| GET | `/health` | không cần đăng nhập | → `{"backend": "UP", "database": "UP"}` (503 nếu DB lỗi) |
| POST | `/auth/login` | mọi người | `{"Email", "Password"}` → `{access, refresh, User}` |
| POST | `/auth/refresh` | mọi người | `{"refresh"}` → `{access}` |
| GET | `/auth/me` | đã đăng nhập | → `User` kèm `Roles`, `Permissions` |
| GET | `/users?RoleCode=HORSE_OWNER` | Manager, Head Trainer | người dùng trong CLB (`RoleCode` = `TRAINER`, `WORK_RIDER`, `GROOM`... để chọn người phân công) |
| POST | `/users` | Manager | `{"FullName", "Email", "Phone"?, "Address"?, "RoleCode"? (mặc định HORSE_OWNER), "Password"?}` |
| GET | `/users/{UserID}` | chính mình / Manager cùng CLB | |
| GET | `/clubs` | đã đăng nhập | CLB đang hoạt động (Owner chọn khi đăng ký) |

`POST /users` không gửi `Password` thì backend tạo mật khẩu tạm và trả về `TemporaryPassword` **một lần duy nhất**.

Ví dụ `POST /auth/login`:

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

`access` hết hạn sau 60 phút, `refresh` sau 7 ngày (đổi trong `.env`).

### 4.2 Ngựa

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/horses?RegistrationStatus=&OwnerID=&search=` | mọi vai trò | `search` tìm theo tên, mã, microchip |
| GET | `/horses/{HorseID}` | mọi vai trò | kèm `HealthSummary` |
| POST | `/horses` | Owner, Manager | tạo `Draft` |
| PATCH | `/horses/{HorseID}` | Owner (ngựa mình), Manager | chỉ khi `Draft` / `Rejected`; gửi trường cần đổi |
| POST | `/horses/{HorseID}/submit` | Owner, Manager | `Draft`/`Rejected` → `Submitted`; cần `HorseName`, `DateOfBirth`, `Gender`, `MicrochipNumber` |
| POST | `/horses/{HorseID}/verify` | Manager | `Submitted` → `PendingExam` |
| POST | `/horses/{HorseID}/reject` | Manager | `{"Reason"}`; `Submitted`/`PendingExam` → `Rejected` |
| POST | `/horses/{HorseID}/approve` | Manager | `{"HorseCode", "StallID"?, "ManagerNote"?}`; `PendingExam` → `Approved` |
| POST | `/horses/{HorseID}/archive` | Manager | `{"Reason"}`; `Approved` → `Archived` |
| GET | `/horses/{HorseID}/registration-requests` | xem được ngựa | lịch sử các lần nộp, lý do từ chối |
| GET | `/horses/{HorseID}/audit-logs` | Manager | lịch sử thao tác |
| GET | `/stalls?Status=Available` | Manager, nhân sự | chọn chuồng khi duyệt (xem thêm mục 4.6) |

Body `POST /horses`:

```json
{
  "HorseName": "Thunder", "Breed": "Thoroughbred", "DateOfBirth": "2021-03-10",
  "CoatColor": "Bay", "Gender": "Male", "SireName": "Storm King", "DamName": "Lady Rain",
  "MicrochipNumber": "985000000000001", "PassportNumber": "VN-001",
  "ClubID": 1
}
```

- **Owner tự đăng ký**: gửi `ClubID`; `OwnerID` = chính mình.
- **Manager nhập hộ**: gửi `OwnerID` (tài khoản `HORSE_OWNER`); `ClubID` = CLB của Manager.

Ngựa trả về (`GET /horses/1`):

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
  "Owner": {"UserID": 5, "FullName": "Nguyễn Văn A", "Email": "a@example.com", "Phone": null, "Address": null},
  "CurrentStall": {"StallID": 1, "StallNumber": "A01", "StartDate": "2026-10-10"},
  "HealthSummary": {
    "MedicalRecordID": 1, "ExamDate": "2026-10-10T09:30:00", "ExamType": "Initial Exam",
    "HealthStatus": "Healthy", "TrainingEligibility": "Eligible",
    "Conclusion": "Đủ điều kiện tiếp nhận", "RestrictionNote": null, "FollowUpDate": null
  }
}
```

`GET /horses` trả mảng các ngựa cùng dạng nhưng **không có** `HealthSummary`.
Mọi API thao tác (`submit`, `verify`, `approve`...) đều trả về ngựa sau khi cập nhật, frontend dùng luôn để vẽ lại màn hình.

Điều kiện duyệt (`approve`): Vet đã chốt phiếu khám đầu vào của lần nộp hiện tại,
`HealthStatus` là `Healthy` hoặc `Monitor` và `TrainingEligibility` khác `Not Eligible`.

### 4.3 Giấy tờ

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/horses/{HorseID}/documents` | xem được ngựa | Owner chỉ thấy giấy tờ có `IsVisibleToOwner: true` |
| POST | `/horses/{HorseID}/documents` | Owner (ngựa mình), Manager | `{"DocumentName", "DocumentType", "FileUrl", "IsVisibleToOwner"?}` |

`DocumentType`: `Passport`, `Microchip Certificate`, `Ownership Proof`, `Handover Record`, `Contract`, `Other`.
Backend **chỉ lưu đường dẫn** (`FileUrl`), chưa nhận file. Tạm thời upload lên Google Drive rồi dán link.

### 4.4 Khám bệnh (Vet)

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/vet/pending-initial-exams` | Vet | ngựa `PendingExam` trong CLB chưa có phiếu khám đầu vào đã chốt |
| GET | `/horses/{HorseID}/medical-records` | nhân sự CLB | Vet thấy cả phiếu nháp; người khác chỉ thấy phiếu đã chốt. Owner xem `HealthSummary` |
| POST | `/horses/{HorseID}/medical-records` | Vet | tạo phiếu nháp |
| GET | `/medical-records/{MedicalRecordID}` | nhân sự CLB | |
| PATCH | `/medical-records/{MedicalRecordID}` | Vet lập phiếu | khi còn `Draft` |
| DELETE | `/medical-records/{MedicalRecordID}` | Vet lập phiếu | khi còn `Draft` |
| POST | `/medical-records/{MedicalRecordID}/sign` | Vet lập phiếu | chốt phiếu (`Signed`), cập nhật `Horse.CurrentHealthStatus` |
| GET | `/medical-records/{MedicalRecordID}/amendments` | nhân sự CLB | |
| POST | `/medical-records/{MedicalRecordID}/amendments` | Vet | `{"Reason", "AmendedContent"}`; chỉ cho phiếu đã chốt |

Vet **trực** khám: không phân công Vet trước, Vet nào trong CLB cũng nhận được ngựa trong hàng chờ.
Mỗi lần nộp hồ sơ chỉ có **một** phiếu khám đầu vào; `DraftMedicalRecordID` khác `null` nghĩa là đã có Vet khám dở.

Body tạo phiếu:

```json
{
  "ExamType": "Initial Exam",
  "WeightKg": 480.5, "HeightCm": 162.0,
  "Symptoms": "Không có dấu hiệu bất thường",
  "Diagnosis": "Bình thường",
  "Conclusion": "Đủ điều kiện tiếp nhận",
  "TreatmentPlan": null,
  "HealthStatus": "Healthy",
  "TrainingEligibility": "Eligible",
  "RestrictionNote": null,
  "FollowUpDate": null,
  "Note": "Mục đích khám: tiếp nhận vào CLB"
}
```

- `ExamType`: `Initial Exam` (chỉ khi `PendingExam`), `Routine Exam`, `Injury Exam`, `Follow-up`, `Emergency` (chỉ khi ngựa `Approved`).
- `ExamDate` bỏ trống = thời điểm hiện tại.
- Khi chốt bắt buộc có `HealthStatus`, `TrainingEligibility`; nếu `Restricted` thì phải có `RestrictionNote`.
- `HealthStatus` của phiếu: `Healthy`, `Monitor`, `Injured`, `Recovering`, `Isolated`.
- `TrainingEligibility`: `Eligible`, `Restricted`, `Not Eligible`.

Phiếu trả về:

```json
{
  "MedicalRecordID": 1, "HorseID": 1, "HorseName": "Thunder", "VetID": 2, "VetName": "Demo Veterinarian",
  "RegistrationRequestID": 1, "TrainingSessionID": null,
  "ExamType": "Initial Exam", "ExamDate": "2026-10-10T09:30:00",
  "WeightKg": 480.5, "HeightCm": 162.0,
  "Symptoms": "Không có dấu hiệu bất thường", "Diagnosis": "Bình thường", "Conclusion": "Đủ điều kiện tiếp nhận",
  "InjuryLocation": null, "TreatmentPlan": null,
  "HealthStatus": "Healthy", "TrainingEligibility": "Eligible", "RestrictionNote": null,
  "FollowUpDate": null, "Note": null,
  "RecordStatus": "Signed", "SignedAt": "2026-10-10T09:45:00"
}
```

### 4.5 Yêu cầu sửa lý lịch (sau khi `Approved`)

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| POST | `/horses/{HorseID}/profile-change-requests` | Owner của ngựa | `{"Changes": {"CoatColor": "Dark Bay"}, "Reason", "EvidenceDocumentID"?}` |
| GET | `/profile-change-requests?Status=Pending&HorseID=` | Manager (CLB mình), Owner (của mình) | |
| GET | `/profile-change-requests/{id}` | như trên | |
| POST | `/profile-change-requests/{id}/approve` | Manager | `{"ReviewNote"?}`; backend áp dụng thay đổi vào ngựa |
| POST | `/profile-change-requests/{id}/reject` | Manager | `{"ReviewNote"}` bắt buộc |

Trường được xin sửa: `HorseName`, `Breed`, `DateOfBirth`, `CoatColor`, `Gender`, `SireName`, `DamName`, `MicrochipNumber`, `PassportNumber`.
Mỗi ngựa chỉ có 1 yêu cầu `Pending` tại một thời điểm.

```json
{
  "ProfileChangeRequestID": 1, "HorseID": 1, "HorseName": "Thunder",
  "RequestedBy": 5, "RequestedAt": "2026-10-11T08:00:00",
  "ChangedFields": {
    "Reason": "Màu lông thay đổi theo tuổi",
    "Changes": [{"Field": "CoatColor", "OldValue": "Bay", "NewValue": "Dark Bay"}]
  },
  "EvidenceDocumentID": 1, "Status": "Pending",
  "ReviewedBy": null, "ReviewedAt": null, "ReviewNote": null
}
```

### 4.6 Chuồng

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/stalls?Status=` | Manager, nhân sự | kèm `CurrentHorse` (ngựa đang ở) |
| POST | `/stalls` | Manager | `{"StallNumber": "A05", "StallType": "Standard"}` |
| PATCH | `/stalls/{StallID}` | Manager | `{"StallType"?, "Status": "Maintenance" \| "Available"}`; chuồng đang có ngựa không đổi trạng thái được (`STALL_OCCUPIED`) |
| POST | `/horses/{HorseID}/move-stall` | Manager | `{"StallID": 3}` – chuyển chuồng (chuồng cũ tự về `Available`) |

`Status = Occupied` do backend tự đặt khi xếp ngựa vào chuồng, frontend không gửi giá trị này.

```json
{"StallID": 1, "ClubID": 1, "StallNumber": "A01", "StallType": "Standard", "Status": "Occupied",
 "CurrentHorse": {"HorseID": 1, "HorseName": "Thunder", "StartDate": "2026-10-10"}}
```

Lưu trữ ngựa (`POST /horses/{id}/archive`) giờ làm thêm: kết thúc phân công Trainer (giáo án chưa xong → `Cancelled`,
buổi tập `Assigned` → `Cancelled`), việc chăm sóc chưa làm → `Skipped`, khẩu phần còn hiệu lực → `Expired`.

## 5. Flow 2 – huấn luyện

```
Head Trainer đánh giá ngựa ──> giao 1 Trainer phụ trách ──> Trainer soạn giáo án ──> Head Trainer duyệt
──> Head Trainer xếp buổi tập (Work Rider, Substitute Trainer nếu cần) ──> Work Rider bắt đầu, ghi kết quả
──> (Substitute ghi nhận xét) ──> Trainer phụ trách đánh giá ──> cần điều chỉnh thì tạo bản giáo án mới
```

Chỉ ngựa `Approved` mới vào huấn luyện. Tất cả API Flow 2 cần quyền `HORSE_VIEW` để xem (nhân sự CLB).

### 5.1 Chuyên môn, Trainer

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/specializations` | mọi người | `Flat Racing`, `Steeplechase / Hurdle Racing`, `Harness Racing`, `Endurance / Long-distance Racing`, `Other` |
| GET | `/trainers?SpecializationID=` | Head Trainer, Manager | trainer trong CLB, chuyên môn, số ngựa đang phụ trách |
| POST | `/trainers/{UserID}/specializations` | Head Trainer, Manager | `{"SpecializationID": 1}` – gán chuyên môn cho trainer |
| DELETE | `/trainers/{UserID}/specializations/{SpecializationID}` | Head Trainer, Manager | không xóa được nếu đã dùng trong phân công (`IN_USE`) |

```json
[{"UserID": 4, "FullName": "Demo Trainer", "Email": "trainer@equi.local", "Phone": null,
  "Specializations": [{"SpecializationID": 1, "SpecializationName": "Flat Racing"}], "ActiveHorseCount": 2}]
```

Trainer phải có chuyên môn (`TrainerSpecialization`) trùng với chuyên môn của phân công (ràng buộc khóa ngoại trong SQL).

### 5.2 Đánh giá ngựa

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/horses/{HorseID}/assessments` | nhân sự | mới nhất trước |
| POST | `/horses/{HorseID}/assessments` | Head Trainer | `{"SpecializationID", "QualityScore"? (0–100), "FitnessLevel"?, "AssessmentNote"?, "DecisionStatus"?}` |

- `FitnessLevel`: `Excellent`, `Good`, `Average`, `Needs Monitoring`.
- `DecisionStatus`: `Recommended` (mặc định, phù hợp) hoặc `Rejected` (không phù hợp). Đánh giá `Recommended` mới
  làm các đánh giá `Recommended` cũ **cùng chuyên môn** chuyển `Superseded`.

### 5.3 Phân công Trainer phụ trách

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/trainer-assignments?HorseID=&TrainerID=&Status=Active&mine=1` | nhân sự | `mine=1`: trainer xem ngựa mình phụ trách |
| GET | `/trainer-assignments/{id}` | nhân sự | |
| POST | `/trainer-assignments` | Head Trainer | `{"HorseID", "TrainerID", "SpecializationID", "AssessmentID"?, "StartDate"?, "AssignmentNote"?}` |
| POST | `/trainer-assignments/{id}/end` | Head Trainer | `{"Reason"?}` – kết thúc; giáo án chưa xong và buổi tập `Assigned` bị hủy |

Mỗi ngựa chỉ có **1** trainer phụ trách đang `Active` (`ALREADY_ASSIGNED` nếu đã có; muốn đổi thì `end` rồi giao mới).

```json
{"TrainerHorseAssignmentID": 1, "HorseID": 1, "HorseName": "Thunder", "TrainerID": 4, "TrainerName": "Demo Trainer",
 "SpecializationID": 1, "SpecializationName": "Flat Racing", "AssignedByHeadTrainerID": 2, "AssignedByName": "Demo Head Trainer",
 "AssessmentID": 1, "StartDate": "2026-10-10", "EndDate": null, "Status": "Active", "AssignmentNote": null}
```

### 5.4 Work Rider ưu tiên (quen ngựa)

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/horses/{HorseID}/work-rider-preferences?all=1` | nhân sự | mặc định chỉ trả ưu tiên còn hiệu lực |
| POST | `/horses/{HorseID}/work-rider-preferences` | Head Trainer | `{"WorkRiderID", "Priority"? (1 = ưu tiên nhất), "Note"?}` |
| POST | `/work-rider-preferences/{PreferenceID}/end` | Head Trainer | |

Chỉ để gợi ý khi xếp buổi tập; mỗi buổi vẫn chọn Work Rider riêng.

### 5.5 Giáo án

```
Draft ──submit──> Pending Approval ──approve──> Active ──complete──> Completed
  ^                      │ return (ReviewNote bắt buộc)
  └──────────────────────┘
Draft / Pending Approval / Active ──cancel──> Cancelled
Active ──revise──> bản Draft mới; bản mới được duyệt thì bản cũ tự Completed
```

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/training-plans?HorseID=&TrainerID=&Status=&mine=1` | nhân sự | `Status=Pending Approval` cho màn duyệt của Head Trainer |
| GET | `/training-plans/{id}` | nhân sự | kèm `Stages` |
| POST | `/training-plans` | Trainer phụ trách | tạo `Draft`, có thể gửi luôn `Stages` |
| PATCH | `/training-plans/{id}` | Trainer phụ trách | chỉ khi `Draft`; `Goal`, `StartDate`, `EndDate`, `OverallIntensity`, `Note` |
| POST | `/training-plans/{id}/stages` | Trainer phụ trách | thêm giai đoạn (khi `Draft`) |
| PATCH / DELETE | `/training-plan-stages/{TrainingPlanStageID}` | Trainer phụ trách | khi `Draft` |
| POST | `/training-plans/{id}/submit` | Trainer phụ trách | cần ít nhất 1 giai đoạn (`NO_STAGES`) |
| POST | `/training-plans/{id}/approve` | Head Trainer | `{"ReviewNote"?}` → `Active` |
| POST | `/training-plans/{id}/return` | Head Trainer | `{"ReviewNote"}` → về `Draft` |
| POST | `/training-plans/{id}/complete` | Trainer phụ trách, Head Trainer | buổi `Assigned` còn lại bị hủy |
| POST | `/training-plans/{id}/cancel` | Trainer phụ trách, Head Trainer | `{"Reason"?}` |
| POST | `/training-plans/{id}/revise` | Trainer phụ trách | chép giáo án `Active`/`Completed` thành bản `Draft` mới để điều chỉnh |

Body `POST /training-plans`:

```json
{
  "HorseID": 1, "Goal": "Chuẩn bị giải tháng 12", "StartDate": "2026-10-12", "EndDate": "2026-12-10",
  "OverallIntensity": "Moderate", "Note": null,
  "Stages": [
    {"StageName": "Nền tảng", "StartDate": "2026-10-12", "EndDate": "2026-11-01", "Intensity": "Low",
     "TrainingLoad": 30, "DistanceTargetKm": 3, "Surface": "Turf", "Goal": "Làm quen", "Note": null},
    {"StageName": "Tăng tốc", "StartDate": "2026-11-02", "Intensity": "High", "TrainingLoad": 70}
  ]
}
```

- `OverallIntensity`, `Intensity`: `Low`, `Moderate`, `High`, `Very High`.
- `StageOrder` bỏ trống = tự đánh số 1, 2, 3...; giai đoạn phải nằm trong thời gian giáo án.
- Ngựa đang bị khóa `Full` trùng thời gian giáo án thì không duyệt được (`TRAINING_LOCK_FULL`).

Giáo án trả về:

```json
{
  "TrainingPlanID": 1, "TrainerHorseAssignmentID": 1, "HorseID": 1, "HorseName": "Thunder",
  "TrainerID": 4, "TrainerName": "Demo Trainer", "Goal": "Chuẩn bị giải tháng 12",
  "StartDate": "2026-10-12", "EndDate": "2026-12-10", "OverallIntensity": "Moderate", "Note": null,
  "Status": "Active", "CreatedAt": "2026-10-10T08:00:00", "SubmittedAt": "2026-10-10T08:05:00",
  "ApprovedByHeadTrainerID": 2, "ApprovedAt": "2026-10-10T09:00:00", "ReviewNote": "Đồng ý",
  "Stages": [{"TrainingPlanStageID": 1, "TrainingPlanID": 1, "StageName": "Nền tảng", "StageOrder": 1, "Goal": null,
              "StartDate": "2026-10-12", "EndDate": "2026-11-01", "Intensity": "Low", "TrainingLoad": 30.0,
              "DistanceTargetKm": 3.0, "Surface": "Turf", "Note": null}]
}
```

Mã lỗi riêng: `NOT_PLAN_OWNER` (không phải trainer đang phụ trách), `NO_STAGES`, `DRAFT_EXISTS` (đã có bản đang soạn / chờ duyệt),
`ASSIGNMENT_ENDED`, `IN_USE` (giai đoạn đã có buổi tập).

### 5.6 Buổi tập

```
Assigned ──start (Work Rider, đúng ngày)──> In Progress ──result (Work Rider)──> Completed
Assigned / In Progress ──stop (trainer đang giám sát, Head Trainer) / cancel (Head Trainer)──> Cancelled
Assigned / In Progress ──missed (Head Trainer, từ ngày tập trở đi)──> Missed
```

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/training-sessions?Date=&From=&To=&HorseID=&TrainingPlanID=&WorkRiderID=&Status=&mine=1` | nhân sự | `mine=1`: Work Rider → buổi mình cưỡi; Trainer → buổi mình giám sát (phụ trách hoặc Substitute) |
| GET | `/training-sessions/{id}` | nhân sự | |
| POST | `/training-sessions` | Head Trainer | xếp buổi tập (giáo án phải `Active`) |
| PATCH | `/training-sessions/{id}` | Head Trainer | khi `Assigned`: đổi Work Rider, Substitute, ngày giờ, cường độ... |
| POST | `/training-sessions/{id}/start` | Work Rider của buổi | đúng ngày tập |
| POST | `/training-sessions/{id}/result` | Work Rider của buổi | ghi kết quả → `Completed` |
| POST | `/training-sessions/{id}/substitute-observation` | Substitute Trainer của buổi | `{"SubstituteObservation"}` (bắt buộc với buổi giám sát thay) |
| POST | `/training-sessions/{id}/stop` | trainer đang giám sát, Head Trainer | `{"Reason", "ReportHealth"?, "Severity"?, "Description"?}` |
| POST | `/training-sessions/{id}/cancel` | Head Trainer | `{"Reason"?}` |
| POST | `/training-sessions/{id}/missed` | Head Trainer | `{"Reason"?}` |
| POST | `/training-sessions/{id}/review` | Trainer phụ trách | đánh giá buổi `Completed` (mỗi buổi 1 lần) |
| GET | `/training-reviews?AdjustmentRequired=1&HorseID=&Days=14` | nhân sự | Head Trainer theo dõi đề nghị điều chỉnh giáo án |
| GET | `/training-dashboard?HorseID=` | nhân sự | màn tổng quan trước khi xếp lịch (giống view `vw_HorseTrainingDashboard`) |

Body `POST /training-sessions`:

```json
{
  "TrainingPlanStageID": 1, "WorkRiderID": 5, "SubstituteTrainerID": null,
  "SessionDate": "2026-10-12", "StartTime": "06:00", "EndTime": null, "SequenceNo": null,
  "TrainingType": "Canter", "DurationPlannedMinutes": 45, "DistancePlannedKm": 3.5, "TargetSpeedKmh": 30,
  "TrainingLoad": 30, "Surface": "Turf", "Location": "Đường chạy số 2", "Instructions": "Khởi động 10 phút"
}
```

- `SubstituteTrainerID`: `null` = trainer phụ trách tự giám sát. Chọn Trainer khác (hoặc Head Trainer tự giám sát)
  khi trainer phụ trách bận. Chọn trùng trainer phụ trách thì backend coi như `null`.
- `SequenceNo` bỏ trống = thứ tự tiếp theo trong ngày của Work Rider (`RIDER_SLOT_TAKEN` nếu trùng).
- Không xếp vào ngày đã qua; ngày tập phải nằm trong giai đoạn.
- **Training Lock**: `Full` → không xếp / bắt đầu được (`TRAINING_LOCK_FULL`); `Restricted` → phải ghi `TrainingLoad`
  và không vượt `MaxIntensity` (`TRAINING_LOCK_RESTRICTED`). Màn xếp lịch nên gọi `/training-dashboard` để hiện hạn chế.

Body `POST /training-sessions/{id}/result`:

```json
{
  "ActualDurationMinutes": 44, "ActualDistanceKm": 3.4, "AvgSpeedKmh": 28.5, "MaxSpeedKmh": 41,
  "AvgHeartRate": 150, "MaxHeartRate": 190, "RecoveryMinutes": 12, "PerformanceScore": 78,
  "RiderObservation": "Hơi nặng chân phải cuối buổi", "VideoUrl": null
}
```

Body `POST /training-sessions/{id}/review`:

```json
{"Evaluation": "Good", "TrainerComment": "Ổn", "AdjustmentRequired": true, "AdjustmentNote": "Giảm cự ly tuần sau"}
```

`Evaluation`: `Excellent`, `Good`, `Average`, `Needs Improvement`. `AdjustmentRequired: true` thì bắt buộc `AdjustmentNote`
và Head Trainer thấy trong thông báo.

Buổi tập trả về (giống view `vw_WorkRiderDailySchedule`, kèm kết quả và đánh giá):

```json
{
  "TrainingSessionID": 1, "TrainingPlanStageID": 1, "TrainingPlanID": 1, "StageName": "Nền tảng",
  "HorseID": 1, "HorseName": "Thunder", "HorseCode": "EQ-001",
  "WorkRiderID": 5, "WorkRiderName": "Demo Work Rider", "AssignedByHeadTrainerID": 2,
  "SubstituteTrainerID": 6, "AssignedTrainerID": 4, "AssignedTrainerName": "Demo Trainer",
  "SupervisingTrainerID": 6, "SupervisingTrainerName": "Trainer B", "IsSubstitute": true,
  "SessionDate": "2026-10-12", "StartTime": "06:00:00", "EndTime": "06:45:00", "SequenceNo": 1,
  "TrainingType": "Canter", "DurationPlannedMinutes": 45, "DistancePlannedKm": 3.5, "TargetSpeedKmh": null,
  "TrainingLoad": 30.0, "Surface": "Turf", "Location": "Đường chạy số 2", "Instructions": "Khởi động 10 phút",
  "Status": "Completed",
  "Result": {"TrainingResultID": 1, "TrainingSessionID": 1, "ActualDurationMinutes": 44, "ActualDistanceKm": 3.4,
             "AvgSpeedKmh": 28.5, "MaxSpeedKmh": 41.0, "AvgHeartRate": 150, "MaxHeartRate": 190, "RecoveryMinutes": 12,
             "PerformanceScore": 78.0, "RiderObservation": "Hơi nặng chân phải cuối buổi", "VideoUrl": null,
             "SubstituteObservation": "Ngựa chạy đều", "RecordedAt": "2026-10-12T06:50:00"},
  "Review": null
}
```

Mã lỗi riêng: `PLAN_NOT_ACTIVE`, `RIDER_SLOT_TAKEN`, `NOT_SESSION_RIDER`, `WRONG_DAY`, `NOT_SUBSTITUTE`,
`NOT_ASSIGNED_TRAINER`, `ALREADY_REVIEWED`, `NOT_YET` (đánh vắng buổi chưa tới ngày).

`GET /training-dashboard`:

```json
[{"HorseID": 1, "HorseCode": "EQ-001", "HorseName": "Thunder", "Gender": "Male", "SexClass": "Stallion",
  "CurrentHealthStatus": "Recovering", "TrainerHorseAssignmentID": 1, "TrainerID": 4, "TrainerName": "Demo Trainer",
  "SpecializationName": "Flat Racing", "ActiveTrainingPlanID": 1,
  "IsTrainingLocked": true, "TrainingLockID": 3, "LockLevel": "Restricted", "MaxIntensity": 25.0, "LockEndDate": null,
  "LatestTrainingDate": "2026-10-12", "LatestPerformanceScore": 78.0, "LatestActualDistanceKm": 3.4,
  "LatestAvgSpeedKmh": 28.5, "LatestAvgHeartRate": 150, "LatestRecoveryMinutes": 12}]
```

## 6. Flow 3 – y tế

```
Groom / Work Rider / Trainer / Head Trainer báo sự cố ──> hàng chờ Vet (Urgent trước)
   (Trainer phụ trách và Head Trainer thấy trong thông báo)
──> Vet nhận ca ──> lập phiếu khám gắn báo cáo ──> kê thuốc ──> chốt phiếu (+ Training Lock)
──> xử lý xong báo cáo ──> tái khám đạt ──> mở khóa
```

Phiếu khám (`/horses/{id}/medical-records`, `/medical-records/...`) dùng chung với Flow 1, xem mục 4.4. Flow 3 thêm:

| Mục | Thay đổi |
|---|---|
| Tạo phiếu | thêm `"HealthReportID"` (phiếu xử lý báo cáo nào) và `"TrainingSessionID"` (phát hiện trong buổi tập nào) |
| `TrainingEligibility = Restricted` | phải có `RestrictionNote` ngay cả khi lưu nháp (ràng buộc CHECK trong SQL) |
| Xóa phiếu nháp | xóa luôn thuốc kê trên phiếu, gỡ liên kết báo cáo sức khỏe |
| Chốt phiếu | body tùy chọn `{"TrainingLock": {...}}`; response có thêm `TrainingLock` (xem 6.3) |

### 6.1 Báo cáo sức khỏe

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/horses/{HorseID}/health-reports?open=1` | nhân sự | **mở form báo cáo thì gọi trước**: có báo cáo đang mở thì thêm ghi chú thay vì báo trùng |
| POST | `/horses/{HorseID}/health-reports` | Groom, Work Rider, Trainer, Head Trainer | `{"Severity": "Urgent" \| "Normal", "Description", "ImageUrl"?, "TrainingSessionID"?}` |
| GET | `/health-reports?open=1&Status=&Severity=&HorseID=&mine=1` | nhân sự | `open=1`: hàng chờ Vet, `Urgent` trước rồi cũ trước |
| GET | `/health-reports/{id}` | nhân sự | kèm `Notes` |
| POST | `/health-reports/{id}/notes` | người báo được, Vet | `{"Content"}` |
| POST | `/health-reports/{id}/take` | Vet | Vet trực nhận ca: `Reported` → `Reviewing` |
| POST | `/health-reports/{id}/resolve` | Vet | `{"VetNote"?, "MedicalRecordID"?}` (cần 1 trong 2) → `Resolved` |

- Báo `Urgent` gắn `TrainingSessionID` của buổi đang `In Progress` → buổi tập tự dừng (`Cancelled`), response có `"StoppedSession": true`.
- Trainer đang giám sát cũng có thể dừng buổi và báo luôn: `POST /training-sessions/{id}/stop` với `"ReportHealth": true` (mục 5.6).
- Vet lập phiếu khám với `"HealthReportID"` → báo cáo tự gắn phiếu, chuyển `Reviewing`. Mỗi báo cáo gắn 1 phiếu (`REPORT_ALREADY_LINKED`).

```json
{
  "HealthReportID": 1, "HorseID": 1, "HorseName": "Thunder", "ReportedBy": 7, "ReportedByName": "Demo Groom",
  "ReportedByRoles": ["GROOM"], "TrainingSessionID": null, "ReportedAt": "2026-10-12T07:30:00",
  "Severity": "Normal", "Description": "Chân trước trái hơi nóng", "ImageUrl": null,
  "Status": "Reviewing", "VetID": 3, "VetName": "Demo Veterinarian", "MedicalRecordID": 2, "VetNote": null,
  "ResolvedAt": null,
  "Notes": [{"HealthReportNoteID": 1, "HealthReportID": 1, "NoteBy": 5, "NoteByName": "Demo Work Rider",
             "NoteAt": "2026-10-12T07:45:00", "Content": "Khởi động thấy hơi lệch nhịp"}]
}
```

Mã lỗi riêng: `REPORT_RESOLVED`, `REPORT_ALREADY_LINKED`.

### 6.2 Thuốc điều trị

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/medical-records/{id}/treatments` | nhân sự | |
| POST | `/medical-records/{id}/treatments` | Vet lập phiếu (phiếu còn `Draft`) | `{"MedicineName", "Dose", "Route", "StartDate", "EndDate"?, "WithdrawalUntil"?, "Note"?}` |
| PATCH | `/treatments/{TreatmentID}` | Vet | phiếu nháp: Vet lập phiếu sửa tự do; phiếu đã chốt: chỉ `EndDate`, `WithdrawalUntil` |
| GET | `/horses/{HorseID}/treatments?WithdrawalActive=1` | nhân sự | thuốc còn trong thời gian ngưng thuốc (kiểm tra doping) |

`Route`: `Oral`, `Injection`, `Topical`, `Inhalation`, `Other`. Trả thêm `"WithdrawalActive": true/false`.

### 6.3 Training Lock

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/training-locks?HorseID=&LockStatus=Active` | nhân sự | |
| GET | `/training-locks/{id}` | nhân sự | |
| POST | `/horses/{HorseID}/training-locks` | Vet | `{"Reason", "LockLevel", "MaxIntensity"?, "LockStartDate"?, "LockEndDate"?, "Details"?}` |
| PATCH | `/training-locks/{id}` | Vet | đổi mức, cường độ tối đa, ngày mở dự kiến |
| POST | `/training-locks/{id}/release` | Vet | `{"Note"?}` – cần lần tái khám **chốt sau khi khóa** với kết luận khác `Not Eligible` |

- `LockLevel`: `Full` (cấm tập) hoặc `Restricted` (bắt buộc `MaxIntensity`, so với `TrainingLoad` của buổi tập).
- Mỗi ngựa tối đa 1 lock đang `Active` (`LOCK_EXISTS` → dùng PATCH).
- Tạo / siết lock → buổi tập `Assigned` trong thời gian khóa bị hủy; response có `"CancelledSessionIDs": [..]`.
- **Chốt phiếu khám** của ngựa đã tiếp nhận:
  - gửi `{"TrainingLock": {...}}` → tạo lock (hoặc sửa lock đang có) theo đó;
  - không gửi mà kết luận `Not Eligible` → backend tự khóa `Full` (hoặc nâng lock `Restricted` lên `Full`);
  - kết luận `Eligible` **không** tự mở khóa: Vet bấm mở khóa sau tái khám.

```json
{"TrainingLockID": 3, "HorseID": 1, "HorseName": "Thunder", "CreatedByVetID": 3, "CreatedByName": "Demo Veterinarian",
 "Reason": "Viêm gân nhẹ", "LockLevel": "Restricted", "MaxIntensity": 25.0, "LockStartDate": "2026-10-12T09:00:00",
 "LockEndDate": null, "LockStatus": "Active", "Details": null, "ReleasedByVetID": null, "ReleasedAt": null,
 "CancelledSessionIDs": [12]}
```

Mã lỗi riêng: `LOCK_EXISTS`, `FOLLOW_UP_EXAM_REQUIRED`.

### 6.4 Tiêm phòng, lịch y tế

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/vaccinations?HorseID=&Status=&DueWithinDays=14` | nhân sự | `DueWithinDays`: lịch tiêm sắp tới / quá hạn và mũi nhắc lại sắp tới |
| GET / POST | `/horses/{HorseID}/vaccinations` | xem: nhân sự; tạo: Vet | `{"VaccineName", "VaccinationDate", "NextDueDate"?, "Status"?, "Note"?, "ExternalVet"?}` |
| PATCH | `/vaccinations/{id}` | Vet | vd `{"Status": "Completed", "NextDueDate": "2027-04-01"}` |
| GET | `/medical-schedules?From=&To=&HorseID=&Status=&ScheduleType=` | nhân sự | |
| GET / POST | `/horses/{HorseID}/medical-schedules` | xem: nhân sự; tạo: Vet | `{"ScheduleType", "ScheduledDate", "Status"?, "Note"?, "ExternalVet"?}` |
| PATCH | `/medical-schedules/{id}` | Vet | |

- Vaccination `Status`: `Scheduled`, `Completed`, `Overdue`, `Cancelled`. Trả thêm `IsOverdue` (đã quá ngày mà vẫn `Scheduled`).
- `ScheduleType`: `Vaccination`, `Deworming`, `Farrier`, `Routine Examination`. `Status`: `Scheduled`, `Completed`, `Cancelled`, `Overdue`.
- `"ExternalVet": true` → bác sĩ ngoài (không có tài khoản), `VetID = null`. Mặc định `VetID` = Vet đang đăng nhập.

## 7. Flow 4 – chăm sóc và dinh dưỡng

### 7.1 Khẩu phần

```
Head Trainer lập (Pending) ──Vet approve──> Approved ──Vet adjust──> Adjusted
     ^                          │ Vet reject (VetNote bắt buộc)
     └── Head Trainer sửa ── Rejected
```

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/horses/{HorseID}/diet-plans` | nhân sự | |
| POST | `/horses/{HorseID}/diet-plans` | Head Trainer | `{"DietDescription"?, "StartDate", "EndDate"?, "Meals": [...]}` (ít nhất 1 bữa) |
| GET | `/horses/{HorseID}/current-diet` | nhân sự | khẩu phần đang áp dụng hôm nay (`null` nếu chưa có) – màn của Groom |
| GET | `/diet-plans?Status=Pending&HorseID=` | nhân sự | Vet xem khẩu phần chờ duyệt |
| GET | `/diet-plans/{id}` | nhân sự | |
| PATCH | `/diet-plans/{id}` | Head Trainer | khi `Pending`/`Rejected`; gửi `Meals` thì thay toàn bộ bữa; sau khi sửa → `Pending` |
| POST | `/diet-plans/{id}/approve` | Vet | `{"VetNote"?}` (người lập không tự duyệt) |
| POST | `/diet-plans/{id}/reject` | Vet | `{"VetNote"}` |
| POST | `/diet-plans/{id}/adjust` | Vet | `{"VetNote", "Meals"?, "EndDate"?...}` – điều chỉnh khẩu phần đang áp dụng |

```json
{"MealTime": "06:00", "FeedType": "Yến mạch", "Quantity": 3, "Unit": "kg", "Note": null}
```

Khẩu phần mới được duyệt: khẩu phần cũ trùng thời gian bắt đầu trước thì kết thúc vào hôm trước ngày khẩu phần mới;
bắt đầu cùng ngày / sau thì chuyển `Expired`. Khẩu phần mới bắt đầu trong tương lai thì khẩu phần hiện tại vẫn dùng tới hôm đó.

```json
{"DietPlanID": 1, "HorseID": 1, "HorseName": "Thunder", "CreatedByHeadTrainerID": 2, "CreatedByName": "Demo Head Trainer",
 "ReviewedByVetID": 3, "ReviewedByName": "Demo Veterinarian", "DietDescription": "Khẩu phần hồi phục",
 "StartDate": "2026-10-12", "EndDate": null, "Status": "Approved", "VetNote": null,
 "CreatedAt": "2026-10-10T08:00:00", "ApprovedAt": "2026-10-10T10:00:00",
 "Meals": [{"DietMealID": 1, "MealTime": "06:00:00", "FeedType": "Yến mạch", "Quantity": 3.0, "Unit": "kg", "Note": null}]}
```

Mã lỗi riêng: `SELF_APPROVAL`.

### 7.2 Việc chăm sóc

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/care-tasks?Date=&From=&To=&HorseID=&GroomID=&Status=&mine=1` | nhân sự | `mine=1`: việc của Groom đang đăng nhập |
| GET | `/care-tasks/{id}` | nhân sự | |
| POST | `/care-tasks` | Head Trainer, Manager (giao việc); Groom (tự tạo) | `{"HorseID", "GroomID", "TaskType", "ScheduledAt", "Note"?}` – Groom tự tạo thì bỏ `GroomID` |
| PATCH | `/care-tasks/{id}` | người giao / Groom tự tạo | khi `Pending`; đổi `GroomID` chỉ Head Trainer / Manager |
| POST | `/care-tasks/{id}/complete` | Groom được giao | `{"Note"?}` → `Completed` |
| POST | `/care-tasks/{id}/skip` | Groom, người giao | `{"Reason"}` → `Skipped` |

`TaskType`: `Feeding`, `Cleaning`, `Bathing`, `Ice Leg Soak`. `AssignedBy = null` nghĩa là Groom tự tạo.
Thấy ngựa bất thường khi chăm sóc → báo qua mục 6.1.

```json
{"CareTaskID": 1, "HorseID": 1, "HorseName": "Thunder", "GroomID": 7, "GroomName": "Demo Groom", "AssignedBy": 2,
 "AssignedByName": "Demo Head Trainer", "TaskType": "Ice Leg Soak", "ScheduledAt": "2026-10-12T15:00:00",
 "Status": "Pending", "CompletedAt": null, "Note": "20 phút"}
```

Mã lỗi riêng: `NOT_TASK_OWNER`, `NOT_TASK_GROOM`.

### 7.3 Kho vật tư

| Method | URL | Ai dùng | Ghi chú |
|---|---|---|---|
| GET | `/inventory-items?ItemType=&Status=&LowStock=1` | Manager, Groom, Head Trainer | |
| POST | `/inventory-items` | Manager | `{"ItemName", "ItemType", "Unit", "Quantity"?, "MinimumQuantity"?}` |
| PATCH | `/inventory-items/{id}` | Manager | `ItemName`, `ItemType`, `Unit`, `MinimumQuantity`; `"Status": "Inactive"` để ngưng dùng, `"Reactivate": true` để dùng lại |
| POST | `/inventory-items/{id}/stock` | Manager | `{"Change": 50, "Note"?}` – nhập kho (số dương) / điều chỉnh giảm (số âm) |
| GET | `/inventory-requests?Status=&mine=1` | Manager (cả CLB), Groom / Head Trainer (của mình) | |
| POST | `/inventory-requests` | Groom, Head Trainer | `{"Reason"?, "Items": [{"InventoryItemID", "RequestedQuantity", "Note"?}]}` |
| POST | `/inventory-requests/{id}/approve` | Manager | `{"Items"?: [{"InventoryItemID", "ApprovedQuantity"}]}` – bỏ trống = duyệt đủ; trừ kho |
| POST | `/inventory-requests/{id}/reject` | Manager | `{"Note"}` |
| POST | `/inventory-requests/{id}/cancel` | người gửi | khi còn `Pending` |

- `ItemType`: `Food`, `Medicine`, `Care Equipment`.
- `Status` vật tư tự tính: `Out of Stock` (hết), `Low Stock` (≤ `MinimumQuantity`), `Available`; `Inactive` do Manager đặt.
- Bảng `InventoryRequest` không có cột ghi chú của Manager: lý do từ chối trả về ở `RejectNote` (lấy từ Audit Log).
  `ApprovedBy` / `ApprovedAt` là người / lúc xử lý (duyệt hoặc từ chối).
- Kho không có bảng lịch sử nhập xuất; mọi lần nhập kho / xuất kho ghi trong Audit Log.

```json
{"InventoryRequestID": 1, "ClubID": 1, "RequestedBy": 7, "RequestedByName": "Demo Groom", "ApprovedBy": 1,
 "ApprovedByName": "Demo Club Manager", "RequestDate": "2026-10-12T08:00:00", "Status": "Approved", "Reason": "Hết cám",
 "ApprovedAt": "2026-10-12T09:00:00", "RejectNote": null,
 "Items": [{"InventoryRequestItemID": 1, "InventoryItemID": 1, "ItemName": "Cám viên", "Unit": "kg",
            "RequestedQuantity": 20.0, "ApprovedQuantity": 20.0, "Note": null}]}
```

Mã lỗi riêng: `INSUFFICIENT_STOCK`, `NOT_REQUESTER`.

## 8. Thông báo

`GET /notifications` – việc cần chú ý của người đang đăng nhập. Database không có bảng thông báo nên danh sách được
**tính lại mỗi lần gọi** từ dữ liệu hiện tại (không có "đã đọc"). Frontend gọi khi mở trang hoặc mỗi 1–2 phút để hiện chuông.

```json
[{"Type": "HEALTH_REPORT", "Priority": "High", "Title": "Báo cáo sức khỏe (Urgent) - Reported",
  "Message": "Demo Work Rider: Ngựa què chân sau phải khi phi", "EntityName": "HealthReport", "EntityID": 4,
  "HorseID": 1, "HorseName": "Thunder", "At": "2026-10-12T06:20:00"}]
```

Sắp xếp: `Priority = High` trước, mới trước. `EntityName` + `EntityID` cho biết bấm vào thì mở màn nào.

| Vai trò | `Type` |
|---|---|
| Club Manager | `HORSE_TO_VERIFY`, `HORSE_TO_APPROVE`, `PROFILE_CHANGE`, `INVENTORY_REQUEST`, `LOW_STOCK` |
| Vet | `HEALTH_REPORT`, `INITIAL_EXAM`, `VACCINATION_DUE`, `MEDICAL_SCHEDULE`, `DRAFT_RECORD`, `DIET_TO_REVIEW` |
| Head Trainer | `HEALTH_REPORT` (mọi ngựa trong CLB), `PLAN_TO_APPROVE`, `ADJUSTMENT_REQUIRED`, `DIET_RETURNED` |
| Trainer | `HEALTH_REPORT` (ngựa mình phụ trách), `PLAN_RETURNED`, `SUPERVISE_TODAY`, `SUBSTITUTE_OBSERVATION`, `SESSION_TO_REVIEW` |
| Work Rider | `RIDE_TODAY` |
| Groom | `CARE_TASK` |
| Horse Owner | `HORSE_REJECTED`, `PROFILE_CHANGE_DONE` |

## 9. Frontend cần sửa gì (Flow 1)

Code mẫu đã kiểm tra kiểu (TypeScript strict) nằm trong `docs/frontend/`. Chép vào `equi-fe`:

| File mẫu | Chép vào | Việc |
|---|---|---|
| `docs/frontend/types.ts` | `src/types/index.ts` | kiểu dữ liệu mới theo tên cột DB |
| `docs/frontend/apiClient.ts` | `src/api/apiClient.ts` | gắn JWT, tự refresh token, đọc lỗi `detail`/`code`, thêm `apiPatch`, `apiDelete` |
| `docs/frontend/authApi.ts` | `src/api/authApi.ts` (mới) | đăng nhập thật thay màn chọn vai trò demo |
| `docs/frontend/horseApi.ts` | `src/api/horseApi.ts` | mỗi nghiệp vụ một API |
| `docs/frontend/userApi.ts` | `src/api/userApi.ts` | |

`.env.local` của frontend (không commit):

```
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://localhost:8000
```

### 9.1 Hàm trong `horseApi.ts`

| Hàm cũ (MockAPI) | Thay bằng |
|---|---|
| `getHorses()` | `getHorses({RegistrationStatus?, OwnerID?, search?})` → `GET /horses` |
| `getHorseById(id)` | giữ tên → `GET /horses/{id}` |
| `createHorse(payload)` | giữ tên, body theo tên cột + `ClubID` (Owner) hoặc `OwnerID` (Manager) |
| `updateHorse(id, payload)` (PUT cả con ngựa) | `PATCH /horses/{id}`, chỉ gửi trường cần đổi, chỉ khi `Draft`/`Rejected` |
| *(chưa có)* | `submitHorse`, `verifyHorse`, `rejectHorse`, `archiveHorse` |
| `saveExaminationDraft(horseId, vet, input)` | `saveExaminationDraft(horseId, input, draftId?)` → POST lần đầu, PATCH các lần sau |
| `finalizeExamination(horseId, vet, input)` | `finalizeExamination(horseId, input, draftId?)` → lưu rồi `POST /medical-records/{id}/sign` |
| `completeHorseIntake(horseId, managerId)` | `completeHorseIntake(horseId, HorseCode, StallID?, ManagerNote?)` → `POST /horses/{id}/approve` |
| `isHorseAssignedToVet(horse, user)` | **bỏ**: Vet trực, không phân công |
| `getLatestHorse`, `putHorsePreservingData`, `toExamination` | **bỏ**: backend lo trạng thái, audit log |
| `normalizeHorse`, `normalizeUser` | **bỏ**: dùng thẳng JSON backend |
| *(chưa có)* | `getPendingInitialExams`, `getMedicalRecords`, `addAmendment`, `getHorseDocuments`, `addHorseDocument`, `requestProfileChange`, `getProfileChangeRequests`, `approveProfileChange`, `rejectProfileChange`, `getStalls`, `getClubs`, `getRegistrationRequests`, `getHorseAuditLogs` |

### 9.2 Đổi tên trường của ngựa

| Frontend cũ | Backend | Ghi chú |
|---|---|---|
| `id` | `HorseID` | số, không phải chuỗi |
| `clubId` | `ClubID` | |
| `code` | `HorseCode` | `null` cho tới khi `Approved` |
| `name` | `HorseName` | |
| `breed`, `dateOfBirth`, `coatColor`, `microchipNumber` | `Breed`, `DateOfBirth`, `CoatColor`, `MicrochipNumber` | |
| `sex`: `MALE`/`FEMALE`/`GELDING` | `Gender`: `Male`/`Female`/`Gelding` | thêm `SexClass` để hiển thị |
| `registrationNumber` | `PassportNumber` | |
| `sireId`, `damId` | `SireName`, `DamName` | nhập **tên** cha mẹ, không chọn ngựa |
| `ownerUserId` | `OwnerID` | thông tin liên hệ ở `Owner` |
| `profileStatus` | `RegistrationStatus` | xem bảng 5.3 |
| `healthStatus` | `CurrentHealthStatus` | xem bảng 5.4 |
| `archiveReason` | `ArchiveReason` | |
| `createdAt`, `updatedAt` | `CreatedAt`, `UpdatedAt` | |
| `intake.assignedVetId` | **bỏ** | Vet trực |
| `intake.completedAt`, `completedBy` | `RegistrationRequest.ReviewedAt`, `ReviewedByClubManagerID` | `GET /horses/{id}/registration-requests` |
| `intake.handoverNotes`, `intakeNotes` | `RegistrationRequest.ManagerNote` | gửi kèm `approve` |
| `intake.handoverDocuments` | giấy tờ loại `Handover Record` | `/horses/{id}/documents` |
| `healthAssessment` | `HealthSummary` | chỉ có ở `GET /horses/{id}` |
| `examinations[]` | `GET /horses/{id}/medical-records` | |
| `documents[]` | `GET /horses/{id}/documents` | |
| `correctionRequests[]` | `GET /profile-change-requests?HorseID={id}` | |
| `auditLogs[]` | `GET /horses/{id}/audit-logs` | |
| `ownershipHistory[]` | **bỏ** | nhóm đã chốt không lưu lịch sử sở hữu |
| `medicalRecords[]`, `vaccinations[]` | Flow 3 (chưa làm) | |

### 9.3 Trạng thái hồ sơ

| `profileStatus` cũ | `RegistrationStatus` mới |
|---|---|
| `DRAFT` | `Draft` |
| *(chưa có)* | `Submitted` (Manager cần bấm **Xác minh**) |
| `PENDING_EXAM` | `PendingExam` và `InitialExamSigned === false` |
| `PENDING_COMPLETION` | `PendingExam` và `InitialExamSigned === true` (hàm `isPendingCompletion`) |
| `RECEIVED` | `Approved` |
| *(chưa có)* | `Rejected` |
| `ARCHIVED` | `Archived` |

### 9.4 Tình trạng sức khỏe

Database tách **sức khỏe** (`HealthStatus`) và **được tập hay không** (`TrainingEligibility`).

| `healthStatus` cũ | Mới |
|---|---|
| `NOT_ASSESSED` | `CurrentHealthStatus: "Unknown"` |
| `ELIGIBLE` | `HealthStatus: "Healthy"` + `TrainingEligibility: "Eligible"` |
| `MONITORING` | `"Monitor"` |
| `INJURED` | `"Injured"` |
| `ISOLATION` | `"Isolated"` |
| *(chưa có)* | `"Recovering"` |

Form khám cần thêm ô chọn `TrainingEligibility`. Điều kiện duyệt cũ `healthStatus === 'ELIGIBLE'`
đổi thành: `HealthStatus` là `Healthy`/`Monitor` **và** `TrainingEligibility !== 'Not Eligible'` (backend tự kiểm tra).

### 9.5 Form khám (`ExaminationInput` cũ → `MedicalRecordInput`)

| Cũ | Mới |
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
| `purpose` | `ExamType` (`Initial Exam` khi tiếp nhận); ghi chú thêm vào `Note` |
| `status: DRAFT/FINALIZED` | `RecordStatus: Draft/Signed` |

### 9.6 Người dùng, đăng nhập

| Cũ | Mới |
|---|---|
| màn chọn vai trò demo | màn đăng nhập → `login(Email, Password)` trong `authApi.ts` |
| `user.id` | `UserID` |
| `user.clubId` | `ClubID` |
| `user.role`: `CLUB_MANAGER`/`OWNER`/`VET` | `user.Roles`: `CLUB_MANAGER`/`HORSE_OWNER`/`VETERINARIAN` (mảng) |
| `user.isActive` | `Status === "Active"` |
| `fullName`, `email`, `phone`, `address`, `createdAt` | `FullName`, `Email`, `Phone`, `Address`, `CreatedAt` |

### 9.7 Màn hình

| Route | Gọi API |
|---|---|
| `/manager/horses` | `getHorses({RegistrationStatus})` |
| `/manager/horses/new` | `getUsers('HORSE_OWNER')` để chọn chủ, rồi `createHorse({... , OwnerID})` |
| `/horses/:id` | `getHorseById`, `getHorseDocuments`, `getRegistrationRequests` |
| `/manager/horses/:id/intake` | `verifyHorse` / `rejectHorse` |
| `/manager/horses/:id/post-exam` | `getHorseById` (xem `HealthSummary`), `getStalls('Available')`, `completeHorseIntake` hoặc `rejectHorse` |
| `/owner/horses` | `getHorses()` (backend tự lọc ngựa của mình) |
| `/owner/horses/:id` | `getHorseById`, `getHorseDocuments` |
| `/owner/horses/:id/correction-request` | `requestProfileChange`, `addHorseDocument` (bằng chứng) |
| `/vet/horses-needing-exam` | `getPendingInitialExams` |
| `/vet/horses/:id` | `getHorseById`, `getMedicalRecords` |
| `/vet/horses/:id/examination` | `saveExaminationDraft`, `finalizeExamination` (truyền `DraftMedicalRecordID`) |
| *(màn mới cho Manager)* | `getProfileChangeRequests({Status: 'Pending'})`, `approveProfileChange`, `rejectProfileChange` |

## 10. Frontend Flow 2–4

Frontend hiện chưa có màn hình Flow 2–4. Khi làm, dùng các file mẫu (đã kiểm tra kiểu TypeScript strict) trong `docs/frontend/`:

| File mẫu | Chép vào | Nội dung |
|---|---|---|
| `types.ts` | `src/types/index.ts` | đã gồm kiểu dữ liệu của cả 4 flow |
| `trainingApi.ts` | `src/api/trainingApi.ts` | Flow 2: chuyên môn, đánh giá, phân công, giáo án, buổi tập, dashboard |
| `medicalApi.ts` | `src/api/medicalApi.ts` | Flow 3: báo cáo sức khỏe, Training Lock, thuốc, tiêm phòng, lịch y tế |
| `careApi.ts` | `src/api/careApi.ts` | Flow 4: khẩu phần, việc chăm sóc, kho vật tư |
| `notificationApi.ts` | `src/api/notificationApi.ts` | chuông thông báo |

Gợi ý màn hình theo vai trò:

| Vai trò | Màn hình | API chính |
|---|---|---|
| Head Trainer | Tổng quan ngựa (khóa tập, trainer, buổi gần nhất) | `getTrainingDashboard` |
| Head Trainer | Đánh giá ngựa, phân công trainer | `createAssessment`, `getTrainers`, `assignTrainer`, `endAssignment` |
| Head Trainer | Duyệt giáo án | `getTrainingPlans({Status: 'Pending Approval'})`, `approvePlan`, `returnPlan` |
| Head Trainer | Lịch tập (xếp buổi, chọn Work Rider / Substitute) | `getSessions({From, To})`, `createSession`, `updateSession`, `getUsers('WORK_RIDER')` |
| Head Trainer | Khẩu phần, giao việc Groom | `createDietPlan`, `createCareTask` |
| Trainer | Ngựa phụ trách, soạn giáo án | `getAssignments({mine: true})`, `createPlan`, `addStage`, `submitPlan`, `revisePlan` |
| Trainer | Buổi giám sát hôm nay, đánh giá buổi tập | `getSessions({mine: true, Date})`, `stopSession`, `addSubstituteObservation`, `reviewSession` |
| Work Rider | Lịch cưỡi hôm nay, ghi kết quả | `getSessions({mine: true, Date})`, `startSession`, `recordResult` |
| Vet | Hàng chờ báo cáo sức khỏe | `getHealthReports({open: true})`, `takeReport`, `resolveReport` |
| Vet | Khám, kê thuốc, chốt, Training Lock | `saveExaminationDraft` (horseApi), `addTreatment`, `signRecord`, `releaseLock` |
| Vet | Tiêm phòng, lịch y tế, duyệt khẩu phần | `getVaccinations({DueWithinDays: 14})`, `approveDietPlan` |
| Groom | Việc hôm nay, khẩu phần, báo sự cố, xin vật tư | `getCareTasks({mine: true, Date})`, `getCurrentDiet`, `reportHealthIssue`, `createInventoryRequest` |
| Manager | Kho vật tư, duyệt yêu cầu | `getInventoryItems`, `adjustStock`, `approveInventoryRequest` |
| Mọi vai trò | Chuông thông báo | `getNotifications` |

