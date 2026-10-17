/* ================================================================
   RACEHORSE TRAINING & MANAGEMENT SYSTEM - DATABASE v2
   SQL Server 2019+

   Dựng lại từ horse.sql theo các góp ý đã chốt trong Gop_y.docx.

   QUY ƯỚC
   - Tên bảng số ít, không thêm "s" ở cuối (Horse, TrainingSession, ...).
   - USER là từ khóa của SQL Server nên bảng người dùng viết là dbo.[User]
     (luôn có ngoặc vuông khi viết SQL tay; ORM tự thêm).
   - Giữ tên cột khóa chính cũ (HorseID, TrainingSessionID, ...) để code ít phải sửa.

   THAY ĐỔI SO VỚI horse.sql
   Flow 1
     - Horse: Gender thêm 'Gelding'; cột tính SexClass (Foal / Colt / Filly / Stallion / Mare / Gelding).
     - Horse: MicrochipNumber, PassportNumber, SireName, DamName (thay Pedigree),
       HorseCode, VerifiedBy/VerifiedAt, ArchivedAt/ArchivedBy/ArchiveReason.
       RegistrationStatus: Draft / Submitted / PendingExam / Approved / Rejected / Archived.
     - RegistrationRequest.Status: Submitted / PendingExam / Approved / Rejected.
     - HorseDocument: UploadedBy, IsVisibleToOwner, CHECK DocumentType.
     - ProfileChangeRequest (mới): Owner xin sửa lý lịch, Manager duyệt.
   Flow 2
     - TrainerHorseAssignment: mỗi ngựa chỉ 1 phân công Active (unique index); bỏ trạng thái
       Suspended (trainer bận đã có Substitute Trainer lo).
     - TrainingPlan: Head Trainer duyệt trước khi áp dụng
       (Draft -> Pending Approval -> Active; trả về thì quay lại Draft kèm ReviewNote).
     - TrainingSession.SubstituteTrainerID: trainer giám sát thay (NULL = trainer phụ trách).
     - TrainingResult.SubstituteObservation: nhận xét của Substitute Trainer.
   Flow 3
     - TrainingLock: LockLevel (Full / Restricted), MaxIntensity, Reason NVARCHAR.
     - MedicalRecord: WeightKg, HeightCm, Symptoms, Conclusion (khớp phiếu khám của frontend).
     - User: Address.
     - MedicalRecord: RecordStatus (Draft / Signed), SignedAt, ExamDate DATETIME2,
       TrainingSessionID, RestrictionNote; 1 lần khám đầu vào cho mỗi hồ sơ tiếp nhận.
     - MedicalRecordAmendment (mới): đính chính bệnh án đã chốt.
     - Treatment (mới, tùy chọn): thuốc điều trị và thời gian ngưng thuốc.
     - HealthReport (thay CareIncidents): ai cũng báo được, Severity, gắn buổi tập
       và lần khám xử lý. HealthReportNote (mới): người sau thêm ghi chú, không báo trùng.
   Flow 4
     - CareTask.AssignedBy: người giao việc cho Groom.
   Quyền mới: HEALTH_REPORT, HORSE_ARCHIVE, PROFILE_EDIT_REQUEST, PROFILE_EDIT_APPROVE,
              MEDICAL_SIGN, INVENTORY_REQUEST, TRAINING_SESSION_SUPERVISE, TRAINING_PLAN_APPROVE.
   Không làm: bảng lịch sử chủ sở hữu (HorseOwnership) - mỗi ngựa một chủ (Horse.OwnerID).
   Trigger: Training Lock chỉ chặn buổi tập (Full chặn hết, Restricted chặn buổi vượt
            MaxIntensity); giáo án chỉ bị chặn lúc kích hoạt; tạo lock tự hủy buổi tập;
            bệnh án đã chốt không sửa / xóa được.
   ================================================================ */

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF DB_ID(N'RacehorseTrainingManagement') IS NULL
BEGIN
    CREATE DATABASE RacehorseTrainingManagement;
END
GO

USE RacehorseTrainingManagement;
GO

/* ================================================================
   CLEAN REBUILD
   Xóa view, bảng của bản v2 (nếu chạy lại) và bảng cũ tên số nhiều.
   ================================================================ */

DROP VIEW IF EXISTS dbo.vw_HorseTrainingAssignment;
DROP VIEW IF EXISTS dbo.vw_WorkRiderDailySchedule;
DROP VIEW IF EXISTS dbo.vw_HorseTrainingDashboard;
DROP VIEW IF EXISTS dbo.vw_PendingInitialExam;
DROP VIEW IF EXISTS dbo.vw_VetHealthReportQueue;
GO

/* Bảng v2 - theo thứ tự con trước, cha sau */
DROP TABLE IF EXISTS dbo.AuditLog;
DROP TABLE IF EXISTS dbo.InventoryRequestItem;
DROP TABLE IF EXISTS dbo.InventoryRequest;
DROP TABLE IF EXISTS dbo.InventoryItem;
DROP TABLE IF EXISTS dbo.CareTask;
DROP TABLE IF EXISTS dbo.DietMeal;
DROP TABLE IF EXISTS dbo.DietPlan;
DROP TABLE IF EXISTS dbo.HealthReportNote;
DROP TABLE IF EXISTS dbo.HealthReport;
DROP TABLE IF EXISTS dbo.MedicalSchedule;
DROP TABLE IF EXISTS dbo.Vaccination;
DROP TABLE IF EXISTS dbo.Treatment;
DROP TABLE IF EXISTS dbo.MedicalRecordAmendment;
DROP TABLE IF EXISTS dbo.MedicalRecord;
DROP TABLE IF EXISTS dbo.TrainingLock;
DROP TABLE IF EXISTS dbo.TrainingReview;
DROP TABLE IF EXISTS dbo.TrainingResult;
DROP TABLE IF EXISTS dbo.TrainingSession;
DROP TABLE IF EXISTS dbo.TrainingPlanStage;
DROP TABLE IF EXISTS dbo.TrainingPlan;
DROP TABLE IF EXISTS dbo.HorseWorkRiderPreference;
DROP TABLE IF EXISTS dbo.TrainerHorseAssignment;
DROP TABLE IF EXISTS dbo.HorseAssessment;
DROP TABLE IF EXISTS dbo.TrainerRaceResult;
DROP TABLE IF EXISTS dbo.TrainerCredential;
DROP TABLE IF EXISTS dbo.TrainerProfile;
DROP TABLE IF EXISTS dbo.TrainerSpecialization;
DROP TABLE IF EXISTS dbo.Specialization;
DROP TABLE IF EXISTS dbo.StallAssignment;
DROP TABLE IF EXISTS dbo.Stall;
DROP TABLE IF EXISTS dbo.ProfileChangeRequest;
DROP TABLE IF EXISTS dbo.RegistrationRequest;
DROP TABLE IF EXISTS dbo.HorseDocument;
DROP TABLE IF EXISTS dbo.Horse;
DROP TABLE IF EXISTS dbo.UserRole;
DROP TABLE IF EXISTS dbo.[User];
DROP TABLE IF EXISTS dbo.RolePermission;
DROP TABLE IF EXISTS dbo.Permission;
DROP TABLE IF EXISTS dbo.Role;
DROP TABLE IF EXISTS dbo.Club;
GO

/* Bảng cũ (horse.sql, tên số nhiều) - xóa để database chỉ còn một bộ bảng */
DROP TABLE IF EXISTS dbo.AuditLogs;
DROP TABLE IF EXISTS dbo.InventoryRequestItems;
DROP TABLE IF EXISTS dbo.InventoryRequests;
DROP TABLE IF EXISTS dbo.InventoryItems;
DROP TABLE IF EXISTS dbo.CareIncidents;
DROP TABLE IF EXISTS dbo.CareTasks;
DROP TABLE IF EXISTS dbo.DietMeals;
DROP TABLE IF EXISTS dbo.DietPlans;
DROP TABLE IF EXISTS dbo.MedicalSchedules;
DROP TABLE IF EXISTS dbo.Vaccinations;
DROP TABLE IF EXISTS dbo.MedicalRecords;
DROP TABLE IF EXISTS dbo.TrainingLocks;
DROP TABLE IF EXISTS dbo.TrainingReviews;
DROP TABLE IF EXISTS dbo.TrainingResults;
DROP TABLE IF EXISTS dbo.TrainingSessions;
DROP TABLE IF EXISTS dbo.TrainingPlanStages;
DROP TABLE IF EXISTS dbo.TrainingPlans;
DROP TABLE IF EXISTS dbo.HorseWorkRiderPreferences;
DROP TABLE IF EXISTS dbo.TrainerHorseAssignments;
DROP TABLE IF EXISTS dbo.HorseAssessments;
DROP TABLE IF EXISTS dbo.TrainerSpecializations;
DROP TABLE IF EXISTS dbo.Specializations;
DROP TABLE IF EXISTS dbo.StallAssignments;
DROP TABLE IF EXISTS dbo.Stalls;
DROP TABLE IF EXISTS dbo.RegistrationRequests;
DROP TABLE IF EXISTS dbo.HorseDocuments;
DROP TABLE IF EXISTS dbo.Horses;
DROP TABLE IF EXISTS dbo.UserRoles;
DROP TABLE IF EXISTS dbo.Users;
DROP TABLE IF EXISTS dbo.RolePermissions;
DROP TABLE IF EXISTS dbo.Permissions;
DROP TABLE IF EXISTS dbo.Roles;
DROP TABLE IF EXISTS dbo.Clubs;
GO

/* ================================================================
   COMMON / RBAC
   ================================================================ */

CREATE TABLE dbo.Club
(
    ClubID INT IDENTITY(1,1) PRIMARY KEY,
    ClubName NVARCHAR(150) NOT NULL,
    Address NVARCHAR(255),
    Phone VARCHAR(20),
    Email VARCHAR(100),
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_Club_Status DEFAULT 'Active',
    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_Club_CreatedAt DEFAULT SYSDATETIME(),

    CONSTRAINT UQ_Club_ClubName UNIQUE (ClubName),
    CONSTRAINT CK_Club_Status CHECK (Status IN ('Active', 'Inactive'))
);
GO

CREATE TABLE dbo.Role
(
    RoleID INT IDENTITY(1,1) PRIMARY KEY,
    RoleCode VARCHAR(40) NOT NULL,
    RoleName NVARCHAR(100) NOT NULL,
    Description NVARCHAR(500),

    CONSTRAINT UQ_Role_RoleCode UNIQUE (RoleCode),
    CONSTRAINT UQ_Role_RoleName UNIQUE (RoleName)
);
GO

CREATE TABLE dbo.Permission
(
    PermissionID INT IDENTITY(1,1) PRIMARY KEY,
    PermissionCode VARCHAR(60) NOT NULL,
    PermissionName NVARCHAR(150) NOT NULL,
    Description NVARCHAR(500),

    CONSTRAINT UQ_Permission_Code UNIQUE (PermissionCode)
);
GO

CREATE TABLE dbo.RolePermission
(
    RoleID INT NOT NULL,
    PermissionID INT NOT NULL,

    CONSTRAINT PK_RolePermission PRIMARY KEY (RoleID, PermissionID),
    CONSTRAINT FK_RolePermission_Role FOREIGN KEY (RoleID)
        REFERENCES dbo.Role(RoleID),
    CONSTRAINT FK_RolePermission_Permission FOREIGN KEY (PermissionID)
        REFERENCES dbo.Permission(PermissionID)
);
GO

