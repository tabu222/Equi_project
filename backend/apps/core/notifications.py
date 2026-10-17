"""
GET /api/notifications - danh sách "việc cần chú ý" của người đang đăng nhập.

Database không có bảng thông báo, nên danh sách này được TÍNH từ dữ liệu hiện tại mỗi lần gọi
(không có trạng thái đã đọc). Frontend gọi khi mở trang / định kỳ để hiện chuông thông báo.

Flow 1: hồ sơ chờ xác minh/tiếp nhận, khám đầu vào, phiếu nháp và yêu cầu sửa lý lịch.
Flow 2 (khi có apps/training): giáo án chờ duyệt / bị trả về, buổi tập hôm nay, buổi tập chờ đánh giá.
Flow 3: báo cáo sức khỏe chưa xử lý, tiêm phòng / lịch y tế sắp tới.
"""
from datetime import date, timedelta

from django.db.models import Exists, OuterRef
from rest_framework.response import Response
from rest_framework.views import APIView

from . import flows
from .i18n import is_english, translate_text
from .serializers import fmt_datetime


def _item(kind, title, entity, entity_id, horse=None, at=None, urgent=False, message=None):
    return {
        "Type": kind,
        "Priority": "High" if urgent else "Normal",
        "Title": title,
        "Message": message,
        "EntityName": entity,
        "EntityID": entity_id,
        "HorseID": horse.id if horse else None,
        "HorseName": horse.horse_name if horse else None,
        "At": fmt_datetime(at) if hasattr(at, "hour") else (at.isoformat() if at else None),
    }


def build_notifications(user):
    from apps.horses.models import Horse, ProfileChangeRequest
    from apps.medical.models import MedicalRecord
    from apps.medical.services import signed_initial_exams

    today = date.today()
    club = user.club_id
    items = []
    perms = user.permission_codes

    # ---------------- Club Manager ----------------
    if "HORSE_REGISTER_REVIEW" in perms:
        for horse in Horse.objects.filter(club_id=club, registration_status="Submitted"):
            items.append(_item("HORSE_TO_VERIFY", "Hồ sơ ngựa chờ xác minh", "Horse", horse.id, horse,
                               horse.updated_at))
        signed = signed_initial_exams().filter(horse=OuterRef("pk"))
        for horse in Horse.objects.filter(club_id=club, registration_status="PendingExam").annotate(
                done=Exists(signed)).filter(done=True):
            items.append(_item("HORSE_TO_APPROVE", "Vet đã khám đầu vào, chờ duyệt tiếp nhận", "Horse", horse.id,
                               horse, horse.updated_at))
    if "PROFILE_EDIT_APPROVE" in perms:
        for req in ProfileChangeRequest.objects.filter(horse__club_id=club, status="Pending").select_related("horse"):
            items.append(_item("PROFILE_CHANGE", "Yêu cầu sửa lý lịch chờ duyệt", "ProfileChangeRequest", req.id,
                               req.horse, req.requested_at))
    # ---------------- Vet ----------------
    if "MEDICAL_MANAGE" in perms:
        pending = Horse.objects.filter(club_id=club, registration_status="PendingExam").annotate(
            done=Exists(signed_initial_exams().filter(horse=OuterRef("pk")))).filter(done=False)
        for horse in pending:
            items.append(_item("INITIAL_EXAM", "Ngựa chờ khám đầu vào", "Horse", horse.id, horse, horse.verified_at))
        for record in MedicalRecord.objects.filter(horse__club_id=club, vet=user, record_status="Draft"):
            items.append(_item("DRAFT_RECORD", "Phiếu khám nháp chưa chốt", "MedicalRecord", record.id,
                               record.horse, record.exam_date))
    # ---------------- Chủ ngựa ----------------
    if "OWNER_VIEW" in perms:
        for horse in Horse.objects.filter(owner=user, registration_status="Rejected"):
            items.append(_item("HORSE_REJECTED", "Hồ sơ ngựa bị từ chối, cần sửa và gửi lại", "Horse", horse.id,
                               horse, horse.updated_at))
        for req in ProfileChangeRequest.objects.filter(horse__owner=user, status__in=("Approved", "Rejected"),
                                                       reviewed_at__date__gte=today - timedelta(days=7)):
            items.append(_item("PROFILE_CHANGE_DONE", f"Yêu cầu sửa lý lịch: {req.status}", "ProfileChangeRequest",
                               req.id, req.horse, req.reviewed_at, message=req.review_note))

    if flows.has_training():  # Flow 2: giáo án, buổi tập
        from apps.training.notifications import training_items
        items += training_items(user, _item)
    if flows.has_flow3():  # Flow 3: báo cáo sức khỏe, tiêm phòng, lịch y tế
        from apps.medical.notifications import medical_items
        items += medical_items(user, _item)

    # Khẩn trước, mới trước; bỏ trùng (một người có nhiều vai trò)
    unique = {(i["Type"], i["EntityID"]): i for i in items}
    return sorted(unique.values(), key=lambda i: (i["Priority"] != "High", -(_ts(i["At"]))))


def _ts(value):
    if not value:
        return 0
    digits = "".join(ch for ch in value if ch.isdigit())
    return int((digits + "0" * 14)[:14])


class NotificationView(APIView):
    def get(self, request):
        items = build_notifications(request.user)
        if is_english():  # header X-Language: en
            for item in items:
                item["Title"] = translate_text(item["Title"])
                item["Message"] = translate_text(item["Message"])
        return Response(items)
