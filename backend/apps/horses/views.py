from pathlib import Path
import json
from django.conf import settings
from django.db import transaction

from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
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

from . import documents as documents_store
from . import services
from .models import Horse, HorseDocument, ProfileChangeRequest, Stall
from .serializers import (
    ApproveSerializer, HorseCreateSerializer, HorseDetailSerializer, HorseDocumentSerializer,
    HorseDocumentUploadSerializer, HorseSerializer,
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
        "profile_change_options": ("PROFILE_EDIT_REQUEST",),
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
        return queryset.select_for_update() if self.request.method not in ("GET", "HEAD", "OPTIONS") else queryset

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
    @extend_schema(methods=["POST"], request={"multipart/form-data": HorseDocumentUploadSerializer,
                                               "application/json": HorseDocumentSerializer},
                   responses=HorseDocumentSerializer, summary="Tải file giấy tờ / ảnh (multipart) hoặc lưu link (JSON)")
    @action(detail=True, methods=["get", "post"], parser_classes=[JSONParser, MultiPartParser, FormParser])
    def documents(self, request, pk=None):
        """
        GET  -> danh sách giấy tờ (Owner chỉ thấy giấy tờ IsVisibleToOwner).
        POST multipart/form-data {File, DocumentType, DocumentName?, IsVisibleToOwner?} -> tải file lên.
        POST JSON {DocumentName, DocumentType, FileUrl, IsVisibleToOwner?} -> lưu link ngoài (giữ như cũ).
        """
        horse = self.get_object()
        owner_only = not request.user.has_perm(STAFF_VIEW)
        if request.method == "GET":
            documents = horse.documents.select_related("uploaded_by").filter(is_retired=False)
            if owner_only:
                documents = documents.filter(is_visible_to_owner=True)
            return Response(HorseDocumentSerializer(documents, many=True).data)

        if not can_manage_registration(request.user, horse):
            raise PermissionDenied("Bạn không được thêm giấy tờ cho ngựa này.")
        if owner_only and horse.registration_status == Horse.RegistrationStatus.APPROVED:
            raise BusinessRuleError("Hãy gửi tài liệu trong yêu cầu cập nhật hồ sơ để Manager duyệt.", "APPROVAL_REQUIRED")
        if horse.registration_status == Horse.RegistrationStatus.ARCHIVED:
            raise BusinessRuleError("Ngựa đã lưu trữ, không thêm giấy tờ được.", "INVALID_STATUS")

        if "File" in request.FILES or (request.content_type or "").startswith("multipart/"):
            data = HorseDocumentUploadSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            v = data.validated_data
            file = v["File"]
            file_url = documents_store.save_upload(horse.id, file)
            name = (v.get("DocumentName") or "").strip() or Path(file.name).name[:150]
            visible = True if owner_only else v.get("IsVisibleToOwner", True)
            document = HorseDocument.objects.create(
                horse=horse, document_name=name, document_type=v["DocumentType"], file_url=file_url,
                uploaded_by=request.user, is_visible_to_owner=visible,
                is_profile_image=v["DocumentType"] == "Other" and documents_store.content_type(file_url).startswith("image/"),
            )
        else:
            data = HorseDocumentSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            extra = {"is_visible_to_owner": True} if owner_only else {}
            document = data.save(horse=horse, uploaded_by=request.user, **extra)
        log_action(request.user, "ADD_DOCUMENT", horse, {"DocumentID": document.id})
        return Response(HorseDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    # ---------------- yêu cầu sửa lý lịch ----------------
    @action(detail=True, methods=["get"], url_path="profile-change-options")
    def profile_change_options(self, request, pk=None):
        horse = self.get_object()
        if not is_owner_of(request.user, horse):
            raise PermissionDenied()
        return Response({"MaxFileMB": settings.UPLOAD_MAX_MB,
                         "MaxFiles": settings.CHANGE_REQUEST_MAX_FILES,
                         "DocumentTypes": list(HorseDocument.DocumentType.values),
                         "ClearableFields": []})

    @action(detail=True, methods=["post"], url_path="profile-change-requests",
            parser_classes=[JSONParser, MultiPartParser])
    def profile_change_requests(self, request, pk=None):
        horse = self.get_object()
        if not is_owner_of(request.user, horse):
            raise PermissionDenied("Chỉ chủ ngựa được gửi yêu cầu sửa lý lịch.")
        body = request.data
        if (request.content_type or "").startswith("multipart/"):
            try:
                body = json.loads(request.data.get("Payload", ""))
            except (TypeError, ValueError):
                raise ValidationError({"Payload": ["Nội dung yêu cầu không đúng JSON."]})
        data = ProfileChangeRequestCreateSerializer(data=body)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        change = services.create_change_request(horse, request.user, v["Changes"], v["Reason"],
                                                v.get("EvidenceDocumentID"), files=request.FILES,
                                                **{k: value for k, value in v.items()
                                                   if k not in ("Changes", "Reason", "EvidenceDocumentID")})
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
        if self.action == "withdraw":
            return [HasAnyPermission("PROFILE_EDIT_REQUEST")()]
        return [HasAnyPermission("PROFILE_EDIT_APPROVE", "PROFILE_EDIT_REQUEST")()]

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        from .change_requests import withdraw
        return Response(ProfileChangeRequestSerializer(withdraw(self.get_object(), request.user)).data)

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<attachment_index>[0-9]+)")
    def attachment_file(self, request, pk=None, attachment_index=None):
        change = self.get_object()
        items = json.loads(change.changed_fields).get("Attachments", [])
        index = int(attachment_index)
        if index >= len(items) or not items[index].get("StoredFile"):
            raise NotFound("Không tìm thấy file.")
        item = items[index]
        path = documents_store.stored_path(item["StoredFile"])
        if not path.is_file():
            raise NotFound("Không tìm thấy file trên máy chủ.")
        response = FileResponse(open(path, "rb"), content_type=documents_store.content_type(item["StoredFile"]),
                                as_attachment=request.query_params.get("download") == "1",
                                filename=item.get("OriginalName", item["DocumentName"]))
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response

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
    """GET /api/clubs - danh sách CLB đang hoạt động (công khai: trang đăng ký tài khoản / đăng ký ngựa)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response([
            {"ClubID": club.id, "ClubName": club.club_name, "Address": club.address}
            for club in Club.objects.filter(status="Active")
        ])


class HorseDocumentDetailView(APIView):
    """
    DELETE /api/horse-documents/<DocumentID>
      - Owner: xóa giấy tờ mình đã tải khi hồ sơ còn Nháp / Bị từ chối.
      - Manager: xóa giấy tờ của ngựa trong CLB mình.
      - Giấy tờ đang làm bằng chứng cho yêu cầu sửa lý lịch thì không xóa được.
    """

    @transaction.atomic
    def delete(self, request, document_id):
        document = get_visible_document(request.user, document_id)
        horse = Horse.objects.select_for_update().get(pk=document.horse_id)
        if not can_manage_registration(request.user, horse):
            raise PermissionDenied("Bạn không được xóa giấy tờ của ngựa này.")
        if not request.user.has_perm("HORSE_REGISTER_REVIEW"):
            if document.uploaded_by_id != request.user.pk:
                raise PermissionDenied("Chỉ xóa được giấy tờ do chính bạn tải lên.")
            if horse.registration_status not in services.EDITABLE_STATUSES:
                raise BusinessRuleError("Hồ sơ đã gửi, không xóa giấy tờ được nữa.", "INVALID_STATUS")
        if ProfileChangeRequest.objects.filter(evidence_document=document).exists():
            raise BusinessRuleError("Giấy tờ đang là bằng chứng của yêu cầu sửa lý lịch, không xóa được.",
                                    "DOCUMENT_IN_USE")
        for change in horse.profile_change_requests.all():
            payload = json.loads(change.changed_fields)
            referenced = [i.get("DocumentID") for i in payload.get("EvidenceDocuments", []) + payload.get("RemovedImages", [])]
            referenced += [i.get("id") for i in payload.get("Snapshot", {}).get("Documents", [])]
            if document.id in referenced or any(i.get("StoredFile") == document.file_url
                                                for i in payload.get("Attachments", [])):
                raise BusinessRuleError("Tệp thuộc lịch sử yêu cầu, không được xóa vĩnh viễn.", "DOCUMENT_IN_USE")
        file_url = document.file_url
        log_action(request.user, "DELETE_DOCUMENT", horse, {"DocumentID": document.id,
                                                           "DocumentName": document.document_name})
        document.delete()
        documents_store.delete_file(file_url)
        return Response(status=status.HTTP_204_NO_CONTENT)


class HorseDocumentFileView(APIView):
    """GET /api/horse-documents/<DocumentID>/file -> nội dung file đã tải lên (người được xem ngựa mới tải được)."""

    def get(self, request, document_id):
        document = get_visible_document(request.user, document_id)
        if not documents_store.is_upload(document.file_url):
            raise NotFound("Giấy tờ này là link ngoài, mở bằng FileUrl.")
        path = documents_store.stored_path(document.file_url)
        if not path.exists():
            raise NotFound("Không tìm thấy file trên máy chủ.")
        filename = document.document_name
        if not Path(filename).suffix:
            filename += path.suffix
        return FileResponse(open(path, "rb"), content_type=documents_store.content_type(document.file_url),
                            as_attachment=request.query_params.get("download") == "1", filename=filename)


def get_visible_document(user, document_id):
    document = HorseDocument.objects.select_related("horse").filter(pk=document_id).first()
    if document is None:
        raise NotFound("Không tìm thấy giấy tờ.")
    get_visible_horse(user, document.horse_id)
    if not user.has_perm(STAFF_VIEW) and not document.is_visible_to_owner:
        raise NotFound("Không tìm thấy giấy tờ.")
    return document


def get_visible_horse(user, horse_id):
    horse = horses_visible_to(user).filter(pk=horse_id).first()
    if horse is None:
        raise NotFound("Không tìm thấy ngựa.")
    return horse


__all__ = ["HorseViewSet", "ProfileChangeRequestViewSet", "StallListView", "ClubListView",
           "get_visible_horse", "get_object_or_404"]
