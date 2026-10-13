import secrets

from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.audit import log_action
from apps.core.permissions import HasAnyPermission, user_has_any

from .models import Role, User, UserRole
from .serializers import CurrentUserSerializer, LoginSerializer, UserCreateSerializer, UserSerializer


class LoginView(APIView):
    """
    POST /api/auth/login   body: {"Email": "...", "Password": "..."}
    -> {"access": "<JWT>", "refresh": "<JWT>", "User": {...kèm Roles, Permissions}}
    Frontend gửi access token trong header:  Authorization: Bearer <access>
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'  # để sai mật khẩu trả 401 (không phải 403)

    @extend_schema(request=LoginSerializer, auth=[], summary="Đăng nhập, lấy access / refresh token")
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(request, username=data.validated_data["Email"], password=data.validated_data["Password"])
        if user is None:
            raise AuthenticationFailed("Email hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.")
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "User": CurrentUserSerializer(user).data,
        })


class MeView(APIView):
    """GET /api/auth/me -> người đang đăng nhập, kèm Roles và Permissions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class UserListCreateView(APIView):
    """
    GET  /api/users?RoleCode=HORSE_OWNER  -> người dùng trong CLB của mình (Manager, Head Trainer)
    POST /api/users                       -> Manager tạo tài khoản (mặc định chủ ngựa)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission("RBAC_MANAGE")()]
        # Manager; Head Trainer cần danh sách Trainer / Work Rider / Groom để phân công
        return [HasAnyPermission("RBAC_MANAGE", "HORSE_REGISTER_REVIEW", "TRAINER_ASSIGN", "TRAINING_SESSION_ASSIGN")()]

    def get(self, request):
        users = User.objects.filter(club_id=request.user.club_id).prefetch_related("roles")
        role_code = request.query_params.get("RoleCode")
        if role_code:
            users = users.filter(roles__code=role_code)
        return Response(UserSerializer(users.distinct(), many=True).data)

    def post(self, request):
        data = UserCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        temporary_password = v.get("Password") or secrets.token_urlsafe(9)
        user = User.objects.create_user(
            email=v["Email"],
            password=temporary_password,
            full_name=v["FullName"],
            phone=v.get("Phone") or None,
            address=v.get("Address") or None,
            club_id=request.user.club_id,
        )
        UserRole.objects.create(user=user, role=Role.objects.get(code=v["RoleCode"]), assigned_by=request.user)
        log_action(request.user, "CREATE_USER", user, {"RoleCode": v["RoleCode"]})
        body = UserSerializer(user).data
        if not v.get("Password"):
            body["TemporaryPassword"] = temporary_password  # chỉ trả một lần để Manager báo cho chủ ngựa
        return Response(body, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    """GET /api/users/<UserID> - chính mình, hoặc Manager xem người trong CLB."""

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        is_self = user.pk == request.user.pk
        same_club_manager = (
            user_has_any(request.user, "RBAC_MANAGE", "HORSE_REGISTER_REVIEW")
            and user.club_id == request.user.club_id
        )
        if not (is_self or same_club_manager):
            raise PermissionDenied("Bạn không có quyền xem người dùng này.")
        return Response(UserSerializer(user).data)
