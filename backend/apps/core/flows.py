"""
Backend được nộp từng flow. Flow 1 luôn có; Flow 2-4 thêm dần:

    Flow 2 - Huấn luyện   apps/training           (có trong INSTALLED_APPS)
    Flow 3 - Y tế         apps/medical có thêm Training Lock, báo cáo sức khỏe...
    Flow 4 - Chăm sóc     apps/care

Chức năng của flow trước mà cần flow sau (ví dụ Training Lock chặn buổi tập) chỉ chạy khi flow sau
đã có; khi chưa có thì bỏ qua, không báo lỗi.
"""
from django.conf import settings


def has_training() -> bool:
    """Flow 2 - huấn luyện."""
    return "apps.training" in settings.INSTALLED_APPS


def has_flow3() -> bool:
    """Flow 3 - y tế: nhận ra bằng model TrainingLock trong apps/medical (Flow 1 chỉ có phiếu khám)."""
    try:
        from apps.medical import models
    except ImportError:
        return False
    return hasattr(models, "TrainingLock") and hasattr(models, "HealthReport")


def has_care() -> bool:
    """Flow 4 - chăm sóc."""
    return "apps.care" in settings.INSTALLED_APPS
