"""
GET /api/notifications - danh sách "việc cần chú ý" của người đang đăng nhập.

Database không có bảng thông báo, nên danh sách này được TÍNH từ dữ liệu hiện tại mỗi lần gọi
(không có trạng thái đã đọc). Frontend gọi khi mở trang / định kỳ để hiện chuông thông báo.

Ví dụ: Work Rider báo sự cố sức khỏe -> báo cáo vào hàng chờ của Vet, đồng thời hiện trong
thông báo của Trainer phụ trách và Head Trainer của ngựa đó (Gop_y mục 3.4).
"""
from datetime import date, timedelta

from django.db.models import Exists, OuterRef
from rest_framework.response import Response
from rest_framework.views import APIView

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


def _health_reports(user, horse_filter=None):
    from apps.medical.models import HealthReport

    reports = HealthReport.objects.filter(horse__club_id=user.club_id).exclude(status="Resolved").select_related(
        "horse", "reported_by")
    if horse_filter is not None:
        reports = reports.filter(**horse_filter)
    return [
        _item("HEALTH_REPORT", f"Báo cáo sức khỏe ({r.severity}) - {r.status}", "HealthReport", r.id, r.horse,
              r.reported_at, r.severity == "Urgent", f"{r.reported_by.full_name}: {r.description[:120]}")
        for r in reports
    ]


