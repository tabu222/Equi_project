"""
Luật nghiệp vụ Flow 2 - huấn luyện.

Giáo án:   Draft ──submit──> Pending Approval ──approve──> Active ──complete──> Completed
             ^                     │ return (kèm ReviewNote)
             └─────────────────────┘
           Draft / Pending Approval / Active ──cancel──> Cancelled
           Điều chỉnh giáo án đang Active: tạo bản mới (revise) -> duyệt -> bản cũ tự chuyển Completed.

Buổi tập:  Assigned ──start (Work Rider)──> In Progress ──result (Work Rider)──> Completed
           Assigned / In Progress ──stop (trainer đang giám sát) / cancel──> Cancelled
           Assigned / In Progress ──missed──> Missed
           Xếp / sửa / hủy / đánh vắng: Head Trainer cho mọi ngựa, Trainer cho ngựa mình đang phụ trách.

Giai đoạn: trainer phụ trách (hoặc Head Trainer) "chốt" giai đoạn kèm nhận xét -> tổng kết gửi chủ ngựa.

Training Lock (Flow 3) chặn buổi tập giống trigger SQL Server:
  Full -> không xếp / bắt đầu buổi tập; Restricted -> TrainingLoad phải có và <= MaxIntensity.
"""
from datetime import date

from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core import flows
from apps.core.audit import log_action
from apps.core.exceptions import TRIGGER_MESSAGES, BusinessRuleError
from apps.core.permissions import require_club_user
from apps.horses.models import Horse

from . import owner_emails
from .models import (
    HorseAssessment, HorseWorkRiderPreference, TrainerCredential, TrainerHorseAssignment, TrainerProfile,
    TrainerRaceResult, TrainerSpecialization, TrainingPlan, TrainingPlanStage, TrainingResult, TrainingReview,
    TrainingSession,
)

P = TrainingPlan.Status
S = TrainingSession.Status
OPEN_PLAN_STATUSES = (P.DRAFT, P.PENDING_APPROVAL, P.ACTIVE)
SUPERVISOR_ROLES = ("TRAINER", "HEAD_TRAINER")


# ---------------------------------------------------------------------------
# Kiểm tra chung
# ---------------------------------------------------------------------------
def ensure_horse_in_training(horse):
    if horse.registration_status != Horse.RegistrationStatus.APPROVED:
        raise BusinessRuleError("Chỉ ngựa đã được tiếp nhận (Approved) mới đưa vào huấn luyện.", "HORSE_NOT_APPROVED")


def active_assignment(horse):
    return horse.trainer_assignments.filter(status=TrainerHorseAssignment.Status.ACTIVE).select_related(
        "trainer", "specialization").first()


def active_lock(horse):
    """Training Lock đang hiệu lực (Flow 3). Chưa có Flow 3 thì không có lock nào -> None."""
    if not flows.has_flow3():
        return None
    from apps.medical.models import TrainingLock

    return TrainingLock.objects.filter(horse=horse, lock_status=TrainingLock.Status.ACTIVE).first()


def check_session_lock(horse, session_date, training_load):
    """Giống TRG_TrainingSession_BlockLockedHorse (chỉ áp cho buổi Assigned / In Progress)."""
    lock = active_lock(horse)
    if lock is None or not lock.covers(session_date):
        return
    if lock.lock_level == "Full":
        raise BusinessRuleError(TRIGGER_MESSAGES["51002"], "TRAINING_LOCK_FULL")
    if lock.max_intensity is not None and (training_load is None or training_load > lock.max_intensity):
        raise BusinessRuleError(
            f"Ngựa đang bị hạn chế tập: buổi tập phải ghi TrainingLoad và không vượt {lock.max_intensity}.",
            "TRAINING_LOCK_RESTRICTED",
        )


def check_plan_lock(plan):
    """Giống TRG_TrainingPlan_BlockLockedHorse: không kích hoạt giáo án khi ngựa đang bị khóa Full."""
    lock = active_lock(plan.assignment.horse)
    if lock is None or lock.lock_level != "Full":
        return
    lock_end = lock.lock_end_date.date() if lock.lock_end_date else date.max
    plan_end = plan.end_date or date.max
    if plan.start_date <= lock_end and plan_end >= lock.lock_start_date.date():
        raise BusinessRuleError(TRIGGER_MESSAGES["51001"], "TRAINING_LOCK_FULL")


