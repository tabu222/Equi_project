"""
FLOW 1 - đăng ký và tiếp nhận ngựa: Horse, HorseDocument, RegistrationRequest,
ProfileChangeRequest, Stall, StallAssignment (horse_v2.sql).
"""
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import Club


class Horse(models.Model):
    class RegistrationStatus(models.TextChoices):
        DRAFT = "Draft"                # Owner / Manager đang soạn
        SUBMITTED = "Submitted"        # đã gửi, chờ CLB kiểm tra giấy tờ
        PENDING_EXAM = "PendingExam"   # chờ Vet trực khám đầu vào
        APPROVED = "Approved"          # đã tiếp nhận vào CLB
        REJECTED = "Rejected"          # bị từ chối (sửa và gửi lại được)
        ARCHIVED = "Archived"          # lưu trữ (rời CLB)

    class HealthStatus(models.TextChoices):
        UNKNOWN = "Unknown"
        HEALTHY = "Healthy"
        MONITOR = "Monitor"
        INJURED = "Injured"
        RECOVERING = "Recovering"
        ISOLATED = "Isolated"

    class Gender(models.TextChoices):
        MALE = "Male"
        FEMALE = "Female"
        GELDING = "Gelding"

    id = models.AutoField(primary_key=True, db_column="HorseID")
    club = models.ForeignKey(Club, on_delete=models.DO_NOTHING, db_column="ClubID", related_name="horses")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="OwnerID", related_name="owned_horses"
    )

    horse_name = models.CharField(max_length=100, db_column="HorseName")
    breed = models.CharField(max_length=100, null=True, blank=True, db_column="Breed")
    date_of_birth = models.DateField(null=True, blank=True, db_column="DateOfBirth")
    coat_color = models.CharField(max_length=50, null=True, blank=True, db_column="CoatColor")
    gender = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True, db_column="Gender")
    sire_name = models.CharField(max_length=100, null=True, blank=True, db_column="SireName")
    dam_name = models.CharField(max_length=100, null=True, blank=True, db_column="DamName")
    microchip_number = models.CharField(max_length=30, null=True, blank=True, db_column="MicrochipNumber")
    passport_number = models.CharField(max_length=50, null=True, blank=True, db_column="PassportNumber")

    horse_code = models.CharField(max_length=30, null=True, blank=True, db_column="HorseCode")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="VerifiedBy", related_name="+",
    )
    verified_at = models.DateTimeField(null=True, blank=True, db_column="VerifiedAt")

    registration_status = models.CharField(
        max_length=20, choices=RegistrationStatus.choices, default=RegistrationStatus.DRAFT,
        db_column="RegistrationStatus",
    )
    current_health_status = models.CharField(
        max_length=30, choices=HealthStatus.choices, default=HealthStatus.UNKNOWN, db_column="CurrentHealthStatus"
    )

    archived_at = models.DateTimeField(null=True, blank=True, db_column="ArchivedAt")
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="ArchivedBy", related_name="+",
    )
    archive_reason = models.CharField(max_length=500, null=True, blank=True, db_column="ArchiveReason")

    created_at = models.DateTimeField(default=timezone.now, db_column="CreatedAt")
    updated_at = models.DateTimeField(default=timezone.now, db_column="UpdatedAt")

    # Cột tính SexClass có sẵn trong SQL Server; không khai báo thành field để Django không ghi vào nó.

    class Meta:
        managed = False
        db_table = "Horse"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.horse_name

    @property
    def sex_class(self):
        """Giống cột tính SexClass trong horse_v2.sql: Foal / Colt / Filly / Stallion / Mare / Gelding."""
        if not self.gender:
            return None
        if self.gender == self.Gender.GELDING:
            return "Gelding"
        if not self.date_of_birth:
            return None
        today = date.today()

        def years_ago(n):
            try:
                return today.replace(year=today.year - n)
            except ValueError:  # 29/02
                return today.replace(year=today.year - n, day=28)

        if self.date_of_birth > years_ago(1):
            return "Foal"
        if self.date_of_birth > years_ago(4):
            return "Colt" if self.gender == self.Gender.MALE else "Filly"
        return "Stallion" if self.gender == self.Gender.MALE else "Mare"

    def touch(self):
        self.updated_at = timezone.now()


