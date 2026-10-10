from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=False)
router.include_root_view = False
router.register("diet-plans", views.DietPlanViewSet, basename="diet-plan")
router.register("care-tasks", views.CareTaskViewSet, basename="care-task")
router.register("inventory-items", views.InventoryItemViewSet, basename="inventory-item")
router.register("inventory-requests", views.InventoryRequestViewSet, basename="inventory-request")

urlpatterns = [
    path("horses/<int:horse_id>/diet-plans", views.HorseDietPlanView.as_view()),
    path("horses/<int:horse_id>/current-diet", views.CurrentDietView.as_view()),
    *router.urls,
]
