from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=False)
router.include_root_view = False
router.register("horses", views.HorseViewSet, basename="horse")
router.register("profile-change-requests", views.ProfileChangeRequestViewSet, basename="profile-change-request")

urlpatterns = [
    path("stalls", views.StallListView.as_view(), name="stall-list"),
    path("stalls/<int:stall_id>", views.StallDetailView.as_view(), name="stall-detail"),
    path("horses/<int:horse_id>/move-stall", views.MoveStallView.as_view(), name="move-stall"),
    path("clubs", views.ClubListView.as_view(), name="club-list"),
    *router.urls,
]