def can_manage_sessions(user, assignment) -> bool:
    """Head Trainer (người duyệt giáo án) xếp buổi tập cho mọi ngựa; Trainer chỉ cho ngựa mình đang phụ trách."""
    if user.has_perm("TRAINING_PLAN_APPROVE"):
        return True
    return (user.has_perm("TRAINING_SESSION_ASSIGN") and assignment.trainer_id == user.pk
            and assignment.status == TrainerHorseAssignment.Status.ACTIVE)


def ensure_session_manager(user, assignment):
    if not can_manage_sessions(user, assignment):
        raise PermissionDenied("Bạn chỉ xếp / sửa buổi tập của ngựa mình đang phụ trách.")


def cancel_sessions(queryset, user, reason):
    ids = list(queryset.values_list("id", flat=True))
    if ids:
        TrainingSession.objects.filter(id__in=ids).update(status=S.CANCELLED)
        for session in TrainingSession.objects.filter(id__in=ids):
            log_action(user, "CANCEL_TRAINING_SESSION", session, {"Reason": reason})
    return ids


def sessions_of_horse(horse):
    return TrainingSession.objects.filter(stage__plan__assignment__horse=horse)


# ---------------------------------------------------------------------------
# Chuyên môn của Trainer
# ---------------------------------------------------------------------------
def add_trainer_specialization(trainer, specialization, user):
    if TrainerSpecialization.objects.filter(trainer=trainer, specialization=specialization).exists():
        raise BusinessRuleError("Trainer đã có chuyên môn này.", "ALREADY_EXISTS")
    link = TrainerSpecialization.objects.create(trainer=trainer, specialization=specialization)
    log_action(user, "ADD_TRAINER_SPECIALIZATION", trainer, {"SpecializationID": specialization.id})
    return link


def update_trainer_profile(trainer, user, values):
    """Tạo / sửa hồ sơ trainer (ngày bắt đầu làm nghề, điểm đánh giá)."""
    profile = TrainerProfile.objects.filter(trainer=trainer).first() or TrainerProfile(trainer=trainer)
    for attr, value in values.items():
        setattr(profile, attr, value)
    profile.updated_at = timezone.now()
    profile.updated_by = user
    profile.save()
    log_action(user, "UPDATE_TRAINER_PROFILE", trainer, {
        "CareerStartDate": profile.career_start_date.isoformat() if profile.career_start_date else None,
        "TrainerRating": str(profile.trainer_rating) if profile.trainer_rating is not None else None,
    })
    return profile


def add_trainer_credential(trainer, user, values):
    credential = TrainerCredential.objects.create(trainer=trainer, created_by=user, created_at=timezone.now(),
                                                  **values)
    log_action(user, "ADD_TRAINER_CREDENTIAL", trainer, {
        "CredentialID": credential.id, "CredentialType": credential.credential_type, "Title": credential.title,
    })
    return credential


def delete_trainer_credential(credential, user):
    log_action(user, "DELETE_TRAINER_CREDENTIAL", credential.trainer, {
        "CredentialID": credential.id, "Title": credential.title,
    })
    credential.delete()


def add_race_result(trainer, user, values):
    """Ghi 1 lần ngựa của trainer ra đường đua. Ngựa trong CLB thì lấy tên ngựa từ hồ sơ."""
    horse = values.get("horse")
    if horse is not None:
        if horse.club_id != trainer.club_id:
            raise ValidationError({"HorseID": ["Ngựa không thuộc CLB của trainer."]})
        values["horse_name"] = horse.horse_name
    values["horse_name"] = values["horse_name"].strip()
    result = TrainerRaceResult.objects.create(trainer=trainer, created_by=user, created_at=timezone.now(), **values)
    log_action(user, "ADD_TRAINER_RACE_RESULT", trainer, {
        "RaceResultID": result.id, "RaceDate": result.race_date.isoformat(), "FinishPosition": result.finish_position,
    })
    return result


def delete_race_result(result, user):
    log_action(user, "DELETE_TRAINER_RACE_RESULT", result.trainer, {"RaceResultID": result.id})
    result.delete()


def remove_trainer_specialization(trainer, specialization, user):
    link = TrainerSpecialization.objects.filter(trainer=trainer, specialization=specialization).first()
    if link is None:
        raise BusinessRuleError("Trainer không có chuyên môn này.", "NOT_FOUND")
    if TrainerHorseAssignment.objects.filter(trainer=trainer, specialization=specialization).exists():
        raise BusinessRuleError("Chuyên môn này đã được dùng trong phân công ngựa nên không xóa được.", "IN_USE")
    TrainerSpecialization.objects.filter(trainer=trainer, specialization=specialization).delete()
    log_action(user, "REMOVE_TRAINER_SPECIALIZATION", trainer, {"SpecializationID": specialization.id})


