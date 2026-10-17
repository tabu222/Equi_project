import secrets

from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import emails
from apps.core.audit import log_action
from apps.core.permissions import HasAnyPermission, user_has_any

from .models import Role, User, UserRole
from .google_auth import verify_google_credential
from .serializers import (
    CurrentUserSerializer, GoogleLoginSerializer, GoogleSignupSerializer, LoginSerializer, OwnerRegisterSerializer,
    UserCreateSerializer, UserSerializer,
)


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


class RegisterThrottle(AnonRateThrottle):
    rate = "20/hour"  # chặn spam tạo tài khoản hàng loạt


class RegisterView(APIView):
    """
    POST /api/auth/register  (không cần đăng nhập) - chủ ngựa tự tạo tài khoản.
    body: {"FullName", "Email", "Phone", "Address", "Password", "ClubID"}
    -> 201 {"access", "refresh", "User"}  (đăng nhập luôn, giống /api/auth/login)
    Vai trò luôn là HORSE_OWNER; nhân viên CLB vẫn do Manager tạo qua POST /api/users.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    @extend_schema(request=OwnerRegisterSerializer, auth=[], summary="Chủ ngựa tự đăng ký tài khoản")
    def post(self, request):
        data = OwnerRegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = User.objects.create_user(
            email=v["Email"],
            password=v["Password"],
            full_name=v["FullName"].strip(),
            phone=v["Phone"],
            address=v["Address"].strip(),
            club_id=v["ClubID"],
        )
        UserRole.objects.create(user=user, role=Role.objects.get(code="HORSE_OWNER"), assigned_by=None)
        log_action(user, "REGISTER_OWNER", user, {"ClubID": v["ClubID"]})
        emails.account_registered(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "User": CurrentUserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


def _token_response(user, code=status.HTTP_200_OK):
    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "User": CurrentUserSerializer(user).data,
    }, status=code)


class GoogleThrottle(AnonRateThrottle):
    rate = "120/hour"


class GoogleLoginView(APIView):
    """
    POST /api/auth/google  (không cần đăng nhập)
      {"Credential": "<ID token Google>"}
        -> email đã có tài khoản: 200 {access, refresh, User}  (mọi vai trò, kể cả nhân viên CLB)
        -> chưa có: 200 {"SignupRequired": true, "Email", "FullName"}  -> FE hỏi thêm thông tin
      {"Credential", "FullName"?, "Phone", "Address", "ClubID"}
        -> tạo tài khoản CHỦ NGỰA (không có mật khẩu, đăng nhập bằng Google): 201 {access, refresh, User}
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [GoogleThrottle]

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'

    @extend_schema(request=GoogleLoginSerializer, auth=[], summary="Đăng nhập / đăng ký bằng Google")
    def post(self, request):
        data = GoogleLoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        google = verify_google_credential(data.validated_data["Credential"])
        user = User.objects.filter(email__iexact=google["email"]).first()
        if user is not None:
            if not user.is_active:
                raise AuthenticationFailed("Email hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.")
            log_action(user, "LOGIN_GOOGLE", user)
            return _token_response(user)

        if not data.wants_signup:
            return Response({"SignupRequired": True, "Email": google["email"], "FullName": google["name"]})

        body = {key: data.validated_data.get(key) for key in ("Phone", "Address", "ClubID")}
        body["FullName"] = (data.validated_data.get("FullName") or google["name"]).strip()
        body["Email"] = google["email"]
        signup = GoogleSignupSerializer(data=body)
        signup.is_valid(raise_exception=True)
        v = signup.validated_data
        user = User.objects.create_user(
            email=v["Email"], password=None, full_name=v["FullName"], phone=v["Phone"],
            address=v["Address"].strip(), club_id=v["ClubID"],
        )
        UserRole.objects.create(user=user, role=Role.objects.get(code="HORSE_OWNER"), assigned_by=None)
        log_action(user, "REGISTER_OWNER", user, {"ClubID": v["ClubID"], "Via": "Google"})
        emails.account_registered(user)
        return _token_response(user, status.HTTP_201_CREATED)


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

    # Trainer chỉ có TRAINING_SESSION_ASSIGN: chỉ cần danh sách người để xếp buổi tập (rider, trainer giám sát thay)
    SESSION_ROLES = ("WORK_RIDER", "TRAINER", "HEAD_TRAINER")

    def get(self, request):
        users = User.objects.filter(club_id=request.user.club_id).prefetch_related("roles")
        role_code = request.query_params.get("RoleCode")
        if not user_has_any(request.user, "RBAC_MANAGE", "HORSE_REGISTER_REVIEW", "TRAINER_ASSIGN"):
            if role_code and role_code not in self.SESSION_ROLES:
                raise PermissionDenied("Bạn chỉ xem được danh sách Work Rider / Trainer.")
            users = users.filter(roles__code__in=self.SESSION_ROLES)
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
        emails.account_created_by_manager(user, request.user)
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
