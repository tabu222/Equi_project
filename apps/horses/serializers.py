import json
from datetime import date

from rest_framework import serializers

from apps.core.serializers import DBColumnModelSerializer, fmt_datetime

from .models import Horse, HorseDocument, ProfileChangeRequest, RegistrationRequest, Stall

# Các trường lý lịch: Owner / Manager được nhập khi hồ sơ còn Draft hoặc Rejected,
# và là các trường được phép xin sửa (ProfileChangeRequest) sau khi đã Approved.
PROFILE_FIELDS = [
    "horse_name", "breed", "date_of_birth", "coat_color", "gender",
    "sire_name", "dam_name", "microchip_number", "passport_number",
]


class OwnerBriefSerializer(serializers.Serializer):
    UserID = serializers.IntegerField(source="id")
    FullName = serializers.CharField(source="full_name")
    Email = serializers.CharField(source="email")
    Phone = serializers.CharField(source="phone", allow_null=True)
    Address = serializers.CharField(source="address", allow_null=True)


class HorseSerializer(DBColumnModelSerializer):
    """
    Ngựa trả về đúng tên cột database, cộng thêm vài thông tin tính sẵn:
      SexClass          Foal / Colt / Filly / Stallion / Mare / Gelding (giống cột tính trong SQL)
      InitialExamSigned true khi Vet đã chốt phiếu khám đầu vào của lần nộp hiện tại
      Owner             thông tin liên hệ chủ ngựa
      CurrentStall      chuồng đang ở (null nếu chưa xếp)
    """

    SexClass = serializers.SerializerMethodField()
    InitialExamSigned = serializers.SerializerMethodField()
    Owner = OwnerBriefSerializer(source="owner", read_only=True)
    CurrentStall = serializers.SerializerMethodField()

    class Meta:
        model = Horse
        fields = [
            "id", "club", "owner", *PROFILE_FIELDS, "horse_code", "verified_by", "verified_at",
            "registration_status", "current_health_status", "archived_at", "archived_by", "archive_reason",
            "created_at", "updated_at", "SexClass", "InitialExamSigned", "Owner", "CurrentStall",
        ]
        read_only_fields = fields

    def get_SexClass(self, obj):
        return obj.sex_class

    def get_InitialExamSigned(self, obj):
        annotated = getattr(obj, "initial_exam_signed", None)
        if annotated is not None:
            return bool(annotated)
        from apps.medical.services import has_signed_initial_exam

        return has_signed_initial_exam(obj)

    def get_CurrentStall(self, obj):
        assignment = obj.stall_assignments.filter(status="Active").select_related("stall").first()
        if not assignment:
            return None
        return {"StallID": assignment.stall_id, "StallNumber": assignment.stall.stall_number,
                "StartDate": assignment.start_date}


class HorseDetailSerializer(HorseSerializer):
    """Chi tiết một ngựa: thêm tóm tắt sức khỏe (lần khám đã chốt gần nhất). Owner chỉ thấy phần tóm tắt này."""

    HealthSummary = serializers.SerializerMethodField()

    class Meta(HorseSerializer.Meta):
        fields = HorseSerializer.Meta.fields + ["HealthSummary"]
        read_only_fields = fields

    def get_HealthSummary(self, obj):
        from apps.medical.services import latest_signed_record

        record = latest_signed_record(obj)
        if record is None:
            return None
        return {
            "MedicalRecordID": record.id,
            "ExamDate": fmt_datetime(record.exam_date),
            "ExamType": record.exam_type,
            "HealthStatus": record.health_status,
            "TrainingEligibility": record.training_eligibility,
            "Conclusion": record.conclusion,
            "RestrictionNote": record.restriction_note,
            "FollowUpDate": record.follow_up_date,
        }


class HorseWriteSerializer(DBColumnModelSerializer):
    """Tạo / sửa lý lịch ngựa. Body dùng tên cột: {"HorseName": ..., "MicrochipNumber": ...}."""

    class Meta:
        model = Horse
        fields = PROFILE_FIELDS
        extra_kwargs = {"horse_name": {"required": True}}

    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Ngày sinh không được ở tương lai.")
        return value

    def validate_microchip_number(self, value):
        value = (value or "").strip() or None
        if value:
            others = Horse.objects.filter(microchip_number=value)
            if self.instance is not None:
                others = others.exclude(pk=self.instance.pk)
            if others.exists():
                raise serializers.ValidationError("Số microchip đã tồn tại ở một ngựa khác.")
        return value