class HorseDocument(models.Model):
    class DocumentType(models.TextChoices):
        PASSPORT = "Passport"
        MICROCHIP_CERTIFICATE = "Microchip Certificate"
        OWNERSHIP_PROOF = "Ownership Proof"
        HANDOVER_RECORD = "Handover Record"
        CONTRACT = "Contract"
        OTHER = "Other"

    id = models.AutoField(primary_key=True, db_column="DocumentID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="documents")
    document_name = models.CharField(max_length=150, db_column="DocumentName")
    document_type = models.CharField(max_length=50, choices=DocumentType.choices, db_column="DocumentType")
    file_url = models.CharField(max_length=500, null=True, blank=True, db_column="FileUrl")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="UploadedBy", related_name="+",
    )
    is_visible_to_owner = models.BooleanField(default=True, db_column="IsVisibleToOwner")
    uploaded_at = models.DateTimeField(default=timezone.now, db_column="UploadedAt")

    class Meta:
        managed = False
        db_table = "HorseDocument"
        ordering = ["-uploaded_at", "-id"]


class RegistrationRequest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "Submitted"
        PENDING_EXAM = "PendingExam"
        APPROVED = "Approved"
        REJECTED = "Rejected"

    id = models.AutoField(primary_key=True, db_column="RegistrationRequestID")
    horse = models.ForeignKey(
        Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="registration_requests"
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="OwnerID", related_name="+")
    club = models.ForeignKey(Club, on_delete=models.DO_NOTHING, db_column="ClubID", related_name="+")
    request_date = models.DateTimeField(default=timezone.now, db_column="RequestDate")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_column="Status")
    manager_note = models.CharField(max_length=1000, null=True, blank=True, db_column="ManagerNote")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="ReviewedByClubManagerID", related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, db_column="ReviewedAt")

    class Meta:
        managed = False
        db_table = "RegistrationRequest"
        ordering = ["-request_date", "-id"]


class ProfileChangeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending"
        APPROVED = "Approved"
        REJECTED = "Rejected"

    id = models.AutoField(primary_key=True, db_column="ProfileChangeRequestID")
    horse = models.ForeignKey(
        Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="profile_change_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="RequestedBy", related_name="+"
    )
    requested_at = models.DateTimeField(default=timezone.now, db_column="RequestedAt")
    changed_fields = models.TextField(db_column="ChangedFields")  # JSON: {"Reason": ..., "Changes": [...]}
    evidence_document = models.ForeignKey(
        HorseDocument, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="EvidenceDocumentID", related_name="+",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_column="Status")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="ReviewedBy", related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, db_column="ReviewedAt")
    review_note = models.CharField(max_length=1000, null=True, blank=True, db_column="ReviewNote")

    class Meta:
        managed = False
        db_table = "ProfileChangeRequest"
        ordering = ["-requested_at", "-id"]


class Stall(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "Available"
        OCCUPIED = "Occupied"
        MAINTENANCE = "Maintenance"

    id = models.AutoField(primary_key=True, db_column="StallID")
    club = models.ForeignKey(Club, on_delete=models.DO_NOTHING, db_column="ClubID", related_name="stalls")
    stall_number = models.CharField(max_length=30, db_column="StallNumber")
    stall_type = models.CharField(max_length=50, null=True, blank=True, db_column="StallType")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_column="Status")

    class Meta:
        managed = False
        db_table = "Stall"
        ordering = ["stall_number"]


class StallAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active"
        ENDED = "Ended"

    id = models.AutoField(primary_key=True, db_column="StallAssignmentID")
    stall = models.ForeignKey(Stall, on_delete=models.DO_NOTHING, db_column="StallID", related_name="assignments")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="stall_assignments")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(null=True, blank=True, db_column="EndDate")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_column="Status")

    class Meta:
        managed = False
        db_table = "StallAssignment"
        ordering = ["-start_date", "-id"]
