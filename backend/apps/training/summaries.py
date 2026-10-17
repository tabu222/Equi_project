"""
Kết quả huấn luyện cho chủ ngựa (owner). Mọi số liệu TÍNH từ dữ liệu buổi tập, không lưu bảng riêng.

Chủ ngựa thấy (chỉ ngựa của mình, chỉ giáo án đã từng được duyệt):
  - Buổi tập Completed ĐÃ ĐƯỢC TRAINER ĐÁNH GIÁ: tổng quan + chi tiết (kết quả, nhận xét trainer).
  - Buổi Cancelled / Missed đã tới ngày: kèm lý do (lấy từ AuditLog), không có số liệu.
  - Không thấy: buổi chưa tập / đang tập / chưa đánh giá, nhận xét của Substitute Trainer.
Tổng kết theo GIAI ĐOẠN của giáo án (trainer chốt giai đoạn) và theo CẢ GIÁO ÁN:
  số buổi, quãng đường so với mục tiêu, tốc độ / điểm trung bình (so với giai đoạn trước),
  số lượng từng loại đánh giá, sức khỏe trong kỳ (khi có Flow 3), nhận xét của trainer.
  Số liệu kết quả chỉ tính trên buổi đã được trainer đánh giá (giống những gì chủ ngựa nhìn thấy).
"""
import json
from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.core import flows
from apps.core.models import AuditLog
from apps.core.serializers import fmt_datetime

from .models import TrainingPlan, TrainingSession

S = TrainingSession.Status
EVALUATIONS = ["Excellent", "Good", "Average", "Needs Improvement"]
END_ACTIONS = ("STOP_TRAINING_SESSION", "CANCEL_TRAINING_SESSION", "MISS_TRAINING_SESSION")
SESSION_RELATED = ("stage__plan__assignment__horse", "stage__plan__assignment__trainer", "work_rider", "result")


# ---------------------------------------------------------------------------
# Buổi tập chủ ngựa được xem
# ---------------------------------------------------------------------------
def owner_plans(horse):
    """Giáo án đã từng được duyệt (Active / Completed / Cancelled sau khi chạy). Bản nháp, chờ duyệt thì không."""
    return (TrainingPlan.objects.filter(assignment__horse=horse, approved_at__isnull=False)
            .select_related("assignment__trainer", "assignment__specialization").prefetch_related("stages")
            .order_by("-start_date", "-id"))


def visible_sessions(queryset, today=None):
    today = today or date.today()
    return (queryset.filter(Q(status=S.COMPLETED, reviews__isnull=False)
                            | Q(status__in=(S.CANCELLED, S.MISSED), session_date__lte=today))
            .filter(stage__plan__approved_at__isnull=False)
            .select_related(*SESSION_RELATED).prefetch_related("reviews__trainer").distinct()
            .order_by("-session_date", "-start_time", "-id"))


def end_reasons(session_ids):
    """{TrainingSessionID: (ActionType, Reason)} của lần dừng / hủy / đánh vắng gần nhất."""
    found = {}
    logs = AuditLog.objects.filter(entity_name=TrainingSession._meta.db_table, entity_id__in=list(session_ids),
                                   action_type__in=END_ACTIONS).order_by("action_time", "id")
    for log in logs:
        try:
            reason = json.loads(log.details or "{}").get("Reason")
        except (TypeError, ValueError):
            reason = None
        found[log.entity_id] = (log.action_type, reason)
    return found


def _num(value):
    return float(value) if value is not None else None


def _review(session):
    reviews = list(session.reviews.all())
    return reviews[0] if reviews else None


def _result(session):
    try:
        return session.result
    except ObjectDoesNotExist:  # buổi hủy / vắng không có kết quả
        return None


def session_overview(session, reasons):
    review, result = _review(session), _result(session)
    action, reason = reasons.get(session.id, (None, None))
    has_numbers = session.status == S.COMPLETED and result is not None
    return {
        "TrainingSessionID": session.id,
        "SessionDate": session.session_date,
        "StartTime": session.start_time,
        "TrainingType": session.training_type,
        "TrainingPlanID": session.stage.plan_id,
        "TrainingPlanStageID": session.stage_id,
        "StageName": session.stage.stage_name,
        "Status": session.status,
        "DurationMinutes": result.actual_duration_minutes if has_numbers else None,
        "DistanceKm": _num(result.actual_distance_km) if has_numbers else None,
        "PerformanceScore": _num(result.performance_score) if has_numbers else None,
        "Evaluation": review.evaluation if review else None,
        "IsStopped": action == "STOP_TRAINING_SESSION",
        "Reason": reason if session.status != S.COMPLETED else None,
    }


