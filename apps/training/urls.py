from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=False)
router.include_root_view = False
router.register("trainer-assignments", views.TrainerAssignmentViewSet, basename="trainer-assignment")
router.register("training-plans", views.TrainingPlanViewSet, basename="training-plan")
router.register("training-sessions", views.TrainingSessionViewSet, basename="training-session")

urlpatterns = [
    path("specializations", views.SpecializationListView.as_view()),
    path("trainers", views.TrainerListView.as_view()),
    path("trainers/<int:user_id>/specializations", views.TrainerSpecializationView.as_view()),
    path("trainers/<int:user_id>/specializations/<int:spec_id>", views.TrainerSpecializationView.as_view()),
    path("horses/<int:horse_id>/assessments", views.HorseAssessmentView.as_view()),
    path("horses/<int:horse_id>/work-rider-preferences", views.WorkRiderPreferenceView.as_view()),
    path("work-rider-preferences/<int:pref_id>/end", views.WorkRiderPreferenceEndView.as_view()),
    path("training-plan-stages/<int:stage_id>", views.TrainingPlanStageView.as_view()),
    path("training-reviews", views.TrainingReviewListView.as_view()),
    path("training-dashboard", views.TrainingDashboardView.as_view()),
    *router.urls,
]
