from django.urls import path

from . import views
from .notifications import NotificationView

urlpatterns = [
    path("health", views.health, name="health"),
    path("notifications", NotificationView.as_view(), name="notifications"),
]