def session_detail(session, reasons):
    body = session_overview(session, reasons)
    review, result = _review(session), _result(session)
    has_numbers = session.status == S.COMPLETED and result is not None
    body.update({
        "HorseID": session.horse.id,
        "HorseName": session.horse.horse_name,
        "TrainerName": session.assignment.trainer.full_name,
        "WorkRiderName": session.work_rider.full_name,
        "Surface": session.surface,
        "Location": session.location,
        "DurationPlannedMinutes": session.duration_planned_minutes,
        "DistancePlannedKm": _num(session.distance_planned_km),
        "TargetSpeedKmh": _num(session.target_speed_kmh),
        "AvgSpeedKmh": _num(result.avg_speed_kmh) if has_numbers else None,
        "MaxSpeedKmh": _num(result.max_speed_kmh) if has_numbers else None,
        "AvgHeartRate": result.avg_heart_rate if has_numbers else None,
        "MaxHeartRate": result.max_heart_rate if has_numbers else None,
        "RecoveryMinutes": result.recovery_minutes if has_numbers else None,
        "RiderObservation": result.rider_observation if has_numbers else None,
        "VideoUrl": result.video_url if has_numbers else None,
        "TrainerComment": review.trainer_comment if review else None,
        "AdjustmentRequired": review.adjustment_required if review else False,
        "AdjustmentNote": review.adjustment_note if review else None,
        "ReviewedBy": review.trainer.full_name if review else None,
        "ReviewDate": fmt_datetime(review.review_date) if review else None,
    })
    return body


# ---------------------------------------------------------------------------
# Tổng kết một khoảng (giai đoạn / cả giáo án)
# ---------------------------------------------------------------------------
def _avg(values, digits=1):
    values = [float(v) for v in values if v is not None]
    return round(sum(values) / len(values), digits) if values else None


def _health(horse, start, end):
    """Sức khỏe trong kỳ (Flow 3): số lần khóa tập, số báo cáo sức khỏe. Chưa có Flow 3 -> None."""
    if not flows.has_flow3():
        return None
    from apps.medical.models import HealthReport, TrainingLock

    locks = TrainingLock.objects.filter(horse=horse, lock_start_date__date__lte=end).filter(
        Q(lock_end_date__isnull=True) | Q(lock_end_date__date__gte=start))
    reports = HealthReport.objects.filter(horse=horse, reported_at__date__gte=start, reported_at__date__lte=end)
    lock_count, report_count = locks.count(), reports.count()
    return {
        "TrainingLockCount": lock_count,
        "HealthReportCount": report_count,
        "UrgentHealthReportCount": reports.filter(severity="Urgent").count(),
        "IsLockedNow": TrainingLock.objects.filter(horse=horse, lock_status="Active").exists(),
        "Text": "Bình thường" if not (lock_count or report_count)
        else f"{lock_count} lần khóa tập, {report_count} báo cáo sức khỏe",
    }


def period_summary(sessions, horse, start, end, distance_target=None):
    """sessions: mọi buổi tập của kỳ (queryset). end: ngày cuối kỳ (hoặc hôm nay nếu kỳ chưa xong)."""
    rows = list(sessions.select_related("result").prefetch_related("reviews"))
    reviewed = [s for s in rows if s.status == S.COMPLETED and _review(s) is not None]
    results = [r for r in (_result(s) for s in reviewed) if r is not None]
    distance = round(sum(float(r.actual_distance_km or 0) for r in results), 2)
    target = float(distance_target) if distance_target else None
    evaluations = {name: 0 for name in EVALUATIONS}
    for s in reviewed:
        evaluations[_review(s).evaluation] = evaluations.get(_review(s).evaluation, 0) + 1
    count = {status: sum(1 for s in rows if s.status == status) for status in S.values}
    return {
        "From": start,
        "To": end,
        "PlannedSessions": len(rows),
        "CompletedSessions": count[S.COMPLETED],
        "ReviewedSessions": len(reviewed),
        "AwaitingReviewSessions": count[S.COMPLETED] - len(reviewed),
        "CancelledSessions": count[S.CANCELLED],
        "MissedSessions": count[S.MISSED],
        "UpcomingSessions": count[S.ASSIGNED] + count[S.IN_PROGRESS],
        "TotalDistanceKm": distance,
        "DistanceTargetKm": target,
        "DistanceProgressPercent": round(distance * 100 / target, 1) if target else None,
        "TotalDurationMinutes": sum(r.actual_duration_minutes or 0 for r in results),
        "AvgDistancePerSessionKm": round(distance / len(results), 2) if results else None,
        "AvgSpeedKmh": _avg(r.avg_speed_kmh for r in results),
        "MaxSpeedKmh": max((float(r.max_speed_kmh) for r in results if r.max_speed_kmh is not None), default=None),
        "AvgPerformanceScore": _avg(r.performance_score for r in results),
        "AvgHeartRate": _avg((r.avg_heart_rate for r in results), 0),
        "AvgRecoveryMinutes": _avg(r.recovery_minutes for r in results),
        "Evaluations": evaluations,
        "Health": _health(horse, start, end),
    }


