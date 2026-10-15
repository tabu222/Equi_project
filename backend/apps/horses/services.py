"""
Luật nghiệp vụ Flow 1. View chỉ gọi các hàm ở đây; mọi kiểm tra trạng thái nằm ở backend.

Draft ──submit──> Submitted ──verify──> PendingExam ──(Vet chốt khám đầu vào)──> approve ──> Approved ──archive──> Archived
  ^                   │                      │
  └──── sửa ──── Rejected <──── reject ──────┘
"""
import json

from django.utils import timezone

from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.medical.services import signed_initial_exam_for

from .models import Horse, ProfileChangeRequest, RegistrationRequest, Stall, StallAssignment
from .serializers import PROFILE_FIELDS

S = Horse.RegistrationStatus
EDITABLE_STATUSES = (S.DRAFT, S.REJECTED)
SUBMIT_REQUIRED = {
    "horse_name": "HorseName",
    "date_of_birth": "DateOfBirth",
    "gender": "Gender",
    "microchip_number": "MicrochipNumber",
}


def _require_status(horse, allowed, action):
    if horse.registration_status not in allowed:
        raise BusinessRuleError(
            f"Không thể {action} khi hồ sơ đang ở trạng thái {horse.registration_status}.",
            "INVALID_STATUS",
        )


def latest_request(horse):
    return horse.registration_requests.order_by("-request_date", "-id").first()


def ensure_editable(horse):
    _require_status(horse, EDITABLE_STATUSES, "sửa lý lịch")


def submit(horse, user):
    _require_status(horse, EDITABLE_STATUSES, "gửi hồ sơ")
    missing = [col for attr, col in SUBMIT_REQUIRED.items() if not getattr(horse, attr)]
    if missing:
        raise BusinessRuleError(f"Cần nhập đủ thông tin trước khi gửi: {', '.join(missing)}.", "MISSING_FIELDS")
    now = timezone.now()
    request = RegistrationRequest.objects.create(
        horse=horse, owner_id=horse.owner_id, club_id=horse.club_id, request_date=now,
        status=RegistrationRequest.Status.SUBMITTED,
    )
    horse.registration_status = S.SUBMITTED
    horse.touch()
    horse.save(update_fields=["registration_status", "updated_at"])
    log_action(user, "SUBMIT_REGISTRATION", horse, {"RegistrationRequestID": request.id})
    return horse


def verify(horse, user):
    """Club Manager đã đối chiếu giấy tờ, microchip -> chuyển sang chờ Vet trực khám."""
    _require_status(horse, (S.SUBMITTED,), "xác minh hồ sơ")
    request = latest_request(horse)
    now = timezone.now()
    horse.registration_status = S.PENDING_EXAM
    horse.verified_by = user
    horse.verified_at = now
    horse.touch()
    horse.save(update_fields=["registration_status", "verified_by", "verified_at", "updated_at"])
    request.status = RegistrationRequest.Status.PENDING_EXAM
    request.save(update_fields=["status"])
    log_action(user, "VERIFY_REGISTRATION", horse, {"RegistrationRequestID": request.id})
    return horse


def reject(horse, user, reason):
    _require_status(horse, (S.SUBMITTED, S.PENDING_EXAM), "từ chối hồ sơ")
    request = latest_request(horse)
    now = timezone.now()
    horse.registration_status = S.REJECTED
    horse.touch()
    horse.save(update_fields=["registration_status", "updated_at"])
    request.status = RegistrationRequest.Status.REJECTED
    request.manager_note = reason
    request.reviewed_by = user
    request.reviewed_at = now
    request.save(update_fields=["status", "manager_note", "reviewed_by", "reviewed_at"])
    log_action(user, "REJECT_REGISTRATION", horse, {"Reason": reason})
    return horse


