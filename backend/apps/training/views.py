"""API Flow 2 - huấn luyện. Chi tiết từng API: docs/API.md mục Flow 2."""
from datetime import date, timedelta

from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import flows
from apps.core.params import date_param, flag_param, int_param
from apps.core.permissions import HasAnyPermission, club_users_with_role
from apps.core.serializers import fmt_datetime
from apps.horses.models import Horse
from apps.horses.views import get_visible_horse

from . import profiles, services, summaries
from .models import (
    HorseAssessment, HorseWorkRiderPreference, Specialization, TrainerCredential, TrainerHorseAssignment, TrainerProfile,
    TrainerRaceResult, TrainingPlan, TrainingPlanStage, TrainingReview, TrainingSession,
)
from .serializers import (
    AssignTrainerSerializer, HorseAssessmentSerializer, NoteSerializer, ReasonOptionalSerializer,
    SpecializationSerializer, StageCloseSerializer, StopSessionSerializer, SubstituteObservationSerializer,
    TrainerCredentialSerializer, TrainerHorseAssignmentSerializer, TrainerProfileWriteSerializer,
    TrainerRaceResultSerializer, TrainerSpecializationSerializer,
    TrainingPlanCreateSerializer, TrainingPlanSerializer, TrainingPlanStageSerializer, TrainingPlanWriteSerializer,
    TrainingResultSerializer, TrainingReviewSerializer, TrainingSessionSerializer, TrainingSessionWriteSerializer,
    WorkRiderPreferenceCreateSerializer, WorkRiderPreferenceSerializer,
)

STAFF_VIEW = "HORSE_VIEW"


def staff_horse(user, horse_id):
    """Ngựa trong CLB của nhân sự đang đăng nhập (404 nếu không thấy)."""
    if not user.has_perm(STAFF_VIEW):
        raise PermissionDenied("Bạn không có quyền xem dữ liệu huấn luyện.")
    return get_visible_horse(user, horse_id)



# ---------------------------------------------------------------------------
# Chuyên môn, Trainer
# ---------------------------------------------------------------------------
class SpecializationListView(APIView):
    """GET /api/specializations"""

    def get(self, request):
        return Response(SpecializationSerializer(Specialization.objects.filter(status="Active"), many=True).data)


TRAINER_VIEWERS = ("TRAINER_ASSIGN", "RBAC_MANAGE")   # Head Trainer, Manager (trainer xem hồ sơ của mình)
TRAINER_EDITORS = ("TRAINER_ASSIGN", "RBAC_MANAGE")


def latest_recommendation(horse):
    """Phiếu đánh giá còn hiệu lực gần nhất của ngựa (DecisionStatus = Recommended)."""
    return (horse.assessments.filter(decision_status=HorseAssessment.Decision.RECOMMENDED)
            .select_related("specialization").order_by("-assessment_date", "-id").first())


def trainer_row(trainer, active_counts=None):
    """Thông tin 1 trainer: tên, chuyên môn, hồ sơ năng lực (tính từ giấy tờ, kết quả đua), số ngựa đang phụ trách."""
    links = list(trainer.specialization_links.select_related("specialization"))
    profile = TrainerProfile.objects.filter(trainer=trainer).first()
    if active_counts is None:
        count = TrainerHorseAssignment.objects.filter(trainer=trainer, status="Active").count()
    else:
        count = active_counts.get(trainer.id, 0)
    credentials = TrainerCredential.objects.filter(trainer=trainer).values_list("credential_type", "issued_date")
    results = TrainerRaceResult.objects.filter(trainer=trainer).values_list("race_date", "finish_position")
    return {
        "UserID": trainer.id, "FullName": trainer.full_name, "Email": trainer.email, "Phone": trainer.phone,
        "Specializations": [{"SpecializationID": link.specialization_id,
                             "SpecializationName": link.specialization.name} for link in links],
        **profiles.profile_body(trainer, profile, count, list(credentials), list(results)),
    }


def club_trainer(user, trainer_id):
    trainer = club_users_with_role(user.club_id, "TRAINER").filter(pk=trainer_id).first()
    if trainer is None:
        raise NotFound("Không tìm thấy trainer trong CLB.")
    return trainer


