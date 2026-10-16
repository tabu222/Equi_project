"""Xác minh "ID token" mà nút Đăng nhập với Google (Google Identity Services) trả về cho frontend."""
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

from apps.core.exceptions import BusinessRuleError


def verify_google_credential(credential: str) -> dict:
    """Trả về {"email", "name"} của tài khoản Google; token sai / hết hạn / khác Client ID -> 401."""
    if not settings.GOOGLE_CLIENT_ID:
        raise BusinessRuleError("Máy chủ chưa bật đăng nhập Google (thiếu GOOGLE_CLIENT_ID trong .env).",
                                "GOOGLE_LOGIN_DISABLED")
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        info = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except Exception as exc:  # noqa: BLE001 - ValueError / lỗi mạng khi lấy khóa của Google
        raise AuthenticationFailed("Không xác minh được tài khoản Google, vui lòng thử lại.") from exc
    if not info.get("email") or not info.get("email_verified"):
        raise AuthenticationFailed("Tài khoản Google này chưa xác minh email.")
    return {"email": info["email"].lower(), "name": info.get("name") or info["email"].split("@")[0]}