CREATE TABLE dbo.[User]
(
    UserID INT IDENTITY(1,1) PRIMARY KEY,
    ClubID INT NULL,
    FullName NVARCHAR(150) NOT NULL,
    Email VARCHAR(100) NOT NULL,
    PasswordHash VARCHAR(255) NOT NULL,
    Phone VARCHAR(20),
    Address NVARCHAR(255),              -- địa chỉ liên hệ (chủ ngựa: giao nhận ngựa, giấy tờ)
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_User_Status DEFAULT 'Active',
    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_User_CreatedAt DEFAULT SYSDATETIME(),

    CONSTRAINT UQ_User_Email UNIQUE (Email),
    CONSTRAINT FK_User_Club FOREIGN KEY (ClubID)
        REFERENCES dbo.Club(ClubID),
    CONSTRAINT CK_User_Status CHECK (Status IN ('Active', 'Inactive', 'Suspended'))
);
GO

CREATE TABLE dbo.UserRole
(
    UserID INT NOT NULL,
    RoleID INT NOT NULL,
    AssignedAt DATETIME2 NOT NULL CONSTRAINT DF_UserRole_AssignedAt DEFAULT SYSDATETIME(),
    AssignedBy INT NULL,

    CONSTRAINT PK_UserRole PRIMARY KEY (UserID, RoleID),
    CONSTRAINT FK_UserRole_User FOREIGN KEY (UserID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_UserRole_Role FOREIGN KEY (RoleID)
        REFERENCES dbo.Role(RoleID),
    CONSTRAINT FK_UserRole_AssignedBy FOREIGN KEY (AssignedBy)
        REFERENCES dbo.[User](UserID)
);
GO

/* ================================================================
   FLOW 1 - HORSE REGISTRATION & PROFILE MANAGEMENT

   Draft (Owner đang soạn) -> Submitted (chờ CLB kiểm tra giấy tờ)
   -> PendingExam (chờ Vet trực khám đầu vào) -> Approved / Rejected
   -> Archived (lưu trữ). Rejected: Owner sửa và gửi lại thành Submitted.
   ================================================================ */

CREATE TABLE dbo.Horse
(
    HorseID INT IDENTITY(1,1) PRIMARY KEY,
    ClubID INT NOT NULL,
    OwnerID INT NOT NULL,

    /* Owner nhập */
    HorseName NVARCHAR(100) NOT NULL,
    Breed NVARCHAR(100),
    DateOfBirth DATE,
    CoatColor NVARCHAR(50),
    Gender VARCHAR(10),                 -- Male / Female / Gelding (đực đã thiến)
    SireName NVARCHAR(100),             -- tên ngựa cha
    DamName NVARCHAR(100),              -- tên ngựa mẹ
    MicrochipNumber VARCHAR(30) NULL,
    PassportNumber VARCHAR(50) NULL,

    /* CLB gán / xác minh */
    HorseCode VARCHAR(30) NULL,         -- mã ngựa nội bộ, gán khi duyệt
    VerifiedBy INT NULL,                -- Club Manager đối chiếu giấy tờ, microchip
    VerifiedAt DATETIME2 NULL,

    RegistrationStatus VARCHAR(20) NOT NULL CONSTRAINT DF_Horse_RegistrationStatus DEFAULT 'Draft',
    CurrentHealthStatus VARCHAR(30) NOT NULL CONSTRAINT DF_Horse_HealthStatus DEFAULT 'Unknown',

    ArchivedAt DATETIME2 NULL,
    ArchivedBy INT NULL,
    ArchiveReason NVARCHAR(500),

    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_Horse_CreatedAt DEFAULT SYSDATETIME(),
    UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_Horse_UpdatedAt DEFAULT SYSDATETIME(),

    /* Phân loại theo giới tính + tuổi, tự tính mỗi lần đọc (không lưu cứng vì tuổi thay đổi):
         Foal     : ngựa con dưới 1 tuổi
         Colt     : ngựa đực tơ 1 - dưới 4 tuổi, chưa thiến
         Filly    : ngựa cái non 1 - dưới 4 tuổi
         Stallion : ngựa đực từ 4 tuổi, chưa thiến
         Mare     : ngựa cái từ 4 tuổi
         Gelding  : ngựa đực đã thiến, mọi lứa tuổi */
    SexClass AS
    (
        CASE
            WHEN Gender IS NULL THEN NULL
            WHEN Gender = 'Gelding' THEN 'Gelding'
            WHEN DateOfBirth IS NULL THEN NULL
            WHEN DateOfBirth > DATEADD(YEAR, -1, CAST(GETDATE() AS DATE)) THEN 'Foal'
            WHEN DateOfBirth > DATEADD(YEAR, -4, CAST(GETDATE() AS DATE))
                THEN CASE Gender WHEN 'Male' THEN 'Colt' ELSE 'Filly' END
            ELSE CASE Gender WHEN 'Male' THEN 'Stallion' ELSE 'Mare' END
        END
    ),

    CONSTRAINT FK_Horse_Club FOREIGN KEY (ClubID)
        REFERENCES dbo.Club(ClubID),
    CONSTRAINT FK_Horse_Owner FOREIGN KEY (OwnerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_Horse_VerifiedBy FOREIGN KEY (VerifiedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_Horse_ArchivedBy FOREIGN KEY (ArchivedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_Horse_Gender CHECK (Gender IN ('Male', 'Female', 'Gelding') OR Gender IS NULL),
    CONSTRAINT CK_Horse_RegistrationStatus CHECK
    (
        RegistrationStatus IN ('Draft', 'Submitted', 'PendingExam', 'Approved', 'Rejected', 'Archived')
    ),
    CONSTRAINT CK_Horse_HealthStatus CHECK
    (
        CurrentHealthStatus IN ('Unknown', 'Healthy', 'Monitor', 'Injured', 'Recovering', 'Isolated')
    ),
    CONSTRAINT CK_Horse_Archive CHECK
    (
        RegistrationStatus <> 'Archived' OR (ArchivedAt IS NOT NULL AND ArchivedBy IS NOT NULL)
    ),
    CONSTRAINT CK_Horse_ApprovedHasCode CHECK
    (
        RegistrationStatus NOT IN ('Approved', 'Archived') OR HorseCode IS NOT NULL
    )
);
GO

CREATE TABLE dbo.HorseDocument
(
    DocumentID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    DocumentName NVARCHAR(150) NOT NULL,
    DocumentType VARCHAR(50) NOT NULL,
    FileUrl VARCHAR(500),
    UploadedBy INT NULL,
    IsVisibleToOwner BIT NOT NULL CONSTRAINT DF_HorseDocument_Visible DEFAULT 1,
    IsPrimary BIT NOT NULL CONSTRAINT DF_HorseDocument_Primary DEFAULT 0,
    IsRetired BIT NOT NULL CONSTRAINT DF_HorseDocument_Retired DEFAULT 0,
    IsProfileImage BIT NOT NULL CONSTRAINT DF_HorseDocument_ProfileImage DEFAULT 0,
    ReplacesDocumentID INT NULL,
    UploadedAt DATETIME2 NOT NULL CONSTRAINT DF_HorseDocument_UploadedAt DEFAULT SYSDATETIME(),

    CONSTRAINT FK_HorseDocument_PreviousVersion FOREIGN KEY (ReplacesDocumentID)
        REFERENCES dbo.HorseDocument(DocumentID),
    CONSTRAINT FK_HorseDocument_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_HorseDocument_UploadedBy FOREIGN KEY (UploadedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_HorseDocument_Type CHECK
    (
        DocumentType IN ('Passport', 'Microchip Certificate', 'Ownership Proof',
                         'Handover Record', 'Contract', 'Other')
    )
);
GO

/* Mỗi lần Owner gửi (hoặc gửi lại sau khi bị từ chối) tạo một dòng, giữ lịch sử các lần nộp. */
CREATE TABLE dbo.RegistrationRequest
(
    RegistrationRequestID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    OwnerID INT NOT NULL,
    ClubID INT NOT NULL,

    RequestDate DATETIME2 NOT NULL CONSTRAINT DF_RegistrationRequest_RequestDate DEFAULT SYSDATETIME(),
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_RegistrationRequest_Status DEFAULT 'Submitted',
    ManagerNote NVARCHAR(1000),
    ReviewedByClubManagerID INT NULL,
    ReviewedAt DATETIME2 NULL,

    CONSTRAINT FK_RegistrationRequest_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_RegistrationRequest_Owner FOREIGN KEY (OwnerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_RegistrationRequest_Club FOREIGN KEY (ClubID)
        REFERENCES dbo.Club(ClubID),
    CONSTRAINT FK_RegistrationRequest_Manager FOREIGN KEY (ReviewedByClubManagerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_RegistrationRequest_Status CHECK
    (
        Status IN ('Submitted', 'PendingExam', 'Approved', 'Rejected')
    )
);
GO

/* Sau khi duyệt, Owner không sửa trực tiếp lý lịch; gửi yêu cầu kèm bằng chứng để Manager duyệt. */
CREATE TABLE dbo.ProfileChangeRequest
(
    ProfileChangeRequestID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    RequestedBy INT NOT NULL,
    RequestedAt DATETIME2 NOT NULL CONSTRAINT DF_ProfileChangeRequest_RequestedAt DEFAULT SYSDATETIME(),
    ChangedFields NVARCHAR(MAX) NOT NULL,      -- ví dụ JSON: {"CoatColor": ["Bay", "Dark Bay"]}
    EvidenceDocumentID INT NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_ProfileChangeRequest_Status DEFAULT 'Pending',
    ReviewedBy INT NULL,
    ReviewedAt DATETIME2 NULL,
    ReviewNote NVARCHAR(1000),

    CONSTRAINT FK_ProfileChangeRequest_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_ProfileChangeRequest_RequestedBy FOREIGN KEY (RequestedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_ProfileChangeRequest_Evidence FOREIGN KEY (EvidenceDocumentID)
        REFERENCES dbo.HorseDocument(DocumentID),
    CONSTRAINT FK_ProfileChangeRequest_ReviewedBy FOREIGN KEY (ReviewedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_ProfileChangeRequest_Status CHECK
    (
        Status IN ('Pending', 'Approved', 'Rejected', 'Withdrawn')
    ),
    CONSTRAINT CK_ProfileChangeRequest_Review CHECK
    (
        Status = 'Pending' OR (ReviewedBy IS NOT NULL AND ReviewedAt IS NOT NULL)
    )
);
GO

/* ================================================================
   FLOW 1 SUPPORT - STABLE / STALL
   ================================================================ */

CREATE TABLE dbo.Stall
(
    StallID INT IDENTITY(1,1) PRIMARY KEY,
    ClubID INT NOT NULL,
    StallNumber VARCHAR(30) NOT NULL,
    StallType VARCHAR(50),
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_Stall_Status DEFAULT 'Available',

    CONSTRAINT FK_Stall_Club FOREIGN KEY (ClubID)
        REFERENCES dbo.Club(ClubID),
    CONSTRAINT UQ_Stall_Club_Number UNIQUE (ClubID, StallNumber),
    CONSTRAINT CK_Stall_Status CHECK
    (
        Status IN ('Available', 'Occupied', 'Maintenance')
    )
);
GO

CREATE TABLE dbo.StallAssignment
(
    StallAssignmentID INT IDENTITY(1,1) PRIMARY KEY,
    StallID INT NOT NULL,
    HorseID INT NOT NULL,
    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_StallAssignment_Status DEFAULT 'Active',

    CONSTRAINT FK_StallAssignment_Stall FOREIGN KEY (StallID)
        REFERENCES dbo.Stall(StallID),
    CONSTRAINT FK_StallAssignment_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT CK_StallAssignment_Dates CHECK (EndDate IS NULL OR EndDate >= StartDate),
    CONSTRAINT CK_StallAssignment_Status CHECK (Status IN ('Active', 'Ended'))
);
GO

/* ================================================================
   FLOW 2 - TRAINING PLAN MANAGEMENT

     Head Trainer -> HorseAssessment -> TrainerHorseAssignment (1 trainer phụ trách / ngựa)
     Trainer -> TrainingPlan -> TrainingPlanStage -> Head Trainer duyệt giáo án
     Head Trainer -> TrainingSession (giao Work Rider; chỉ định Substitute Trainer khi cần)
     Work Rider -> TrainingResult; Substitute Trainer -> SubstituteObservation
     Trainer phụ trách -> TrainingReview (AdjustmentRequired = 1 thì báo Head Trainer)
   ================================================================ */

CREATE TABLE dbo.Specialization
(
    SpecializationID INT IDENTITY(1,1) PRIMARY KEY,
    SpecializationCode VARCHAR(50) NOT NULL,
    SpecializationName NVARCHAR(150) NOT NULL,
    Description NVARCHAR(1000),
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_Specialization_Status DEFAULT 'Active',

    CONSTRAINT UQ_Specialization_Code UNIQUE (SpecializationCode),
    CONSTRAINT UQ_Specialization_Name UNIQUE (SpecializationName),
    CONSTRAINT CK_Specialization_Status CHECK (Status IN ('Active', 'Inactive'))
);
GO

CREATE TABLE dbo.TrainerSpecialization
(
    TrainerID INT NOT NULL,
    SpecializationID INT NOT NULL,
    AssignedAt DATETIME2 NOT NULL CONSTRAINT DF_TrainerSpecialization_AssignedAt DEFAULT SYSDATETIME(),

    CONSTRAINT PK_TrainerSpecialization PRIMARY KEY (TrainerID, SpecializationID),
    CONSTRAINT FK_TrainerSpecialization_Trainer FOREIGN KEY (TrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainerSpecialization_Specialization FOREIGN KEY (SpecializationID)
        REFERENCES dbo.Specialization(SpecializationID)
);
GO

/* Hồ sơ năng lực Trainer (Head Trainer / Manager nhập). Backend TÍNH, không lưu:
     YearsOfExperience = số năm từ CareerStartDate; ExperienceLevel: 0-2 năm Junior, 3-5 Intermediate,
     6-10 Senior, trên 10 Expert; Seniority = số năm từ bằng cấp / chứng chỉ / giấy phép sớm nhất (TrainerCredential);
     WinRate / PlaceRate = tỉ lệ về nhất / top 3 trong 12 tháng gần nhất, CareerStarts / CareerWins = cả sự nghiệp
     (TrainerRaceResult). */
CREATE TABLE dbo.TrainerProfile
(
    TrainerID INT NOT NULL PRIMARY KEY,
    CareerStartDate DATE NULL,
    TrainerRating DECIMAL(2,1) NULL,
    UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_TrainerProfile_UpdatedAt DEFAULT SYSDATETIME(),
    UpdatedBy INT NULL,

    CONSTRAINT FK_TrainerProfile_Trainer FOREIGN KEY (TrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainerProfile_UpdatedBy FOREIGN KEY (UpdatedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_TrainerProfile_Rating CHECK (TrainerRating IS NULL OR (TrainerRating >= 0 AND TrainerRating <= 5))
);
GO

/* Bằng cấp, chứng chỉ, giấy phép hành nghề, bằng khen của trainer (minh chứng thâm niên nghề). */
CREATE TABLE dbo.TrainerCredential
(
    CredentialID INT IDENTITY(1,1) PRIMARY KEY,
    TrainerID INT NOT NULL,
    CredentialType VARCHAR(20) NOT NULL,
    Title NVARCHAR(200) NOT NULL,
    IssuedBy NVARCHAR(200) NULL,
    IssuedDate DATE NOT NULL,
    ExpiryDate DATE NULL,
    FileUrl VARCHAR(500) NULL,
    Note NVARCHAR(1000) NULL,
    CreatedBy INT NOT NULL,
    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_TrainerCredential_CreatedAt DEFAULT SYSDATETIME(),

    CONSTRAINT FK_TrainerCredential_Trainer FOREIGN KEY (TrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainerCredential_CreatedBy FOREIGN KEY (CreatedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_TrainerCredential_Type CHECK (CredentialType IN ('Degree', 'Certificate', 'License', 'Award')),
    CONSTRAINT CK_TrainerCredential_Dates CHECK (ExpiryDate IS NULL OR ExpiryDate >= IssuedDate)
);
GO

/* Mỗi lần ngựa do trainer chuẩn bị ra đường đua (HorseID NULL = ngựa ngoài CLB, chỉ ghi HorseName). */
CREATE TABLE dbo.TrainerRaceResult
(
    RaceResultID INT IDENTITY(1,1) PRIMARY KEY,
    TrainerID INT NOT NULL,
    HorseID INT NULL,
    HorseName NVARCHAR(100) NOT NULL,
    RaceDate DATE NOT NULL,
    RaceName NVARCHAR(200) NOT NULL,
    RaceClass VARCHAR(20) NOT NULL CONSTRAINT DF_TrainerRaceResult_Class DEFAULT 'Other',
    FinishPosition INT NOT NULL,
    FieldSize INT NOT NULL,
    Note NVARCHAR(1000) NULL,
    CreatedBy INT NOT NULL,
    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_TrainerRaceResult_CreatedAt DEFAULT SYSDATETIME(),

    CONSTRAINT FK_TrainerRaceResult_Trainer FOREIGN KEY (TrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainerRaceResult_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_TrainerRaceResult_CreatedBy FOREIGN KEY (CreatedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_TrainerRaceResult_Class CHECK
        (RaceClass IN ('Group 1', 'Group 2', 'Group 3', 'Listed', 'Handicap', 'Maiden', 'Other')),
    CONSTRAINT CK_TrainerRaceResult_Position CHECK (FieldSize >= 2 AND FinishPosition BETWEEN 1 AND FieldSize)
);
GO
CREATE INDEX IX_TrainerRaceResult_Trainer_Date ON dbo.TrainerRaceResult (TrainerID, RaceDate);
GO

CREATE TABLE dbo.HorseAssessment
(
    AssessmentID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    HeadTrainerID INT NOT NULL,
    SpecializationID INT NOT NULL,

    AssessmentDate DATETIME2 NOT NULL CONSTRAINT DF_HorseAssessment_Date DEFAULT SYSDATETIME(),
    QualityScore DECIMAL(5,2) NULL,
    FitnessLevel VARCHAR(30),
    AssessmentNote NVARCHAR(2000),
    DecisionStatus VARCHAR(20) NOT NULL CONSTRAINT DF_HorseAssessment_Status DEFAULT 'Recommended',

    CONSTRAINT FK_HorseAssessment_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_HorseAssessment_HeadTrainer FOREIGN KEY (HeadTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_HorseAssessment_Specialization FOREIGN KEY (SpecializationID)
        REFERENCES dbo.Specialization(SpecializationID),
    CONSTRAINT CK_HorseAssessment_QualityScore CHECK
    (
        QualityScore IS NULL OR (QualityScore >= 0 AND QualityScore <= 100)
    ),
    CONSTRAINT CK_HorseAssessment_FitnessLevel CHECK
    (
        FitnessLevel IS NULL OR FitnessLevel IN ('Excellent', 'Good', 'Average', 'Needs Monitoring')
    ),
    CONSTRAINT CK_HorseAssessment_DecisionStatus CHECK
    (
        DecisionStatus IN ('Recommended', 'Rejected', 'Superseded')
    )
);
GO

CREATE TABLE dbo.TrainerHorseAssignment
(
    TrainerHorseAssignmentID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    TrainerID INT NOT NULL,
    SpecializationID INT NOT NULL,
    AssignedByHeadTrainerID INT NOT NULL,
    AssessmentID INT NULL,

    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_TrainerHorseAssignment_Status DEFAULT 'Active',
    AssignmentNote NVARCHAR(1000),

    CONSTRAINT FK_TrainerHorseAssignment_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_TrainerHorseAssignment_TrainerSpecialization
        FOREIGN KEY (TrainerID, SpecializationID)
        REFERENCES dbo.TrainerSpecialization(TrainerID, SpecializationID),
    CONSTRAINT FK_TrainerHorseAssignment_HeadTrainer FOREIGN KEY (AssignedByHeadTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainerHorseAssignment_Assessment FOREIGN KEY (AssessmentID)
        REFERENCES dbo.HorseAssessment(AssessmentID),
    CONSTRAINT CK_TrainerHorseAssignment_Dates CHECK
    (
        EndDate IS NULL OR EndDate >= StartDate
    ),
    CONSTRAINT CK_TrainerHorseAssignment_Status CHECK
    (
        Status IN ('Active', 'Ended')
    )
);
GO

/* Head Trainer đánh dấu Work Rider quen ngựa để ưu tiên; không cố định người cưỡi. */
CREATE TABLE dbo.HorseWorkRiderPreference
(
    PreferenceID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    WorkRiderID INT NOT NULL,
    AssignedByHeadTrainerID INT NOT NULL,

    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    Priority INT NOT NULL CONSTRAINT DF_HorseWorkRiderPreference_Priority DEFAULT 1,
    IsPreferred BIT NOT NULL CONSTRAINT DF_HorseWorkRiderPreference_IsPreferred DEFAULT 1,
    Note NVARCHAR(1000),

    CONSTRAINT FK_HorseWorkRiderPreference_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_HorseWorkRiderPreference_WorkRider FOREIGN KEY (WorkRiderID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_HorseWorkRiderPreference_HeadTrainer FOREIGN KEY (AssignedByHeadTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_HorseWorkRiderPreference_Dates CHECK
    (
        EndDate IS NULL OR EndDate >= StartDate
    ),
    CONSTRAINT CK_HorseWorkRiderPreference_Priority CHECK (Priority > 0)
);
GO

CREATE TABLE dbo.TrainingPlan
(
    TrainingPlanID INT IDENTITY(1,1) PRIMARY KEY,
    TrainerHorseAssignmentID INT NOT NULL,

    Goal NVARCHAR(1000),
    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    OverallIntensity VARCHAR(30),
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_TrainingPlan_Status DEFAULT 'Draft',
    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_TrainingPlan_CreatedAt DEFAULT SYSDATETIME(),
    Note NVARCHAR(2000),

    /* Head Trainer duyệt giáo án trước khi áp dụng */
    SubmittedAt DATETIME2 NULL,
    ApprovedByHeadTrainerID INT NULL,
    ApprovedAt DATETIME2 NULL,
    ReviewNote NVARCHAR(1000),          -- lý do trả về hoặc ghi chú khi duyệt

    CONSTRAINT FK_TrainingPlan_TrainerHorseAssignment FOREIGN KEY (TrainerHorseAssignmentID)
        REFERENCES dbo.TrainerHorseAssignment(TrainerHorseAssignmentID),
    CONSTRAINT FK_TrainingPlan_ApprovedBy FOREIGN KEY (ApprovedByHeadTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_TrainingPlan_Dates CHECK
    (
        EndDate IS NULL OR EndDate >= StartDate
    ),
    CONSTRAINT CK_TrainingPlan_Intensity CHECK
    (
        OverallIntensity IS NULL OR OverallIntensity IN ('Low', 'Moderate', 'High', 'Very High')
    ),
    CONSTRAINT CK_TrainingPlan_Status CHECK
    (
        Status IN ('Draft', 'Pending Approval', 'Active', 'Completed', 'Cancelled')
    ),
    CONSTRAINT CK_TrainingPlan_Approval CHECK
    (
        (Status <> 'Pending Approval' OR SubmittedAt IS NOT NULL)
        AND (Status NOT IN ('Active', 'Completed') OR (ApprovedByHeadTrainerID IS NOT NULL AND ApprovedAt IS NOT NULL))
    )
);
GO

CREATE TABLE dbo.TrainingPlanStage
(
    TrainingPlanStageID INT IDENTITY(1,1) PRIMARY KEY,
    TrainingPlanID INT NOT NULL,

    StageName NVARCHAR(100) NOT NULL,
    StageOrder INT NOT NULL,
    Goal NVARCHAR(1000),
    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    Intensity VARCHAR(30),
    TrainingLoad DECIMAL(10,2) NULL,
    DistanceTargetKm DECIMAL(10,2) NULL,
    Surface VARCHAR(50),
    Note NVARCHAR(1500),
    -- Trainer chốt giai đoạn: tổng kết gửi chủ ngựa
    ClosedAt DATETIME2 NULL,
    ClosedByID INT NULL,
    SummaryNote NVARCHAR(2000) NULL,

    CONSTRAINT FK_TrainingPlanStage_Plan FOREIGN KEY (TrainingPlanID)
        REFERENCES dbo.TrainingPlan(TrainingPlanID),
    CONSTRAINT FK_TrainingPlanStage_ClosedBy FOREIGN KEY (ClosedByID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT UQ_TrainingPlanStage_Order UNIQUE (TrainingPlanID, StageOrder),
    CONSTRAINT CK_TrainingPlanStage_Order CHECK (StageOrder > 0),
    CONSTRAINT CK_TrainingPlanStage_Dates CHECK
    (
        EndDate IS NULL OR EndDate >= StartDate
    ),
    CONSTRAINT CK_TrainingPlanStage_Intensity CHECK
    (
        Intensity IS NULL OR Intensity IN ('Low', 'Moderate', 'High', 'Very High')
    )
);
GO

CREATE TABLE dbo.TrainingSession
(
    TrainingSessionID INT IDENTITY(1,1) PRIMARY KEY,
    TrainingPlanStageID INT NOT NULL,

    /* Head Trainer giao Work Rider cho từng buổi. */
    WorkRiderID INT NOT NULL,
    AssignedByHeadTrainerID INT NOT NULL,

    /* Trainer giám sát thay khi trainer phụ trách bận.
       NULL = trainer phụ trách (TrainerHorseAssignment) tự giám sát. */
    SubstituteTrainerID INT NULL,

    SessionDate DATE NOT NULL,
    StartTime TIME(0) NOT NULL,
    EndTime TIME(0) NULL,
    SequenceNo INT NOT NULL,

    TrainingType VARCHAR(60) NOT NULL,
    DurationPlannedMinutes INT NULL,
    DistancePlannedKm DECIMAL(10,2) NULL,
    TargetSpeedKmh DECIMAL(8,2) NULL,
    TrainingLoad DECIMAL(10,2) NULL,
    Surface VARCHAR(50),
    Location NVARCHAR(150),
    Instructions NVARCHAR(2000),

    Status VARCHAR(20) NOT NULL CONSTRAINT DF_TrainingSession_Status DEFAULT 'Assigned',

    CONSTRAINT FK_TrainingSession_Stage FOREIGN KEY (TrainingPlanStageID)
        REFERENCES dbo.TrainingPlanStage(TrainingPlanStageID),
    CONSTRAINT FK_TrainingSession_WorkRider FOREIGN KEY (WorkRiderID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainingSession_HeadTrainer FOREIGN KEY (AssignedByHeadTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainingSession_SubstituteTrainer FOREIGN KEY (SubstituteTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT UQ_TrainingSession_RiderSlot UNIQUE (WorkRiderID, SessionDate, SequenceNo),
    CONSTRAINT CK_TrainingSession_Sequence CHECK (SequenceNo > 0),
    CONSTRAINT CK_TrainingSession_Time CHECK (EndTime IS NULL OR EndTime >= StartTime),
    CONSTRAINT CK_TrainingSession_Duration CHECK
    (
        DurationPlannedMinutes IS NULL OR DurationPlannedMinutes > 0
    ),
    CONSTRAINT CK_TrainingSession_Distance CHECK
    (
        DistancePlannedKm IS NULL OR DistancePlannedKm >= 0
    ),
    CONSTRAINT CK_TrainingSession_Status CHECK
    (
        Status IN ('Assigned', 'In Progress', 'Completed', 'Cancelled', 'Missed')
    )
);
GO

CREATE TABLE dbo.TrainingResult
(
    TrainingResultID INT IDENTITY(1,1) PRIMARY KEY,
    TrainingSessionID INT NOT NULL,

    ActualDurationMinutes INT NULL,
    ActualDistanceKm DECIMAL(10,2) NULL,
    AvgSpeedKmh DECIMAL(8,2) NULL,
    MaxSpeedKmh DECIMAL(8,2) NULL,
    AvgHeartRate INT NULL,
    MaxHeartRate INT NULL,
    RecoveryMinutes INT NULL,
    PerformanceScore DECIMAL(5,2) NULL,
    RiderObservation NVARCHAR(2000),            -- Work Rider ghi cảm nhận khi cưỡi
    SubstituteObservation NVARCHAR(2000) NULL,  -- Substitute Trainer ghi những gì quan sát được
    VideoUrl VARCHAR(500),
    RecordedAt DATETIME2 NOT NULL CONSTRAINT DF_TrainingResult_RecordedAt DEFAULT SYSDATETIME(),

    CONSTRAINT FK_TrainingResult_Session FOREIGN KEY (TrainingSessionID)
        REFERENCES dbo.TrainingSession(TrainingSessionID),
    CONSTRAINT UQ_TrainingResult_Session UNIQUE (TrainingSessionID),
    CONSTRAINT CK_TrainingResult_Performance CHECK
    (
        PerformanceScore IS NULL OR (PerformanceScore >= 0 AND PerformanceScore <= 100)
    ),
    CONSTRAINT CK_TrainingResult_HeartRate CHECK
    (
        (AvgHeartRate IS NULL OR AvgHeartRate > 0)
        AND (MaxHeartRate IS NULL OR MaxHeartRate > 0)
    ),
    CONSTRAINT CK_TrainingResult_Distance CHECK
    (
        ActualDistanceKm IS NULL OR ActualDistanceKm >= 0
    )
);
GO

CREATE TABLE dbo.TrainingReview
(
    TrainingReviewID INT IDENTITY(1,1) PRIMARY KEY,
    TrainingSessionID INT NOT NULL,
    TrainerID INT NOT NULL,                     -- trainer phụ trách

    ReviewDate DATETIME2 NOT NULL CONSTRAINT DF_TrainingReview_ReviewDate DEFAULT SYSDATETIME(),
    Evaluation VARCHAR(30),
    TrainerComment NVARCHAR(2000),
    AdjustmentRequired BIT NOT NULL CONSTRAINT DF_TrainingReview_AdjustmentRequired DEFAULT 0,
    AdjustmentNote NVARCHAR(1500),

    CONSTRAINT FK_TrainingReview_Session FOREIGN KEY (TrainingSessionID)
        REFERENCES dbo.TrainingSession(TrainingSessionID),
    CONSTRAINT FK_TrainingReview_Trainer FOREIGN KEY (TrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_TrainingReview_Evaluation CHECK
    (
        Evaluation IS NULL OR Evaluation IN ('Excellent', 'Good', 'Average', 'Needs Improvement')
    )
);
GO

/* ================================================================
   FLOW 3 - MEDICAL & INJURY MANAGEMENT
   ================================================================ */

/* LockLevel = 'Full': cấm tập hoàn toàn.
   LockLevel = 'Restricted': được tập nhẹ, buổi tập không được vượt MaxIntensity
   (so với TrainingSession.TrainingLoad). */
CREATE TABLE dbo.TrainingLock
(
    TrainingLockID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    CreatedByVetID INT NOT NULL,

    Reason NVARCHAR(100) NOT NULL,
    LockLevel VARCHAR(20) NOT NULL CONSTRAINT DF_TrainingLock_Level DEFAULT 'Full',
    MaxIntensity DECIMAL(10,2) NULL,
    LockStartDate DATETIME2 NOT NULL,
    LockEndDate DATETIME2 NULL,
    LockStatus VARCHAR(20) NOT NULL CONSTRAINT DF_TrainingLock_Status DEFAULT 'Active',
    Details NVARCHAR(2000),
    ReleasedByVetID INT NULL,
    ReleasedAt DATETIME2 NULL,

    CONSTRAINT FK_TrainingLock_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_TrainingLock_CreatedByVet FOREIGN KEY (CreatedByVetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_TrainingLock_ReleasedByVet FOREIGN KEY (ReleasedByVetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_TrainingLock_Level CHECK
    (
        LockLevel IN ('Full', 'Restricted')
        AND (LockLevel = 'Restricted' OR MaxIntensity IS NULL)
        AND (MaxIntensity IS NULL OR MaxIntensity >= 0)
    ),
    CONSTRAINT CK_TrainingLock_Dates CHECK
    (
        LockEndDate IS NULL OR LockEndDate >= LockStartDate
    ),
    CONSTRAINT CK_TrainingLock_Status CHECK
    (
        LockStatus IN ('Active', 'Released')
        AND (LockStatus = 'Active' OR (LockEndDate IS NOT NULL AND ReleasedByVetID IS NOT NULL))
    )
);
GO

/* RecordStatus: Draft (Vet đang ghi, sửa được) -> Signed (đã chốt, không sửa đè;
   muốn sửa thì thêm MedicalRecordAmendment). */
CREATE TABLE dbo.MedicalRecord
(
    MedicalRecordID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    VetID INT NOT NULL,
    RegistrationRequestID INT NULL,     -- lần khám đầu vào gắn với hồ sơ tiếp nhận
    TrainingSessionID INT NULL,         -- bệnh phát hiện trong buổi tập nào

    ExamDate DATETIME2 NOT NULL,
    ExamType VARCHAR(50) NOT NULL,
    WeightKg DECIMAL(6,1) NULL,         -- cân nặng lúc khám
    HeightCm DECIMAL(5,1) NULL,         -- chiều cao (đo đến u vai) lúc khám
    Symptoms NVARCHAR(1500),            -- triệu chứng / quan sát
    Diagnosis NVARCHAR(1500),
    Conclusion NVARCHAR(1500),          -- kết luận của Vet
    InjuryLocation NVARCHAR(500),
    TreatmentPlan NVARCHAR(3000),
    HealthStatus VARCHAR(30),
    TrainingEligibility VARCHAR(30),
    RestrictionNote NVARCHAR(1000),     -- ghi rõ hạn chế khi Restricted
    FollowUpDate DATE NULL,
    Note NVARCHAR(1500),

    RecordStatus VARCHAR(20) NOT NULL CONSTRAINT DF_MedicalRecord_RecordStatus DEFAULT 'Draft',
    SignedAt DATETIME2 NULL,

    CONSTRAINT FK_MedicalRecord_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_MedicalRecord_Vet FOREIGN KEY (VetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_MedicalRecord_RegistrationRequest FOREIGN KEY (RegistrationRequestID)
        REFERENCES dbo.RegistrationRequest(RegistrationRequestID),
    CONSTRAINT FK_MedicalRecord_TrainingSession FOREIGN KEY (TrainingSessionID)
        REFERENCES dbo.TrainingSession(TrainingSessionID),
    CONSTRAINT CK_MedicalRecord_ExamType CHECK
    (
        ExamType IN ('Initial Exam', 'Routine Exam', 'Injury Exam', 'Follow-up', 'Emergency')
    ),
    CONSTRAINT CK_MedicalRecord_HealthStatus CHECK
    (
        HealthStatus IS NULL OR HealthStatus IN ('Healthy', 'Monitor', 'Injured', 'Recovering', 'Isolated')
    ),
    CONSTRAINT CK_MedicalRecord_TrainingEligibility CHECK
    (
        TrainingEligibility IS NULL OR TrainingEligibility IN ('Eligible', 'Restricted', 'Not Eligible')
    ),
    CONSTRAINT CK_MedicalRecord_Restriction CHECK
    (
        TrainingEligibility IS NULL OR TrainingEligibility <> 'Restricted' OR RestrictionNote IS NOT NULL
    ),
    CONSTRAINT CK_MedicalRecord_Measures CHECK
    (
        (WeightKg IS NULL OR WeightKg > 0)
        AND (HeightCm IS NULL OR HeightCm > 0)
    ),
    CONSTRAINT CK_MedicalRecord_FollowUp CHECK
    (
        FollowUpDate IS NULL OR FollowUpDate >= CAST(ExamDate AS DATE)
    ),
    CONSTRAINT CK_MedicalRecord_RecordStatus CHECK
    (
        RecordStatus IN ('Draft', 'Signed')
        AND (RecordStatus = 'Draft' OR SignedAt IS NOT NULL)
    )
);
GO

CREATE TABLE dbo.MedicalRecordAmendment
(
    MedicalRecordAmendmentID INT IDENTITY(1,1) PRIMARY KEY,
    MedicalRecordID INT NOT NULL,
    AmendedBy INT NOT NULL,
    AmendedAt DATETIME2 NOT NULL CONSTRAINT DF_MedicalRecordAmendment_AmendedAt DEFAULT SYSDATETIME(),
    Reason NVARCHAR(1000) NOT NULL,
    AmendedContent NVARCHAR(MAX) NOT NULL,

    CONSTRAINT FK_MedicalRecordAmendment_Record FOREIGN KEY (MedicalRecordID)
        REFERENCES dbo.MedicalRecord(MedicalRecordID),
    CONSTRAINT FK_MedicalRecordAmendment_AmendedBy FOREIGN KEY (AmendedBy)
        REFERENCES dbo.[User](UserID)
);
GO

/* Tùy chọn: có thể để giai đoạn sau nếu thầy thấy vượt phạm vi. */
CREATE TABLE dbo.Treatment
(
    TreatmentID INT IDENTITY(1,1) PRIMARY KEY,
    MedicalRecordID INT NOT NULL,
    MedicineName NVARCHAR(150) NOT NULL,
    Dose NVARCHAR(100) NOT NULL,
    Route VARCHAR(30) NOT NULL,
    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    WithdrawalUntil DATE NULL,          -- ngày hết thời gian ngưng thuốc (kiểm tra doping)
    Note NVARCHAR(1000),

    CONSTRAINT FK_Treatment_MedicalRecord FOREIGN KEY (MedicalRecordID)
        REFERENCES dbo.MedicalRecord(MedicalRecordID),
    CONSTRAINT CK_Treatment_Route CHECK
    (
        Route IN ('Oral', 'Injection', 'Topical', 'Inhalation', 'Other')
    ),
    CONSTRAINT CK_Treatment_Dates CHECK
    (
        (EndDate IS NULL OR EndDate >= StartDate)
        AND (WithdrawalUntil IS NULL OR WithdrawalUntil >= StartDate)
    )
);
GO

CREATE TABLE dbo.Vaccination
(
    VaccinationID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    VetID INT NULL,

    VaccineName NVARCHAR(150) NOT NULL,
    VaccinationDate DATE NOT NULL,
    NextDueDate DATE NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_Vaccination_Status DEFAULT 'Scheduled',
    Note NVARCHAR(1000),

    CONSTRAINT FK_Vaccination_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_Vaccination_Vet FOREIGN KEY (VetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_Vaccination_Dates CHECK
    (
        NextDueDate IS NULL OR NextDueDate >= VaccinationDate
    ),
    CONSTRAINT CK_Vaccination_Status CHECK
    (
        Status IN ('Scheduled', 'Completed', 'Overdue', 'Cancelled')
    )
);
GO

CREATE TABLE dbo.MedicalSchedule
(
    MedicalScheduleID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    VetID INT NULL,

    ScheduleType VARCHAR(50) NOT NULL,
    ScheduledDate DATE NOT NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_MedicalSchedule_Status DEFAULT 'Scheduled',
    Note NVARCHAR(1000),

    CONSTRAINT FK_MedicalSchedule_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_MedicalSchedule_Vet FOREIGN KEY (VetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_MedicalSchedule_Type CHECK
    (
        ScheduleType IN ('Vaccination', 'Deworming', 'Farrier', 'Routine Examination')
    ),
    CONSTRAINT CK_MedicalSchedule_Status CHECK
    (
        Status IN ('Scheduled', 'Completed', 'Cancelled', 'Overdue')
    )
);
GO

/* Báo cáo sự cố sức khỏe (thay CareIncidents).
   Groom, Work Rider, Trainer (kể cả Substitute), Head Trainer đều báo được (quyền HEALTH_REPORT).
   Báo cáo vào hàng chờ của Vet trực; Trainer phụ trách và Head Trainer nhận thông báo. */
CREATE TABLE dbo.HealthReport
(
    HealthReportID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    ReportedBy INT NOT NULL,
    TrainingSessionID INT NULL,         -- phát hiện trong buổi tập nào (nếu có)

    ReportedAt DATETIME2 NOT NULL CONSTRAINT DF_HealthReport_ReportedAt DEFAULT SYSDATETIME(),
    Severity VARCHAR(10) NOT NULL CONSTRAINT DF_HealthReport_Severity DEFAULT 'Normal',
    Description NVARCHAR(2500) NOT NULL,
    ImageUrl VARCHAR(500),

    Status VARCHAR(20) NOT NULL CONSTRAINT DF_HealthReport_Status DEFAULT 'Reported',
    VetID INT NULL,                     -- Vet trực nhận ca
    MedicalRecordID INT NULL,           -- lần khám Vet tạo để xử lý báo cáo
    VetNote NVARCHAR(2000),
    ResolvedAt DATETIME2 NULL,

    CONSTRAINT FK_HealthReport_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_HealthReport_ReportedBy FOREIGN KEY (ReportedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_HealthReport_TrainingSession FOREIGN KEY (TrainingSessionID)
        REFERENCES dbo.TrainingSession(TrainingSessionID),
    CONSTRAINT FK_HealthReport_Vet FOREIGN KEY (VetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_HealthReport_MedicalRecord FOREIGN KEY (MedicalRecordID)
        REFERENCES dbo.MedicalRecord(MedicalRecordID),
    CONSTRAINT CK_HealthReport_Severity CHECK (Severity IN ('Urgent', 'Normal')),
    CONSTRAINT CK_HealthReport_Status CHECK
    (
        Status IN ('Reported', 'Reviewing', 'Resolved')
        AND (Status = 'Reported' OR VetID IS NOT NULL)
        AND (Status <> 'Resolved' OR ResolvedAt IS NOT NULL)
    )
);
GO

/* Sự cố đã có người báo: người sau thêm ghi chú vào báo cáo có sẵn thay vì báo trùng. */
CREATE TABLE dbo.HealthReportNote
(
    HealthReportNoteID INT IDENTITY(1,1) PRIMARY KEY,
    HealthReportID INT NOT NULL,
    NoteBy INT NOT NULL,
    NoteAt DATETIME2 NOT NULL CONSTRAINT DF_HealthReportNote_NoteAt DEFAULT SYSDATETIME(),
    Content NVARCHAR(2000) NOT NULL,

    CONSTRAINT FK_HealthReportNote_Report FOREIGN KEY (HealthReportID)
        REFERENCES dbo.HealthReport(HealthReportID),
    CONSTRAINT FK_HealthReportNote_NoteBy FOREIGN KEY (NoteBy)
        REFERENCES dbo.[User](UserID)
);
GO

/* ================================================================
   FLOW 4 - STABLE CARE & NUTRITION
   ================================================================ */

CREATE TABLE dbo.DietPlan
(
    DietPlanID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    CreatedByHeadTrainerID INT NOT NULL,
    ReviewedByVetID INT NULL,

    DietDescription NVARCHAR(2000),
    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_DietPlan_Status DEFAULT 'Pending',
    VetNote NVARCHAR(1500),
    CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_DietPlan_CreatedAt DEFAULT SYSDATETIME(),
    ApprovedAt DATETIME2 NULL,

    CONSTRAINT FK_DietPlan_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_DietPlan_HeadTrainer FOREIGN KEY (CreatedByHeadTrainerID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_DietPlan_Vet FOREIGN KEY (ReviewedByVetID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_DietPlan_Dates CHECK
    (
        EndDate IS NULL OR EndDate >= StartDate
    ),
    CONSTRAINT CK_DietPlan_Status CHECK
    (
        Status IN ('Pending', 'Approved', 'Rejected', 'Adjusted', 'Expired')
    )
);
GO

CREATE TABLE dbo.DietMeal
(
    DietMealID INT IDENTITY(1,1) PRIMARY KEY,
    DietPlanID INT NOT NULL,

    MealTime TIME(0) NOT NULL,
    FeedType NVARCHAR(100) NOT NULL,
    Quantity DECIMAL(10,2) NOT NULL,
    Unit VARCHAR(30) NOT NULL,
    Note NVARCHAR(1000),

    CONSTRAINT FK_DietMeal_DietPlan FOREIGN KEY (DietPlanID)
        REFERENCES dbo.DietPlan(DietPlanID),
    CONSTRAINT CK_DietMeal_Quantity CHECK (Quantity > 0)
);
GO

CREATE TABLE dbo.CareTask
(
    CareTaskID INT IDENTITY(1,1) PRIMARY KEY,
    HorseID INT NOT NULL,
    GroomID INT NOT NULL,
    AssignedBy INT NULL,                -- người giao việc; NULL nếu Groom tự tạo

    TaskType VARCHAR(50) NOT NULL,
    ScheduledAt DATETIME2 NOT NULL,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_CareTask_Status DEFAULT 'Pending',
    CompletedAt DATETIME2 NULL,
    Note NVARCHAR(1000),

    CONSTRAINT FK_CareTask_Horse FOREIGN KEY (HorseID)
        REFERENCES dbo.Horse(HorseID),
    CONSTRAINT FK_CareTask_Groom FOREIGN KEY (GroomID)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_CareTask_AssignedBy FOREIGN KEY (AssignedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_CareTask_Type CHECK
    (
        TaskType IN ('Feeding', 'Cleaning', 'Bathing', 'Ice Leg Soak')
    ),
    CONSTRAINT CK_CareTask_Status CHECK
    (
        Status IN ('Pending', 'Completed', 'Skipped')
        AND (Status <> 'Completed' OR CompletedAt IS NOT NULL)
    )
);
GO

CREATE TABLE dbo.InventoryItem
(
    InventoryItemID INT IDENTITY(1,1) PRIMARY KEY,
    ClubID INT NOT NULL,

    ItemName NVARCHAR(150) NOT NULL,
    ItemType VARCHAR(50) NOT NULL,
    Quantity DECIMAL(12,2) NOT NULL CONSTRAINT DF_InventoryItem_Quantity DEFAULT 0,
    Unit VARCHAR(30) NOT NULL,
    MinimumQuantity DECIMAL(12,2) NOT NULL CONSTRAINT DF_InventoryItem_Minimum DEFAULT 0,
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_InventoryItem_Status DEFAULT 'Available',

    CONSTRAINT FK_InventoryItem_Club FOREIGN KEY (ClubID)
        REFERENCES dbo.Club(ClubID),
    CONSTRAINT CK_InventoryItem_Type CHECK
    (
        ItemType IN ('Food', 'Medicine', 'Care Equipment')
    ),
    CONSTRAINT CK_InventoryItem_Quantity CHECK
    (
        Quantity >= 0 AND MinimumQuantity >= 0
    ),
    CONSTRAINT CK_InventoryItem_Status CHECK
    (
        Status IN ('Available', 'Low Stock', 'Out of Stock', 'Inactive')
    )
);
GO

CREATE TABLE dbo.InventoryRequest
(
    InventoryRequestID INT IDENTITY(1,1) PRIMARY KEY,
    ClubID INT NOT NULL,
    RequestedBy INT NOT NULL,
    ApprovedBy INT NULL,

    RequestDate DATETIME2 NOT NULL CONSTRAINT DF_InventoryRequest_Date DEFAULT SYSDATETIME(),
    Status VARCHAR(20) NOT NULL CONSTRAINT DF_InventoryRequest_Status DEFAULT 'Pending',
    Reason NVARCHAR(1500),
    ApprovedAt DATETIME2 NULL,

    CONSTRAINT FK_InventoryRequest_Club FOREIGN KEY (ClubID)
        REFERENCES dbo.Club(ClubID),
    CONSTRAINT FK_InventoryRequest_RequestedBy FOREIGN KEY (RequestedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT FK_InventoryRequest_ApprovedBy FOREIGN KEY (ApprovedBy)
        REFERENCES dbo.[User](UserID),
    CONSTRAINT CK_InventoryRequest_Status CHECK
    (
        Status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')
    )
);
GO

CREATE TABLE dbo.InventoryRequestItem
(
    InventoryRequestItemID INT IDENTITY(1,1) PRIMARY KEY,
    InventoryRequestID INT NOT NULL,
    InventoryItemID INT NOT NULL,

    RequestedQuantity DECIMAL(12,2) NOT NULL,
    ApprovedQuantity DECIMAL(12,2) NULL,
    Note NVARCHAR(1000),

    CONSTRAINT FK_InventoryRequestItem_Request FOREIGN KEY (InventoryRequestID)
        REFERENCES dbo.InventoryRequest(InventoryRequestID),
    CONSTRAINT FK_InventoryRequestItem_Item FOREIGN KEY (InventoryItemID)
        REFERENCES dbo.InventoryItem(InventoryItemID),
    CONSTRAINT UQ_InventoryRequestItem UNIQUE (InventoryRequestID, InventoryItemID),
    CONSTRAINT CK_InventoryRequestItem_Quantity CHECK
    (
        RequestedQuantity > 0
        AND (ApprovedQuantity IS NULL OR (ApprovedQuantity >= 0 AND ApprovedQuantity <= RequestedQuantity))
    )
);
GO

/* ================================================================
   AUDIT LOG
   ================================================================ */

CREATE TABLE dbo.AuditLog
(
    AuditLogID BIGINT IDENTITY(1,1) PRIMARY KEY,
    UserID INT NULL,
    ActionType VARCHAR(50) NOT NULL,
    EntityName VARCHAR(100) NOT NULL,
    EntityID INT NULL,
    ActionTime DATETIME2 NOT NULL CONSTRAINT DF_AuditLog_ActionTime DEFAULT SYSDATETIME(),
    Details NVARCHAR(MAX),

    CONSTRAINT FK_AuditLog_User FOREIGN KEY (UserID)
        REFERENCES dbo.[User](UserID)
);
GO

/* ================================================================
   INDEXES
   ================================================================ */

CREATE INDEX IX_User_ClubID
    ON dbo.[User](ClubID);

CREATE INDEX IX_UserRole_RoleID
    ON dbo.UserRole(RoleID);

CREATE INDEX IX_Horse_ClubID_Status
    ON dbo.Horse(ClubID, RegistrationStatus);

CREATE INDEX IX_Horse_OwnerID
    ON dbo.Horse(OwnerID);

/* Microchip không trùng; mã ngựa không trùng trong một CLB */
CREATE UNIQUE INDEX UX_Horse_MicrochipNumber
    ON dbo.Horse(MicrochipNumber)
    WHERE MicrochipNumber IS NOT NULL;

CREATE UNIQUE INDEX UX_Horse_Club_HorseCode
    ON dbo.Horse(ClubID, HorseCode)
    WHERE HorseCode IS NOT NULL;

CREATE INDEX IX_HorseDocument_HorseID
    ON dbo.HorseDocument(HorseID);

CREATE INDEX IX_RegistrationRequest_ClubID_Status
    ON dbo.RegistrationRequest(ClubID, Status);

CREATE INDEX IX_ProfileChangeRequest_HorseID_Status
    ON dbo.ProfileChangeRequest(HorseID, Status);

CREATE INDEX IX_StallAssignment_HorseID_Status
    ON dbo.StallAssignment(HorseID, Status);

CREATE UNIQUE INDEX UX_StallAssignment_OneActivePerStall
    ON dbo.StallAssignment(StallID)
    WHERE Status = 'Active';

CREATE UNIQUE INDEX UX_StallAssignment_OneActivePerHorse
    ON dbo.StallAssignment(HorseID)
    WHERE Status = 'Active';

CREATE INDEX IX_TrainerSpecialization_SpecializationID
    ON dbo.TrainerSpecialization(SpecializationID);

CREATE INDEX IX_HorseAssessment_HorseID_Date
    ON dbo.HorseAssessment(HorseID, AssessmentDate DESC);

/* Mỗi ngựa chỉ có một trainer phụ trách tại một thời điểm */
CREATE UNIQUE INDEX UX_TrainerHorseAssignment_OneActivePerHorse
    ON dbo.TrainerHorseAssignment(HorseID)
    WHERE Status = 'Active';

CREATE INDEX IX_TrainerHorseAssignment_TrainerID_Status
    ON dbo.TrainerHorseAssignment(TrainerID, Status);

CREATE INDEX IX_HorseWorkRiderPreference_HorseID
    ON dbo.HorseWorkRiderPreference(HorseID, IsPreferred, Priority);

CREATE INDEX IX_TrainingPlan_AssignmentID_Status
    ON dbo.TrainingPlan(TrainerHorseAssignmentID, Status);

CREATE INDEX IX_TrainingPlanStage_PlanID_Date
    ON dbo.TrainingPlanStage(TrainingPlanID, StartDate, EndDate);

CREATE INDEX IX_TrainingSession_StageID_Date
    ON dbo.TrainingSession(TrainingPlanStageID, SessionDate);

CREATE INDEX IX_TrainingSession_Substitute_Date
    ON dbo.TrainingSession(SubstituteTrainerID, SessionDate)
    WHERE SubstituteTrainerID IS NOT NULL;

CREATE INDEX IX_TrainingReview_SessionID
    ON dbo.TrainingReview(TrainingSessionID);

CREATE INDEX IX_TrainingLock_HorseID_Dates
    ON dbo.TrainingLock(HorseID, LockStartDate, LockEndDate);

CREATE UNIQUE INDEX UX_TrainingLock_OneActivePerHorse
    ON dbo.TrainingLock(HorseID)
    WHERE LockStatus = 'Active';

CREATE INDEX IX_MedicalRecord_HorseID_Date
    ON dbo.MedicalRecord(HorseID, ExamDate DESC);

/* Mỗi hồ sơ tiếp nhận chỉ có 1 lần khám đầu vào (Vet trực khám, không cần chỉ định) */
CREATE UNIQUE INDEX UX_MedicalRecord_OneInitialExamPerRequest
    ON dbo.MedicalRecord(RegistrationRequestID)
    WHERE ExamType = 'Initial Exam' AND RegistrationRequestID IS NOT NULL;

CREATE INDEX IX_MedicalRecordAmendment_RecordID
    ON dbo.MedicalRecordAmendment(MedicalRecordID);

CREATE INDEX IX_Treatment_RecordID
    ON dbo.Treatment(MedicalRecordID);

CREATE INDEX IX_Vaccination_HorseID_DueDate
    ON dbo.Vaccination(HorseID, NextDueDate);

CREATE INDEX IX_MedicalSchedule_HorseID_Date
    ON dbo.MedicalSchedule(HorseID, ScheduledDate);

CREATE INDEX IX_HealthReport_Status_Severity
    ON dbo.HealthReport(Status, Severity, ReportedAt);

CREATE INDEX IX_HealthReport_HorseID_Date
    ON dbo.HealthReport(HorseID, ReportedAt DESC);

CREATE INDEX IX_HealthReportNote_ReportID
    ON dbo.HealthReportNote(HealthReportID);

CREATE INDEX IX_DietPlan_HorseID_Status
    ON dbo.DietPlan(HorseID, Status);

CREATE INDEX IX_CareTask_HorseID_Date
    ON dbo.CareTask(HorseID, ScheduledAt);

CREATE INDEX IX_CareTask_Groom_Date
    ON dbo.CareTask(GroomID, ScheduledAt);

CREATE INDEX IX_InventoryItem_ClubID_Status
    ON dbo.InventoryItem(ClubID, Status);

CREATE INDEX IX_InventoryRequest_ClubID_Status
    ON dbo.InventoryRequest(ClubID, Status);

CREATE INDEX IX_AuditLog_UserID_ActionTime
    ON dbo.AuditLog(UserID, ActionTime DESC);
GO

/* ================================================================
   VIEWS
   ================================================================ */

CREATE VIEW dbo.vw_HorseTrainingAssignment
AS
SELECT
    h.HorseID,
    h.HorseName,
    s.SpecializationID,
    s.SpecializationName,
    tha.TrainerHorseAssignmentID,
    tha.TrainerID,
    tr.FullName AS TrainerName,
    tha.AssignedByHeadTrainerID,
    ht.FullName AS HeadTrainerName,
    tha.StartDate,
    tha.EndDate,
    tha.Status AS AssignmentStatus
FROM dbo.TrainerHorseAssignment tha
JOIN dbo.Horse h
    ON h.HorseID = tha.HorseID
JOIN dbo.Specialization s
    ON s.SpecializationID = tha.SpecializationID
JOIN dbo.[User] tr
    ON tr.UserID = tha.TrainerID
JOIN dbo.[User] ht
    ON ht.UserID = tha.AssignedByHeadTrainerID;
GO

/* Lịch tập trong ngày của Work Rider, kèm trainer giám sát buổi đó */
CREATE VIEW dbo.vw_WorkRiderDailySchedule
AS
SELECT
    ts.TrainingSessionID,
    ts.SessionDate,
    ts.StartTime,
    ts.EndTime,
    ts.SequenceNo,
    ts.WorkRiderID,
    wr.FullName AS WorkRiderName,
    h.HorseID,
    h.HorseName,
    s.SpecializationName,
    tha.TrainerID AS AssignedTrainerID,
    COALESCE(ts.SubstituteTrainerID, tha.TrainerID) AS SupervisingTrainerID,
    sup.FullName AS SupervisingTrainerName,
    CAST(CASE WHEN ts.SubstituteTrainerID IS NULL THEN 0 ELSE 1 END AS BIT) AS IsSubstitute,
    ts.TrainingType,
    ts.DurationPlannedMinutes,
    ts.DistancePlannedKm,
    ts.TargetSpeedKmh,
    ts.TrainingLoad,
    ts.Surface,
    ts.Location,
    ts.Instructions,
    ts.Status
FROM dbo.TrainingSession ts
JOIN dbo.[User] wr
    ON wr.UserID = ts.WorkRiderID
JOIN dbo.TrainingPlanStage tps
    ON tps.TrainingPlanStageID = ts.TrainingPlanStageID
JOIN dbo.TrainingPlan tp
    ON tp.TrainingPlanID = tps.TrainingPlanID
JOIN dbo.TrainerHorseAssignment tha
    ON tha.TrainerHorseAssignmentID = tp.TrainerHorseAssignmentID
JOIN dbo.Horse h
    ON h.HorseID = tha.HorseID
JOIN dbo.Specialization s
    ON s.SpecializationID = tha.SpecializationID
JOIN dbo.[User] sup
    ON sup.UserID = COALESCE(ts.SubstituteTrainerID, tha.TrainerID);
GO

CREATE VIEW dbo.vw_HorseTrainingDashboard
AS
SELECT
    h.HorseID,
    h.HorseCode,
    h.HorseName,
    h.Gender,
    h.SexClass,
    h.CurrentHealthStatus,
    h.RegistrationStatus,
    h.OwnerID,
    s.SpecializationName,
    tr.FullName AS TrainerName,
    CAST(CASE WHEN lk.TrainingLockID IS NULL THEN 0 ELSE 1 END AS BIT) AS IsTrainingLocked,
    lk.LockLevel,
    lk.MaxIntensity,
    latest.SessionDate AS LatestTrainingDate,
    latest.PerformanceScore AS LatestPerformanceScore,
    latest.ActualDistanceKm AS LatestActualDistanceKm,
    latest.AvgSpeedKmh AS LatestAvgSpeedKmh,
    latest.AvgHeartRate AS LatestAvgHeartRate,
    latest.RecoveryMinutes AS LatestRecoveryMinutes
FROM dbo.Horse h
OUTER APPLY
(
    /* Trainer đang phụ trách */
    SELECT TOP (1) tha.SpecializationID, tha.TrainerID
    FROM dbo.TrainerHorseAssignment tha
    WHERE tha.HorseID = h.HorseID
      AND tha.Status = 'Active'
    ORDER BY tha.StartDate DESC
) cur
OUTER APPLY
(
    /* Lock đang hiệu lực (tối đa 1 nhờ UX_TrainingLock_OneActivePerHorse) */
    SELECT TOP (1) tl.TrainingLockID, tl.LockLevel, tl.MaxIntensity
    FROM dbo.TrainingLock tl
    WHERE tl.HorseID = h.HorseID
      AND tl.LockStatus = 'Active'
) lk
OUTER APPLY
(
    /* Buổi tập hoàn thành gần nhất */
    SELECT TOP (1)
        ts2.SessionDate,
        r.PerformanceScore,
        r.ActualDistanceKm,
        r.AvgSpeedKmh,
        r.AvgHeartRate,
        r.RecoveryMinutes
    FROM dbo.TrainingSession ts2
    JOIN dbo.TrainingPlanStage tps2
        ON tps2.TrainingPlanStageID = ts2.TrainingPlanStageID
    JOIN dbo.TrainingPlan tp2
        ON tp2.TrainingPlanID = tps2.TrainingPlanID
    JOIN dbo.TrainerHorseAssignment tha2
        ON tha2.TrainerHorseAssignmentID = tp2.TrainerHorseAssignmentID
    LEFT JOIN dbo.TrainingResult r
        ON r.TrainingSessionID = ts2.TrainingSessionID
    WHERE tha2.HorseID = h.HorseID
      AND ts2.Status = 'Completed'
    ORDER BY ts2.SessionDate DESC, ts2.EndTime DESC, ts2.TrainingSessionID DESC
) latest
LEFT JOIN dbo.Specialization s
    ON s.SpecializationID = cur.SpecializationID
LEFT JOIN dbo.[User] tr
    ON tr.UserID = cur.TrainerID;
GO

/* Danh sách "Chờ khám đầu vào" chung cho Vet trực */
CREATE VIEW dbo.vw_PendingInitialExam
AS
SELECT
    rr.RegistrationRequestID,
    rr.ClubID,
    h.HorseID,
    h.HorseName,
    h.MicrochipNumber,
    rr.RequestDate,
    DATEDIFF(HOUR, rr.RequestDate, SYSDATETIME()) AS WaitingHours
FROM dbo.RegistrationRequest rr
JOIN dbo.Horse h
    ON h.HorseID = rr.HorseID
WHERE rr.Status = 'PendingExam'
  AND NOT EXISTS
  (
      SELECT 1
      FROM dbo.MedicalRecord mr
      WHERE mr.RegistrationRequestID = rr.RegistrationRequestID
        AND mr.ExamType = 'Initial Exam'
  );
GO

/* Hàng chờ báo cáo sức khỏe của Vet: chưa xử lý xong, Urgent lên trước */
CREATE VIEW dbo.vw_VetHealthReportQueue
AS
SELECT
    hr.HealthReportID,
    hr.HorseID,
    h.HorseName,
    h.ClubID,
    hr.Severity,
    hr.Status,
    hr.ReportedAt,
    hr.ReportedBy,
    rp.FullName AS ReportedByName,
    hr.TrainingSessionID,
    hr.Description,
    hr.VetID,
    CASE hr.Severity WHEN 'Urgent' THEN 1 ELSE 2 END AS PriorityOrder
FROM dbo.HealthReport hr
JOIN dbo.Horse h
    ON h.HorseID = hr.HorseID
JOIN dbo.[User] rp
    ON rp.UserID = hr.ReportedBy
WHERE hr.Status IN ('Reported', 'Reviewing');
GO

/* ================================================================
   TRIGGERS
   ================================================================ */

/* Buổi tập: không cho xếp hoặc bắt đầu buổi tập (Assigned / In Progress) trong thời gian
   ngựa bị khóa. Hủy, đánh vắng, ghi nhận buổi đã xong vẫn được.
   - Full: chặn mọi buổi tập.
   - Restricted: chặn buổi tập không ghi TrainingLoad hoặc vượt MaxIntensity. */
CREATE TRIGGER dbo.TRG_TrainingSession_BlockLockedHorse
ON dbo.TrainingSession
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS
    (
        SELECT 1
        FROM inserted i
        JOIN dbo.TrainingPlanStage tps
            ON tps.TrainingPlanStageID = i.TrainingPlanStageID
        JOIN dbo.TrainingPlan tp
            ON tp.TrainingPlanID = tps.TrainingPlanID
        JOIN dbo.TrainerHorseAssignment tha
            ON tha.TrainerHorseAssignmentID = tp.TrainerHorseAssignmentID
        JOIN dbo.TrainingLock tl
            ON tl.HorseID = tha.HorseID
        WHERE i.Status IN ('Assigned', 'In Progress')
          AND tl.LockStatus = 'Active'
          AND tl.LockLevel = 'Full'
          AND i.SessionDate BETWEEN CAST(tl.LockStartDate AS DATE)
                                AND CAST(COALESCE(tl.LockEndDate, '9999-12-31') AS DATE)
    )
    BEGIN
        THROW 51002, 'Cannot assign a Training Session during a Full Training Lock.', 1;
    END;

    IF EXISTS
    (
        SELECT 1
        FROM inserted i
        JOIN dbo.TrainingPlanStage tps
            ON tps.TrainingPlanStageID = i.TrainingPlanStageID
        JOIN dbo.TrainingPlan tp
            ON tp.TrainingPlanID = tps.TrainingPlanID
        JOIN dbo.TrainerHorseAssignment tha
            ON tha.TrainerHorseAssignmentID = tp.TrainerHorseAssignmentID
        JOIN dbo.TrainingLock tl
            ON tl.HorseID = tha.HorseID
        WHERE i.Status IN ('Assigned', 'In Progress')
          AND tl.LockStatus = 'Active'
          AND tl.LockLevel = 'Restricted'
          AND tl.MaxIntensity IS NOT NULL
          AND (i.TrainingLoad IS NULL OR i.TrainingLoad > tl.MaxIntensity)
          AND i.SessionDate BETWEEN CAST(tl.LockStartDate AS DATE)
                                AND CAST(COALESCE(tl.LockEndDate, '9999-12-31') AS DATE)
    )
    BEGIN
        THROW 51003, 'Training Session exceeds the MaxIntensity of a Restricted Training Lock.', 1;
    END;
END;
GO

/* Giáo án: soạn / sửa luôn được; chỉ chặn lúc KÍCH HOẠT khi ngựa đang bị khóa Full. */
CREATE TRIGGER dbo.TRG_TrainingPlan_BlockLockedHorse
ON dbo.TrainingPlan
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS
    (
        SELECT 1
        FROM inserted i
        LEFT JOIN deleted d
            ON d.TrainingPlanID = i.TrainingPlanID
        JOIN dbo.TrainerHorseAssignment tha
            ON tha.TrainerHorseAssignmentID = i.TrainerHorseAssignmentID
        JOIN dbo.TrainingLock tl
            ON tl.HorseID = tha.HorseID
        WHERE i.Status = 'Active'
          AND (d.Status IS NULL OR d.Status <> 'Active')
          AND tl.LockStatus = 'Active'
          AND tl.LockLevel = 'Full'
          AND i.StartDate <= CAST(COALESCE(tl.LockEndDate, '9999-12-31') AS DATE)
          AND COALESCE(i.EndDate, '9999-12-31') >= CAST(tl.LockStartDate AS DATE)
    )
    BEGIN
        THROW 51001, 'Cannot activate a Training Plan while the horse has an active Full Training Lock.', 1;
    END;
END;
GO

/* Vet tạo / siết lock: tự hủy các buổi tập 'Assigned' trong thời gian khóa
   (Full: hủy hết; Restricted: hủy buổi vượt MaxIntensity). */
CREATE TRIGGER dbo.TRG_TrainingLock_CancelSessions
ON dbo.TrainingLock
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE ts
    SET ts.Status = 'Cancelled'
    FROM dbo.TrainingSession ts
    JOIN dbo.TrainingPlanStage tps
        ON tps.TrainingPlanStageID = ts.TrainingPlanStageID
    JOIN dbo.TrainingPlan tp
        ON tp.TrainingPlanID = tps.TrainingPlanID
    JOIN dbo.TrainerHorseAssignment tha
        ON tha.TrainerHorseAssignmentID = tp.TrainerHorseAssignmentID
    JOIN inserted i
        ON i.HorseID = tha.HorseID
    WHERE i.LockStatus = 'Active'
      AND ts.Status = 'Assigned'
      AND ts.SessionDate BETWEEN CAST(i.LockStartDate AS DATE)
                             AND CAST(COALESCE(i.LockEndDate, '9999-12-31') AS DATE)
      AND
      (
          i.LockLevel = 'Full'
          OR (i.LockLevel = 'Restricted' AND i.MaxIntensity IS NOT NULL
              AND (ts.TrainingLoad IS NULL OR ts.TrainingLoad > i.MaxIntensity))
      );
END;
GO

/* Bệnh án đã chốt (Signed) không được sửa đè hay xóa; dùng MedicalRecordAmendment. */
CREATE TRIGGER dbo.TRG_MedicalRecord_ProtectSigned
ON dbo.MedicalRecord
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (SELECT 1 FROM deleted d WHERE d.RecordStatus = 'Signed')
    BEGIN
        THROW 51004, 'A signed Medical Record cannot be changed or deleted. Add a MedicalRecordAmendment instead.', 1;
    END;
END;
GO

/* ================================================================
   SEED DATA
   ================================================================ */

INSERT INTO dbo.Role (RoleCode, RoleName, Description)
VALUES
('CLUB_MANAGER',  N'Club Manager',        N'Quản lý câu lạc bộ, duyệt hồ sơ ngựa và phân quyền.'),
('HEAD_TRAINER',  N'Head Trainer',        N'Đánh giá ngựa, phân công Trainer, duyệt giáo án, xếp buổi tập, chỉ định Substitute Trainer.'),
('TRAINER',       N'Trainer',             N'Phụ trách ngựa, xây dựng giáo án, giám sát và đánh giá buổi tập.'),
('WORK_RIDER',    N'Work Rider',          N'Trực tiếp cưỡi ngựa, thực hiện buổi tập và ghi kết quả.'),
('VETERINARIAN',  N'Veterinarian',        N'Khám theo ca trực, chẩn đoán, điều trị, quản lý Training Lock.'),
('GROOM',         N'Groom / Stable Hand', N'Chăm sóc ngựa, chuồng trại và báo cáo sự cố sức khỏe.'),
('HORSE_OWNER',   N'Horse Owner',         N'Đăng ký ngựa vào CLB và theo dõi ngựa của mình.');
GO

INSERT INTO dbo.Specialization (SpecializationCode, SpecializationName, Description)
VALUES
('FLAT_RACING',         N'Flat Racing',                      N'Đua trên đường chạy phẳng.'),
('STEEPLECHASE_HURDLE', N'Steeplechase / Hurdle Racing',     N'Đua vượt chướng ngại vật / vượt rào.'),
('HARNESS_RACING',      N'Harness Racing',                   N'Đua xe kéo / harness racing.'),
('ENDURANCE',           N'Endurance / Long-distance Racing', N'Đua đường trường / sức bền.'),
('OTHER',               N'Other',                            N'Chuyên môn khác nếu câu lạc bộ cần mở rộng.');
GO

INSERT INTO dbo.Permission (PermissionCode, PermissionName, Description)
VALUES
('CLUB_MANAGE',                N'Quản lý câu lạc bộ',         N'Quản lý danh mục và cấu hình câu lạc bộ.'),
('RBAC_MANAGE',                N'Quản lý phân quyền',         N'Gán vai trò và quyền cho người dùng.'),
('AUDIT_VIEW',                 N'Xem Audit Log',              N'Xem nhật ký thao tác hệ thống.'),
('HORSE_VIEW',                 N'Xem hồ sơ ngựa',             N'Xem hồ sơ và trạng thái ngựa.'),
('HORSE_REGISTER',             N'Đăng ký ngựa',               N'Owner tạo, lưu nháp và gửi hồ sơ đăng ký ngựa.'),
('HORSE_REGISTER_REVIEW',      N'Duyệt đăng ký ngựa',         N'Kiểm tra giấy tờ, microchip; duyệt hoặc từ chối hồ sơ.'),
('HORSE_ARCHIVE',              N'Lưu trữ hồ sơ ngựa',         N'Chuyển hồ sơ ngựa sang Archived kèm lý do.'),
('PROFILE_EDIT_REQUEST',       N'Gửi yêu cầu sửa lý lịch',    N'Owner gửi yêu cầu sửa lý lịch ngựa kèm bằng chứng.'),
('PROFILE_EDIT_APPROVE',       N'Duyệt yêu cầu sửa lý lịch',  N'Club Manager duyệt hoặc từ chối yêu cầu sửa lý lịch.'),
('HORSE_ASSESS',               N'Đánh giá phân loại ngựa',    N'Head Trainer đánh giá chất lượng và chuyên môn của ngựa.'),
('TRAINER_ASSIGN',             N'Phân công Trainer',          N'Head Trainer giao ngựa cho Trainer phụ trách theo chuyên môn.'),
('TRAINING_PLAN_MANAGE',       N'Quản lý giáo án',            N'Trainer phụ trách tạo, điều chỉnh và gửi duyệt giáo án.'),
('TRAINING_PLAN_APPROVE',      N'Duyệt giáo án',              N'Head Trainer duyệt hoặc trả về giáo án trước khi áp dụng.'),
('TRAINING_SESSION_ASSIGN',    N'Xếp buổi tập',               N'Xếp buổi tập, giao Work Rider, chỉ định Substitute Trainer: Head Trainer cho mọi ngựa, Trainer cho ngựa mình đang phụ trách.'),
('TRAINING_SESSION_SUPERVISE', N'Giám sát buổi tập',          N'Có mặt giám sát, dừng buổi tập khi ngựa có vấn đề, ghi nhận xét khi giám sát thay.'),
('TRAINING_RESULT_UPDATE',     N'Cập nhật kết quả tập',       N'Work Rider bắt đầu buổi tập và ghi kết quả thực tế.'),
('TRAINING_REVIEW',            N'Đánh giá buổi tập',          N'Trainer phụ trách đánh giá kết quả và đề xuất điều chỉnh giáo án.'),
('HEALTH_REPORT',              N'Báo cáo sự cố sức khỏe',     N'Báo bất thường sức khỏe của ngựa cho Vet.'),
('MEDICAL_MANAGE',             N'Quản lý y tế',               N'Khám, chẩn đoán, cập nhật hồ sơ y tế, xử lý báo cáo sức khỏe.'),
('MEDICAL_SIGN',               N'Chốt bệnh án',               N'Vet chốt bệnh án và lập phiếu đính chính.'),
('TRAINING_LOCK_MANAGE',       N'Quản lý Training Lock',      N'Khóa / mở / hạn chế huấn luyện theo tình trạng sức khỏe.'),
('CARE_MANAGE',                N'Quản lý chăm sóc',           N'Tạo và cập nhật nhiệm vụ chăm sóc.'),
('DIET_MANAGE',                N'Quản lý khẩu phần',          N'Tạo / phê duyệt / điều chỉnh khẩu phần.'),
('INVENTORY_REQUEST',          N'Gửi yêu cầu vật tư',         N'Gửi yêu cầu xuất kho vật tư.'),
('INVENTORY_MANAGE',           N'Quản lý vật tư',             N'Theo dõi kho và phê duyệt yêu cầu vật tư.'),
('OWNER_VIEW',                 N'Quyền xem của chủ ngựa',     N'Chỉ xem các ngựa thuộc sở hữu của mình.');
GO

INSERT INTO dbo.RolePermission (RoleID, PermissionID)
SELECT r.RoleID, p.PermissionID
FROM
(
    VALUES
    -- Club Manager
    ('CLUB_MANAGER', 'CLUB_MANAGE'),
    ('CLUB_MANAGER', 'RBAC_MANAGE'),
    ('CLUB_MANAGER', 'AUDIT_VIEW'),
    ('CLUB_MANAGER', 'HORSE_VIEW'),
    ('CLUB_MANAGER', 'HORSE_REGISTER_REVIEW'),
    ('CLUB_MANAGER', 'HORSE_ARCHIVE'),
    ('CLUB_MANAGER', 'PROFILE_EDIT_APPROVE'),
    ('CLUB_MANAGER', 'INVENTORY_MANAGE'),
    -- Head Trainer
    ('HEAD_TRAINER', 'HORSE_VIEW'),
    ('HEAD_TRAINER', 'HORSE_ASSESS'),
    ('HEAD_TRAINER', 'TRAINER_ASSIGN'),
    ('HEAD_TRAINER', 'TRAINING_PLAN_APPROVE'),
    ('HEAD_TRAINER', 'TRAINING_SESSION_ASSIGN'),
    ('HEAD_TRAINER', 'TRAINING_SESSION_SUPERVISE'),
    ('HEAD_TRAINER', 'HEALTH_REPORT'),
    ('HEAD_TRAINER', 'DIET_MANAGE'),
    ('HEAD_TRAINER', 'INVENTORY_REQUEST'),
    -- Trainer (phụ trách hoặc Substitute)
    ('TRAINER', 'HORSE_VIEW'),
    ('TRAINER', 'TRAINING_PLAN_MANAGE'),
    ('TRAINER', 'TRAINING_SESSION_ASSIGN'),
    ('TRAINER', 'TRAINING_SESSION_SUPERVISE'),
    ('TRAINER', 'TRAINING_REVIEW'),
    ('TRAINER', 'HEALTH_REPORT'),
    -- Work Rider
    ('WORK_RIDER', 'HORSE_VIEW'),
    ('WORK_RIDER', 'TRAINING_RESULT_UPDATE'),
    ('WORK_RIDER', 'HEALTH_REPORT'),
    -- Veterinarian
    ('VETERINARIAN', 'HORSE_VIEW'),
    ('VETERINARIAN', 'MEDICAL_MANAGE'),
    ('VETERINARIAN', 'MEDICAL_SIGN'),
    ('VETERINARIAN', 'TRAINING_LOCK_MANAGE'),
    ('VETERINARIAN', 'DIET_MANAGE'),
    -- Groom
    ('GROOM', 'HORSE_VIEW'),
    ('GROOM', 'CARE_MANAGE'),
    ('GROOM', 'HEALTH_REPORT'),
    ('GROOM', 'INVENTORY_REQUEST'),
    -- Horse Owner
    ('HORSE_OWNER', 'HORSE_REGISTER'),
    ('HORSE_OWNER', 'PROFILE_EDIT_REQUEST'),
    ('HORSE_OWNER', 'OWNER_VIEW')
) AS m (RoleCode, PermissionCode)
JOIN dbo.Role r
    ON r.RoleCode = m.RoleCode
JOIN dbo.Permission p
    ON p.PermissionCode = m.PermissionCode;
GO

/* ================================================================
   END
   ================================================================ */