# ---------------------------------------------------------------------------
# Đánh giá ngựa, phân công Trainer
# ---------------------------------------------------------------------------
def create_assessment(horse, user, values):
    ensure_horse_in_training(horse)
    if values.get("decision_status", HorseAssessment.Decision.RECOMMENDED) == HorseAssessment.Decision.SUPERSEDED:
        raise ValidationError({"DecisionStatus": ["Chỉ chọn Recommended hoặc Rejected."]})
    if values.get("decision_status", HorseAssessment.Decision.RECOMMENDED) == HorseAssessment.Decision.RECOMMENDED:
        # Đánh giá mới thay cho đánh giá Recommended cũ cùng chuyên môn
        horse.assessments.filter(decision_status=HorseAssessment.Decision.RECOMMENDED,
                                 specialization=values["specialization"]).update(
            decision_status=HorseAssessment.Decision.SUPERSEDED)
    assessment = HorseAssessment.objects.create(horse=horse, head_trainer=user, assessment_date=timezone.now(),
                                                **values)
    log_action(user, "ASSESS_HORSE", horse, {"AssessmentID": assessment.id})
    return assessment


def assign_trainer(horse, user, trainer_id, specialization, assessment=None, start_date=None, note=None):
    ensure_horse_in_training(horse)
    trainer = require_club_user(trainer_id, horse.club_id, "TRAINER", field="TrainerID")
    if active_assignment(horse) is not None:
        raise BusinessRuleError("Ngựa đã có trainer phụ trách. Kết thúc phân công cũ trước khi giao trainer mới.",
                                "ALREADY_ASSIGNED")
    if not TrainerSpecialization.objects.filter(trainer=trainer, specialization=specialization).exists():
        raise BusinessRuleError("Trainer chưa có chuyên môn này (TrainerSpecialization).", "SPECIALIZATION_MISMATCH")
    if assessment is not None and assessment.horse_id != horse.pk:
        raise ValidationError({"AssessmentID": ["Phiếu đánh giá không thuộc ngựa này."]})
    assignment = TrainerHorseAssignment.objects.create(
        horse=horse, trainer=trainer, specialization=specialization, assigned_by=user, assessment=assessment,
        start_date=start_date or date.today(), assignment_note=note or None,
    )
    log_action(user, "ASSIGN_TRAINER", horse, {"TrainerHorseAssignmentID": assignment.id, "TrainerID": trainer.id})
    return assignment


def end_assignment(assignment, user, reason=None):
    """
    Kết thúc phân công: giáo án chưa xong -> Cancelled, buổi tập chưa diễn ra (Assigned) -> Cancelled.
    Trainer mới phải soạn giáo án mới.
    """
    if assignment.status != TrainerHorseAssignment.Status.ACTIVE:
        raise BusinessRuleError("Phân công này đã kết thúc.", "INVALID_STATUS")
    today = date.today()
    cancelled = cancel_sessions(
        TrainingSession.objects.filter(stage__plan__assignment=assignment, status=S.ASSIGNED),
        user, "Kết thúc phân công trainer",
    )
    assignment.plans.filter(status__in=OPEN_PLAN_STATUSES).update(status=P.CANCELLED)
    assignment.status = TrainerHorseAssignment.Status.ENDED
    assignment.end_date = max(today, assignment.start_date)
    if reason:
        assignment.assignment_note = ((assignment.assignment_note or "") + f"\n[Kết thúc] {reason}").strip()[:1000]
    assignment.save(update_fields=["status", "end_date", "assignment_note"])
    log_action(user, "END_TRAINER_ASSIGNMENT", assignment.horse,
               {"TrainerHorseAssignmentID": assignment.id, "Reason": reason, "CancelledSessionIDs": cancelled})
    return assignment


def add_work_rider_preference(horse, user, work_rider_id, priority=1, note=None, start_date=None):
    ensure_horse_in_training(horse)
    rider = require_club_user(work_rider_id, horse.club_id, "WORK_RIDER", field="WorkRiderID")
    if horse.work_rider_preferences.filter(work_rider=rider, end_date__isnull=True).exists():
        raise BusinessRuleError("Work Rider này đã nằm trong danh sách ưu tiên của ngựa.", "ALREADY_EXISTS")
    preference = HorseWorkRiderPreference.objects.create(
        horse=horse, work_rider=rider, assigned_by=user, start_date=start_date or date.today(),
        priority=priority, note=note or None,
    )
    log_action(user, "ADD_WORK_RIDER_PREFERENCE", horse, {"PreferenceID": preference.id})
    return preference


