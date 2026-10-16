from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.horses.models import Horse, RegistrationRequest
from .models import MedicalRecord, MedicalRecordAmendment
ACTIVE_REQUEST_STATUSES = ("PendingExam", "Approved")

def signed_initial_exams():
    return MedicalRecord.objects.filter(
        exam_type=MedicalRecord.ExamType.INITIAL,
        record_status=MedicalRecord.RecordStatus.SIGNED,
        registration_request__status__in=ACTIVE_REQUEST_STATUSES,
    )


def annotate_initial_exam_signed(horse_queryset):
    """Thêm cột tạm initial_exam_signed cho danh sách ngựa (1 truy vấn, không lặp từng con)."""
    return horse_queryset.annotate(
        initial_exam_signed=Exists(signed_initial_exams().filter(horse=OuterRef("pk")))
    )


def has_signed_initial_exam(horse) -> bool:
    return signed_initial_exams().filter(horse=horse).exists()


def signed_initial_exam_for(horse):
    return signed_initial_exams().filter(horse=horse).order_by("-signed_at", "-id").first()


def latest_signed_record(horse):
    return (
        MedicalRecord.objects.filter(horse=horse, record_status=MedicalRecord.RecordStatus.SIGNED)
        .order_by("-exam_date", "-id")
        .first()
    )


def current_pending_request(horse):
    return (
        horse.registration_requests.filter(status=RegistrationRequest.Status.PENDING_EXAM)
        .order_by("-request_date", "-id")
        .first()
    )


def ensure_draft_owner(record, user):
    if record.is_signed:
        raise BusinessRuleError("Phiếu khám đã chốt không được sửa. Hãy thêm phiếu đính chính.", "RECORD_SIGNED")
    if record.vet_id != user.pk:
        raise BusinessRuleError("Chỉ Vet lập phiếu mới được sửa / chốt phiếu nháp này.", "NOT_RECORD_OWNER")


def check_restriction_note(values, record=None):
    """CK_MedicalRecord_Restriction: TrainingEligibility = Restricted thì phải có RestrictionNote (kể cả phiếu nháp)."""
    eligibility = values.get("training_eligibility", getattr(record, "training_eligibility", None))
    note = values.get("restriction_note", getattr(record, "restriction_note", None))
    if eligibility == MedicalRecord.TrainingEligibility.RESTRICTED and not note:
        raise ValidationError({"RestrictionNote": ["Mức Restricted cần ghi rõ hạn chế tập (RestrictionNote)."]})


def update_record(record, user, values: dict):
    ensure_draft_owner(record, user)
    check_restriction_note(values, record)
    if "exam_type" in values and values["exam_type"] != record.exam_type:
        raise BusinessRuleError("Không được đổi loại khám. Hãy xóa phiếu nháp và lập phiếu mới.", "EXAM_TYPE_LOCKED")
    for attr, value in values.items():
        setattr(record, attr, value)
    record.save()
    log_action(user, "UPDATE_MEDICAL_RECORD", record)
    return record


def add_amendment(record, user, reason: str, content: str):
    if not record.is_signed:
        raise BusinessRuleError("Phiếu nháp thì sửa trực tiếp, không cần phiếu đính chính.", "RECORD_NOT_SIGNED")
    amendment = MedicalRecordAmendment.objects.create(
        medical_record=record, amended_by=user, amended_at=timezone.now(), reason=reason, amended_content=content,
    )
    log_action(user, "AMEND_MEDICAL_RECORD", record, {"MedicalRecordAmendmentID": amendment.id})
    return amendment


def create_record(horse, user, values):
    check_restriction_note(values)
    if values.get("exam_type") != MedicalRecord.ExamType.INITIAL:
        raise BusinessRuleError("Bản backend này chỉ hỗ trợ khám đầu vào Flow 1.", "EXAM_TYPE_UNAVAILABLE")
    if horse.registration_status != Horse.RegistrationStatus.PENDING_EXAM:
        raise BusinessRuleError("Chỉ khám đầu vào khi hồ sơ ngựa đang chờ khám (PendingExam).", "INVALID_STATUS")
    request = current_pending_request(horse)
    if request is None:
        raise BusinessRuleError("Không tìm thấy hồ sơ tiếp nhận đang chờ khám.", "REQUEST_NOT_FOUND")
    if request.medical_records.filter(exam_type=MedicalRecord.ExamType.INITIAL).exists():
        raise BusinessRuleError("Hồ sơ tiếp nhận này đã có phiếu khám đầu vào.", "INITIAL_EXAM_EXISTS")
    values = dict(values)
    values["exam_date"] = values.get("exam_date") or timezone.now()
    record = MedicalRecord.objects.create(horse=horse, vet=user, registration_request=request, **values)
    log_action(user, "CREATE_MEDICAL_RECORD", record, {"HorseID": horse.pk, "ExamType": record.exam_type})
    return record


def delete_draft(record, user):
    ensure_draft_owner(record, user)
    log_action(user, "DELETE_MEDICAL_RECORD", record, {"HorseID": record.horse_id})
    record.delete()


def sign_record(record, user):
    ensure_draft_owner(record, user)
    if record.exam_type != MedicalRecord.ExamType.INITIAL:
        raise BusinessRuleError("Bản backend này chỉ hỗ trợ khám đầu vào Flow 1.", "EXAM_TYPE_UNAVAILABLE")
    current = current_pending_request(record.horse)
    if current is None or current.pk != record.registration_request_id:
        raise BusinessRuleError("Phiếu không thuộc hồ sơ tiếp nhận đang chờ khám.", "INVALID_STATUS")
    missing = [name for name, value in (("HealthStatus", record.health_status),
                                       ("TrainingEligibility", record.training_eligibility)) if not value]
    if missing:
        raise BusinessRuleError(f"Cần nhập đủ trước khi chốt phiếu: {', '.join(missing)}.", "MISSING_FIELDS")
    check_restriction_note({}, record)
    record.record_status = MedicalRecord.RecordStatus.SIGNED
    record.signed_at = timezone.now()
    record.save(update_fields=["record_status", "signed_at"])
    horse = record.horse
    horse.current_health_status = record.health_status
    horse.touch()
    horse.save(update_fields=["current_health_status", "updated_at"])
    log_action(user, "SIGN_MEDICAL_RECORD", record, {"HorseID": horse.pk,
               "HealthStatus": record.health_status, "TrainingEligibility": record.training_eligibility})
    from apps.core import emails
    emails.initial_exam_signed(record)
    return record, None
