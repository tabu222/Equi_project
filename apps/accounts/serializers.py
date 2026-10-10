from rest_framework import serializers

from apps.core.serializers import DBColumnModelSerializer

from .models import Role, User


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


class UserCreateSerializer(serializers.Serializer):
    """Manager tạo tài khoản trong CLB của mình (mặc định là chủ ngựa)."""

    FullName = serializers.CharField(max_length=150)
    Email = serializers.EmailField(max_length=100)
    Phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    Address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    RoleCode = serializers.CharField(required=False, default="HORSE_OWNER")
    Password = serializers.CharField(required=False, allow_blank=True, min_length=6, trim_whitespace=False)

    def validate_Email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email đã được sử dụng.")
        return value.lower()

    def validate_RoleCode(self, value):
        if not Role.objects.filter(code=value).exists():
            raise serializers.ValidationError("RoleCode không tồn tại.")
        return value