def end_work_rider_preference(preference, user):
    if preference.end_date is not None:
        raise BusinessRuleError("Ưu tiên này đã kết thúc.", "INVALID_STATUS")
    preference.end_date = max(date.today(), preference.start_date)
    preference.is_preferred = False
    preference.save(update_fields=["end_date", "is_preferred"])
    log_action(user, "END_WORK_RIDER_PREFERENCE", preference.horse, {"PreferenceID": preference.id})
    return preference


# ---------------------------------------------------------------------------
# Giáo án
# ---------------------------------------------------------------------------
def ensure_plan_owner(plan, user):
    if plan.assignment.trainer_id != user.pk or plan.assignment.status != TrainerHorseAssignment.Status.ACTIVE:
        raise BusinessRuleError("Chỉ trainer đang phụ trách ngựa mới được soạn / sửa giáo án này.", "NOT_PLAN_OWNER")


def ensure_plan_editable(plan, user):
    ensure_plan_owner(plan, user)
    if plan.status != P.DRAFT:
        raise BusinessRuleError("Chỉ sửa được giáo án ở trạng thái Draft.", "INVALID_STATUS")


def validate_stage_dates(plan, start_date, end_date):
    if end_date and end_date < start_date:
        raise ValidationError({"EndDate": ["Ngày kết thúc phải sau ngày bắt đầu."]})
    if start_date < plan.start_date or (plan.end_date and (end_date or start_date) > plan.end_date):
        raise ValidationError({"StartDate": ["Giai đoạn phải nằm trong thời gian của giáo án."]})


def create_plan(horse, user, values, stages):
    ensure_horse_in_training(horse)
    assignment = active_assignment(horse)
    if assignment is None or assignment.trainer_id != user.pk:
        raise BusinessRuleError("Chỉ trainer đang phụ trách ngựa mới được soạn giáo án.", "NOT_PLAN_OWNER")
    if values.get("end_date") and values["end_date"] < values["start_date"]:
        raise ValidationError({"EndDate": ["Ngày kết thúc phải sau ngày bắt đầu."]})
    plan = TrainingPlan.objects.create(assignment=assignment, created_at=timezone.now(), **values)
    for order, stage in enumerate(stages, start=1):
        add_stage(plan, user, {**stage, "stage_order": stage.get("stage_order") or order}, log=False)
    log_action(user, "CREATE_TRAINING_PLAN", plan, {"HorseID": horse.pk})
    return plan


def update_plan(plan, user, values):
    ensure_plan_editable(plan, user)
    for attr, value in values.items():
        setattr(plan, attr, value)
    if plan.end_date and plan.end_date < plan.start_date:
        raise ValidationError({"EndDate": ["Ngày kết thúc phải sau ngày bắt đầu."]})
    for stage in plan.stages.all():
        validate_stage_dates(plan, stage.start_date, stage.end_date)
    plan.save()
    log_action(user, "UPDATE_TRAINING_PLAN", plan)
    return plan


def add_stage(plan, user, values, log=True):
    ensure_plan_editable(plan, user)
    validate_stage_dates(plan, values["start_date"], values.get("end_date"))
    if not values.get("stage_order"):
        values["stage_order"] = (plan.stages.aggregate(m=Max("stage_order"))["m"] or 0) + 1
    if plan.stages.filter(stage_order=values["stage_order"]).exists():
        raise ValidationError({"StageOrder": ["Thứ tự giai đoạn bị trùng trong giáo án."]})
    stage = TrainingPlanStage.objects.create(plan=plan, **values)
    if log:
        log_action(user, "ADD_PLAN_STAGE", plan, {"TrainingPlanStageID": stage.id})
    return stage


def update_stage(stage, user, values):
    ensure_plan_editable(stage.plan, user)
    for attr, value in values.items():
        setattr(stage, attr, value)
    validate_stage_dates(stage.plan, stage.start_date, stage.end_date)
    if stage.plan.stages.filter(stage_order=stage.stage_order).exclude(pk=stage.pk).exists():
        raise ValidationError({"StageOrder": ["Thứ tự giai đoạn bị trùng trong giáo án."]})
    stage.save()
    log_action(user, "UPDATE_PLAN_STAGE", stage.plan, {"TrainingPlanStageID": stage.id})
    return stage