def can_view_trainer(user, trainer_id):
    if user.pk != trainer_id and not any(user.has_perm(code) for code in TRAINER_VIEWERS):
        raise PermissionDenied("Bạn không có quyền xem hồ sơ trainer.")


class TrainerListView(APIView):
    """
    GET /api/trainers                  trainer trong CLB: chuyên môn, kinh nghiệm, cấp độ, số ngựa đang phụ trách
    GET /api/trainers?SpecializationID=1
    GET /api/trainers?HorseID=5        gợi ý trainer cho ngựa: theo chuyên môn và cấp độ (xem apps/training/profiles.py),
                                       trainer phù hợp xếp trước, có IsSuggested / RequiredLevel / SuggestionReason
    """

    permission_classes = [HasAnyPermission(*TRAINER_VIEWERS)]

    @extend_schema(parameters=[
        OpenApiParameter("SpecializationID", OpenApiTypes.INT, description="Chỉ lấy trainer có chuyên môn này"),
        OpenApiParameter("HorseID", OpenApiTypes.INT,
                         description="Gợi ý trainer cho ngựa này (thêm IsSuggested / RequiredLevel / SuggestionReason)"),
    ])
    def get(self, request):
        trainers = club_users_with_role(request.user.club_id, "TRAINER")
        p = request.query_params
        if p.get("SpecializationID"):
            trainers = trainers.filter(specialization_links__specialization_id=int_param(p, "SpecializationID"))
        assessment, horse_id = None, None
        if p.get("HorseID"):
            horse_id = int_param(p, "HorseID")
            assessment = latest_recommendation(staff_horse(request.user, horse_id))
        counts = dict(TrainerHorseAssignment.objects.filter(status="Active", trainer__in=trainers)
                      .values_list("trainer_id").annotate(n=Count("id")).values_list("trainer_id", "n"))
        result = []
        for trainer in trainers.distinct().order_by("full_name"):
            row = trainer_row(trainer, counts)
            if horse_id is not None:
                row.update(profiles.suggestion(row, {s["SpecializationID"] for s in row["Specializations"]},
                                               assessment))
            result.append(row)
        if horse_id is not None:
            result.sort(key=profiles.sort_key)
        return Response(result)


class TrainerDetailView(APIView):
    """
    GET /api/trainers/<UserID> - hồ sơ trainer + ngựa đang phụ trách + bằng cấp / bằng khen + 10 lần đua gần nhất
    (trainer xem được hồ sơ của mình).
    """

    def get(self, request, user_id):
        can_view_trainer(request.user, user_id)
        trainer = club_trainer(request.user, user_id)
        body = trainer_row(trainer)
        active = (TrainerHorseAssignment.objects.filter(trainer=trainer, status="Active")
                  .select_related("horse", "specialization").order_by("start_date"))
        body["ActiveHorses"] = [{
            "TrainerHorseAssignmentID": a.id, "HorseID": a.horse_id, "HorseName": a.horse.horse_name,
            "HorseCode": a.horse.horse_code, "SpecializationName": a.specialization.name, "StartDate": a.start_date,
        } for a in active]
        body["Credentials"] = TrainerCredentialSerializer(
            TrainerCredential.objects.filter(trainer=trainer).select_related("created_by"), many=True).data
        body["RecentRaceResults"] = TrainerRaceResultSerializer(
            TrainerRaceResult.objects.filter(trainer=trainer)[:10], many=True).data
        return Response(body)


class TrainerProfileView(APIView):
    """PATCH /api/trainers/<UserID>/profile {"CareerStartDate", "TrainerRating"} - Head Trainer / Manager."""

    permission_classes = [HasAnyPermission(*TRAINER_EDITORS)]

    def patch(self, request, user_id):
        trainer = club_trainer(request.user, user_id)
        data = TrainerProfileWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        services.update_trainer_profile(trainer, request.user, dict(data.validated_data))
        return Response(trainer_row(trainer))


