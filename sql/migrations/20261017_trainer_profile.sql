-- Flow 2 - hồ sơ năng lực Trainer: thêm 3 bảng TrainerProfile, TrainerCredential, TrainerRaceResult
-- cho database ĐÃ CÓ dữ liệu (database mới chỉ cần chạy horse_v2.sql). Chạy lại nhiều lần không sao.
-- Sau đó chạy: python manage.py seed_demo --password <...>  để có hồ sơ của 3 trainer mẫu.

IF OBJECT_ID('dbo.TrainerProfile', 'U') IS NULL
BEGIN
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
END;
GO

IF OBJECT_ID('dbo.TrainerCredential', 'U') IS NULL
BEGIN
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
END;
GO

IF OBJECT_ID('dbo.TrainerRaceResult', 'U') IS NULL
BEGIN
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
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_TrainerRaceResult_Trainer_Date')
    CREATE INDEX IX_TrainerRaceResult_Trainer_Date ON dbo.TrainerRaceResult (TrainerID, RaceDate);
GO
