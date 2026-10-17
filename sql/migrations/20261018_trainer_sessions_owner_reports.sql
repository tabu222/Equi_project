-- Flow 2 - Trainer tự xếp buổi tập + chủ ngựa xem kết quả huấn luyện.
-- Cho database ĐÃ CÓ dữ liệu (database mới chỉ cần chạy horse_v2.sql). Chạy lại nhiều lần không sao.
--   1. Role TRAINER được quyền TRAINING_SESSION_ASSIGN (backend chỉ cho xếp buổi tập của ngựa mình đang phụ trách).
--   2. TrainingPlanStage thêm ClosedAt, ClosedByID, SummaryNote: trainer chốt giai đoạn -> tổng kết gửi chủ ngựa.

UPDATE dbo.Permission
SET Description = N'Xếp buổi tập, giao Work Rider, chỉ định Substitute Trainer: Head Trainer cho mọi ngựa, Trainer cho ngựa mình đang phụ trách.'
WHERE PermissionCode = 'TRAINING_SESSION_ASSIGN';
GO

INSERT INTO dbo.RolePermission (RoleID, PermissionID)
SELECT r.RoleID, p.PermissionID
FROM dbo.Role r
JOIN dbo.Permission p ON p.PermissionCode = 'TRAINING_SESSION_ASSIGN'
WHERE r.RoleCode = 'TRAINER'
  AND NOT EXISTS (SELECT 1 FROM dbo.RolePermission rp WHERE rp.RoleID = r.RoleID AND rp.PermissionID = p.PermissionID);
GO

IF COL_LENGTH('dbo.TrainingPlanStage', 'ClosedAt') IS NULL
    ALTER TABLE dbo.TrainingPlanStage ADD ClosedAt DATETIME2 NULL;
GO

IF COL_LENGTH('dbo.TrainingPlanStage', 'ClosedByID') IS NULL
    ALTER TABLE dbo.TrainingPlanStage ADD ClosedByID INT NULL;
GO

IF COL_LENGTH('dbo.TrainingPlanStage', 'SummaryNote') IS NULL
    ALTER TABLE dbo.TrainingPlanStage ADD SummaryNote NVARCHAR(2000) NULL;
GO

IF OBJECT_ID('dbo.FK_TrainingPlanStage_ClosedBy', 'F') IS NULL
    ALTER TABLE dbo.TrainingPlanStage ADD CONSTRAINT FK_TrainingPlanStage_ClosedBy
        FOREIGN KEY (ClosedByID) REFERENCES dbo.[User](UserID);
GO