def delete_stage(stage, user):
    ensure_plan_editable(stage.plan, user)
    if stage.sessions.exists():
        raise BusinessRuleError("Giai đoạn đã có buổi tập nên không xóa được.", "IN_USE")
    plan = stage.plan
    stage_id = stage.id
    stage.delete()
    log_action(user, "DELETE_PLAN_STAGE", plan, {"TrainingPlanStageID": stage_id})


def submit_plan(plan, user):
    ensure_plan_editable(plan, user)
    if not plan.stages.exists():
        raise BusinessRuleError("Giáo án cần ít nhất một giai đoạn trước khi gửi duyệt.", "NO_STAGES")
    plan.status = P.PENDING_APPROVAL
    plan.submitted_at = timezone.now()
    plan.save(update_fields=["status", "submitted_at"])
    log_action(user, "SUBMIT_TRAINING_PLAN", plan)
    return plan


def ensure_pending(plan):
    if plan.status != P.PENDING_APPROVAL:
        raise BusinessRuleError("Giáo án không ở trạng thái chờ duyệt.", "INVALID_STATUS")
    if plan.assignment.status != TrainerHorseAssignment.Status.ACTIVE:
        raise BusinessRuleError("Phân công trainer của giáo án này đã kết thúc.", "ASSIGNMENT_ENDED")


def approve_plan(plan, user, note=None):
    """Head Trainer duyệt -> Active. Giáo án Active cũ của cùng phân công (bản trước khi điều chỉnh) -> Completed."""
    ensure_pending(plan)
    check_plan_lock(plan)
    now = timezone.now()
    replaced = []
    for old in plan.assignment.plans.filter(status=P.ACTIVE).exclude(pk=plan.pk):
        cancel_sessions(TrainingSession.objects.filter(stage__plan=old, status=S.ASSIGNED), user,
                        f"Giáo án #{old.id} được thay bằng giáo án #{plan.id}")
        old.status = P.COMPLETED
        old.save(update_fields=["status"])
        replaced.append(old.id)
    plan.status = P.ACTIVE
    plan.approved_by = user
    plan.approved_at = now
    plan.review_note = note or plan.review_note
    plan.save(update_fields=["status", "approved_by", "approved_at", "review_note"])
    log_action(user, "APPROVE_TRAINING_PLAN", plan, {"ReplacedPlanIDs": replaced})
    owner_emails.plan_approved(plan)
    return plan


def return_plan(plan, user, note):
    ensure_pending(plan)
    if not note:
        raise BusinessRuleError("Cần ghi lý do trả về (ReviewNote).", "REVIEW_NOTE_REQUIRED")
    plan.status = P.DRAFT
    plan.review_note = note
    plan.save(update_fields=["status", "review_note"])
    log_action(user, "RETURN_TRAINING_PLAN", plan, {"ReviewNote": note})
    return plan


def complete_plan(plan, user):
    if plan.status != P.ACTIVE:
        raise BusinessRuleError("Chỉ kết thúc được giáo án đang Active.", "INVALID_STATUS")
    cancelled = cancel_sessions(TrainingSession.objects.filter(stage__plan=plan, status=S.ASSIGNED), user,
                                f"Kết thúc giáo án #{plan.id}")
    plan.status = P.COMPLETED
    plan.save(update_fields=["status"])
    # Giai đoạn đã bắt đầu mà chưa chốt thì chốt luôn cùng giáo án (không gửi tổng kết riêng từng giai đoạn)
    plan.stages.filter(closed_at__isnull=True, start_date__lte=date.today()).update(
        closed_at=timezone.now(), closed_by=user)
    log_action(user, "COMPLETE_TRAINING_PLAN", plan, {"CancelledSessionIDs": cancelled})
    owner_emails.plan_completed(plan)
    return plan


def cancel_plan(plan, user, reason=None):
    if plan.status not in OPEN_PLAN_STATUSES:
        raise BusinessRuleError("Giáo án đã kết thúc hoặc đã hủy.", "INVALID_STATUS")
    cancelled = cancel_sessions(TrainingSession.objects.filter(stage__plan=plan, status=S.ASSIGNED), user,
                                f"Hủy giáo án #{plan.id}")
    plan.status = P.CANCELLED
    if reason:
        plan.review_note = reason[:1000]
    plan.save(update_fields=["status", "review_note"])
    log_action(user, "CANCEL_TRAINING_PLAN", plan, {"Reason": reason, "CancelledSessionIDs": cancelled})
    return plan