class TrainerCredentialListView(APIView):
    """
    GET  /api/trainers/<UserID>/credentials   bằng cấp, chứng chỉ, giấy phép hành nghề, bằng khen
    POST /api/trainers/<UserID>/credentials   Head Trainer / Manager thêm (sau khi xem giấy tờ gốc)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(*TRAINER_EDITORS)()]
        return super().get_permissions()

    def get(self, request, user_id):
        can_view_trainer(request.user, user_id)
        trainer = club_trainer(request.user, user_id)
        items = TrainerCredential.objects.filter(trainer=trainer).select_related("created_by")
        return Response(TrainerCredentialSerializer(items, many=True).data)

    def post(self, request, user_id):
        trainer = club_trainer(request.user, user_id)
        data = TrainerCredentialSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        credential = services.add_trainer_credential(trainer, request.user, dict(data.validated_data))
        return Response(TrainerCredentialSerializer(credential).data, status=status.HTTP_201_CREATED)


class TrainerCredentialDetailView(APIView):
    """DELETE /api/trainer-credentials/<CredentialID>"""

    permission_classes = [HasAnyPermission(*TRAINER_EDITORS)]

    def delete(self, request, credential_id):
        credential = TrainerCredential.objects.filter(pk=credential_id, trainer__club_id=request.user.club_id).first()
        if credential is None:
            raise NotFound("Không tìm thấy giấy tờ.")
        services.delete_trainer_credential(credential, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainerRaceResultListView(APIView):
    """
    GET  /api/trainers/<UserID>/race-results?From=&To=   các lần ngựa của trainer ra đường đua (mới nhất trước)
    POST /api/trainers/<UserID>/race-results             Head Trainer / Manager ghi kết quả
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(*TRAINER_EDITORS)()]
        return super().get_permissions()

    @extend_schema(parameters=[
        OpenApiParameter("From", OpenApiTypes.DATE, description="Từ ngày đua (YYYY-MM-DD)"),
        OpenApiParameter("To", OpenApiTypes.DATE, description="Đến ngày đua (YYYY-MM-DD)"),
    ])
    def get(self, request, user_id):
        can_view_trainer(request.user, user_id)
        items = TrainerRaceResult.objects.filter(trainer=club_trainer(request.user, user_id))
        p = request.query_params
        if p.get("From"):
            items = items.filter(race_date__gte=date_param(p, "From"))
        if p.get("To"):
            items = items.filter(race_date__lte=date_param(p, "To"))
        return Response(TrainerRaceResultSerializer(items, many=True).data)

    def post(self, request, user_id):
        trainer = club_trainer(request.user, user_id)
        data = TrainerRaceResultSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.add_race_result(trainer, request.user, dict(data.validated_data))
        return Response(TrainerRaceResultSerializer(result).data, status=status.HTTP_201_CREATED)


