"""
Y tế (horse_v2.sql, không có migrations):
  Flow 1 - phiếu khám đầu vào: MedicalRecord, MedicalRecordAmendment.
  Flow 3 - y tế: TrainingLock, Treatment, Vaccination, MedicalSchedule, HealthReport, HealthReportNote.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core import flows
from apps.horses.models import Horse, RegistrationRequest


class MedicalRecord(models.Model):
    class ExamType(models.TextChoices):
        INITIAL = "Initial Exam"
        ROUTINE = "Routine Exam"
        INJURY = "Injury Exam"
        FOLLOW_UP = "Follow-up"
        EMERGENCY = "Emergency"

    class HealthStatus(models.TextChoices):
        HEALTHY = "Healthy"
        MONITOR = "Monitor"
        INJURED = "Injured"
        RECOVERING = "Recovering"
        ISOLATED = "Isolated"

    class TrainingEligibility(models.TextChoices):
        ELIGIBLE = "Eligible"
        RESTRICTED = "Restricted"
        NOT_ELIGIBLE = "Not Eligible"

    class RecordStatus(models.TextChoices):
        DRAFT = "Draft"
        SIGNED = "Signed"

    id = models.AutoField(primary_key=True, db_column="MedicalRecordID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="medical_records")
    vet = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="VetID", related_name="+")
    registration_request = models.ForeignKey(
        RegistrationRequest, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="RegistrationRequestID", related_name="medical_records",
    )
    # Buổi tập (Flow 2) mà lần khám này xử lý; giữ dạng số để Flow 1 chạy được khi chưa có Flow 2.
    training_session_id = models.IntegerField(null=True, blank=True, db_column="TrainingSessionID")

    exam_date = models.DateTimeField(db_column="ExamDate")
    exam_type = models.CharField(max_length=50, choices=ExamType.choices, db_column="ExamType")
    weight_kg = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, db_column="WeightKg")
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, db_column="HeightCm")
    symptoms = models.CharField(max_length=1500, null=True, blank=True, db_column="Symptoms")
    diagnosis = models.CharField(max_length=1500, null=True, blank=True, db_column="Diagnosis")
    conclusion = models.CharField(max_length=1500, null=True, blank=True, db_column="Conclusion")
    injury_location = models.CharField(max_length=500, null=True, blank=True, db_column="InjuryLocation")
    treatment_plan = models.CharField(max_length=3000, null=True, blank=True, db_column="TreatmentPlan")
    health_status = models.CharField(
        max_length=30, choices=HealthStatus.choices, null=True, blank=True, db_column="HealthStatus"
    )
    training_eligibility = models.CharField(
        max_length=30, choices=TrainingEligibility.choices, null=True, blank=True, db_column="TrainingEligibility"
    )
    restriction_note = models.CharField(max_length=1000, null=True, blank=True, db_column="RestrictionNote")
    follow_up_date = models.DateField(null=True, blank=True, db_column="FollowUpDate")
    note = models.CharField(max_length=1500, null=True, blank=True, db_column="Note")

    record_status = models.CharField(
        max_length=20, choices=RecordStatus.choices, default=RecordStatus.DRAFT, db_column="RecordStatus"
    )
    signed_at = models.DateTimeField(null=True, blank=True, db_column="SignedAt")

    class Meta:
        managed = False
        db_table = "MedicalRecord"
        ordering = ["-exam_date", "-id"]

    @property
    def is_signed(self):
        return self.record_status == self.RecordStatus.SIGNED

    @property
    def passes_intake(self):
        """Khám đầu vào ĐẠT: sức khỏe Healthy / Monitor và không bị cấm tập."""
        return (
            self.health_status in (self.HealthStatus.HEALTHY, self.HealthStatus.MONITOR)
            and self.training_eligibility != self.TrainingEligibility.NOT_ELIGIBLE
        )


class MedicalRecordAmendment(models.Model):
    id = models.AutoField(primary_key=True, db_column="MedicalRecordAmendmentID")
    medical_record = models.ForeignKey(
        MedicalRecord, on_delete=models.DO_NOTHING, db_column="MedicalRecordID", related_name="amendments"
    )
    amended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="AmendedBy", related_name="+"
    )
    amended_at = models.DateTimeField(default=timezone.now, db_column="AmendedAt")
    reason = models.CharField(max_length=1000, db_column="Reason")
    amended_content = models.TextField(db_column="AmendedContent")

    class Meta:
        managed = False
        db_table = "MedicalRecordAmendment"
        ordering = ["amended_at", "id"]


class TrainingLock(models.Model):
    """
    Khóa huấn luyện do Vet tạo. Mỗi ngựa tối đa 1 lock Active (UX_TrainingLock_OneActivePerHorse).
      Full       : cấm tập hoàn toàn.
      Restricted : được tập nhẹ, buổi tập phải có TrainingLoad <= MaxIntensity.
    """

    class Level(models.TextChoices):
        FULL = "Full"
        RESTRICTED = "Restricted"

    class Status(models.TextChoices):
        ACTIVE = "Active"
        RELEASED = "Released"

    id = models.AutoField(primary_key=True, db_column="TrainingLockID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="training_locks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="CreatedByVetID",
                                   related_name="+")
    reason = models.CharField(max_length=100, db_column="Reason")
    lock_level = models.CharField(max_length=20, choices=Level.choices, default=Level.FULL, db_column="LockLevel")
    max_intensity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        db_column="MaxIntensity")
    lock_start_date = models.DateTimeField(db_column="LockStartDate")
    lock_end_date = models.DateTimeField(null=True, blank=True, db_column="LockEndDate")
    lock_status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE,
                                   db_column="LockStatus")
    details = models.CharField(max_length=2000, null=True, blank=True, db_column="Details")
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                                    db_column="ReleasedByVetID", related_name="+")
    released_at = models.DateTimeField(null=True, blank=True, db_column="ReleasedAt")

    class Meta:
        managed = False
        db_table = "TrainingLock"
        ordering = ["-lock_start_date", "-id"]

    def covers(self, day) -> bool:
        """Ngày `day` có nằm trong thời gian khóa không (so theo ngày, giống trigger SQL)."""
        if day < self.lock_start_date.date():
            return False
        return self.lock_end_date is None or day <= self.lock_end_date.date()


class Treatment(models.Model):
    class Route(models.TextChoices):
        ORAL = "Oral"
        INJECTION = "Injection"
        TOPICAL = "Topical"
        INHALATION = "Inhalation"
        OTHER = "Other"

    id = models.AutoField(primary_key=True, db_column="TreatmentID")
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.DO_NOTHING, db_column="MedicalRecordID",
                                       related_name="treatments")
    medicine_name = models.CharField(max_length=150, db_column="MedicineName")
    dose = models.CharField(max_length=100, db_column="Dose")
    route = models.CharField(max_length=30, choices=Route.choices, db_column="Route")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(null=True, blank=True, db_column="EndDate")
    withdrawal_until = models.DateField(null=True, blank=True, db_column="WithdrawalUntil")
    note = models.CharField(max_length=1000, null=True, blank=True, db_column="Note")

    class Meta:
        managed = False
        db_table = "Treatment"
        ordering = ["-start_date", "-id"]


class Vaccination(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "Scheduled"
        COMPLETED = "Completed"
        OVERDUE = "Overdue"
        CANCELLED = "Cancelled"

    id = models.AutoField(primary_key=True, db_column="VaccinationID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="vaccinations")
    vet = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                            db_column="VetID", related_name="+")
    vaccine_name = models.CharField(max_length=150, db_column="VaccineName")
    vaccination_date = models.DateField(db_column="VaccinationDate")
    next_due_date = models.DateField(null=True, blank=True, db_column="NextDueDate")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED, db_column="Status")
    note = models.CharField(max_length=1000, null=True, blank=True, db_column="Note")

    class Meta:
        managed = False
        db_table = "Vaccination"
        ordering = ["-vaccination_date", "-id"]


class MedicalSchedule(models.Model):
    class ScheduleType(models.TextChoices):
        VACCINATION = "Vaccination"
        DEWORMING = "Deworming"
        FARRIER = "Farrier"
        ROUTINE = "Routine Examination"

    class Status(models.TextChoices):
        SCHEDULED = "Scheduled"
        COMPLETED = "Completed"
        CANCELLED = "Cancelled"
        OVERDUE = "Overdue"

    id = models.AutoField(primary_key=True, db_column="MedicalScheduleID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID",
                              related_name="medical_schedules")
    vet = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                            db_column="VetID", related_name="+")
    schedule_type = models.CharField(max_length=50, choices=ScheduleType.choices, db_column="ScheduleType")
    scheduled_date = models.DateField(db_column="ScheduledDate")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED, db_column="Status")
    note = models.CharField(max_length=1000, null=True, blank=True, db_column="Note")

    class Meta:
        managed = False
        db_table = "MedicalSchedule"
        ordering = ["scheduled_date", "id"]


class HealthReport(models.Model):
    """Báo cáo sự cố sức khỏe: Groom, Work Rider, Trainer, Head Trainer báo ngang quyền; Vet trực xử lý."""

    class Severity(models.TextChoices):
        URGENT = "Urgent"
        NORMAL = "Normal"

    class Status(models.TextChoices):
        REPORTED = "Reported"      # mới báo, chưa Vet nào nhận
        REVIEWING = "Reviewing"    # Vet đã nhận ca
        RESOLVED = "Resolved"      # đã xử lý xong

    id = models.AutoField(primary_key=True, db_column="HealthReportID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="health_reports")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="ReportedBy",
                                    related_name="+")
    if flows.has_training():  # báo cáo phát hiện trong buổi tập (Flow 2)
        training_session = models.ForeignKey("training.TrainingSession", on_delete=models.DO_NOTHING, null=True,
                                             blank=True, db_column="TrainingSessionID",
                                             related_name="health_reports")
    else:  # chưa có Flow 2: giữ cột để model khớp bảng, chưa dùng
        training_session_id = models.IntegerField(null=True, blank=True, db_column="TrainingSessionID")
    reported_at = models.DateTimeField(default=timezone.now, db_column="ReportedAt")
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.NORMAL,
                                db_column="Severity")
    description = models.CharField(max_length=2500, db_column="Description")
    image_url = models.CharField(max_length=500, null=True, blank=True, db_column="ImageUrl")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED, db_column="Status")
    vet = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                            db_column="VetID", related_name="+")
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.DO_NOTHING, null=True, blank=True,
                                       db_column="MedicalRecordID", related_name="health_reports")
    vet_note = models.CharField(max_length=2000, null=True, blank=True, db_column="VetNote")
    resolved_at = models.DateTimeField(null=True, blank=True, db_column="ResolvedAt")

    class Meta:
        managed = False
        db_table = "HealthReport"
        ordering = ["-reported_at", "-id"]


class HealthReportNote(models.Model):
    id = models.AutoField(primary_key=True, db_column="HealthReportNoteID")
    report = models.ForeignKey(HealthReport, on_delete=models.DO_NOTHING, db_column="HealthReportID",
                               related_name="notes")
    note_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="NoteBy",
                                related_name="+")
    note_at = models.DateTimeField(default=timezone.now, db_column="NoteAt")
    content = models.CharField(max_length=2000, db_column="Content")

    class Meta:
        managed = False
        db_table = "HealthReportNote"
        ordering = ["note_at", "id"]
