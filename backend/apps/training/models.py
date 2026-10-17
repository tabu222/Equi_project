"""
FLOW 2 - huấn luyện (horse_v2.sql):
  Specialization, TrainerSpecialization, TrainerProfile, TrainerCredential, TrainerRaceResult, HorseAssessment,
  TrainerHorseAssignment, HorseWorkRiderPreference, TrainingPlan, TrainingPlanStage, TrainingSession, TrainingResult,
  TrainingReview.

Head Trainer đánh giá ngựa -> giao 1 Trainer phụ trách -> Trainer soạn giáo án -> Head Trainer duyệt
-> Head Trainer xếp buổi tập (giao Work Rider, chỉ định Substitute Trainer khi cần)
-> Work Rider bắt đầu buổi tập, ghi kết quả -> Trainer phụ trách đánh giá.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.horses.models import Horse

INTENSITY_CHOICES = [(v, v) for v in ("Low", "Moderate", "High", "Very High")]


class Specialization(models.Model):
    id = models.AutoField(primary_key=True, db_column="SpecializationID")
    code = models.CharField(max_length=50, unique=True, db_column="SpecializationCode")
    name = models.CharField(max_length=150, unique=True, db_column="SpecializationName")
    description = models.CharField(max_length=1000, null=True, blank=True, db_column="Description")
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")],
                              db_column="Status")

    class Meta:
        managed = False
        db_table = "Specialization"
        ordering = ["id"]


class TrainerSpecialization(models.Model):
    pk = models.CompositePrimaryKey("trainer", "specialization")
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="TrainerID", related_name="specialization_links"
    )
    specialization = models.ForeignKey(
        Specialization, on_delete=models.DO_NOTHING, db_column="SpecializationID", related_name="trainer_links"
    )
    assigned_at = models.DateTimeField(default=timezone.now, db_column="AssignedAt")

    class Meta:
        managed = False
        db_table = "TrainerSpecialization"


class TrainerProfile(models.Model):
    """
    Hồ sơ năng lực Trainer (1 dòng / trainer), Head Trainer / Manager cập nhật.
    YearsOfExperience, ExperienceLevel, Seniority, WinRate... không lưu mà tính ra (apps/training/profiles.py).
    """

    trainer = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.DO_NOTHING,
                                   db_column="TrainerID", related_name="trainer_profile")
    career_start_date = models.DateField(null=True, blank=True, db_column="CareerStartDate")
    trainer_rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True,
                                         db_column="TrainerRating")
    updated_at = models.DateTimeField(default=timezone.now, db_column="UpdatedAt")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                                   db_column="UpdatedBy", related_name="+")

    class Meta:
        managed = False
        db_table = "TrainerProfile"


class TrainerCredential(models.Model):
    """Bằng cấp / chứng chỉ / giấy phép hành nghề / bằng khen của trainer (minh chứng cho thâm niên nghề)."""

    class Type(models.TextChoices):
        DEGREE = "Degree"            # bằng cấp
        CERTIFICATE = "Certificate"  # chứng chỉ
        LICENSE = "License"          # giấy phép hành nghề
        AWARD = "Award"              # bằng khen, giải thưởng

    id = models.AutoField(primary_key=True, db_column="CredentialID")
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="TrainerID",
                                related_name="trainer_credentials")
    credential_type = models.CharField(max_length=20, choices=Type.choices, db_column="CredentialType")
    title = models.CharField(max_length=200, db_column="Title")
    issued_by = models.CharField(max_length=200, null=True, blank=True, db_column="IssuedBy")
    issued_date = models.DateField(db_column="IssuedDate")
    expiry_date = models.DateField(null=True, blank=True, db_column="ExpiryDate")
    file_url = models.CharField(max_length=500, null=True, blank=True, db_column="FileUrl")
    note = models.CharField(max_length=1000, null=True, blank=True, db_column="Note")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="CreatedBy",
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now, db_column="CreatedAt")

    class Meta:
        managed = False
        db_table = "TrainerCredential"
        ordering = ["-issued_date", "-id"]


class TrainerRaceResult(models.Model):
    """Một lần ngựa do trainer chuẩn bị ra đường đua (để tính WinRate, CareerWins... sát thực tế)."""

    class RaceClass(models.TextChoices):
        GROUP_1 = "Group 1"
        GROUP_2 = "Group 2"
        GROUP_3 = "Group 3"
        LISTED = "Listed"
        HANDICAP = "Handicap"
        MAIDEN = "Maiden"
        OTHER = "Other"

    id = models.AutoField(primary_key=True, db_column="RaceResultID")
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="TrainerID",
                                related_name="trainer_race_results")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, null=True, blank=True, db_column="HorseID",
                              related_name="race_results")
    horse_name = models.CharField(max_length=100, db_column="HorseName")
    race_date = models.DateField(db_column="RaceDate")
    race_name = models.CharField(max_length=200, db_column="RaceName")
    race_class = models.CharField(max_length=20, choices=RaceClass.choices, default=RaceClass.OTHER,
                                  db_column="RaceClass")
    finish_position = models.IntegerField(db_column="FinishPosition")
    field_size = models.IntegerField(db_column="FieldSize")
    note = models.CharField(max_length=1000, null=True, blank=True, db_column="Note")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="CreatedBy",
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now, db_column="CreatedAt")

    class Meta:
        managed = False
        db_table = "TrainerRaceResult"
        ordering = ["-race_date", "-id"]


class HorseAssessment(models.Model):
    class FitnessLevel(models.TextChoices):
        EXCELLENT = "Excellent"
        GOOD = "Good"
        AVERAGE = "Average"
        NEEDS_MONITORING = "Needs Monitoring"

    class Decision(models.TextChoices):
        RECOMMENDED = "Recommended"   # phù hợp chuyên môn này
        REJECTED = "Rejected"         # không phù hợp
        SUPERSEDED = "Superseded"     # đã có đánh giá mới hơn

    id = models.AutoField(primary_key=True, db_column="AssessmentID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="assessments")
    head_trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="HeadTrainerID", related_name="+"
    )
    specialization = models.ForeignKey(
        Specialization, on_delete=models.DO_NOTHING, db_column="SpecializationID", related_name="+"
    )
    assessment_date = models.DateTimeField(default=timezone.now, db_column="AssessmentDate")
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                        db_column="QualityScore")
    fitness_level = models.CharField(max_length=30, choices=FitnessLevel.choices, null=True, blank=True,
                                     db_column="FitnessLevel")
    assessment_note = models.CharField(max_length=2000, null=True, blank=True, db_column="AssessmentNote")
    decision_status = models.CharField(max_length=20, choices=Decision.choices, default=Decision.RECOMMENDED,
                                       db_column="DecisionStatus")

    class Meta:
        managed = False
        db_table = "HorseAssessment"
        ordering = ["-assessment_date", "-id"]


class TrainerHorseAssignment(models.Model):
    """Trainer phụ trách ngựa. Mỗi ngựa chỉ có 1 phân công Active (UX_TrainerHorseAssignment_OneActivePerHorse)."""

    class Status(models.TextChoices):
        ACTIVE = "Active"
        ENDED = "Ended"

    id = models.AutoField(primary_key=True, db_column="TrainerHorseAssignmentID")
    horse = models.ForeignKey(
        Horse, on_delete=models.DO_NOTHING, db_column="HorseID", related_name="trainer_assignments"
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="TrainerID", related_name="+"
    )
    specialization = models.ForeignKey(
        Specialization, on_delete=models.DO_NOTHING, db_column="SpecializationID", related_name="+"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="AssignedByHeadTrainerID", related_name="+"
    )
    assessment = models.ForeignKey(
        HorseAssessment, on_delete=models.DO_NOTHING, null=True, blank=True, db_column="AssessmentID",
        related_name="+",
    )
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(null=True, blank=True, db_column="EndDate")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_column="Status")
    assignment_note = models.CharField(max_length=1000, null=True, blank=True, db_column="AssignmentNote")

    class Meta:
        managed = False
        db_table = "TrainerHorseAssignment"
        ordering = ["-start_date", "-id"]


class HorseWorkRiderPreference(models.Model):
    """Work Rider quen ngựa (ưu tiên khi xếp buổi tập), không cố định người cưỡi."""

    id = models.AutoField(primary_key=True, db_column="PreferenceID")
    horse = models.ForeignKey(Horse, on_delete=models.DO_NOTHING, db_column="HorseID",
                              related_name="work_rider_preferences")
    work_rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="WorkRiderID",
                                   related_name="+")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING,
                                    db_column="AssignedByHeadTrainerID", related_name="+")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(null=True, blank=True, db_column="EndDate")
    priority = models.IntegerField(default=1, db_column="Priority")
    is_preferred = models.BooleanField(default=True, db_column="IsPreferred")
    note = models.CharField(max_length=1000, null=True, blank=True, db_column="Note")

    class Meta:
        managed = False
        db_table = "HorseWorkRiderPreference"
        ordering = ["priority", "id"]


class TrainingPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "Draft"
        PENDING_APPROVAL = "Pending Approval"
        ACTIVE = "Active"
        COMPLETED = "Completed"
        CANCELLED = "Cancelled"

    id = models.AutoField(primary_key=True, db_column="TrainingPlanID")
    assignment = models.ForeignKey(TrainerHorseAssignment, on_delete=models.DO_NOTHING,
                                   db_column="TrainerHorseAssignmentID", related_name="plans")
    goal = models.CharField(max_length=1000, null=True, blank=True, db_column="Goal")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(null=True, blank=True, db_column="EndDate")
    overall_intensity = models.CharField(max_length=30, choices=INTENSITY_CHOICES, null=True, blank=True,
                                         db_column="OverallIntensity")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_column="Status")
    created_at = models.DateTimeField(default=timezone.now, db_column="CreatedAt")
    note = models.CharField(max_length=2000, null=True, blank=True, db_column="Note")
    submitted_at = models.DateTimeField(null=True, blank=True, db_column="SubmittedAt")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                                    db_column="ApprovedByHeadTrainerID", related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True, db_column="ApprovedAt")
    review_note = models.CharField(max_length=1000, null=True, blank=True, db_column="ReviewNote")

    class Meta:
        managed = False
        db_table = "TrainingPlan"
        ordering = ["-created_at", "-id"]


class TrainingPlanStage(models.Model):
    id = models.AutoField(primary_key=True, db_column="TrainingPlanStageID")
    plan = models.ForeignKey(TrainingPlan, on_delete=models.DO_NOTHING, db_column="TrainingPlanID",
                             related_name="stages")
    stage_name = models.CharField(max_length=100, db_column="StageName")
    stage_order = models.IntegerField(db_column="StageOrder")
    goal = models.CharField(max_length=1000, null=True, blank=True, db_column="Goal")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(null=True, blank=True, db_column="EndDate")
    intensity = models.CharField(max_length=30, choices=INTENSITY_CHOICES, null=True, blank=True,
                                 db_column="Intensity")
    training_load = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        db_column="TrainingLoad")
    distance_target_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             db_column="DistanceTargetKm")
    surface = models.CharField(max_length=50, null=True, blank=True, db_column="Surface")
    note = models.CharField(max_length=1500, null=True, blank=True, db_column="Note")
    # Trainer chốt giai đoạn -> gửi tổng kết cho chủ ngựa (xem apps/training/summaries.py)
    closed_at = models.DateTimeField(null=True, blank=True, db_column="ClosedAt")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
                                  db_column="ClosedByID", related_name="+")
    summary_note = models.CharField(max_length=2000, null=True, blank=True, db_column="SummaryNote")

    class Meta:
        managed = False
        db_table = "TrainingPlanStage"
        ordering = ["stage_order", "id"]


class TrainingSession(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "Assigned"
        IN_PROGRESS = "In Progress"
        COMPLETED = "Completed"
        CANCELLED = "Cancelled"
        MISSED = "Missed"

    id = models.AutoField(primary_key=True, db_column="TrainingSessionID")
    stage = models.ForeignKey(TrainingPlanStage, on_delete=models.DO_NOTHING, db_column="TrainingPlanStageID",
                              related_name="sessions")
    work_rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="WorkRiderID",
                                   related_name="+")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING,
                                    db_column="AssignedByHeadTrainerID", related_name="+")
    substitute_trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True,
                                           blank=True, db_column="SubstituteTrainerID", related_name="+")
    session_date = models.DateField(db_column="SessionDate")
    start_time = models.TimeField(db_column="StartTime")
    end_time = models.TimeField(null=True, blank=True, db_column="EndTime")
    sequence_no = models.IntegerField(db_column="SequenceNo")
    training_type = models.CharField(max_length=60, db_column="TrainingType")
    duration_planned_minutes = models.IntegerField(null=True, blank=True, db_column="DurationPlannedMinutes")
    distance_planned_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                              db_column="DistancePlannedKm")
    target_speed_kmh = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                           db_column="TargetSpeedKmh")
    training_load = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        db_column="TrainingLoad")
    surface = models.CharField(max_length=50, null=True, blank=True, db_column="Surface")
    location = models.CharField(max_length=150, null=True, blank=True, db_column="Location")
    instructions = models.CharField(max_length=2000, null=True, blank=True, db_column="Instructions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED, db_column="Status")

    class Meta:
        managed = False
        db_table = "TrainingSession"
        ordering = ["session_date", "start_time", "sequence_no", "id"]

    # Buổi tập không có HorseID trực tiếp: Session -> Stage -> Plan -> Assignment -> Horse
    @property
    def assignment(self):
        return self.stage.plan.assignment

    @property
    def horse(self):
        return self.assignment.horse

    @property
    def supervising_trainer_id(self):
        """Trainer có mặt giám sát: Substitute nếu có, không thì trainer phụ trách."""
        return self.substitute_trainer_id or self.assignment.trainer_id


class TrainingResult(models.Model):
    id = models.AutoField(primary_key=True, db_column="TrainingResultID")
    session = models.OneToOneField(TrainingSession, on_delete=models.DO_NOTHING, db_column="TrainingSessionID",
                                   related_name="result")
    actual_duration_minutes = models.IntegerField(null=True, blank=True, db_column="ActualDurationMinutes")
    actual_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             db_column="ActualDistanceKm")
    avg_speed_kmh = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        db_column="AvgSpeedKmh")
    max_speed_kmh = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        db_column="MaxSpeedKmh")
    avg_heart_rate = models.IntegerField(null=True, blank=True, db_column="AvgHeartRate")
    max_heart_rate = models.IntegerField(null=True, blank=True, db_column="MaxHeartRate")
    recovery_minutes = models.IntegerField(null=True, blank=True, db_column="RecoveryMinutes")
    performance_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                            db_column="PerformanceScore")
    rider_observation = models.CharField(max_length=2000, null=True, blank=True, db_column="RiderObservation")
    substitute_observation = models.CharField(max_length=2000, null=True, blank=True,
                                              db_column="SubstituteObservation")
    video_url = models.CharField(max_length=500, null=True, blank=True, db_column="VideoUrl")
    recorded_at = models.DateTimeField(default=timezone.now, db_column="RecordedAt")

    class Meta:
        managed = False
        db_table = "TrainingResult"


class TrainingReview(models.Model):
    class Evaluation(models.TextChoices):
        EXCELLENT = "Excellent"
        GOOD = "Good"
        AVERAGE = "Average"
        NEEDS_IMPROVEMENT = "Needs Improvement"

    id = models.AutoField(primary_key=True, db_column="TrainingReviewID")
    session = models.ForeignKey(TrainingSession, on_delete=models.DO_NOTHING, db_column="TrainingSessionID",
                                related_name="reviews")
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, db_column="TrainerID",
                                related_name="+")
    review_date = models.DateTimeField(default=timezone.now, db_column="ReviewDate")
    evaluation = models.CharField(max_length=30, choices=Evaluation.choices, null=True, blank=True,
                                  db_column="Evaluation")
    trainer_comment = models.CharField(max_length=2000, null=True, blank=True, db_column="TrainerComment")
    adjustment_required = models.BooleanField(default=False, db_column="AdjustmentRequired")
    adjustment_note = models.CharField(max_length=1500, null=True, blank=True, db_column="AdjustmentNote")

    class Meta:
        managed = False
        db_table = "TrainingReview"
        ordering = ["-review_date", "-id"]
