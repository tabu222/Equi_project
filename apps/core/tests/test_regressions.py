"""Các lỗi đã tìm thấy khi rà soát; giữ test để không bị lặp lại."""
from datetime import timedelta

from apps.care.models import DietPlan
from apps.medical.models import HealthReport
from apps.training.models import TrainingSession

from .test_training import TODAY, TrainingTestCase


class RegressionTests(TrainingTestCase):
    def test_delete_draft_linked_to_report_and_treatment(self):
        horse_id = self.approved_horse()
        vet = self.client_for(self.vet)
        report = self.client_for(self.groom).post(f"/api/horses/{horse_id}/health-reports",
                                                  {"Description": "Bỏ ăn"}, format="json").data
        record = vet.post(f"/api/horses/{horse_id}/medical-records",
                          {"ExamType": "Routine Exam", "HealthReportID": report["HealthReportID"]}, format="json").data
        vet.post(f"/api/medical-records/{record['MedicalRecordID']}/treatments", {
            "MedicineName": "Vitamin", "Dose": "10ml", "Route": "Injection", "StartDate": TODAY.isoformat()},
            format="json")
        self.assertEqual(vet.delete(f"/api/medical-records/{record['MedicalRecordID']}").status_code, 204)
        self.assertIsNone(HealthReport.objects.get(pk=report["HealthReportID"]).medical_record_id)
        # gắn lại báo cáo vào phiếu mới được
        res = vet.post(f"/api/horses/{horse_id}/medical-records",
                       {"ExamType": "Routine Exam", "HealthReportID": report["HealthReportID"]}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        res = self.client_for(self.vet2).post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Routine Exam", "HealthReportID": report["HealthReportID"]}, format="json")
        self.assertEqual(res.data["code"], "REPORT_ALREADY_LINKED")

    def test_signed_treatment_only_end_dates(self):
        horse_id = self.approved_horse()
        vet = self.client_for(self.vet)
        record = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Routine Exam", "HealthStatus": "Healthy", "TrainingEligibility": "Eligible"},
            format="json").data
        rid = record["MedicalRecordID"]
        treatment = vet.post(f"/api/medical-records/{rid}/treatments", {
            "MedicineName": "Kháng sinh", "Dose": "5ml", "Route": "Injection", "StartDate": TODAY.isoformat()},
            format="json").data
        self.assertEqual(self.client_for(self.vet2).post(f"/api/medical-records/{rid}/treatments", {
            "MedicineName": "X", "Dose": "1", "Route": "Oral", "StartDate": TODAY.isoformat()}, format="json")
            .data["code"], "NOT_RECORD_OWNER")
        vet.post(f"/api/medical-records/{rid}/sign")
        other = self.client_for(self.vet2)
        self.assertEqual(other.patch(f"/api/treatments/{treatment['TreatmentID']}", {"Dose": "50ml"}, format="json")
                         .data["code"], "RECORD_SIGNED")
        res = other.patch(f"/api/treatments/{treatment['TreatmentID']}",
                          {"EndDate": (TODAY + timedelta(days=3)).isoformat()}, format="json")
        self.assertEqual(res.status_code, 200, res.data)

    def test_release_needs_exam_after_lock_even_if_backdated(self):
        horse_id = self.approved_horse()
        vet = self.client_for(self.vet)
        record = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Injury Exam", "HealthStatus": "Injured", "TrainingEligibility": "Restricted",
            "RestrictionNote": "Đi bộ"}, format="json").data
        res = vet.post(f"/api/medical-records/{record['MedicalRecordID']}/sign", {"TrainingLock": {
            "Reason": "Chấn thương", "LockLevel": "Restricted", "MaxIntensity": 20,
            "LockStartDate": f"{(TODAY - timedelta(days=2)).isoformat()}T00:00:00"}}, format="json")
        lock_id = res.data["TrainingLock"]["TrainingLockID"]
        self.assertEqual(vet.post(f"/api/training-locks/{lock_id}/release").data["code"], "FOLLOW_UP_EXAM_REQUIRED")

    def test_future_diet_keeps_current_until_start(self):
        horse_id = self.approved_horse()
        head, vet = self.client_for(self.head), self.client_for(self.vet)
        meals = [{"MealTime": "06:00", "FeedType": "Yến mạch", "Quantity": 3, "Unit": "kg"}]
        current = head.post(f"/api/horses/{horse_id}/diet-plans", {"StartDate": TODAY.isoformat(), "Meals": meals},
                            format="json").data["DietPlanID"]
        vet.post(f"/api/diet-plans/{current}/approve", {}, format="json")
        future_start = TODAY + timedelta(days=30)
        future = head.post(f"/api/horses/{horse_id}/diet-plans", {"StartDate": future_start.isoformat(),
                                                                  "Meals": meals}, format="json").data["DietPlanID"]
        vet.post(f"/api/diet-plans/{future}/approve", {}, format="json")
        self.assertEqual(head.get(f"/api/horses/{horse_id}/current-diet").data["DietPlanID"], current)
        plan = DietPlan.objects.get(pk=current)
        self.assertEqual((plan.status, plan.end_date), ("Approved", future_start - timedelta(days=1)))

    def test_completed_plan_cancels_sessions_and_blocks_start(self):
        horse_id, plan, stage_id = self.ready_horse()
        sid = self.session(stage_id)["TrainingSessionID"]
        self.client_for(self.head).post(f"/api/training-plans/{plan['TrainingPlanID']}/complete")
        self.assertEqual(TrainingSession.objects.get(pk=sid).status, "Cancelled")

    def test_ended_trainer_cannot_review(self):
        horse_id, plan, stage_id = self.ready_horse()
        sid = self.session(stage_id)["TrainingSessionID"]
        rider = self.client_for(self.rider)
        rider.post(f"/api/training-sessions/{sid}/start")
        rider.post(f"/api/training-sessions/{sid}/result", {"PerformanceScore": 70}, format="json")
        assignment = plan["TrainerHorseAssignmentID"]
        self.client_for(self.head).post(f"/api/trainer-assignments/{assignment}/end", {}, format="json")
        res = self.client_for(self.trainer).post(f"/api/training-sessions/{sid}/review", {"Evaluation": "Good"},
                                                 format="json")
        self.assertEqual(res.data["code"], "NOT_ASSIGNED_TRAINER")

    def test_bad_query_params_return_400(self):
        head = self.client_for(self.head)
        for url in ("/api/training-reviews?Days=abc", "/api/training-sessions?HorseID=abc",
                    "/api/vaccinations?DueWithinDays=x", "/api/horses?OwnerID=x", "/api/care-tasks?From=2026-13-01"):
            self.assertEqual(head.get(url).status_code, 400, url)
