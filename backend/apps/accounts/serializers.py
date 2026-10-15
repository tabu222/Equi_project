import re

from rest_framework import serializers

from apps.core.serializers import DBColumnModelSerializer

from .models import Club, Role, User


class UserSerializer(DBColumnModelSerializer):
    """Thông tin người dùng (không bao giờ trả PasswordHash)."""

    Roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "club", "full_name", "email", "phone", "address", "status", "created_at", "Roles"]
        read_only_fields = fields

    def get_Roles(self, obj):
        return sorted(obj.role_codes)


class CurrentUserSerializer(UserSerializer):
    """Người đang đăng nhập: kèm danh sách quyền để frontend ẩn / hiện nút."""

    Permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["Permissions"]
        read_only_fields = fields

    def get_Permissions(self, obj):
        return sorted(obj.permission_codes)


class LoginSerializer(serializers.Serializer):
    Email = serializers.EmailField()
    Password = serializers.CharField(trim_whitespace=False)


PHONE_RE = re.compile(r"^(0\d{9}|\+84\d{9})$")


class UserCreateSerializer(serializers.Serializer):
    """Manager tạo tài khoản trong CLB của mình (mặc định là chủ ngựa)."""

    FullName = serializers.CharField(max_length=150)
    Email = serializers.EmailField(max_length=100)
    Phone = serializers.CharField(max_length=20, error_messages={
        "required": "Cần nhập số điện thoại (Phone).", "blank": "Cần nhập số điện thoại (Phone)."})
    Address = serializers.CharField(max_length=255, error_messages={
        "required": "Cần nhập địa chỉ (Address).", "blank": "Cần nhập địa chỉ (Address)."})
    RoleCode = serializers.CharField(required=False, default="HORSE_OWNER")
    Password = serializers.CharField(required=False, allow_blank=True, min_length=6, trim_whitespace=False)

    def validate_Email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email đã được sử dụng.")
        return value.lower()

    def validate_Phone(self, value):
        phone = value.replace(" ", "").replace(".", "")
        if not PHONE_RE.match(phone):
            raise serializers.ValidationError(
                "Số điện thoại không hợp lệ: 10 số bắt đầu bằng 0 (vd 0901234567) hoặc dạng +84 (vd +84901234567)."
            )
        return phone

    def validate_RoleCode(self, value):
        if not Role.objects.filter(code=value).exists():
            raise serializers.ValidationError("RoleCode không tồn tại.")
        return value


class OwnerRegisterSerializer(UserCreateSerializer):
    """Chủ ngựa tự tạo tài khoản ở trang đăng nhập (luôn là HORSE_OWNER, không chọn vai trò khác)."""

    RoleCode = None
    Password = serializers.CharField(min_length=6, trim_whitespace=False, error_messages={
        "required": "Cần nhập mật khẩu.", "blank": "Cần nhập mật khẩu.",
        "min_length": "Mật khẩu phải có ít nhất 6 ký tự."})
    ClubID = serializers.IntegerField(error_messages={
        "required": "Cần chọn câu lạc bộ.", "invalid": "Cần chọn câu lạc bộ."})

    def validate_ClubID(self, value):
        if not Club.objects.filter(pk=value, status="Active").exists():
            raise serializers.ValidationError("Câu lạc bộ không tồn tại hoặc đã ngừng hoạt động.")
        return value


class GoogleLoginSerializer(serializers.Serializer):
    """
    Bước 1: chỉ gửi Credential -> có tài khoản thì đăng nhập; chưa có thì trả SignupRequired.
    Bước 2 (chủ ngựa mới): gửi lại Credential kèm Phone, Address, ClubID (FullName không bắt buộc).
    """

    Credential = serializers.CharField(error_messages={"required": "Thiếu Credential từ Google."})
    FullName = serializers.CharField(max_length=150, required=False, allow_blank=True)
    Phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    Address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ClubID = serializers.IntegerField(required=False, allow_null=True)

    @property
    def wants_signup(self):
        v = self.validated_data
        return bool(v.get("Phone") or v.get("Address") or v.get("ClubID"))


class GoogleSignupSerializer(OwnerRegisterSerializer):
    """Kiểm tra thông tin bổ sung khi tạo tài khoản chủ ngựa bằng Google (không cần mật khẩu)."""

    Password = None
    FullName = serializers.CharField(max_length=150)
