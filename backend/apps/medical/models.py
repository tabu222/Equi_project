"""Existing SQL models required for Flow 1 intake examinations; no migrations."""
from django.conf import settings
from django.db import models
from django.utils import timezone
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
    # Flow 2 is absent. Preserve the nullable SQL column without loading its models.
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
