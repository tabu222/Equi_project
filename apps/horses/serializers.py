import json
import re
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


MICROCHIP_RE = re.compile(r"^\d{15}$")
PASSPORT_RE = re.compile(r"^[A-Z0-9][A-Z0-9/-]{4,49}$")
OLDEST_HORSE_YEARS = 40
TEXT_FIELDS = ["horse_name", "breed", "coat_color", "sire_name", "dam_name"]


def _required_text(label):
    return {"required": True, "allow_null": False, "allow_blank": False,
            "error_messages": {"required": f"Cần nhập {label}.", "blank": f"Cần nhập {label}.",
                               "null": f"Cần nhập {label}."}}


class HorseWriteSerializer(DBColumnModelSerializer):
    """
    Tạo / sửa lý lịch ngựa. Body dùng tên cột: {"HorseName": ..., "MicrochipNumber": ...}.
    Mọi trường lý lịch đều bắt buộc (không để trống / null). Sai ở đâu thì báo đúng trường đó:
      MicrochipNumber  đúng 15 chữ số (chuẩn ISO 11784/11785), không trùng ngựa khác
      PassportNumber   chữ in hoa, số, "-" hoặc "/", 5-50 ký tự, không trùng ngựa khác
      DateOfBirth      không ở tương lai, không quá 40 năm
      SireName / DamName  khác tên ngựa và khác nhau
    """

    class Meta:
        model = Horse
        fields = PROFILE_FIELDS
        extra_kwargs = {
            "horse_name": _required_text("tên ngựa (HorseName)"),
            "breed": _required_text("giống ngựa (Breed)"),
            "coat_color": _required_text("màu lông (CoatColor)"),
            "sire_name": _required_text("tên ngựa cha (SireName)"),
            "dam_name": _required_text("tên ngựa mẹ (DamName)"),
            "microchip_number": _required_text("số microchip (MicrochipNumber)"),
            "passport_number": _required_text("số hộ chiếu / đăng ký (PassportNumber)"),
            "date_of_birth": {"required": True, "allow_null": False, "error_messages": {
                "required": "Cần nhập ngày sinh (DateOfBirth).", "null": "Cần nhập ngày sinh (DateOfBirth).",
                "invalid": "Ngày sinh phải theo dạng YYYY-MM-DD, vd 2021-03-12."}},
            "gender": {"required": True, "allow_null": False, "allow_blank": False, "error_messages": {
                "required": "Cần chọn giới tính (Gender).", "null": "Cần chọn giới tính (Gender).",
                "blank": "Cần chọn giới tính (Gender).",
                "invalid_choice": "Giới tính phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến)."}},
        }

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        for attr in TEXT_FIELDS:
            if attr in values:
                values[attr] = values[attr].strip()
        return values

    def validate_date_of_birth(self, value):
        today = date.today()
        if value > today:
            raise serializers.ValidationError("Ngày sinh không được ở tương lai.")
        if value < today.replace(year=today.year - OLDEST_HORSE_YEARS):
            raise serializers.ValidationError(f"Ngày sinh không hợp lệ: ngựa không thể quá {OLDEST_HORSE_YEARS} tuổi.")
        return value

    def _others(self):
        others = Horse.objects.all()
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        return others

    def validate_microchip_number(self, value):
        value = value.replace(" ", "").strip()
        if not MICROCHIP_RE.match(value):
            raise serializers.ValidationError(
                "Số microchip phải gồm đúng 15 chữ số (chuẩn ISO 11784/11785; 3 số đầu là mã quốc gia "
                "hoặc nhà sản xuất), vd 985141000123401."
            )
        if self._others().filter(microchip_number=value).exists():
            raise serializers.ValidationError("Số microchip đã tồn tại ở một ngựa khác.")
        return value

    def validate_passport_number(self, value):
        value = value.strip().upper()
        if not PASSPORT_RE.match(value):
            raise serializers.ValidationError(
                "Số hộ chiếu / đăng ký chỉ gồm chữ, số, dấu '-' hoặc '/', dài 5-50 ký tự, vd VN-TB-2021-0142."
            )
        if self._others().filter(passport_number__iexact=value).exists():
            raise serializers.ValidationError("Số hộ chiếu / đăng ký đã được dùng cho một ngựa khác.")
        return value

    def validate(self, attrs):
        def current(attr):
            if attr in attrs:
                return attrs[attr]
            return getattr(self.instance, attr, None) if self.instance is not None else None

        name, sire, dam = (current(a) or "" for a in ("horse_name", "sire_name", "dam_name"))
        errors = {}
        if sire and sire.casefold() == name.casefold():
            errors["SireName"] = ["Tên ngựa cha không được trùng tên chính con ngựa này."]
        if dam and dam.casefold() == name.casefold():
            errors["DamName"] = ["Tên ngựa mẹ không được trùng tên chính con ngựa này."]
        if sire and dam and sire.casefold() == dam.casefold():
            errors.setdefault("DamName", []).append("Tên ngựa cha và ngựa mẹ không được giống nhau.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


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
