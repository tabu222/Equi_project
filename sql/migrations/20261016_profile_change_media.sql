-- Additive migration for EXISTING SQL Server databases. Do not run horse_v2.sql
-- against existing data (that script recreates the entire demo schema).
SET XACT_ABORT ON;
BEGIN TRANSACTION;
IF COL_LENGTH('dbo.HorseDocument', 'IsPrimary') IS NULL
    ALTER TABLE dbo.HorseDocument ADD IsPrimary BIT NOT NULL
        CONSTRAINT DF_HorseDocument_Primary DEFAULT 0;
IF COL_LENGTH('dbo.HorseDocument', 'IsRetired') IS NULL
    ALTER TABLE dbo.HorseDocument ADD IsRetired BIT NOT NULL
        CONSTRAINT DF_HorseDocument_Retired DEFAULT 0;
IF COL_LENGTH('dbo.HorseDocument', 'ReplacesDocumentID') IS NULL
    ALTER TABLE dbo.HorseDocument ADD ReplacesDocumentID INT NULL;
IF COL_LENGTH('dbo.HorseDocument', 'IsProfileImage') IS NULL
BEGIN
    ALTER TABLE dbo.HorseDocument ADD IsProfileImage BIT NOT NULL
        CONSTRAINT DF_HorseDocument_ProfileImage DEFAULT 0;
    EXEC sp_executesql N'UPDATE dbo.HorseDocument SET IsProfileImage = 1
        WHERE DocumentType = ''Other'' AND FileUrl LIKE ''upload:%''
        AND (LOWER(FileUrl) LIKE ''%.jpg'' OR LOWER(FileUrl) LIKE ''%.jpeg''
            OR LOWER(FileUrl) LIKE ''%.png'' OR LOWER(FileUrl) LIKE ''%.webp'')';
END;
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_HorseDocument_PreviousVersion')
    EXEC sp_executesql N'ALTER TABLE dbo.HorseDocument ADD CONSTRAINT FK_HorseDocument_PreviousVersion
        FOREIGN KEY (ReplacesDocumentID) REFERENCES dbo.HorseDocument(DocumentID)';
-- Broaden the enum without changing or deleting any existing request.
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_ProfileChangeRequest_Status')
    ALTER TABLE dbo.ProfileChangeRequest DROP CONSTRAINT CK_ProfileChangeRequest_Status;
ALTER TABLE dbo.ProfileChangeRequest WITH CHECK ADD CONSTRAINT CK_ProfileChangeRequest_Status
    CHECK (Status IN ('Pending', 'Approved', 'Rejected', 'Withdrawn'));
COMMIT TRANSACTION;
