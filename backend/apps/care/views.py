"""API Flow 4 - chăm sóc và dinh dưỡng. Chi tiết từng API: docs/API.md mục Flow 4."""
from datetime import datetime, time

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.params import date_param, flag_param, int_param
from apps.core.permissions import HasAnyPermission
from apps.horses.views import get_visible_horse

from . import services
from .models import CareTask, DietPlan, InventoryItem, InventoryRequest
from .serializers import (
    CareTaskSerializer, CareTaskWriteSerializer, DietPlanSerializer, DietPlanWriteSerializer,
    InventoryApproveSerializer, InventoryItemSerializer, InventoryItemWriteSerializer, InventoryRequestCreateSerializer,
    InventoryRequestSerializer, NoteSerializer, ReasonSerializer, RejectSerializer, StockSerializer,
    VetDietDecisionSerializer,
)

STAFF_VIEW = "HORSE_VIEW"




def _meals(values):
    meals = values.pop("Meals", None)
    return [dict(m) for m in meals] if meals is not None else None


# ---------------------------------------------------------------------------
# Khẩu phần
# ---------------------------------------------------------------------------
def can_create_diet(user):
    """Head Trainer lập khẩu phần (cột CreatedByHeadTrainerID)."""
    return user.has_perm("DIET_MANAGE") and user.has_role("HEAD_TRAINER")


def can_review_diet(user):
    """Vet duyệt / trả về / điều chỉnh khẩu phần."""
    return user.has_perm("DIET_MANAGE") and user.has_perm("MEDICAL_MANAGE")


class HorseDietPlanView(APIView):
    """
    GET  /api/horses/<HorseID>/diet-plans
    POST /api/horses/<HorseID>/diet-plans   Head Trainer lập khẩu phần (Pending, chờ Vet duyệt)
    """

    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request, horse_id):
        horse = get_visible_horse(request.user, horse_id)
        plans = horse.diet_plans.select_related("created_by", "reviewed_by", "horse").prefetch_related("meals")
        return Response(DietPlanSerializer(plans, many=True).data)

    def post(self, request, horse_id):
        if not can_create_diet(request.user):
            raise PermissionDenied("Chỉ Head Trainer lập khẩu phần.")
        horse = get_visible_horse(request.user, horse_id)
        data = DietPlanWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        plan = services.create_diet_plan(horse, request.user, values, _meals(values) or [])
        return Response(DietPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class CurrentDietView(APIView):
    """GET /api/horses/<HorseID>/current-diet - khẩu phần đang áp dụng hôm nay (null nếu chưa có)."""

    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request, horse_id):
        plan = services.current_diet_plan(get_visible_horse(request.user, horse_id))
        return Response(DietPlanSerializer(plan).data if plan else None)


class DietPlanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET   /api/diet-plans?Status=Pending&HorseID=     (Vet xem khẩu phần chờ duyệt)
    PATCH /api/diet-plans/<id>                        Head Trainer sửa / gửi lại
    POST  /api/diet-plans/<id>/approve|reject|adjust  Vet
    """

    serializer_class = DietPlanSerializer
    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get_queryset(self):
        qs = DietPlan.objects.filter(horse__club_id=self.request.user.club_id).select_related(
            "horse", "created_by", "reviewed_by").prefetch_related("meals")
        p = self.request.query_params
        if p.get("Status"):
            qs = qs.filter(status=p["Status"])
        if p.get("HorseID"):
            qs = qs.filter(horse_id=int_param(p, "HorseID"))
        return qs

    def _out(self, plan):
        return Response(DietPlanSerializer(self.get_queryset().get(pk=plan.pk)).data)

    def _decision(self, request):
        if not can_review_diet(request.user):
            raise PermissionDenied("Chỉ Vet duyệt / điều chỉnh khẩu phần.")
        data = VetDietDecisionSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return dict(data.validated_data)

    def partial_update(self, request, pk=None):
        if not can_create_diet(request.user):
            raise PermissionDenied("Chỉ Head Trainer sửa khẩu phần.")
        data = DietPlanWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        meals = _meals(values)
        return self._out(services.update_diet_plan(self.get_object(), request.user, values, meals))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        values = self._decision(request)
        return self._out(services.approve_diet_plan(self.get_object(), request.user, values.get("VetNote")))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        values = self._decision(request)
        return self._out(services.reject_diet_plan(self.get_object(), request.user, values.get("VetNote")))

    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        values = self._decision(request)
        note = values.pop("VetNote", None)
        meals = _meals(values)
        return self._out(services.adjust_diet_plan(self.get_object(), request.user, note, values, meals))


# ---------------------------------------------------------------------------
# Việc chăm sóc
# ---------------------------------------------------------------------------
class CareTaskViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/care-tasks?Date=&From=&To=&HorseID=&GroomID=&Status=&mine=1
    POST /api/care-tasks                     Head Trainer / Manager giao việc, Groom tự tạo
    PATCH /api/care-tasks/<id>               sửa việc chưa làm
    POST /api/care-tasks/<id>/complete       Groom xác nhận đã làm   {"Note"?}
    POST /api/care-tasks/<id>/skip           bỏ qua                  {"Reason"}
    """

    serializer_class = CareTaskSerializer
    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get_queryset(self):
        qs = CareTask.objects.filter(horse__club_id=self.request.user.club_id).select_related(
            "horse", "groom", "assigned_by")
        p = self.request.query_params
        if p.get("Date"):
            day = date_param(p, "Date")
            qs = qs.filter(scheduled_at__gte=datetime.combine(day, time.min),
                           scheduled_at__lte=datetime.combine(day, time.max))
        if p.get("From"):
            qs = qs.filter(scheduled_at__gte=datetime.combine(date_param(p, "From"), time.min))
        if p.get("To"):
            qs = qs.filter(scheduled_at__lte=datetime.combine(date_param(p, "To"), time.max))
        if p.get("HorseID"):
            qs = qs.filter(horse_id=int_param(p, "HorseID"))
        if p.get("GroomID"):
            qs = qs.filter(groom_id=int_param(p, "GroomID"))
        if p.get("Status"):
            qs = qs.filter(status=p["Status"])
        if flag_param(p, "mine"):
            qs = qs.filter(groom=self.request.user)
        return qs

    def _out(self, task, code=status.HTTP_200_OK):
        return Response(CareTaskSerializer(self.get_queryset().get(pk=task.pk)).data, status=code)

    def _require_care_role(self):
        if not (self.request.user.has_perm("CARE_MANAGE") or services.is_care_assigner(self.request.user)):
            raise PermissionDenied("Bạn không có quyền quản lý việc chăm sóc.")

    def create(self, request):
        self._require_care_role()
        data = CareTaskWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        horse = get_visible_horse(request.user, values.pop("HorseID"))
        groom_id = values.pop("GroomID", None)
        return self._out(services.create_care_task(horse, request.user, values, groom_id), status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        self._require_care_role()
        data = CareTaskWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        values.pop("HorseID", None)
        groom_id = values.pop("GroomID", None)
        return self._out(services.update_care_task(self.get_object(), request.user, values, groom_id))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        data = NoteSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        return self._out(services.complete_care_task(self.get_object(), request.user, data.validated_data.get("Note")))

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        self._require_care_role()
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.skip_care_task(self.get_object(), request.user, data.validated_data["Reason"]))


