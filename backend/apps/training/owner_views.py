"""
API chủ ngựa xem kết quả huấn luyện (quyền OWNER_VIEW, chỉ ngựa của mình). Cách tính: apps/training/summaries.py.

GET /api/owner/horses/<HorseID>/training-plans          giáo án đã duyệt + tổng kết chung
GET /api/owner/training-plans/<TrainingPlanID>           tổng kết giáo án + từng giai đoạn (so với giai đoạn trước)
GET /api/owner/horses/<HorseID>/training-sessions        buổi tập đã được trainer đánh giá + buổi hủy / vắng (tổng quan)
GET /api/owner/training-sessions/<TrainingSessionID>     chi tiết một buổi
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.params import date_param, int_param
from apps.core.permissions import HasAnyPermission
from apps.horses.models import Horse

from . import summaries
from .models import TrainingPlan, TrainingSession

OWNER_VIEW = "OWNER_VIEW"


def owner_horse(user, horse_id):
    horse = Horse.objects.filter(pk=horse_id, owner=user).first()
    if horse is None:
        raise NotFound("Không tìm thấy ngựa của bạn.")
    return horse


def horse_body(horse):
    return {"HorseID": horse.id, "HorseName": horse.horse_name, "HorseCode": horse.horse_code}


class OwnerTrainingPlanListView(APIView):
    """GET /api/owner/horses/<HorseID>/training-plans - giáo án đã duyệt của ngựa (mới nhất trước) + tổng kết chung."""

    permission_classes = [HasAnyPermission(OWNER_VIEW)]

    def get(self, request, horse_id):
        horse = owner_horse(request.user, horse_id)
        rows = []
        for plan in summaries.owner_plans(horse):
            body = summaries.plan_summary(plan)
            body.pop("Stages")
            rows.append(body)
        return Response({**horse_body(horse), "Plans": rows})


class OwnerTrainingPlanDetailView(APIView):
    """GET /api/owner/training-plans/<TrainingPlanID> - tổng kết giáo án và từng giai đoạn."""

    permission_classes = [HasAnyPermission(OWNER_VIEW)]

    def get(self, request, plan_id):
        plan = (TrainingPlan.objects.filter(pk=plan_id, approved_at__isnull=False,
                                            assignment__horse__owner=request.user)
                .select_related("assignment__horse", "assignment__trainer", "assignment__specialization").first())
        if plan is None:
            raise NotFound("Không tìm thấy giáo án.")
        return Response({**horse_body(plan.assignment.horse), **summaries.plan_summary(plan)})


class OwnerTrainingSessionListView(APIView):
    """
    GET /api/owner/horses/<HorseID>/training-sessions?From=&To=&TrainingPlanID=&TrainingPlanStageID=
    Tổng quan từng buổi: ngày, loại bài tập, thời lượng, quãng đường, điểm phong độ, đánh giá trainer, trạng thái.
    Chỉ buổi đã được trainer đánh giá; buổi hủy / vắng kèm lý do.
    """

    permission_classes = [HasAnyPermission(OWNER_VIEW)]

    @extend_schema(parameters=[
        OpenApiParameter("From", OpenApiTypes.DATE), OpenApiParameter("To", OpenApiTypes.DATE),
        OpenApiParameter("TrainingPlanID", OpenApiTypes.INT), OpenApiParameter("TrainingPlanStageID", OpenApiTypes.INT),
    ])
    def get(self, request, horse_id):
        horse = owner_horse(request.user, horse_id)
        qs = TrainingSession.objects.filter(stage__plan__assignment__horse=horse)
        p = request.query_params
        if p.get("From"):
            qs = qs.filter(session_date__gte=date_param(p, "From"))
        if p.get("To"):
            qs = qs.filter(session_date__lte=date_param(p, "To"))
        if p.get("TrainingPlanID"):
            qs = qs.filter(stage__plan_id=int_param(p, "TrainingPlanID"))
        if p.get("TrainingPlanStageID"):
            qs = qs.filter(stage_id=int_param(p, "TrainingPlanStageID"))
        sessions = list(summaries.visible_sessions(qs))
        reasons = summaries.end_reasons(s.id for s in sessions)
        return Response([summaries.session_overview(s, reasons) for s in sessions])


class OwnerTrainingSessionDetailView(APIView):
    """GET /api/owner/training-sessions/<id> - thêm tốc độ, nhịp tim, hồi phục, nhận xét rider, video, nhận xét trainer."""

    permission_classes = [HasAnyPermission(OWNER_VIEW)]

    def get(self, request, session_id):
        session = summaries.visible_sessions(TrainingSession.objects.filter(
            pk=session_id, stage__plan__assignment__horse__owner=request.user)).first()
        if session is None:
            raise NotFound("Không tìm thấy buổi tập (hoặc buổi tập chưa được trainer đánh giá).")
        return Response(summaries.session_detail(session, summaries.end_reasons([session.id])))
