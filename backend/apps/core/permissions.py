"""
Kiểm tra quyền theo PermissionCode trong database.

Ví dụ trong view:
    permission_classes = [HasAnyPermission("HORSE_REGISTER_REVIEW")]
Người dùng có ít nhất một trong các quyền liệt kê thì được phép.
Quyền của người dùng = các PermissionCode gắn với các Role của họ (UserRole -> RolePermission).
"""
from rest_framework.permissions import BasePermission


class _HasAnyPermission(BasePermission):
    message = "Bạn không có quyền thực hiện thao tác này."

    def __init__(self, codes):
        self.codes = tuple(codes)

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return any(user.has_perm(code) for code in self.codes)


class HasAnyPermission:
    """Dùng được trực tiếp trong permission_classes (DRF sẽ gọi để tạo instance)."""

    def __init__(self, *codes):
        self.codes = codes

    def __call__(self):
        return _HasAnyPermission(self.codes)


def user_has_any(user, *codes) -> bool:
    return bool(user and user.is_authenticated and any(user.has_perm(c) for c in codes))


def club_users_with_role(club_id, *role_codes):
    from apps.accounts.models import User

    return User.objects.filter(club_id=club_id, status="Active", roles__code__in=role_codes).distinct()


def require_club_user(user_id, club_id, *role_codes, field="UserID"):
    """Người được chọn (Work Rider, Trainer, Groom...) phải thuộc CLB và có đúng vai trò. Sai -> lỗi 400 ở `field`."""
    from rest_framework.exceptions import ValidationError

    found = club_users_with_role(club_id, *role_codes).filter(pk=user_id).first() if user_id else None
    if found is None:
        raise ValidationError({field: [f"Cần chọn người dùng đang hoạt động trong CLB có vai trò {' / '.join(role_codes)}."]})
    return found