class TrainerRaceResultDetailView(APIView):
    """DELETE /api/trainer-race-results/<RaceResultID> (ghi nhầm)"""

    permission_classes = [HasAnyPermission(*TRAINER_EDITORS)]

    def delete(self, request, result_id):
        result = TrainerRaceResult.objects.filter(pk=result_id, trainer__club_id=request.user.club_id).first()
        if result is None:
            raise NotFound("Không tìm thấy kết quả đua.")
        services.delete_race_result(result, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainerSpecializationView(APIView):
    """
    POST   /api/trainers/<UserID>/specializations            {"SpecializationID": 1}
    DELETE /api/trainers/<UserID>/specializations/<SpecID>
    """

    permission_classes = [HasAnyPermission("TRAINER_ASSIGN", "RBAC_MANAGE")]

    def _trainer(self, request, user_id):
        trainer = club_users_with_role(request.user.club_id, "TRAINER").filter(pk=user_id).first()
        if trainer is None:
            raise NotFound("Không tìm thấy trainer trong CLB.")
        return trainer

    def post(self, request, user_id, spec_id=None):
        data = TrainerSpecializationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        spec = Specialization.objects.filter(pk=data.validated_data["SpecializationID"]).first()
        if spec is None:
            raise ValidationError({"SpecializationID": ["Chuyên môn không tồn tại."]})
        services.add_trainer_specialization(self._trainer(request, user_id), spec, request.user)
        return Response({"TrainerID": user_id, "SpecializationID": spec.id}, status=status.HTTP_201_CREATED)

    def delete(self, request, user_id, spec_id=None):
        spec = Specialization.objects.filter(pk=spec_id).first() if spec_id else None
        if spec is None:
            raise NotFound("Chuyên môn không tồn tại.")
        services.remove_trainer_specialization(self._trainer(request, user_id), spec, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Đánh giá ngựa
# ---------------------------------------------------------------------------
class HorseAssessmentView(APIView):
    """GET / POST /api/horses/<HorseID>/assessments"""

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission("HORSE_ASSESS")()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, horse_id):
        horse = staff_horse(request.user, horse_id)
        items = horse.assessments.select_related("head_trainer", "specialization")
        return Response(HorseAssessmentSerializer(items, many=True).data)

    def post(self, request, horse_id):
        horse = staff_horse(request.user, horse_id)
        data = HorseAssessmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        assessment = services.create_assessment(horse, request.user, dict(data.validated_data))
        return Response(HorseAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Phân công Trainer
# ---------------------------------------------------------------------------
class TrainerAssignmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/trainer-assignments?HorseID=&TrainerID=&Status=Active
    POST /api/trainer-assignments                 Head Trainer giao trainer phụ trách
    POST /api/trainer-assignments/<id>/end        Head Trainer kết thúc phân công
    """

    serializer_class = TrainerHorseAssignmentSerializer

    def get_permissions(self):
        if self.action in ("create", "end"):
            return [HasAnyPermission("TRAINER_ASSIGN")()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get_queryset(self):
        qs = TrainerHorseAssignment.objects.filter(horse__club_id=self.request.user.club_id).select_related(
            "horse", "trainer", "specialization", "assigned_by")
        p = self.request.query_params
        if p.get("HorseID"):
            qs = qs.filter(horse_id=int_param(p, "HorseID"))
        if p.get("TrainerID"):
            qs = qs.filter(trainer_id=int_param(p, "TrainerID"))
        if p.get("Status"):
            qs = qs.filter(status=p["Status"])
        if flag_param(p, "mine"):
            qs = qs.filter(trainer=self.request.user)
        return qs

    def create(self, request):
        data = AssignTrainerSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        horse = staff_horse(request.user, v["HorseID"])
        spec = Specialization.objects.filter(pk=v["SpecializationID"]).first()
        if spec is None:
            raise ValidationError({"SpecializationID": ["Chuyên môn không tồn tại."]})
        assessment = None
        if v.get("AssessmentID"):
            assessment = HorseAssessment.objects.filter(pk=v["AssessmentID"]).first()
            if assessment is None:
                raise ValidationError({"AssessmentID": ["Phiếu đánh giá không tồn tại."]})
        assignment = services.assign_trainer(horse, request.user, v["TrainerID"], spec, assessment,
                                             v.get("StartDate"), v.get("AssignmentNote"))
        body = TrainerHorseAssignmentSerializer(assignment).data
        # Không chặn, chỉ nhắc Head Trainer khi giao ngựa tốt cho trainer chưa đủ kinh nghiệm
        row = trainer_row(assignment.trainer)
        check = profiles.suggestion(row, {s["SpecializationID"] for s in row["Specializations"]},
                                    assessment or latest_recommendation(horse))
        body["TrainerExperienceLevel"] = row["ExperienceLevel"]
        body["RequiredLevel"] = check["RequiredLevel"]
        body["LevelWarning"] = None if check["MatchesLevel"] else (
            f"Ngựa này nên giao trainer {check['RequiredLevel']} trở lên, trainer đang là {row['ExperienceLevel']}.")
        return Response(body, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        data = ReasonOptionalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        assignment = services.end_assignment(self.get_object(), request.user, data.validated_data.get("Reason"))
        return Response(TrainerHorseAssignmentSerializer(assignment).data)


# ---------------------------------------------------------------------------
# Work Rider ưu tiên
# ---------------------------------------------------------------------------
def ensure_horse_session_manager(user, horse):
    """Head Trainer: mọi ngựa; Trainer: ngựa mình đang phụ trách (ngựa chưa có trainer thì chỉ Head Trainer)."""
    assignment = services.active_assignment(horse)
    if user.has_perm("TRAINING_PLAN_APPROVE") or (assignment and services.can_manage_sessions(user, assignment)):
        return
    raise PermissionDenied("Bạn chỉ quản lý Work Rider / buổi tập của ngựa mình đang phụ trách.")

class WorkRiderPreferenceView(APIView):
    """GET / POST /api/horses/<HorseID>/work-rider-preferences"""

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission("TRAINING_SESSION_ASSIGN")()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, horse_id):
        horse = staff_horse(request.user, horse_id)
        items = horse.work_rider_preferences.select_related("work_rider")
        if not flag_param(request.query_params, "all"):
            items = items.filter(end_date__isnull=True)
        return Response(WorkRiderPreferenceSerializer(items, many=True).data)

    def post(self, request, horse_id):
        horse = staff_horse(request.user, horse_id)
        ensure_horse_session_manager(request.user, horse)
        data = WorkRiderPreferenceCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        pref = services.add_work_rider_preference(horse, request.user, v["WorkRiderID"], v["Priority"],
                                                  v.get("Note"), v.get("StartDate"))
        return Response(WorkRiderPreferenceSerializer(pref).data, status=status.HTTP_201_CREATED)


class WorkRiderPreferenceEndView(APIView):
    """POST /api/work-rider-preferences/<id>/end"""

    permission_classes = [HasAnyPermission("TRAINING_SESSION_ASSIGN")]

    def post(self, request, pref_id):
        pref = HorseWorkRiderPreference.objects.filter(pk=pref_id, horse__club_id=request.user.club_id).first()
        if pref is None:
            raise NotFound("Không tìm thấy.")
        ensure_horse_session_manager(request.user, pref.horse)
        return Response(WorkRiderPreferenceSerializer(services.end_work_rider_preference(pref, request.user)).data)


# ---------------------------------------------------------------------------
# Giáo án
# ---------------------------------------------------------------------------
class TrainingPlanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = TrainingPlanSerializer

    action_permissions = {
        "create": ("TRAINING_PLAN_MANAGE",),
        "partial_update": ("TRAINING_PLAN_MANAGE",),
        "stages": ("TRAINING_PLAN_MANAGE",),
        "submit": ("TRAINING_PLAN_MANAGE",),
        "revise": ("TRAINING_PLAN_MANAGE",),
        "approve": ("TRAINING_PLAN_APPROVE",),
        "return_plan": ("TRAINING_PLAN_APPROVE",),
        "complete": ("TRAINING_PLAN_MANAGE", "TRAINING_PLAN_APPROVE"),
        "cancel": ("TRAINING_PLAN_MANAGE", "TRAINING_PLAN_APPROVE"),
    }

    def get_permissions(self):
        return [HasAnyPermission(*self.action_permissions.get(self.action, (STAFF_VIEW,)))()]

    def get_queryset(self):
        qs = TrainingPlan.objects.filter(assignment__horse__club_id=self.request.user.club_id).select_related(
            "assignment__horse", "assignment__trainer").prefetch_related("stages")
        p = self.request.query_params
        if p.get("HorseID"):
            qs = qs.filter(assignment__horse_id=int_param(p, "HorseID"))
        if p.get("TrainerID"):
            qs = qs.filter(assignment__trainer_id=int_param(p, "TrainerID"))
        if p.get("Status"):
            qs = qs.filter(status=p["Status"])
        if flag_param(p, "mine"):
            qs = qs.filter(assignment__trainer=self.request.user)
        return qs

    def _out(self, plan, code=status.HTTP_200_OK):
        return Response(TrainingPlanSerializer(self.get_queryset().get(pk=plan.pk)).data, status=code)

    def create(self, request):
        data = TrainingPlanCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        horse = staff_horse(request.user, values.pop("HorseID"))
        stages = [dict(s) for s in values.pop("Stages", [])]
        plan = services.create_plan(horse, request.user, values, stages)
        return self._out(plan, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        data = TrainingPlanWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return self._out(services.update_plan(self.get_object(), request.user, dict(data.validated_data)))

    @action(detail=True, methods=["post"])
    def stages(self, request, pk=None):
        data = TrainingPlanStageSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        stage = services.add_stage(self.get_object(), request.user, dict(data.validated_data))
        return Response(TrainingPlanStageSerializer(stage).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self._out(services.submit_plan(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = NoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.approve_plan(self.get_object(), request.user, data.validated_data.get("ReviewNote")))

    @action(detail=True, methods=["post"], url_path="return")
    def return_plan(self, request, pk=None):
        data = NoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.return_plan(self.get_object(), request.user, data.validated_data.get("ReviewNote")))

    def _owner_or_approver(self, plan):
        if not self.request.user.has_perm("TRAINING_PLAN_APPROVE"):
            services.ensure_plan_owner(plan, self.request.user)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        plan = self.get_object()
        self._owner_or_approver(plan)
        return self._out(services.complete_plan(plan, request.user))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        plan = self.get_object()
        self._owner_or_approver(plan)
        data = ReasonOptionalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.cancel_plan(plan, request.user, data.validated_data.get("Reason")))

    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):
        return self._out(services.revise_plan(self.get_object(), request.user), status.HTTP_201_CREATED)


class TrainingPlanStageView(APIView):
    """PATCH / DELETE /api/training-plan-stages/<id> (giáo án Draft, trainer phụ trách)"""

    permission_classes = [HasAnyPermission("TRAINING_PLAN_MANAGE")]

    def _stage(self, request, stage_id):
        stage = TrainingPlanStage.objects.filter(
            pk=stage_id, plan__assignment__horse__club_id=request.user.club_id).select_related("plan__assignment").first()
        if stage is None:
            raise NotFound("Không tìm thấy giai đoạn.")
        return stage

    def patch(self, request, stage_id):
        data = TrainingPlanStageSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        stage = services.update_stage(self._stage(request, stage_id), request.user, dict(data.validated_data))
        return Response(TrainingPlanStageSerializer(stage).data)

    def delete(self, request, stage_id):
        services.delete_stage(self._stage(request, stage_id), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainingPlanStageCloseView(APIView):
    """
    POST /api/training-plan-stages/<id>/close {"SummaryNote": "..."} - trainer phụ trách (hoặc Head Trainer)
    chốt giai đoạn: hệ thống gửi tổng kết giai đoạn cho chủ ngựa (chuông + email).
    Điều kiện: giáo án Active / Completed, giai đoạn đã bắt đầu, không còn buổi Assigned / In Progress.
    """

    permission_classes = [HasAnyPermission("TRAINING_PLAN_MANAGE", "TRAINING_PLAN_APPROVE")]

    @extend_schema(request=StageCloseSerializer)
    def post(self, request, stage_id):
        stage = TrainingPlanStage.objects.filter(
            pk=stage_id, plan__assignment__horse__club_id=request.user.club_id).select_related(
            "plan__assignment__horse__owner", "plan__assignment__trainer").first()
        if stage is None:
            raise NotFound("Không tìm thấy giai đoạn.")
        data = StageCloseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        stage = services.close_stage(stage, request.user, data.validated_data.get("SummaryNote"))
        return Response(summaries.stage_summary(stage))


# ---------------------------------------------------------------------------
# Buổi tập
# ---------------------------------------------------------------------------
SESSION_RELATED = ("stage__plan__assignment__horse", "stage__plan__assignment__trainer", "work_rider",
                   "substitute_trainer")


class TrainingSessionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/training-sessions?Date=&From=&To=&HorseID=&WorkRiderID=&Status=&mine=1
         mine=1: Work Rider -> buổi mình cưỡi; Trainer -> buổi mình giám sát (phụ trách hoặc Substitute)
    """

    serializer_class = TrainingSessionSerializer

    action_permissions = {
        "create": ("TRAINING_SESSION_ASSIGN",),
        "partial_update": ("TRAINING_SESSION_ASSIGN",),
        "cancel": ("TRAINING_SESSION_ASSIGN",),
        "missed": ("TRAINING_SESSION_ASSIGN",),
        "start": ("TRAINING_RESULT_UPDATE",),
        "result": ("TRAINING_RESULT_UPDATE",),
        "stop": ("TRAINING_SESSION_SUPERVISE", "TRAINING_SESSION_ASSIGN"),
        "substitute_observation": ("TRAINING_SESSION_SUPERVISE",),
        "review": ("TRAINING_REVIEW",),
    }

    def get_permissions(self):
        return [HasAnyPermission(*self.action_permissions.get(self.action, (STAFF_VIEW,)))()]

    def get_queryset(self):
        user = self.request.user
        qs = TrainingSession.objects.filter(stage__plan__assignment__horse__club_id=user.club_id).select_related(
            *SESSION_RELATED).prefetch_related("reviews")
        p = self.request.query_params
        if p.get("Date"):
            qs = qs.filter(session_date=date_param(p, "Date"))
        if p.get("From"):
            qs = qs.filter(session_date__gte=date_param(p, "From"))
        if p.get("To"):
            qs = qs.filter(session_date__lte=date_param(p, "To"))
        if p.get("HorseID"):
            qs = qs.filter(stage__plan__assignment__horse_id=int_param(p, "HorseID"))
        if p.get("TrainingPlanID"):
            qs = qs.filter(stage__plan_id=int_param(p, "TrainingPlanID"))
        if p.get("WorkRiderID"):
            qs = qs.filter(work_rider_id=int_param(p, "WorkRiderID"))
        if p.get("Status"):
            qs = qs.filter(status=p["Status"])
        if flag_param(p, "mine"):
            qs = qs.filter(
                Q(work_rider=user) | Q(substitute_trainer=user)
                | Q(substitute_trainer__isnull=True, stage__plan__assignment__trainer=user)
            )
        return qs

    def _out(self, session, code=status.HTTP_200_OK):
        return Response(TrainingSessionSerializer(self.get_queryset().get(pk=session.pk)).data, status=code)

    def _stage(self, stage):
        if stage.plan.assignment.horse.club_id != self.request.user.club_id:
            raise ValidationError({"TrainingPlanStageID": ["Giai đoạn không thuộc CLB của bạn."]})
        return stage

    def create(self, request):
        data = TrainingSessionWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        stage = self._stage(values.pop("stage"))
        services.ensure_session_manager(request.user, stage.plan.assignment)
        return self._out(services.create_session(stage, request.user, values), status.HTTP_201_CREATED)

    def _managed_session(self):
        """Buổi tập mà người đang đăng nhập được sửa / hủy / đánh vắng."""
        session = self.get_object()
        services.ensure_session_manager(self.request.user, session.assignment)
        return session

    def partial_update(self, request, pk=None):
        session = self._managed_session()
        data = TrainingSessionWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if "stage" in values:
            self._stage(values["stage"])
        return self._out(services.update_session(session, request.user, values))

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._out(services.start_session(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def result(self, request, pk=None):
        data = TrainingResultSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session = self.get_object()
        services.record_result(session, request.user, dict(data.validated_data))
        return self._out(session)

    @action(detail=True, methods=["post"], url_path="substitute-observation")
    def substitute_observation(self, request, pk=None):
        data = SubstituteObservationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session = self.get_object()
        services.add_substitute_observation(session, request.user, data.validated_data["SubstituteObservation"])
        return self._out(session)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        """Trainer đang giám sát (hoặc Head Trainer) dừng buổi tập; có Flow 3 và ReportHealth=true thì báo luôn cho Vet."""
        session = self.get_object()
        if not (services.is_supervisor(session, request.user)
                or services.can_manage_sessions(request.user, session.assignment)):
            raise PermissionDenied("Chỉ trainer đang giám sát buổi tập, trainer phụ trách hoặc Head Trainer "
                                   "mới dừng buổi tập.")
        data = StopSessionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        services.stop_session(session, request.user, v["Reason"])
        body = TrainingSessionSerializer(self.get_queryset().get(pk=session.pk)).data
        if v.get("ReportHealth"):  # chỉ có khi đã có Flow 3
            from apps.medical import services as medical_services

            report = medical_services.create_health_report(
                session.horse, request.user, {"severity": v["Severity"],
                                              "description": v.get("Description") or v["Reason"],
                                              "training_session": session})
            body["HealthReportID"] = report.id
        return Response(body)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        data = ReasonOptionalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session = self._managed_session()
        services.cancel_session(session, request.user, data.validated_data.get("Reason") or "Hủy buổi tập")
        return self._out(session)

    @action(detail=True, methods=["post"])
    def missed(self, request, pk=None):
        data = ReasonOptionalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session = self._managed_session()
        services.mark_missed(session, request.user, data.validated_data.get("Reason"))
        return self._out(session)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        data = TrainingReviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        review = services.review_session(self.get_object(), request.user, dict(data.validated_data))
        return Response(TrainingReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class TrainingReviewListView(APIView):
    """GET /api/training-reviews?AdjustmentRequired=1&HorseID=&Days=14 - Head Trainer theo dõi đánh giá."""

    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request):
        p = request.query_params
        qs = TrainingReview.objects.filter(
            session__stage__plan__assignment__horse__club_id=request.user.club_id
        ).select_related("trainer", "session__stage__plan__assignment__horse")
        if flag_param(p, "AdjustmentRequired"):
            qs = qs.filter(adjustment_required=True)
        if p.get("HorseID"):
            qs = qs.filter(session__stage__plan__assignment__horse_id=int_param(p, "HorseID"))
        if p.get("Days"):
            qs = qs.filter(session__session_date__gte=date.today() - timedelta(days=int_param(p, "Days")))
        return Response(TrainingReviewSerializer(qs, many=True).data)


class TrainingDashboardView(APIView):
    """
    GET /api/training-dashboard?HorseID= - giống view vw_HorseTrainingDashboard:
    ngựa đã tiếp nhận + trainer phụ trách + Training Lock đang hiệu lực + giáo án Active + buổi tập gần nhất.
    Head Trainer xem trước khi xếp buổi tập (ngựa Restricted hiện rõ MaxIntensity).
    """

    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request):
        horses = Horse.objects.filter(club_id=request.user.club_id,
                                      registration_status=Horse.RegistrationStatus.APPROVED).order_by("horse_name")
        if request.query_params.get("HorseID"):
            horses = horses.filter(pk=int_param(request.query_params, "HorseID"))
        result = []
        for horse in horses:
            assignment = services.active_assignment(horse)
            lock = services.active_lock(horse)
            plan = assignment.plans.filter(status="Active").first() if assignment else None
            latest = (services.sessions_of_horse(horse).filter(status="Completed")
                      .select_related("result").order_by("-session_date", "-end_time", "-id").first())
            latest_result = getattr(latest, "result", None) if latest else None
            result.append({
                "HorseID": horse.id, "HorseCode": horse.horse_code, "HorseName": horse.horse_name,
                "Gender": horse.gender, "SexClass": horse.sex_class,
                "CurrentHealthStatus": horse.current_health_status,
                "TrainerHorseAssignmentID": assignment.id if assignment else None,
                "TrainerID": assignment.trainer_id if assignment else None,
                "TrainerName": assignment.trainer.full_name if assignment else None,
                "SpecializationName": assignment.specialization.name if assignment else None,
                "ActiveTrainingPlanID": plan.id if plan else None,
                "LatestTrainingDate": latest.session_date if latest else None,
                "LatestPerformanceScore": getattr(latest_result, "performance_score", None),
                "LatestActualDistanceKm": getattr(latest_result, "actual_distance_km", None),
                "LatestAvgSpeedKmh": getattr(latest_result, "avg_speed_kmh", None),
                "LatestAvgHeartRate": getattr(latest_result, "avg_heart_rate", None),
                "LatestRecoveryMinutes": getattr(latest_result, "recovery_minutes", None),
            })
            if flows.has_flow3():  # Training Lock là của Flow 3
                result[-1].update({
                    "IsTrainingLocked": lock is not None,
                    "TrainingLockID": lock.id if lock else None,
                    "LockLevel": lock.lock_level if lock else None,
                    "MaxIntensity": lock.max_intensity if lock else None,
                    "LockEndDate": fmt_datetime(lock.lock_end_date) if lock else None,
                })
        return Response(result)