COMPARED_KEYS = ("AvgSpeedKmh", "AvgPerformanceScore", "AvgDistancePerSessionKm", "AvgRecoveryMinutes")


def compare(current, previous):
    """Chênh lệch so với kỳ trước (dương = tăng). Thiếu số liệu thì None."""
    if previous is None:
        return None
    return {key: (round(current[key] - previous[key], 2)
                  if current.get(key) is not None and previous.get(key) is not None else None)
            for key in COMPARED_KEYS}


def stage_state(stage, today=None):
    today = today or date.today()
    if stage.closed_at is not None:
        return "Closed"
    if stage.start_date > today:
        return "NotStarted"
    return "InProgress"


def stage_end(stage):
    return stage.end_date or stage.plan.end_date


def stage_summary(stage, previous_summary=None, today=None):
    today = today or date.today()
    state = stage_state(stage, today)
    end = stage_end(stage)
    if state == "Closed":   # chốt sớm thì tính đến ngày chốt
        end = min(end, stage.closed_at.date()) if end else stage.closed_at.date()
    else:
        end = min(end, today) if end else today
    summary = None
    if state != "NotStarted":
        summary = period_summary(stage.sessions.all(), stage.plan.assignment.horse, stage.start_date, end,
                                 stage.distance_target_km)
    planned_end = stage_end(stage)
    return {
        "TrainingPlanStageID": stage.id,
        "StageOrder": stage.stage_order,
        "StageName": stage.stage_name,
        "Goal": stage.goal,
        "StartDate": stage.start_date,
        "EndDate": stage.end_date,
        "Intensity": stage.intensity,
        "StageState": state,
        "IsOverdue": state == "InProgress" and planned_end is not None and planned_end < today,
        "AsOf": None if state != "InProgress" else today,
        "ClosedAt": fmt_datetime(stage.closed_at),
        "ClosedByName": stage.closed_by.full_name if stage.closed_by_id else None,
        "SummaryNote": stage.summary_note,
        "Summary": summary,
        "ComparedToPreviousStage": compare(summary, previous_summary) if summary else None,
    }


def plan_progress(plan, today=None):
    """% thời gian giáo án đã đi qua (không có ngày kết thúc -> None)."""
    today = today or date.today()
    if plan.status == TrainingPlan.Status.COMPLETED:
        return 100.0
    if not plan.end_date or plan.end_date <= plan.start_date:
        return None
    done = (min(today, plan.end_date) - plan.start_date).days
    return round(max(0, done) * 100 / (plan.end_date - plan.start_date).days, 1)


def plan_header(plan, today=None):
    today = today or date.today()
    current = next((s for s in plan.stages.all() if stage_state(s, today) == "InProgress"), None)
    return {
        "TrainingPlanID": plan.id,
        "Goal": plan.goal,
        "StartDate": plan.start_date,
        "EndDate": plan.end_date,
        "Status": plan.status,
        "TrainerName": plan.assignment.trainer.full_name,
        "SpecializationName": plan.assignment.specialization.name,
        "ApprovedAt": fmt_datetime(plan.approved_at),
        "ProgressPercent": plan_progress(plan, today),
        "StageCount": len(plan.stages.all()),
        "CurrentStageName": current.stage_name if current else None,
    }


def plan_summary(plan, today=None):
    """Toàn bộ giáo án: tổng kết chung + từng giai đoạn (so với giai đoạn trước)."""
    today = today or date.today()
    horse = plan.assignment.horse
    end = min(plan.end_date, today) if plan.end_date else today
    sessions = TrainingSession.objects.filter(stage__plan=plan)
    target = sum(float(s.distance_target_km) for s in plan.stages.all() if s.distance_target_km) or None
    stages, previous = [], None
    for stage in plan.stages.all():
        row = stage_summary(stage, previous, today)
        stages.append(row)
        if row["Summary"] is not None:
            previous = row["Summary"]
    return {**plan_header(plan, today),
            "Summary": period_summary(sessions, horse, plan.start_date, max(end, plan.start_date), target),
            "Stages": stages}
