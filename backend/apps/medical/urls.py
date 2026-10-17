from django.urls import path

from . import views

urlpatterns = [
    # Phiếu khám
    path("vet/pending-initial-exams", views.PendingInitialExamView.as_view()),
    path("horses/<int:horse_id>/medical-records", views.HorseMedicalRecordListView.as_view()),
    path("medical-records/<int:record_id>", views.MedicalRecordDetailView.as_view()),
    path("medical-records/<int:record_id>/sign", views.MedicalRecordSignView.as_view()),
    path("medical-records/<int:record_id>/amendments", views.MedicalRecordAmendmentView.as_view()),
    # ---------------- Flow 3 ----------------
    # Thuốc kê trên phiếu khám
    path("medical-records/<int:record_id>/treatments", views.RecordTreatmentView.as_view()),
    path("treatments/<int:treatment_id>", views.TreatmentDetailView.as_view()),
    path("horses/<int:horse_id>/treatments", views.HorseTreatmentView.as_view()),
    # Training Lock
    path("training-locks", views.TrainingLockListView.as_view()),
    path("horses/<int:horse_id>/training-locks", views.HorseTrainingLockView.as_view()),
    path("training-locks/<int:lock_id>", views.TrainingLockDetailView.as_view()),
    path("training-locks/<int:lock_id>/release", views.TrainingLockReleaseView.as_view()),
    # Tiêm phòng, lịch y tế
    path("vaccinations", views.VaccinationListView.as_view()),
    path("horses/<int:horse_id>/vaccinations", views.VaccinationListView.as_view()),
    path("vaccinations/<int:vaccination_id>", views.VaccinationDetailView.as_view()),
    path("medical-schedules", views.MedicalScheduleListView.as_view()),
    path("horses/<int:horse_id>/medical-schedules", views.MedicalScheduleListView.as_view()),
    path("medical-schedules/<int:schedule_id>", views.MedicalScheduleDetailView.as_view()),
    # Báo cáo sức khỏe
    path("health-reports", views.HealthReportListView.as_view()),
    path("horses/<int:horse_id>/health-reports", views.HealthReportListView.as_view()),
    path("health-reports/<int:report_id>", views.HealthReportDetailView.as_view()),
    path("health-reports/<int:report_id>/notes", views.HealthReportNoteView.as_view()),
    path("health-reports/<int:report_id>/take", views.HealthReportTakeView.as_view()),
    path("health-reports/<int:report_id>/resolve", views.HealthReportResolveView.as_view()),
]
