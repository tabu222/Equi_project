from rest_framework import serializers

from apps.core.serializers import DBColumnModelSerializer

from .models import (
    HorseAssessment, HorseWorkRiderPreference, Specialization, TrainerHorseAssignment, TrainingPlan,
    TrainingPlanStage, TrainingResult, TrainingReview, TrainingSession,
)


def _name(user):
    return user.full_name if user else None


# ---------------------------------------------------------------------------
# Chuyên môn, đánh giá, phân công
# ---------------------------------------------------------------------------
class SpecializationSerializer(DBColumnModelSerializer):
    class Meta:
        model = Specialization
        fields = ["id", "code", "name", "description", "status"]
        read_only_fields = fields


class HorseAssessmentSerializer(DBColumnModelSerializer):
    HeadTrainerName = serializers.CharField(source="head_trainer.full_name", read_only=True)
    SpecializationName = serializers.CharField(source="specialization.name", read_only=True)

    class Meta:
        model = HorseAssessment
        fields = ["id", "horse", "head_trainer", "HeadTrainerName", "specialization", "SpecializationName",
                  "assessment_date", "quality_score", "fitness_level", "assessment_note", "decision_status"]
        read_only_fields = ["id", "horse", "head_trainer", "HeadTrainerName", "SpecializationName",
                            "assessment_date"]

    def validate_quality_score(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("Điểm chất lượng từ 0 đến 100.")
        return value


class TrainerHorseAssignmentSerializer(DBColumnModelSerializer):
    HorseName = serializers.CharField(source="horse.horse_name", read_only=True)
    TrainerName = serializers.CharField(source="trainer.full_name", read_only=True)
    SpecializationName = serializers.CharField(source="specialization.name", read_only=True)
    AssignedByName = serializers.CharField(source="assigned_by.full_name", read_only=True)

    class Meta:
        model = TrainerHorseAssignment
        fields = ["id", "horse", "HorseName", "trainer", "TrainerName", "specialization", "SpecializationName",
                  "assigned_by", "AssignedByName", "assessment", "start_date", "end_date", "status",
                  "assignment_note"]
        read_only_fields = fields


class AssignTrainerSerializer(serializers.Serializer):
    HorseID = serializers.IntegerField()
    TrainerID = serializers.IntegerField()
    SpecializationID = serializers.IntegerField()
    AssessmentID = serializers.IntegerField(required=False, allow_null=True)
    StartDate = serializers.DateField(required=False, allow_null=True)
    AssignmentNote = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)


class WorkRiderPreferenceSerializer(DBColumnModelSerializer):
    WorkRiderName = serializers.CharField(source="work_rider.full_name", read_only=True)

    class Meta:
        model = HorseWorkRiderPreference
        fields = ["id", "horse", "work_rider", "WorkRiderName", "assigned_by", "start_date", "end_date",
                  "priority", "is_preferred", "note"]
        read_only_fields = fields


class WorkRiderPreferenceCreateSerializer(serializers.Serializer):
    WorkRiderID = serializers.IntegerField()
    Priority = serializers.IntegerField(min_value=1, default=1)
    StartDate = serializers.DateField(required=False, allow_null=True)
    Note = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)


# ---------------------------------------------------------------------------
# Giáo án
# ---------------------------------------------------------------------------
STAGE_FIELDS = ["stage_name", "stage_order", "goal", "start_date", "end_date", "intensity", "training_load",
                "distance_target_km", "surface", "note"]
PLAN_FIELDS = ["goal", "start_date", "end_date", "overall_intensity", "note"]


