from django.urls import path

from . import views

urlpatterns = [
    # Phiếu khám
    path("vet/pending-initial-exams", views.PendingInitialExamView.as_view()),
    path("horses/<int:horse_id>/medical-records", views.HorseMedicalRecordListView.as_view()),
    path("medical-records/<int:record_id>", views.MedicalRecordDetailView.as_view()),
    path("medical-records/<int:record_id>/sign", views.MedicalRecordSignView.as_view()),
    path("medical-records/<int:record_id>/amendments", views.MedicalRecordAmendmentView.as_view()),
]