def revise_plan(plan, user):
    """Điều chỉnh giáo án (sau đánh giá buổi tập): chép thành bản Draft mới để sửa rồi gửi duyệt lại."""
    ensure_plan_owner(plan, user)
    if plan.status not in (P.ACTIVE, P.COMPLETED):
        raise BusinessRuleError("Chỉ tạo bản điều chỉnh từ giáo án Active hoặc Completed.", "INVALID_STATUS")
    if plan.assignment.plans.filter(status__in=(P.DRAFT, P.PENDING_APPROVAL)).exists():
        raise BusinessRuleError("Đã có một bản giáo án đang soạn / chờ duyệt cho ngựa này.", "DRAFT_EXISTS")
    copy = TrainingPlan.objects.create(
        assignment=plan.assignment, goal=plan.goal, start_date=max(plan.start_date, date.today()),
        end_date=plan.end_date if not plan.end_date or plan.end_date >= date.today() else None,
        overall_intensity=plan.overall_intensity, note=f"Điều chỉnh từ giáo án #{plan.id}",
        created_at=timezone.now(),
    )
    for stage in plan.stages.all():
        end = stage.end_date
        if end and end < copy.start_date:
            continue  # giai đoạn đã qua thì không chép
        TrainingPlanStage.objects.create(
            plan=copy, stage_name=stage.stage_name, stage_order=stage.stage_order, goal=stage.goal,
            start_date=max(stage.start_date, copy.start_date), end_date=end, intensity=stage.intensity,
            training_load=stage.training_load, distance_target_km=stage.distance_target_km,
            surface=stage.surface, note=stage.note,
        )
    log_action(user, "REVISE_TRAINING_PLAN", copy, {"FromTrainingPlanID": plan.id})
    return copy


# ---------------------------------------------------------------------------
# Buổi tập
# ---------------------------------------------------------------------------
def _validate_session(stage, values, session=None):
    plan = stage.plan
    if plan.status != P.ACTIVE:
        raise BusinessRuleError("Chỉ xếp buổi tập cho giáo án đang Active (đã được duyệt).", "PLAN_NOT_ACTIVE")
    horse = plan.assignment.horse
    ensure_horse_in_training(horse)
    session_date = values.get("session_date", getattr(session, "session_date", None))
    stage_end = stage.end_date or plan.end_date
    if session_date < stage.start_date or (stage_end and session_date > stage_end):
        raise ValidationError({"SessionDate": ["Ngày tập phải nằm trong thời gian của giai đoạn."]})
    if session is None and session_date < date.today():
        raise ValidationError({"SessionDate": ["Không xếp buổi tập vào ngày đã qua."]})
    start_time = values.get("start_time", getattr(session, "start_time", None))
    end_time = values.get("end_time", getattr(session, "end_time", None))
    if end_time and start_time and end_time < start_time:
        raise ValidationError({"EndTime": ["Giờ kết thúc phải sau giờ bắt đầu."]})
    load = values.get("training_load", getattr(session, "training_load", None))
    check_session_lock(horse, session_date, load)
    return horse, session_date


def _resolve_people(horse, values):
    rider_id = values.pop("work_rider_id", None)
    if rider_id is not None:
        values["work_rider"] = require_club_user(rider_id, horse.club_id, "WORK_RIDER", field="WorkRiderID")
    if "substitute_trainer_id" in values:
        substitute_id = values.pop("substitute_trainer_id")
        if substitute_id is None:
            values["substitute_trainer"] = None
        else:
            substitute = require_club_user(substitute_id, horse.club_id, *SUPERVISOR_ROLES,
                                           field="SubstituteTrainerID")
            # Chọn chính trainer phụ trách thì coi như không có Substitute
            values["substitute_trainer"] = None if substitute.pk == active_assignment(horse).trainer_id else substitute


def _check_rider_slot(values, session=None):
    rider = values.get("work_rider") or getattr(session, "work_rider", None)
    day = values.get("session_date") or getattr(session, "session_date", None)
    others = TrainingSession.objects.filter(work_rider=rider, session_date=day)
    if session is not None:
        others = others.exclude(pk=session.pk)
    if not values.get("sequence_no") and session is None:
        values["sequence_no"] = (others.aggregate(m=Max("sequence_no"))["m"] or 0) + 1
    sequence = values.get("sequence_no") or getattr(session, "sequence_no", None)
    if others.filter(sequence_no=sequence).exists():
        raise BusinessRuleError("Work Rider đã có buổi tập khác ở cùng ngày và cùng thứ tự (SequenceNo).",
                                "RIDER_SLOT_TAKEN")