def approve(horse, user, horse_code, stall_id=None, manager_note=None):
    """Hoàn tất tiếp nhận: cần phiếu khám đầu vào đã chốt và đạt; gán mã ngựa, xếp chuồng (nếu có)."""
    _require_status(horse, (S.PENDING_EXAM,), "duyệt hồ sơ")
    exam = signed_initial_exam_for(horse)
    if exam is None:
        raise BusinessRuleError("Ngựa chưa có phiếu khám đầu vào đã chốt.", "INITIAL_EXAM_REQUIRED")
    if not exam.passes_intake:
        raise BusinessRuleError(
            "Kết quả khám đầu vào không đạt (sức khỏe phải là Healthy hoặc Monitor và không bị cấm tập). "
            "Hãy từ chối hồ sơ.",
            "INITIAL_EXAM_FAILED",
        )
    horse_code = horse_code.strip()
    if Horse.objects.filter(club_id=horse.club_id, horse_code__iexact=horse_code).exclude(pk=horse.pk).exists():
        raise BusinessRuleError("Mã ngựa đã tồn tại trong câu lạc bộ.", "DUPLICATE_HORSE_CODE")

    now = timezone.now()
    stall = None
    if stall_id:
        stall = Stall.objects.filter(pk=stall_id, club_id=horse.club_id).first()
        if stall is None:
            raise BusinessRuleError("Chuồng không tồn tại trong câu lạc bộ.", "STALL_NOT_FOUND")
        if stall.status != Stall.Status.AVAILABLE or stall.assignments.filter(status="Active").exists():
            raise BusinessRuleError("Chuồng này không còn trống.", "STALL_NOT_AVAILABLE")

    horse.registration_status = S.APPROVED
    horse.horse_code = horse_code
    horse.current_health_status = exam.health_status
    horse.touch()
    horse.save(update_fields=["registration_status", "horse_code", "current_health_status", "updated_at"])

    request = exam.registration_request
    request.status = RegistrationRequest.Status.APPROVED
    request.reviewed_by = user
    request.reviewed_at = now
    if manager_note:
        request.manager_note = manager_note
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "manager_note"])

    if stall is not None:
        StallAssignment.objects.create(stall=stall, horse=horse, start_date=now.date())
        stall.status = Stall.Status.OCCUPIED
        stall.save(update_fields=["status"])

    log_action(user, "APPROVE_REGISTRATION", horse, {"HorseCode": horse_code, "StallID": stall_id})
    return horse


def archive(horse, user, reason):
    """
    Ngựa rời CLB: lưu trữ hồ sơ, trả chuồng, kết thúc phân công trainer (hủy giáo án / buổi tập chưa diễn ra),
    bỏ các việc chăm sóc chưa làm, khẩu phần đang áp dụng chuyển Expired.
    """
    from apps.care.models import CareTask, DietPlan
    from apps.training.services import active_assignment, end_assignment

    _require_status(horse, (S.APPROVED,), "lưu trữ hồ sơ")
    now = timezone.now()
    for assignment in horse.stall_assignments.filter(status="Active").select_related("stall"):
        assignment.status = StallAssignment.Status.ENDED
        assignment.end_date = now.date()
        assignment.save(update_fields=["status", "end_date"])
        assignment.stall.status = Stall.Status.AVAILABLE
        assignment.stall.save(update_fields=["status"])
    assignment = active_assignment(horse)
    if assignment is not None:
        end_assignment(assignment, user, "Ngựa rời CLB")
    for task in CareTask.objects.filter(horse=horse, status=CareTask.Status.PENDING):
        task.status = CareTask.Status.SKIPPED
        task.note = ((task.note or "") + "\n[Bỏ qua] Ngựa đã rời CLB").strip()[:1000]
        task.save(update_fields=["status", "note"])
    DietPlan.objects.filter(horse=horse, status__in=("Pending", "Approved", "Adjusted")).update(status="Expired")

    horse.registration_status = S.ARCHIVED
    horse.archived_at = now
    horse.archived_by = user
    horse.archive_reason = reason
    horse.touch()
    horse.save(update_fields=["registration_status", "archived_at", "archived_by", "archive_reason", "updated_at"])
    log_action(user, "ARCHIVE_HORSE", horse, {"Reason": reason})
    return horse


# ---------------------------------------------------------------------------
# Yêu cầu sửa lý lịch (sau khi ngựa đã Approved)
# ---------------------------------------------------------------------------
COLUMN_TO_ATTR = {Horse._meta.get_field(attr).db_column: attr for attr in PROFILE_FIELDS}


def create_change_request(horse, user, changes: dict, reason: str, evidence_document_id=None):
    _require_status(horse, (S.APPROVED,), "gửi yêu cầu sửa lý lịch")
    if horse.profile_change_requests.filter(status=ProfileChangeRequest.Status.PENDING).exists():
        raise BusinessRuleError("Ngựa này đang có một yêu cầu sửa lý lịch chờ duyệt.", "PENDING_REQUEST_EXISTS")
    unknown = [col for col in changes if col not in COLUMN_TO_ATTR]
    if unknown:
        raise BusinessRuleError(
            f"Không được xin sửa các trường: {', '.join(unknown)}. Chỉ được: {', '.join(COLUMN_TO_ATTR)}.",
            "FIELD_NOT_EDITABLE",
        )
    if not changes:
        raise BusinessRuleError("Chưa có trường nào cần sửa.", "NO_CHANGES")
    if evidence_document_id and not horse.documents.filter(pk=evidence_document_id).exists():
        raise BusinessRuleError("Tài liệu bằng chứng không thuộc ngựa này.", "EVIDENCE_NOT_FOUND")
    # kiểm tra giá trị mới ngay khi gửi (sai định dạng microchip, trùng hộ chiếu...) thay vì đợi lúc duyệt
    from .serializers import HorseWriteSerializer

    HorseWriteSerializer(horse, data=changes, partial=True).is_valid(raise_exception=True)

    items = []
    for column, new_value in changes.items():
        old_value = getattr(horse, COLUMN_TO_ATTR[column])
        items.append({"Field": column, "OldValue": None if old_value is None else str(old_value),
                      "NewValue": new_value})
    request = ProfileChangeRequest.objects.create(
        horse=horse, requested_by=user,
        changed_fields=json.dumps({"Reason": reason, "Changes": items}, ensure_ascii=False),
        evidence_document_id=evidence_document_id,
    )
    log_action(user, "REQUEST_PROFILE_CHANGE", horse, {"ProfileChangeRequestID": request.id})
    return request