class TrainingPlanStageSerializer(DBColumnModelSerializer):
    class Meta:
        model = TrainingPlanStage
        fields = ["id", "plan", *STAGE_FIELDS]
        read_only_fields = ["id", "plan"]
        extra_kwargs = {"stage_order": {"required": False}}

    def validate_stage_order(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Thứ tự giai đoạn phải lớn hơn 0.")
        return value

    def validate(self, attrs):
        for name in ("training_load", "distance_target_km"):
            if attrs.get(name) is not None and attrs[name] < 0:
                raise serializers.ValidationError({self.fields_by_attr(name): ["Không được âm."]})
        return attrs

    def fields_by_attr(self, attr):
        return next((key for key, field in self.fields.items() if field.source == attr), attr)


class TrainingPlanSerializer(DBColumnModelSerializer):
    """Giáo án kèm thông tin ngựa, trainer và các giai đoạn."""

    HorseID = serializers.IntegerField(source="assignment.horse_id", read_only=True)
    HorseName = serializers.CharField(source="assignment.horse.horse_name", read_only=True)
    TrainerID = serializers.IntegerField(source="assignment.trainer_id", read_only=True)
    TrainerName = serializers.CharField(source="assignment.trainer.full_name", read_only=True)
    Stages = TrainingPlanStageSerializer(source="stages", many=True, read_only=True)

    class Meta:
        model = TrainingPlan
        fields = ["id", "assignment", "HorseID", "HorseName", "TrainerID", "TrainerName", *PLAN_FIELDS, "status",
                  "created_at", "submitted_at", "approved_by", "approved_at", "review_note", "Stages"]
        read_only_fields = fields


class TrainingPlanWriteSerializer(DBColumnModelSerializer):
    class Meta:
        model = TrainingPlan
        fields = PLAN_FIELDS


class TrainingPlanCreateSerializer(TrainingPlanWriteSerializer):
    """Body: {"HorseID": 1, "Goal": ..., "StartDate": ..., "Stages": [{"StageName": ..., "StartDate": ...}]}"""

    HorseID = serializers.IntegerField(write_only=True)
    Stages = TrainingPlanStageSerializer(many=True, required=False)

    class Meta(TrainingPlanWriteSerializer.Meta):
        fields = PLAN_FIELDS + ["HorseID", "Stages"]


class NoteSerializer(serializers.Serializer):
    ReviewNote = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)


class ReasonOptionalSerializer(serializers.Serializer):
    Reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)


# ---------------------------------------------------------------------------
# Buổi tập
# ---------------------------------------------------------------------------
SESSION_FIELDS = ["session_date", "start_time", "end_time", "sequence_no", "training_type",
                  "duration_planned_minutes", "distance_planned_km", "target_speed_kmh", "training_load", "surface",
                  "location", "instructions"]
RESULT_FIELDS = ["actual_duration_minutes", "actual_distance_km", "avg_speed_kmh", "max_speed_kmh",
                 "avg_heart_rate", "max_heart_rate", "recovery_minutes", "performance_score", "rider_observation",
                 "video_url"]


class TrainingResultSerializer(DBColumnModelSerializer):
    class Meta:
        model = TrainingResult
        fields = ["id", "session", *RESULT_FIELDS, "substitute_observation", "recorded_at"]
        read_only_fields = ["id", "session", "substitute_observation", "recorded_at"]

    def validate(self, attrs):
        score = attrs.get("performance_score")
        if score is not None and not (0 <= score <= 100):
            raise serializers.ValidationError({"PerformanceScore": ["Điểm từ 0 đến 100."]})
        for attr, key in (("avg_heart_rate", "AvgHeartRate"), ("max_heart_rate", "MaxHeartRate")):
            if attrs.get(attr) is not None and attrs[attr] <= 0:
                raise serializers.ValidationError({key: ["Phải lớn hơn 0."]})
        for attr, key in (("actual_distance_km", "ActualDistanceKm"), ("actual_duration_minutes",
                                                                       "ActualDurationMinutes")):
            if attrs.get(attr) is not None and attrs[attr] < 0:
                raise serializers.ValidationError({key: ["Không được âm."]})
        return attrs


class TrainingReviewSerializer(DBColumnModelSerializer):
    TrainerName = serializers.CharField(source="trainer.full_name", read_only=True)
    HorseID = serializers.IntegerField(source="session.stage.plan.assignment.horse_id", read_only=True)
    HorseName = serializers.CharField(source="session.stage.plan.assignment.horse.horse_name", read_only=True)
    SessionDate = serializers.DateField(source="session.session_date", read_only=True)

    class Meta:
        model = TrainingReview
        fields = ["id", "session", "HorseID", "HorseName", "SessionDate", "trainer", "TrainerName", "review_date",
                  "evaluation", "trainer_comment", "adjustment_required", "adjustment_note"]
        read_only_fields = ["id", "session", "HorseID", "HorseName", "SessionDate", "trainer", "TrainerName",
                            "review_date"]


