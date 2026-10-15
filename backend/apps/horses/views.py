from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Club, User
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog
from apps.core.params import int_param
from apps.core.permissions import HasAnyPermission, user_has_any
from apps.core.serializers import fmt_datetime
from apps.medical.services import annotate_initial_exam_signed

from . import services
from .models import Horse, ProfileChangeRequest, Stall
from .serializers import (
    ApproveSerializer, HorseCreateSerializer, HorseDetailSerializer, HorseDocumentSerializer, HorseSerializer,
    HorseWriteSerializer, ProfileChangeRequestCreateSerializer, ProfileChangeRequestSerializer, ReasonSerializer,
    RegistrationRequestSerializer, ReviewNoteSerializer, StallSerializer, StallWriteSerializer,
)

STAFF_VIEW = "HORSE_VIEW"            # nhân sự CLB: xem ngựa trong CLB mình
OWNER_PERMS = ("OWNER_VIEW", "HORSE_REGISTER")
REGISTER = ("HORSE_REGISTER", "HORSE_REGISTER_REVIEW")
REVIEW = ("HORSE_REGISTER_REVIEW",)


def horses_visible_to(user):
    """Nhân sự thấy ngựa trong CLB của mình; chủ ngựa chỉ thấy ngựa của mình."""
    queryset = Horse.objects.select_related("owner", "club")
    if user.has_perm(STAFF_VIEW):
        return queryset.filter(club_id=user.club_id)
    if user_has_any(user, *OWNER_PERMS):
        return queryset.filter(owner=user)
    return queryset.none()


def is_owner_of(user, horse) -> bool:
    return horse.owner_id == user.pk


def can_manage_registration(user, horse) -> bool:
    """Owner sửa / gửi hồ sơ ngựa của mình; Manager làm cho ngựa trong CLB mình."""
    if user.has_perm("HORSE_REGISTER_REVIEW") and horse.club_id == user.club_id:
        return True
    return user.has_perm("HORSE_REGISTER") and is_owner_of(user, horse)


class HorseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/horses ... xem chi tiết từng API trong docs/API.md.
    """

    action_permissions = {
        "create": REGISTER,
        "partial_update": REGISTER,
        "submit": REGISTER,
        "verify": REVIEW,
        "reject": REVIEW,
        "approve": REVIEW,
        "archive": ("HORSE_ARCHIVE",),
        "profile_change_requests": ("PROFILE_EDIT_REQUEST",),
        "audit_logs": ("AUDIT_VIEW",),
    }

    def get_permissions(self):
        codes = self.action_permissions.get(self.action)
        if codes:
            return [HasAnyPermission(*codes)()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = annotate_initial_exam_signed(horses_visible_to(self.request.user))
        params = self.request.query_params
        if params.get("RegistrationStatus"):
            queryset = queryset.filter(registration_status=params["RegistrationStatus"])
        if params.get("OwnerID"):
            queryset = queryset.filter(owner_id=int_param(params, "OwnerID"))
        if params.get("search"):
            term = params["search"].strip()
            queryset = queryset.filter(
                Q(horse_name__icontains=term) | Q(horse_code__icontains=term) | Q(microchip_number__icontains=term)
            )
        return queryset

    def get_serializer_class(self):
        return HorseDetailSerializer if self.action == "retrieve" else HorseSerializer

    def _detail(self, horse, code=status.HTTP_200_OK):
        horse = annotate_initial_exam_signed(Horse.objects.filter(pk=horse.pk)).select_related("owner").get()
        return Response(HorseDetailSerializer(horse).data, status=code)

    # ---------------- tạo / sửa hồ sơ ----------------
    def create(self, request):
        data = HorseCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        club_id = values.pop("ClubID", None)
        owner_id = values.pop("OwnerID", None)
        user = request.user

        if user.has_perm("HORSE_REGISTER_REVIEW"):
            # Manager nhập hộ: chủ ngựa phải là tài khoản Horse Owner
            if not owner_id:
                raise ValidationError({"OwnerID": ["Manager tạo hồ sơ cần chọn chủ ngựa (OwnerID)."]})
            owner = User.objects.filter(pk=owner_id, roles__code="HORSE_OWNER").first()
            if owner is None:
                raise ValidationError({"OwnerID": ["Không tìm thấy chủ ngựa với OwnerID này."]})
            if not user.club_id:
                raise BusinessRuleError(
                    "Tài khoản của bạn chưa thuộc câu lạc bộ nào (ClubID trống) nên chưa tạo được ngựa.", "USER_NO_CLUB"
                )
            club_id = user.club_id
        else:
            # Owner tự đăng ký vào một CLB đang hoạt động
            owner = user
            if not club_id or not Club.objects.filter(pk=club_id, status="Active").exists():
                raise ValidationError({"ClubID": ["Cần chọn câu lạc bộ đang hoạt động (ClubID)."]})

        horse = Horse(club_id=club_id, owner=owner, **values)
        horse.save()
        log_action(user, "CREATE_HORSE", horse)
        return self._detail(horse, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        horse = self.get_object()
        if not can_manage_registration(request.user, horse):
            raise PermissionDenied("Bạn không được sửa hồ sơ ngựa này.")
        services.ensure_editable(horse)
        data = HorseWriteSerializer(horse, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        horse.touch()
        horse.save(update_fields=["updated_at"])
        log_action(request.user, "UPDATE_HORSE", horse, request.data)
        return self._detail(horse)

    # ---------------- luồng tiếp nhận ----------------
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        horse = self.get_object()
        if not can_manage_registration(request.user, horse):
            raise PermissionDenied("Bạn không được gửi hồ sơ ngựa này.")
        return self._detail(services.submit(horse, request.user))

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        return self._detail(services.verify(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._detail(services.reject(self.get_object(), request.user, data.validated_data["Reason"]))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = ApproveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        horse = services.approve(self.get_object(), request.user, v["HorseCode"], v.get("StallID"),
                                 v.get("ManagerNote"))
        return self._detail(horse)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._detail(services.archive(self.get_object(), request.user, data.validated_data["Reason"]))

    @action(detail=True, methods=["get"], url_path="registration-requests")
    def registration_requests(self, request, pk=None):
        horse = self.get_object()
        return Response(RegistrationRequestSerializer(horse.registration_requests.all(), many=True).data)

    # ---------------- giấy tờ ----------------
    @action(detail=True, methods=["get", "post"])
    def documents(self, request, pk=None):
        horse = self.get_object()
        owner_only = not request.user.has_perm(STAFF_VIEW)
        if request.method == "GET":
            documents = horse.documents.all()
            if owner_only:
                documents = documents.filter(is_visible_to_owner=True)
            return Response(HorseDocumentSerializer(documents, many=True).data)

        if not can_manage_registration(request.user, horse):
            raise PermissionDenied("Bạn không được thêm giấy tờ cho ngựa này.")
        data = HorseDocumentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        extra = {"is_visible_to_owner": True} if owner_only else {}
        document = data.save(horse=horse, uploaded_by=request.user, **extra)
        log_action(request.user, "ADD_DOCUMENT", horse, {"DocumentID": document.id})
        return Response(HorseDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    # ---------------- yêu cầu sửa lý lịch ----------------
    @action(detail=True, methods=["post"], url_path="profile-change-requests")
    def profile_change_requests(self, request, pk=None):
        horse = self.get_object()
        if not is_owner_of(request.user, horse):
            raise PermissionDenied("Chỉ chủ ngựa được gửi yêu cầu sửa lý lịch.")
        data = ProfileChangeRequestCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        change = services.create_change_request(horse, request.user, v["Changes"], v["Reason"],
                                                v.get("EvidenceDocumentID"))
        return Response(ProfileChangeRequestSerializer(change).data, status=status.HTTP_201_CREATED)

    # ---------------- lịch sử thao tác ----------------
    @action(detail=True, methods=["get"], url_path="audit-logs")
    def audit_logs(self, request, pk=None):
        horse = self.get_object()
        logs = AuditLog.objects.filter(entity_name="Horse", entity_id=horse.pk).select_related("user")
        return Response([
            {"AuditLogID": log.id, "UserID": log.user_id, "FullName": log.user.full_name if log.user else None,
             "ActionType": log.action_type, "ActionTime": fmt_datetime(log.action_time), "Details": log.details}
            for log in logs
        ])


class ProfileChangeRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/profile-change-requests?Status=Pending   Manager: trong CLB; Owner: của mình
    POST /api/profile-change-requests/<id>/approve      Manager duyệt -> áp dụng thay đổi vào Horse
    POST /api/profile-change-requests/<id>/reject       Manager từ chối (cần ReviewNote)
    """

    serializer_class = ProfileChangeRequestSerializer

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [HasAnyPermission("PROFILE_EDIT_APPROVE")()]
        return [HasAnyPermission("PROFILE_EDIT_APPROVE", "PROFILE_EDIT_REQUEST")()]

    def get_queryset(self):
        user = self.request.user
        queryset = ProfileChangeRequest.objects.select_related("horse")
        if user.has_perm("PROFILE_EDIT_APPROVE"):
            queryset = queryset.filter(horse__club_id=user.club_id)
        else:
            queryset = queryset.filter(horse__owner=user)
        if self.request.query_params.get("Status"):
            queryset = queryset.filter(status=self.request.query_params["Status"])
        if self.request.query_params.get("HorseID"):
            queryset = queryset.filter(horse_id=int_param(self.request.query_params, "HorseID"))
        return queryset

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = ReviewNoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        change = services.approve_change_request(self.get_object(), request.user, data.validated_data.get("ReviewNote"))
        return Response(ProfileChangeRequestSerializer(change).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        data = ReviewNoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        change = services.reject_change_request(self.get_object(), request.user, data.validated_data.get("ReviewNote"))
        return Response(ProfileChangeRequestSerializer(change).data)


class StallListView(APIView):
    """
    GET  /api/stalls?Status=Available - chuồng trong CLB, kèm ngựa đang ở (Manager chọn khi duyệt hồ sơ)
    POST /api/stalls {"StallNumber": "A05", "StallType": "Standard"} - Manager thêm chuồng
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission("CLUB_MANAGE")()]
        return [HasAnyPermission("HORSE_REGISTER_REVIEW", STAFF_VIEW)()]

    def get(self, request):
        stalls = Stall.objects.filter(club_id=request.user.club_id)
        if request.query_params.get("Status"):
            stalls = stalls.filter(status=request.query_params["Status"])
        return Response(StallSerializer(stalls, many=True).data)

    def post(self, request):
        data = StallWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        stall = services.save_stall(request.user, dict(data.validated_data), club_id=request.user.club_id)
        return Response(StallSerializer(stall).data, status=status.HTTP_201_CREATED)


class StallDetailView(APIView):
    """PATCH /api/stalls/<id> {"StallType"?, "Status": "Maintenance" | "Available"}"""

    permission_classes = [HasAnyPermission("CLUB_MANAGE")]

    def patch(self, request, stall_id):
        stall = Stall.objects.filter(pk=stall_id, club_id=request.user.club_id).first()
        if stall is None:
            raise NotFound("Không tìm thấy chuồng.")
        data = StallWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(StallSerializer(services.save_stall(request.user, dict(data.validated_data), stall)).data)


class MoveStallView(APIView):
    """POST /api/horses/<HorseID>/move-stall {"StallID": 3} - chuyển ngựa sang chuồng khác (hoặc xếp chuồng lần đầu)."""

    permission_classes = [HasAnyPermission("CLUB_MANAGE", "HORSE_REGISTER_REVIEW")]

    def post(self, request, horse_id):
        horse = get_visible_horse(request.user, horse_id)
        stall_id = int_param(request.data, "StallID")
        if not stall_id:
            raise ValidationError({"StallID": ["Cần chọn chuồng."]})
        services.move_stall(horse, request.user, stall_id)
        horse = annotate_initial_exam_signed(Horse.objects.filter(pk=horse.pk)).select_related("owner").get()
        return Response(HorseDetailSerializer(horse).data)


class ClubListView(APIView):
    """GET /api/clubs - danh sách CLB đang hoạt động (Owner chọn CLB khi tự đăng ký ngựa)."""

    def get(self, request):
        return Response([
            {"ClubID": club.id, "ClubName": club.club_name, "Address": club.address}
            for club in Club.objects.filter(status="Active")
        ])


def get_visible_horse(user, horse_id):
    horse = horses_visible_to(user).filter(pk=horse_id).first()
    if horse is None:
        raise NotFound("Không tìm thấy ngựa.")
    return horse


__all__ = ["HorseViewSet", "ProfileChangeRequestViewSet", "StallListView", "ClubListView",
           "get_visible_horse", "get_object_or_404"]
