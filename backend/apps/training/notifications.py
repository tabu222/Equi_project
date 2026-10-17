"""Thông báo Flow 2 (gộp vào GET /api/notifications khi đã có Flow 2)."""
from datetime import date, timedelta

from .models import TrainingPlan, TrainingReview, TrainingSession


def training_items(user, make_item):
    """make_item = apps.core.notifications._item (cùng định dạng với thông báo Flow 1)."""
    perms, club, today = user.permission_codes, user.club_id, date.today()
    items = []
    if "TRAINING_PLAN_APPROVE" in perms:  # Head Trainer
        for plan in TrainingPlan.objects.filter(assignment__horse__club_id=club, status="Pending Approval") \
                .select_related("assignment__horse", "assignment__trainer"):
            items.append(make_item("PLAN_TO_APPROVE", f"Giáo án của {plan.assignment.trainer.full_name} chờ duyệt",
                                   "TrainingPlan", plan.id, plan.assignment.horse, plan.submitted_at))
        for review in TrainingReview.objects.filter(
                session__stage__plan__assignment__horse__club_id=club, adjustment_required=True,
                review_date__date__gte=today - timedelta(days=14)).select_related(
                "session__stage__plan__assignment__horse"):
            items.append(make_item("ADJUSTMENT_REQUIRED", "Trainer đề nghị điều chỉnh giáo án", "TrainingReview",
                                   review.id, review.session.stage.plan.assignment.horse, review.review_date,
                                   message=review.adjustment_note))
    if "TRAINING_PLAN_MANAGE" in perms:  # Trainer
        for plan in TrainingPlan.objects.filter(assignment__trainer=user, assignment__status="Active", status="Draft",
                                                submitted_at__isnull=False).select_related("assignment__horse"):
            items.append(make_item("PLAN_RETURNED", "Giáo án bị trả về", "TrainingPlan", plan.id,
                                   plan.assignment.horse, plan.submitted_at, message=plan.review_note))
        for session in TrainingSession.objects.filter(
                session_date=today, status__in=("Assigned", "In Progress"),
                stage__plan__assignment__horse__club_id=club).select_related("stage__plan__assignment__horse"):
            if session.supervising_trainer_id == user.pk:
                items.append(make_item("SUPERVISE_TODAY", f"Giám sát buổi tập {session.start_time:%H:%M}"
                                       + (" (Substitute)" if session.substitute_trainer_id else ""),
                                       "TrainingSession", session.id, session.horse, session.session_date))
        for session in TrainingSession.objects.filter(
                substitute_trainer=user, status="Completed", result__substitute_observation__isnull=True,
                session_date__gte=today - timedelta(days=7)).select_related("stage__plan__assignment__horse"):
            items.append(make_item("SUBSTITUTE_OBSERVATION", "Cần ghi nhận xét buổi tập đã giám sát thay",
                                   "TrainingSession", session.id, session.horse, session.session_date))
        for session in TrainingSession.objects.filter(
                stage__plan__assignment__trainer=user, status="Completed", reviews__isnull=True,
                session_date__gte=today - timedelta(days=7)).select_related("stage__plan__assignment__horse"):
            items.append(make_item("SESSION_TO_REVIEW", "Buổi tập chờ đánh giá", "TrainingSession", session.id,
                                   session.horse, session.session_date))
    if "TRAINING_RESULT_UPDATE" in perms:  # Work Rider
        for session in TrainingSession.objects.filter(work_rider=user, session_date=today,
                                                      status__in=("Assigned", "In Progress")).select_related(
                "stage__plan__assignment__horse"):
            items.append(make_item("RIDE_TODAY", f"Buổi tập {session.start_time:%H:%M} - {session.status}",
                                   "TrainingSession", session.id, session.horse, session.session_date))
    return items