def create_session(stage, user, values):
    horse, _ = _validate_session(stage, values)
    _resolve_people(horse, values)
    _check_rider_slot(values)
    session = TrainingSession.objects.create(stage=stage, assigned_by=user, status=S.ASSIGNED, **values)
    log_action(user, "ASSIGN_TRAINING_SESSION", session, {"HorseID": horse.pk})
    return session


def update_session(session, user, values):
    if session.status != S.ASSIGNED:
        raise BusinessRuleError("Chỉ sửa được buổi tập chưa bắt đầu (Assigned).", "INVALID_STATUS")
    stage = values.pop("stage", None) or session.stage
    if stage.plan_id != session.stage.plan_id:
        raise ValidationError({"TrainingPlanStageID": ["Chỉ chuyển sang giai đoạn khác trong cùng giáo án."]})
    horse, _ = _validate_session(stage, values, session)
    _resolve_people(horse, values)
    _check_rider_slot(values, session)
    session.stage = stage
    for attr, value in values.items():
        setattr(session, attr, value)
    session.save()
    log_action(user, "UPDATE_TRAINING_SESSION", session)
    return session


def start_session(session, user):
    """Work Rider bấm bắt đầu khi ngựa ra sân (giống chấm công)."""
    if session.work_rider_id != user.pk:
        raise BusinessRuleError("Chỉ Work Rider được giao mới bắt đầu buổi tập này.", "NOT_SESSION_RIDER")
    if session.status != S.ASSIGNED:
        raise BusinessRuleError("Buổi tập không ở trạng thái Assigned.", "INVALID_STATUS")
    if session.session_date != date.today():
        raise BusinessRuleError("Chỉ bắt đầu buổi tập vào đúng ngày tập.", "WRONG_DAY")
    if session.stage.plan.status != P.ACTIVE:
        raise BusinessRuleError("Giáo án của buổi tập không còn Active.", "PLAN_NOT_ACTIVE")
    check_session_lock(session.horse, session.session_date, session.training_load)
    session.status = S.IN_PROGRESS
    session.save(update_fields=["status"])
    log_action(user, "START_TRAINING_SESSION", session)
    return session


def _result_for(session):
    try:
        return session.result
    except TrainingResult.DoesNotExist:
        return None


def record_result(session, user, values):
    """Work Rider ghi kết quả -> buổi tập Completed."""
    if session.work_rider_id != user.pk:
        raise BusinessRuleError("Chỉ Work Rider của buổi tập mới ghi kết quả.", "NOT_SESSION_RIDER")
    if session.status != S.IN_PROGRESS:
        raise BusinessRuleError("Cần bắt đầu buổi tập (In Progress) trước khi ghi kết quả.", "INVALID_STATUS")
    result = _result_for(session)
    if result is None:
        result = TrainingResult(session=session)
    for attr, value in values.items():
        setattr(result, attr, value)
    result.recorded_at = timezone.now()
    result.save()
    session.status = S.COMPLETED
    if session.end_time is None:  # CHECK EndTime >= StartTime
        session.end_time = max(timezone.now().time().replace(microsecond=0), session.start_time)
    session.save(update_fields=["status", "end_time"])
    log_action(user, "RECORD_TRAINING_RESULT", session, {"TrainingResultID": result.id})
    return result


def add_substitute_observation(session, user, text):
    """Substitute Trainer ghi nhận xét (bắt buộc với buổi do mình giám sát thay)."""
    if session.substitute_trainer_id != user.pk:
        raise BusinessRuleError("Chỉ Substitute Trainer của buổi tập mới ghi nhận xét này.", "NOT_SUBSTITUTE")
    if session.status not in (S.IN_PROGRESS, S.COMPLETED, S.CANCELLED):
        raise BusinessRuleError("Buổi tập chưa diễn ra.", "INVALID_STATUS")
    result = _result_for(session) or TrainingResult(session=session)
    result.substitute_observation = text
    if result.pk is None:
        result.recorded_at = timezone.now()
    result.save()
    log_action(user, "SUBSTITUTE_OBSERVATION", session)
    return result


def is_supervisor(session, user) -> bool:
    return user.pk == session.supervising_trainer_id