class TrainingSessionSerializer(DBColumnModelSerializer):
    """
    Buổi tập kèm thông tin tính sẵn (giống view vw_WorkRiderDailySchedule):
    HorseID, HorseName, TrainingPlanID, AssignedTrainerID, SupervisingTrainerID, IsSubstitute, Result, Review.
    """

    HorseID = serializers.IntegerField(source="stage.plan.assignment.horse_id", read_only=True)
    HorseName = serializers.CharField(source="stage.plan.assignment.horse.horse_name", read_only=True)
    HorseCode = serializers.CharField(source="stage.plan.assignment.horse.horse_code", read_only=True)
    TrainingPlanID = serializers.IntegerField(source="stage.plan_id", read_only=True)
    StageName = serializers.CharField(source="stage.stage_name", read_only=True)
    WorkRiderName = serializers.CharField(source="work_rider.full_name", read_only=True)
    AssignedTrainerID = serializers.IntegerField(source="stage.plan.assignment.trainer_id", read_only=True)
    AssignedTrainerName = serializers.CharField(source="stage.plan.assignment.trainer.full_name", read_only=True)
    SupervisingTrainerID = serializers.SerializerMethodField()
    SupervisingTrainerName = serializers.SerializerMethodField()
    IsSubstitute = serializers.SerializerMethodField()
    Result = serializers.SerializerMethodField()
    Review = serializers.SerializerMethodField()

    class Meta:
        model = TrainingSession
        fields = ["id", "stage", "TrainingPlanID", "StageName", "HorseID", "HorseName", "HorseCode", "work_rider",
                  "WorkRiderName", "assigned_by", "substitute_trainer", "AssignedTrainerID", "AssignedTrainerName",
                  "SupervisingTrainerID", "SupervisingTrainerName", "IsSubstitute", *SESSION_FIELDS, "status",
                  "Result", "Review"]
        read_only_fields = fields

    def get_SupervisingTrainerID(self, obj):
        return obj.supervising_trainer_id

    def get_SupervisingTrainerName(self, obj):
        return _name(obj.substitute_trainer) or _name(obj.stage.plan.assignment.trainer)

    def get_IsSubstitute(self, obj):
        return obj.substitute_trainer_id is not None

    def get_Result(self, obj):
        try:
            return TrainingResultSerializer(obj.result).data
        except TrainingResult.DoesNotExist:
            return None

    def get_Review(self, obj):
        review = obj.reviews.first()
        return TrainingReviewSerializer(review).data if review else None


class TrainingSessionWriteSerializer(DBColumnModelSerializer):
    """
    Head Trainer xếp / sửa buổi tập.
    Body: {"TrainingPlanStageID": 3, "WorkRiderID": 9, "SubstituteTrainerID": null, "SessionDate": "2026-10-12",
           "StartTime": "06:00", "TrainingType": "Canter", "TrainingLoad": 40, ...}
    SequenceNo bỏ trống = tự lấy thứ tự tiếp theo trong ngày của Work Rider.
    """

    TrainingPlanStageID = serializers.PrimaryKeyRelatedField(source="stage", queryset=TrainingPlanStage.objects.all())
    WorkRiderID = serializers.IntegerField(source="work_rider_id")
    SubstituteTrainerID = serializers.IntegerField(source="substitute_trainer_id", required=False, allow_null=True)

    class Meta:
        model = TrainingSession
        fields = ["TrainingPlanStageID", "WorkRiderID", "SubstituteTrainerID", *SESSION_FIELDS]
        extra_kwargs = {"sequence_no": {"required": False}}

    def validate(self, attrs):
        if attrs.get("sequence_no") is not None and attrs["sequence_no"] <= 0:
            raise serializers.ValidationError({"SequenceNo": ["Phải lớn hơn 0."]})
        if attrs.get("duration_planned_minutes") is not None and attrs["duration_planned_minutes"] <= 0:
            raise serializers.ValidationError({"DurationPlannedMinutes": ["Phải lớn hơn 0."]})
        for attr, key in (("distance_planned_km", "DistancePlannedKm"), ("training_load", "TrainingLoad")):
            if attrs.get(attr) is not None and attrs[attr] < 0:
                raise serializers.ValidationError({key: ["Không được âm."]})
        return attrs


class StopSessionSerializer(serializers.Serializer):
    """Dừng buổi tập; có thể báo luôn sự cố sức khỏe (vào hàng chờ Vet)."""

    Reason = serializers.CharField(max_length=1000)
    ReportHealth = serializers.BooleanField(default=False)
    Severity = serializers.ChoiceField(choices=["Urgent", "Normal"], default="Urgent")
    Description = serializers.CharField(max_length=2500, required=False, allow_blank=True)


class SubstituteObservationSerializer(serializers.Serializer):
    SubstituteObservation = serializers.CharField(max_length=2000)


class TrainerSpecializationSerializer(serializers.Serializer):
    SpecializationID = serializers.IntegerField()
