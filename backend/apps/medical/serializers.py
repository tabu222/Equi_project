from datetime import date
from rest_framework import serializers
from apps.core.serializers import DBColumnModelSerializer
from .models import MedicalRecord, MedicalRecordAmendment
EXAM_FIELDS = ["exam_date", "weight_kg", "height_cm", "symptoms", "diagnosis", "conclusion", "injury_location",
               "treatment_plan", "health_status", "training_eligibility", "restriction_note", "follow_up_date", "note"]

class MedicalRecordSerializer(DBColumnModelSerializer):
    """Phiếu khám: trả về đúng tên cột MedicalRecord, thêm VetName và HorseName để hiển thị."""

    VetName = serializers.CharField(source="vet.full_name", read_only=True)
    HorseName = serializers.CharField(source="horse.horse_name", read_only=True)

    class Meta:
        model = MedicalRecord
        fields = ["id", "horse", "HorseName", "vet", "VetName", "registration_request", "training_session_id",
                  "exam_type", *EXAM_FIELDS, "record_status", "signed_at"]
        read_only_fields = fields


class MedicalRecordWriteSerializer(DBColumnModelSerializer):
    """
    Tạo / sửa phiếu khám (Draft).
    Body ví dụ: {"ExamType": "Initial Exam", "WeightKg": 480.5, "HeightCm": 162, "Symptoms": "...",
                 "HealthStatus": "Healthy", "TrainingEligibility": "Eligible", "Conclusion": "..."}
    ExamDate bỏ trống = thời điểm hiện tại.
    """


    class Meta:
        model = MedicalRecord
        fields = ["exam_type", *EXAM_FIELDS]
        extra_kwargs = {"exam_date": {"required": False}}

    def validate_exam_type(self, value):
        if value != MedicalRecord.ExamType.INITIAL:
            from apps.core.exceptions import BusinessRuleError
            raise BusinessRuleError("Bản backend này chỉ hỗ trợ khám đầu vào Flow 1.", "EXAM_TYPE_UNAVAILABLE")
        return value

    def validate_weight_kg(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Cân nặng phải lớn hơn 0.")
        return value

    def validate_height_cm(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Chiều cao phải lớn hơn 0.")
        return value

    def validate(self, attrs):
        exam_date = attrs.get("exam_date") or getattr(self.instance, "exam_date", None)
        follow_up = attrs.get("follow_up_date", getattr(self.instance, "follow_up_date", None))
        exam_day = exam_date.date() if exam_date else date.today()
        if follow_up and follow_up < exam_day:
            raise serializers.ValidationError({"FollowUpDate": ["Ngày tái khám không được trước ngày khám."]})
        return attrs


class MedicalRecordAmendmentSerializer(DBColumnModelSerializer):
    AmendedByName = serializers.CharField(source="amended_by.full_name", read_only=True)

    class Meta:
        model = MedicalRecordAmendment
        fields = ["id", "medical_record", "amended_by", "AmendedByName", "amended_at", "reason", "amended_content"]
        read_only_fields = ["id", "medical_record", "amended_by", "AmendedByName", "amended_at"]