def approve_change_request(request, user, note=None):
    from .serializers import HorseWriteSerializer

    if request.status != ProfileChangeRequest.Status.PENDING:
        raise BusinessRuleError("Yêu cầu này đã được xử lý.", "INVALID_STATUS")
    horse = request.horse
    payload = {item["Field"]: item["NewValue"] for item in json.loads(request.changed_fields)["Changes"]}
    serializer = HorseWriteSerializer(horse, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    horse.touch()
    horse.save(update_fields=["updated_at"])

    request.status = ProfileChangeRequest.Status.APPROVED
    request.reviewed_by = user
    request.reviewed_at = timezone.now()
    request.review_note = note or None
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    log_action(user, "APPROVE_PROFILE_CHANGE", horse, {"ProfileChangeRequestID": request.id, "Changes": payload})
    return request


def reject_change_request(request, user, note):
    if request.status != ProfileChangeRequest.Status.PENDING:
        raise BusinessRuleError("Yêu cầu này đã được xử lý.", "INVALID_STATUS")
    if not note:
        raise BusinessRuleError("Cần ghi lý do từ chối (ReviewNote).", "REVIEW_NOTE_REQUIRED")
    request.status = ProfileChangeRequest.Status.REJECTED
    request.reviewed_by = user
    request.reviewed_at = timezone.now()
    request.review_note = note
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    log_action(user, "REJECT_PROFILE_CHANGE", request.horse, {"ProfileChangeRequestID": request.id})
    return request


# ---------------------------------------------------------------------------
# Chuồng
# ---------------------------------------------------------------------------
def save_stall(user, values, stall=None, club_id=None):
    stall = stall or Stall(club_id=club_id)
    number = values.get("stall_number")
    if number and Stall.objects.filter(club_id=stall.club_id, stall_number__iexact=number).exclude(pk=stall.pk).exists():
        raise BusinessRuleError("Số chuồng đã tồn tại trong câu lạc bộ.", "DUPLICATE_STALL")
    if values.get("status") and stall.pk and stall.assignments.filter(status="Active").exists():
        raise BusinessRuleError("Chuồng đang có ngựa, chuyển ngựa đi trước khi đổi trạng thái.", "STALL_OCCUPIED")
    for attr, value in values.items():
        setattr(stall, attr, value)
    created = stall.pk is None
    stall.save()
    log_action(user, "CREATE_STALL" if created else "UPDATE_STALL", stall)
    return stall


def move_stall(horse, user, stall_id):
    _require_status(horse, (S.APPROVED,), "xếp chuồng")
    stall = Stall.objects.filter(pk=stall_id, club_id=horse.club_id).first()
    if stall is None:
        raise BusinessRuleError("Chuồng không tồn tại trong câu lạc bộ.", "STALL_NOT_FOUND")
    if stall.status != Stall.Status.AVAILABLE or stall.assignments.filter(status="Active").exists():
        raise BusinessRuleError("Chuồng này không còn trống.", "STALL_NOT_AVAILABLE")
    today = timezone.now().date()
    old_ids = []
    for assignment in horse.stall_assignments.filter(status="Active").select_related("stall"):
        assignment.status = StallAssignment.Status.ENDED
        assignment.end_date = max(today, assignment.start_date)
        assignment.save(update_fields=["status", "end_date"])
        assignment.stall.status = Stall.Status.AVAILABLE
        assignment.stall.save(update_fields=["status"])
        old_ids.append(assignment.stall_id)
    StallAssignment.objects.create(stall=stall, horse=horse, start_date=today)
    stall.status = Stall.Status.OCCUPIED
    stall.save(update_fields=["status"])
    log_action(user, "MOVE_STALL", horse, {"FromStallIDs": old_ids, "ToStallID": stall.id})
    return horse