class HorseCreateSerializer(HorseWriteSerializer):
    """
    Tạo hồ sơ (trạng thái Draft).
      - Owner tự đăng ký: gửi thêm ClubID (CLB muốn gửi ngựa vào). OwnerID = chính mình.
      - Manager nhập hộ: gửi thêm OwnerID (chủ ngựa). ClubID = CLB của Manager.
    """

    ClubID = serializers.IntegerField(required=False, write_only=True)
    OwnerID = serializers.IntegerField(required=False, write_only=True)

    class Meta(HorseWriteSerializer.Meta):
        fields = HorseWriteSerializer.Meta.fields + ["ClubID", "OwnerID"]


class HorseDocumentSerializer(DBColumnModelSerializer):
    class Meta:
        model = HorseDocument
        fields = ["id", "horse", "document_name", "document_type", "file_url", "uploaded_by",
                  "is_visible_to_owner", "uploaded_at"]
        read_only_fields = ["id", "horse", "uploaded_by", "uploaded_at"]
        extra_kwargs = {"file_url": {"required": True, "allow_null": False}}


class RegistrationRequestSerializer(DBColumnModelSerializer):
    class Meta:
        model = RegistrationRequest
        fields = ["id", "horse", "owner", "club", "request_date", "status", "manager_note",
                  "reviewed_by", "reviewed_at"]
        read_only_fields = fields


class StallSerializer(DBColumnModelSerializer):
    CurrentHorse = serializers.SerializerMethodField()

    class Meta:
        model = Stall
        fields = ["id", "club", "stall_number", "stall_type", "status", "CurrentHorse"]
        read_only_fields = fields

    def get_CurrentHorse(self, obj):
        assignment = obj.assignments.filter(status="Active").select_related("horse").first()
        if assignment is None:
            return None
        return {"HorseID": assignment.horse_id, "HorseName": assignment.horse.horse_name,
                "StartDate": assignment.start_date}


class StallWriteSerializer(DBColumnModelSerializer):
    class Meta:
        model = Stall
        fields = ["stall_number", "stall_type", "status"]
        extra_kwargs = {"status": {"required": False}}

    def validate_status(self, value):
        if value == Stall.Status.OCCUPIED:
            raise serializers.ValidationError("Occupied do hệ thống tự đặt khi xếp ngựa vào chuồng.")
        return value


class ProfileChangeRequestSerializer(DBColumnModelSerializer):
    """ChangedFields trả về dạng object: {"Reason": "...", "Changes": [{"Field", "OldValue", "NewValue"}]}."""

    ChangedFields = serializers.SerializerMethodField()
    HorseName = serializers.CharField(source="horse.horse_name", read_only=True)

    class Meta:
        model = ProfileChangeRequest
        fields = ["id", "horse", "HorseName", "requested_by", "requested_at", "ChangedFields",
                  "evidence_document", "status", "reviewed_by", "reviewed_at", "review_note"]
        read_only_fields = fields

    def get_ChangedFields(self, obj):
        try:
            return json.loads(obj.changed_fields)
        except (TypeError, ValueError):
            return obj.changed_fields


class ProfileChangeRequestCreateSerializer(serializers.Serializer):
    """Body: {"Changes": {"CoatColor": "Dark Bay"}, "Reason": "...", "EvidenceDocumentID": 3}"""

    Changes = serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    Reason = serializers.CharField(max_length=1000)
    EvidenceDocumentID = serializers.IntegerField(required=False, allow_null=True)


class ReasonSerializer(serializers.Serializer):
    Reason = serializers.CharField(max_length=1000)


class ApproveSerializer(serializers.Serializer):
    HorseCode = serializers.CharField(max_length=30)
    StallID = serializers.IntegerField(required=False, allow_null=True)
    ManagerNote = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class ReviewNoteSerializer(serializers.Serializer):
    ReviewNote = serializers.CharField(max_length=1000, required=False, allow_blank=True)