# ---------------------------------------------------------------------------
# Kho vật tư
# ---------------------------------------------------------------------------
INVENTORY_ANY = ("INVENTORY_MANAGE", "INVENTORY_REQUEST")


class InventoryItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET   /api/inventory-items?ItemType=&Status=&LowStock=1
    POST  /api/inventory-items                 Manager thêm vật tư
    PATCH /api/inventory-items/<id>            Manager sửa / ngưng dùng
    POST  /api/inventory-items/<id>/stock      Manager nhập kho / điều chỉnh {"Change": 50, "Note"}
    """

    serializer_class = InventoryItemSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasAnyPermission(*INVENTORY_ANY)()]
        return [HasAnyPermission("INVENTORY_MANAGE")()]

    def get_queryset(self):
        qs = InventoryItem.objects.filter(club_id=self.request.user.club_id)
        p = self.request.query_params
        if p.get("ItemType"):
            qs = qs.filter(item_type=p["ItemType"])
        if p.get("Status"):
            qs = qs.filter(status=p["Status"])
        if flag_param(p, "LowStock"):
            qs = qs.filter(status__in=(InventoryItem.Status.LOW_STOCK, InventoryItem.Status.OUT_OF_STOCK))
        return qs

    def create(self, request):
        data = InventoryItemWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = services.save_item(request.user, dict(data.validated_data), club_id=request.user.club_id)
        return Response(InventoryItemSerializer(item).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        data = InventoryItemWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if "quantity" in values:
            raise ValidationError({"Quantity": ["Đổi tồn kho qua POST /inventory-items/<id>/stock."]})
        return Response(InventoryItemSerializer(services.save_item(request.user, values, self.get_object())).data)

    @action(detail=True, methods=["post"])
    def stock(self, request, pk=None):
        data = StockSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        item = services.adjust_stock(self.get_object(), request.user, v["Change"], v.get("Note"))
        return Response(InventoryItemSerializer(item).data)


class InventoryRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/inventory-requests?Status=Pending&mine=1  (Manager: cả CLB; người gửi: của mình)
    POST /api/inventory-requests                        Groom / Head Trainer gửi yêu cầu
    POST /api/inventory-requests/<id>/approve           Manager duyệt + xuất kho  {"Items": [{"InventoryItemID", "ApprovedQuantity"}]}
    POST /api/inventory-requests/<id>/reject            Manager từ chối           {"Note"}
    POST /api/inventory-requests/<id>/cancel            người gửi hủy (khi còn Pending)
    """

    serializer_class = InventoryRequestSerializer

    action_permissions = {
        "create": ("INVENTORY_REQUEST",),
        "cancel": ("INVENTORY_REQUEST",),
        "approve": ("INVENTORY_MANAGE",),
        "reject": ("INVENTORY_MANAGE",),
    }

    def get_permissions(self):
        return [HasAnyPermission(*self.action_permissions.get(self.action, INVENTORY_ANY))()]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryRequest.objects.filter(club_id=user.club_id).select_related(
            "requested_by", "approved_by").prefetch_related("items__item")
        if not user.has_perm("INVENTORY_MANAGE") or flag_param(self.request.query_params, "mine"):
            qs = qs.filter(requested_by=user)
        if self.request.query_params.get("Status"):
            qs = qs.filter(status=self.request.query_params["Status"])
        return qs

    def _out(self, req, code=status.HTTP_200_OK):
        return Response(InventoryRequestSerializer(
            InventoryRequest.objects.prefetch_related("items__item").get(pk=req.pk)).data, status=code)

    def create(self, request):
        data = InventoryRequestCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        req = services.create_inventory_request(request.user, v.get("Reason"), [dict(i) for i in v["Items"]])
        return self._out(req, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = InventoryApproveSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        approved = {i["InventoryItemID"]: i["ApprovedQuantity"] for i in data.validated_data.get("Items", [])}
        return self._out(services.approve_inventory_request(self.get_object(), request.user, approved))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        data = RejectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.reject_inventory_request(self.get_object(), request.user,
                                                           data.validated_data["Note"]))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._out(services.cancel_inventory_request(self.get_object(), request.user))