def build_notifications(user):
    from apps.care.models import CareTask, DietPlan, InventoryItem, InventoryRequest
    from apps.horses.models import Horse, ProfileChangeRequest
    from apps.medical.models import MedicalRecord, MedicalSchedule, Vaccination
    from apps.medical.services import signed_initial_exams
    from apps.training.models import TrainingPlan, TrainingReview, TrainingSession

    today = date.today()
    soon = today + timedelta(days=7)
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
    if "INVENTORY_MANAGE" in perms:
        for req in InventoryRequest.objects.filter(club_id=club, status="Pending").select_related("requested_by"):
            items.append(_item("INVENTORY_REQUEST", f"Yêu cầu vật tư của {req.requested_by.full_name}",
                               "InventoryRequest", req.id, at=req.request_date, message=req.reason))
        for item in InventoryItem.objects.filter(club_id=club, status__in=("Low Stock", "Out of Stock")):
            items.append(_item("LOW_STOCK", f"{item.item_name}: {item.status} ({item.quantity} {item.unit})",
                               "InventoryItem", item.id, urgent=item.status == "Out of Stock"))

    # ---------------- Vet ----------------
    if "MEDICAL_MANAGE" in perms:
        items += _health_reports(user)
        pending = Horse.objects.filter(club_id=club, registration_status="PendingExam").annotate(
            done=Exists(signed_initial_exams().filter(horse=OuterRef("pk")))).filter(done=False)
        for horse in pending:
            items.append(_item("INITIAL_EXAM", "Ngựa chờ khám đầu vào", "Horse", horse.id, horse, horse.verified_at))
        for v in Vaccination.objects.filter(horse__club_id=club, status="Scheduled",
                                            vaccination_date__lte=soon).select_related("horse"):
            items.append(_item("VACCINATION_DUE", f"Tiêm {v.vaccine_name}", "Vaccination", v.id, v.horse,
                               v.vaccination_date, v.vaccination_date < today))
        for s in MedicalSchedule.objects.filter(horse__club_id=club, status="Scheduled",
                                                scheduled_date__lte=soon).select_related("horse"):
            items.append(_item("MEDICAL_SCHEDULE", f"Lịch {s.schedule_type}", "MedicalSchedule", s.id, s.horse,
                               s.scheduled_date, s.scheduled_date < today))
        for record in MedicalRecord.objects.filter(horse__club_id=club, vet=user, record_status="Draft"):
            items.append(_item("DRAFT_RECORD", "Phiếu khám nháp chưa chốt", "MedicalRecord", record.id,
                               record.horse, record.exam_date))
        if "DIET_MANAGE" in perms:
            for plan in DietPlan.objects.filter(horse__club_id=club, status="Pending").select_related("horse"):
                items.append(_item("DIET_TO_REVIEW", "Khẩu phần chờ Vet duyệt", "DietPlan", plan.id, plan.horse,
                                   plan.created_at))

    # ---------------- Head Trainer ----------------
    if "TRAINING_PLAN_APPROVE" in perms:
        items += _health_reports(user) if "MEDICAL_MANAGE" not in perms else []
        for plan in TrainingPlan.objects.filter(assignment__horse__club_id=club, status="Pending Approval") \
                .select_related("assignment__horse", "assignment__trainer"):
            items.append(_item("PLAN_TO_APPROVE", f"Giáo án của {plan.assignment.trainer.full_name} chờ duyệt",
                               "TrainingPlan", plan.id, plan.assignment.horse, plan.submitted_at))
        for review in TrainingReview.objects.filter(
                session__stage__plan__assignment__horse__club_id=club, adjustment_required=True,
                review_date__date__gte=today - timedelta(days=14)).select_related(
                "session__stage__plan__assignment__horse"):
            items.append(_item("ADJUSTMENT_REQUIRED", "Trainer đề nghị điều chỉnh giáo án", "TrainingReview",
                               review.id, review.session.stage.plan.assignment.horse, review.review_date,
                               message=review.adjustment_note))
        for plan in DietPlan.objects.filter(horse__club_id=club, created_by=user, status="Rejected"):
            items.append(_item("DIET_RETURNED", "Khẩu phần bị Vet trả về", "DietPlan", plan.id, plan.horse,
                               plan.created_at, message=plan.vet_note))

    # ---------------- Trainer ----------------
    if "TRAINING_PLAN_MANAGE" in perms:
        items += _health_reports(user, {"horse__trainer_assignments__trainer": user,
                                        "horse__trainer_assignments__status": "Active"})
        for plan in TrainingPlan.objects.filter(assignment__trainer=user, assignment__status="Active", status="Draft",
                                                submitted_at__isnull=False).select_related("assignment__horse"):
            items.append(_item("PLAN_RETURNED", "Giáo án bị trả về", "TrainingPlan", plan.id,
                               plan.assignment.horse, plan.submitted_at, message=plan.review_note))
        for session in TrainingSession.objects.filter(
                session_date=today, status__in=("Assigned", "In Progress"),
                stage__plan__assignment__horse__club_id=club).select_related("stage__plan__assignment__horse"):
            if session.supervising_trainer_id == user.pk:
                items.append(_item("SUPERVISE_TODAY", f"Giám sát buổi tập {session.start_time:%H:%M}"
                                   + (" (Substitute)" if session.substitute_trainer_id else ""),
                                   "TrainingSession", session.id, session.horse, session.session_date))
        for session in TrainingSession.objects.filter(
                substitute_trainer=user, status="Completed", result__substitute_observation__isnull=True,
                session_date__gte=today - timedelta(days=7)).select_related("stage__plan__assignment__horse"):
            items.append(_item("SUBSTITUTE_OBSERVATION", "Cần ghi nhận xét buổi tập đã giám sát thay",
                               "TrainingSession", session.id, session.horse, session.session_date))
        for session in TrainingSession.objects.filter(
                stage__plan__assignment__trainer=user, status="Completed", reviews__isnull=True,
                session_date__gte=today - timedelta(days=7)).select_related("stage__plan__assignment__horse"):
            items.append(_item("SESSION_TO_REVIEW", "Buổi tập chờ đánh giá", "TrainingSession", session.id,
                               session.horse, session.session_date))

    # ---------------- Work Rider ----------------
    if "TRAINING_RESULT_UPDATE" in perms:
        for session in TrainingSession.objects.filter(work_rider=user, session_date=today,
                                                      status__in=("Assigned", "In Progress")).select_related(
                "stage__plan__assignment__horse"):
            items.append(_item("RIDE_TODAY", f"Buổi tập {session.start_time:%H:%M} - {session.status}",
                               "TrainingSession", session.id, session.horse, session.session_date))

    # ---------------- Groom ----------------
    if "CARE_MANAGE" in perms:
        for task in CareTask.objects.filter(groom=user, status="Pending",
                                            scheduled_at__date__lte=today).select_related("horse"):
            items.append(_item("CARE_TASK", f"{task.task_type} lúc {task.scheduled_at:%H:%M %d/%m}", "CareTask",
                               task.id, task.horse, task.scheduled_at, task.scheduled_at.date() < today))

    # ---------------- Chủ ngựa ----------------
    if "OWNER_VIEW" in perms:
        for horse in Horse.objects.filter(owner=user, registration_status="Rejected"):
            items.append(_item("HORSE_REJECTED", "Hồ sơ ngựa bị từ chối, cần sửa và gửi lại", "Horse", horse.id,
                               horse, horse.updated_at))
        for req in ProfileChangeRequest.objects.filter(horse__owner=user, status__in=("Approved", "Rejected"),
                                                       reviewed_at__date__gte=today - timedelta(days=7)):
            items.append(_item("PROFILE_CHANGE_DONE", f"Yêu cầu sửa lý lịch: {req.status}", "ProfileChangeRequest",
                               req.id, req.horse, req.reviewed_at, message=req.review_note))

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
        return Response(build_notifications(request.user))
