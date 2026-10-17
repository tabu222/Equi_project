"""Thông báo Flow 2 (gộp vào GET /api/notifications khi đã có Flow 2)."""
import json
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from apps.core.models import AuditLog

from .models import TrainingPlan, TrainingPlanStage, TrainingReview, TrainingSession

OWNER_DAYS = 7      # chủ ngựa thấy thông báo trong 7 ngày


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
    if "TRAINING_PLAN_MANAGE" in perms or "TRAINING_PLAN_APPROVE" in perms:  # giai đoạn hết hạn chưa chốt
        stages = TrainingPlanStage.objects.filter(
            plan__status="Active", closed_at__isnull=True, plan__assignment__horse__club_id=club).filter(
            Q(end_date__lt=today) | Q(end_date__isnull=True, plan__end_date__lt=today)).select_related(
            "plan__assignment__horse")
        if "TRAINING_PLAN_APPROVE" not in perms:
            stages = stages.filter(plan__assignment__trainer=user, plan__assignment__status="Active")
        for stage in stages:
            items.append(make_item("STAGE_TO_CLOSE", f"Giai đoạn \"{stage.stage_name}\" đã hết hạn, cần chốt tổng kết",
                                   "TrainingPlanStage", stage.id, stage.plan.assignment.horse,
                                   stage.end_date or stage.plan.end_date))
    if "OWNER_VIEW" in perms:  # Chủ ngựa
        items += owner_items(user, make_item, today)
    if "TRAINING_RESULT_UPDATE" in perms:  # Work Rider
        for session in TrainingSession.objects.filter(work_rider=user, session_date=today,
                                                      status__in=("Assigned", "In Progress")).select_related(
                "stage__plan__assignment__horse"):
            items.append(make_item("RIDE_TODAY", f"Buổi tập {session.start_time:%H:%M} - {session.status}",
                                   "TrainingSession", session.id, session.horse, session.session_date))
    return items



def owner_items(user, make_item, today):
    """Kết quả huấn luyện mới của ngựa mình: buổi mới đánh giá (gộp theo ngựa), tổng kết, giáo án mới, buổi bị dừng."""
    since = today - timedelta(days=OWNER_DAYS)
    items = []
    reviewed = defaultdict(list)
    for review in TrainingReview.objects.filter(
            session__stage__plan__assignment__horse__owner=user, review_date__date__gte=today - timedelta(days=2)) \
            .select_related("session__stage__plan__assignment__horse"):
        reviewed[review.session.horse].append(review)
    for horse, reviews in reviewed.items():
        latest = max(r.review_date for r in reviews)
        items.append(make_item("OWNER_SESSIONS_REVIEWED", f"{len(reviews)} buổi tập mới được trainer đánh giá",
                               "Horse", horse.id, horse, latest))
    stages = {st.id: st for st in TrainingPlanStage.objects.filter(
        plan__assignment__horse__owner=user, closed_at__date__gte=since).select_related("plan__assignment__horse")}
    for log in AuditLog.objects.filter(action_type="CLOSE_PLAN_STAGE", entity_name=TrainingPlanStage._meta.db_table,
                                       entity_id__in=list(stages)):
        stage = stages[log.entity_id]
        items.append(make_item("OWNER_STAGE_SUMMARY", f"Đã có tổng kết giai đoạn \"{stage.stage_name}\"",
                               "TrainingPlanStage", stage.id, stage.plan.assignment.horse, stage.closed_at,
                               message=stage.summary_note))
    plans = {p.id: p for p in TrainingPlan.objects.filter(assignment__horse__owner=user).select_related(
        "assignment__horse")}
    for plan in plans.values():
        if plan.approved_at and plan.approved_at.date() >= since:
            items.append(make_item("OWNER_PLAN_APPROVED", "Giáo án huấn luyện mới được duyệt", "TrainingPlan", plan.id,
                                   plan.assignment.horse, plan.approved_at, message=plan.goal))
    for log in AuditLog.objects.filter(action_type="COMPLETE_TRAINING_PLAN", entity_name=TrainingPlan._meta.db_table,
                                       entity_id__in=list(plans), action_time__date__gte=since):
        plan = plans[log.entity_id]
        items.append(make_item("OWNER_PLAN_SUMMARY", "Giáo án đã kết thúc, có tổng kết", "TrainingPlan", plan.id,
                               plan.assignment.horse, log.action_time, message=plan.goal))
    sessions = {s.id: s for s in TrainingSession.objects.filter(
        stage__plan__assignment__horse__owner=user, session_date__gte=since).select_related(
        "stage__plan__assignment__horse")}
    for log in AuditLog.objects.filter(action_type="STOP_TRAINING_SESSION", entity_name=TrainingSession._meta.db_table,
                                       entity_id__in=list(sessions), action_time__date__gte=since):
        session = sessions[log.entity_id]
        items.append(make_item("OWNER_SESSION_STOPPED", "Buổi tập bị dừng giữa chừng", "TrainingSession", session.id,
                               session.horse, log.action_time, urgent=True, message=_reason(log)))
    return items


def _reason(log):
    try:
        return json.loads(log.details or "{}").get("Reason")
    except (TypeError, ValueError):
        return None
