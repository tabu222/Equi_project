from django.contrib.auth.backends import BaseBackend

from .models import User


class EmailBackend(BaseBackend):
    """Đăng nhập bằng Email + mật khẩu trong dbo.[User]. Quyền lấy từ Role -> Permission."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip()
        if not email or password is None:
            return None
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            User().set_password(password)  # vẫn chạy hash để không lộ email có tồn tại hay không
            return None
        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        user = User.objects.filter(pk=user_id).first()
        return user if user and user.is_active else None

    def has_perm(self, user_obj, perm, obj=None):
        return user_obj.is_active and perm in getattr(user_obj, "permission_codes", ())