def stop_session(session, user, reason):
    """Trainer đang giám sát (hoặc Head Trainer) dừng buổi tập khi ngựa có vấn đề -> Cancelled, báo ngay chủ ngựa."""
    _end_session(session, user, "STOP_TRAINING_SESSION", reason)
    owner_emails.session_stopped(session, reason)
    return session


def cancel_session(session, user, reason):
    """Hủy buổi tập (đổi lịch, thời tiết...) -> Cancelled. Không phải sự cố nên không báo khẩn cho chủ ngựa."""
    return _end_session(session, user, "CANCEL_TRAINING_SESSION", reason)


def _end_session(session, user, action, reason):
    if session.status not in (S.ASSIGNED, S.IN_PROGRESS):
        raise BusinessRuleError("Buổi tập đã kết thúc.", "INVALID_STATUS")
    session.status = S.CANCELLED
    session.save(update_fields=["status"])
    log_action(user, action, session, {"Reason": reason})
    return session


def mark_missed(session, user, reason=None):
    if session.status not in (S.ASSIGNED, S.IN_PROGRESS):
        raise BusinessRuleError("Buổi tập đã kết thúc.", "INVALID_STATUS")
    if session.session_date > date.today():
        raise BusinessRuleError("Buổi tập chưa tới ngày, hãy hủy thay vì đánh vắng.", "NOT_YET")
    session.status = S.MISSED
    session.save(update_fields=["status"])
    log_action(user, "MISS_TRAINING_SESSION", session, {"Reason": reason})
    return session


def review_session(session, user, values):
    """Trainer phụ trách đánh giá buổi tập đã xong (Substitute không đánh giá)."""
    assignment = session.assignment
    if assignment.trainer_id != user.pk or assignment.status != TrainerHorseAssignment.Status.ACTIVE:
        raise BusinessRuleError("Chỉ trainer đang phụ trách ngựa mới đánh giá buổi tập.", "NOT_ASSIGNED_TRAINER")
    if session.status != S.COMPLETED:
        raise BusinessRuleError("Chỉ đánh giá buổi tập đã hoàn thành.", "INVALID_STATUS")
    if session.reviews.exists():
        raise BusinessRuleError("Buổi tập này đã được đánh giá.", "ALREADY_REVIEWED")
    if values.get("adjustment_required") and not values.get("adjustment_note"):
        raise ValidationError({"AdjustmentNote": ["Cần ghi nội dung cần điều chỉnh."]})
    review = TrainingReview.objects.create(session=session, trainer=user, review_date=timezone.now(), **values)
    log_action(user, "REVIEW_TRAINING_SESSION", session,
               {"TrainingReviewID": review.id, "AdjustmentRequired": review.adjustment_required})
    return review


# ---------------------------------------------------------------------------
# Chốt giai đoạn -> tổng kết gửi chủ ngựa
# ---------------------------------------------------------------------------
def close_stage(stage, user, summary_note=None):
    plan = stage.plan
    if not (user.has_perm("TRAINING_PLAN_APPROVE") or (
            plan.assignment.trainer_id == user.pk and plan.assignment.status == TrainerHorseAssignment.Status.ACTIVE)):
        raise PermissionDenied("Chỉ trainer đang phụ trách ngựa hoặc Head Trainer mới chốt giai đoạn.")
    if plan.status not in (P.ACTIVE, P.COMPLETED):
        raise BusinessRuleError("Chỉ chốt giai đoạn của giáo án đang Active hoặc đã Completed.", "INVALID_STATUS")
    if stage.closed_at is not None:
        raise BusinessRuleError("Giai đoạn này đã được chốt.", "ALREADY_CLOSED")
    if stage.start_date > date.today():
        raise BusinessRuleError("Giai đoạn chưa bắt đầu nên chưa chốt được.", "NOT_STARTED")
    pending = stage.sessions.filter(status__in=(S.ASSIGNED, S.IN_PROGRESS)).count()
    if pending:
        raise BusinessRuleError(
            f"Giai đoạn còn {pending} buổi tập chưa xong (Assigned / In Progress): hãy hoàn thành, hủy "
            "hoặc đánh vắng trước khi chốt.", "SESSIONS_PENDING")
    stage.closed_at = timezone.now()
    stage.closed_by = user
    stage.summary_note = (summary_note or "").strip() or None
    stage.save(update_fields=["closed_at", "closed_by", "summary_note"])
    log_action(user, "CLOSE_PLAN_STAGE", stage, {"TrainingPlanID": plan.id})
    owner_emails.stage_closed(stage)
    return stage
