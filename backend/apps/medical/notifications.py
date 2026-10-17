"""Thông báo Flow 3 (gộp vào GET /api/notifications khi đã có Flow 3)."""
from datetime import date, timedelta

from apps.core import flows

from .models import HealthReport, MedicalSchedule, TrainingLock, Vaccination


def _health_reports(user, make_item, horse_filter=None):
    reports = HealthReport.objects.filter(horse__club_id=user.club_id).exclude(status="Resolved").select_related(
        "horse", "reported_by")
    if horse_filter is not None:
        reports = reports.filter(**horse_filter)
    return [
        make_item("HEALTH_REPORT", f"Báo cáo sức khỏe ({r.severity}) - {r.status}", "HealthReport", r.id, r.horse,
                  r.reported_at, r.severity == "Urgent", f"{r.reported_by.full_name}: {r.description[:120]}")
        for r in reports
    ]


def medical_items(user, make_item):
    """Vet: báo cáo sức khỏe chưa xử lý, tiêm phòng / lịch y tế 7 ngày tới. Head Trainer, Trainer: báo cáo sức khỏe."""
    perms, club, today = user.permission_codes, user.club_id, date.today()
    soon = today + timedelta(days=7)
    items = []
    if "MEDICAL_MANAGE" in perms:  # Vet
        items += _health_reports(user, make_item)
        for v in Vaccination.objects.filter(horse__club_id=club, status="Scheduled",
                                            vaccination_date__lte=soon).select_related("horse"):
            items.append(make_item("VACCINATION_DUE", f"Tiêm {v.vaccine_name}", "Vaccination", v.id, v.horse,
                                   v.vaccination_date, v.vaccination_date < today))
        for s in MedicalSchedule.objects.filter(horse__club_id=club, status="Scheduled",
                                                scheduled_date__lte=soon).select_related("horse"):
            items.append(make_item("MEDICAL_SCHEDULE", f"Lịch {s.schedule_type}", "MedicalSchedule", s.id, s.horse,
                                   s.scheduled_date, s.scheduled_date < today))
    elif "TRAINING_PLAN_APPROVE" in perms:  # Head Trainer theo dõi mọi báo cáo
        items += _health_reports(user, make_item)
    if "TRAINING_PLAN_MANAGE" in perms and flows.has_training():  # Trainer: báo cáo về ngựa mình phụ trách
        items += _health_reports(user, make_item, {"horse__trainer_assignments__trainer": user,
                                                   "horse__trainer_assignments__status": "Active"})
    if "OWNER_VIEW" in perms:  # Chủ ngựa: ngựa mình đang bị khóa tập / vừa được mở khóa (7 ngày)
        for lock in TrainingLock.objects.filter(horse__owner=user, lock_status="Active").select_related("horse"):
            items.append(make_item("OWNER_TRAINING_LOCKED", f"Ngựa tạm dừng huấn luyện ({lock.lock_level})",
                                   "TrainingLock", lock.id, lock.horse, lock.lock_start_date, True, lock.reason))
        for lock in TrainingLock.objects.filter(horse__owner=user, lock_status="Released",
                                                released_at__date__gte=today - timedelta(days=7)).select_related("horse"):
            items.append(make_item("OWNER_TRAINING_UNLOCKED", "Ngựa được tập lại", "TrainingLock", lock.id, lock.horse,
                                   lock.released_at))
    return items
