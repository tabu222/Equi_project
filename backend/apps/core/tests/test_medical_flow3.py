"""Flow 3: báo cáo sức khỏe -> Vet khám -> Training Lock -> điều trị -> tái khám -> mở khóa; tiêm phòng, lịch y tế."""
from datetime import timedelta

from apps.horses.models import Horse
from apps.training.models import TrainingSession

from .test_training import TODAY, TrainingTestCase


class HealthReportTests(TrainingTestCase):
    def test_report_to_lock_to_release(self):
        horse_id, plan, stage_id = self.ready_horse()
        today_session = self.session(stage_id)["TrainingSessionID"]
        later = self.session(stage_id, day=TODAY + timedelta(days=3), load=20)["TrainingSessionID"]
        groom, vet, trainer, head = (self.client_for(u) for u in (self.groom, self.vet, self.trainer, self.head))

        # 1. Groom báo sự cố; người sau thấy báo cáo đang mở và thêm ghi chú thay vì báo trùng
        res = groom.post(f"/api/horses/{horse_id}/health-reports", {
            "Severity": "Normal", "Description": "Chân trước trái hơi nóng, bỏ nửa bữa sáng"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        report_id = res.data["HealthReportID"]
        self.assertEqual(res.data["ReportedByRoles"], ["GROOM"])
        open_reports = self.client_for(self.rider).get(f"/api/horses/{horse_id}/health-reports?open=1").data
        self.assertEqual([r["HealthReportID"] for r in open_reports], [report_id])
        res = self.client_for(self.rider).post(f"/api/health-reports/{report_id}/notes",
                                               {"Content": "Khởi động thấy hơi lệch nhịp"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self.client_for(self.owner).post(f"/api/horses/{horse_id}/health-reports",
                                                          {"Description": "x"}, format="json").status_code, 403)

        # Trainer phụ trách và Head Trainer thấy trong thông báo
        for client in (trainer, head, vet):
            types = {(n["Type"], n["EntityID"]) for n in client.get("/api/notifications").data}
            self.assertIn(("HEALTH_REPORT", report_id), types)
        self.assertNotIn("HEALTH_REPORT",
                         {n["Type"] for n in self.client_for(self.trainer2).get("/api/notifications").data})

        # 2. Vet nhận ca, lập phiếu khám gắn báo cáo, chốt kèm Training Lock Restricted
        queue = vet.get("/api/health-reports?open=1").data
        self.assertEqual(queue[0]["HealthReportID"], report_id)
        self.assertEqual(vet.post(f"/api/health-reports/{report_id}/take").data["Status"], "Reviewing")
        res = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Injury Exam", "HealthReportID": report_id, "Symptoms": "Sưng nóng cổ chân trái",
            "Diagnosis": "Viêm gân nhẹ", "InjuryLocation": "Cổ chân trước trái", "HealthStatus": "Recovering",
            "TrainingEligibility": "Restricted", "RestrictionNote": "Chỉ đi bộ và chạy nước kiệu nhẹ",
            "FollowUpDate": (TODAY + timedelta(days=7)).isoformat()}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        record_id = res.data["MedicalRecordID"]
        self.assertEqual(vet.get(f"/api/health-reports/{report_id}").data["MedicalRecordID"], record_id)

        res = vet.post(f"/api/medical-records/{record_id}/treatments", {
            "MedicineName": "Phenylbutazone", "Dose": "2g/ngày", "Route": "Oral", "StartDate": TODAY.isoformat(),
            "EndDate": (TODAY + timedelta(days=5)).isoformat(),
            "WithdrawalUntil": (TODAY + timedelta(days=12)).isoformat()}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["WithdrawalActive"])

        res = vet.post(f"/api/medical-records/{record_id}/sign", {"TrainingLock": {
            "Reason": "Viêm gân nhẹ", "LockLevel": "Restricted", "MaxIntensity": 25}}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        lock = res.data["TrainingLock"]
        self.assertEqual(lock["LockLevel"], "Restricted")
        self.assertEqual(lock["CancelledSessionIDs"], [today_session])     # buổi load 30 > 25 bị hủy
        self.assertEqual(TrainingSession.objects.get(pk=later).status, "Assigned")
        self.assertEqual(Horse.objects.get(pk=horse_id).current_health_status, "Recovering")
        self.assertEqual(len(trainer.get(f"/api/horses/{horse_id}/treatments?WithdrawalActive=1").data), 1)

        # 3. Xử lý xong báo cáo
        res = vet.post(f"/api/health-reports/{report_id}/resolve", {"VetNote": "Đã khám, khóa Restricted"},
                       format="json")
        self.assertEqual(res.data["Status"], "Resolved")
        self.assertEqual(groom.post(f"/api/health-reports/{report_id}/notes", {"Content": "x"}, format="json")
                         .data["code"], "REPORT_RESOLVED")

        # 4. Mở khóa cần tái khám đạt
        lock_id = lock["TrainingLockID"]
        self.assertEqual(vet.post(f"/api/training-locks/{lock_id}/release").data["code"], "FOLLOW_UP_EXAM_REQUIRED")
        self.assertEqual(self.client_for(self.trainer).post(f"/api/training-locks/{lock_id}/release")
                         .status_code, 403)
        res = self.client_for(self.vet2).post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Follow-up", "HealthStatus": "Healthy", "TrainingEligibility": "Eligible",
            "Conclusion": "Hết viêm"}, format="json")
        follow_up_id = res.data["MedicalRecordID"]
        res = self.client_for(self.vet2).post(f"/api/medical-records/{follow_up_id}/sign")
        self.assertIsNone(res.data["TrainingLock"])     # tái khám đạt: không tự mở khóa
        res = self.client_for(self.vet2).post(f"/api/training-locks/{lock_id}/release", {"Note": "Tái khám đạt"},
                                              format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["LockStatus"], "Released")
        self.assertEqual(res.data["ReleasedByVetID"], self.vet2.id)
        self.assertIsNotNone(res.data["LockEndDate"])
        self.session(stage_id, day=TODAY + timedelta(days=1), load=60)      # hết khóa, tập bình thường

    def test_not_eligible_auto_full_lock(self):
        horse_id, plan, stage_id = self.ready_horse()
        session_id = self.session(stage_id, day=TODAY + timedelta(days=1), load=10)["TrainingSessionID"]
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Emergency", "HealthStatus": "Injured", "TrainingEligibility": "Not Eligible",
            "Diagnosis": "Nứt xương bàn"}, format="json")
        res = vet.post(f"/api/medical-records/{res.data['MedicalRecordID']}/sign")
        self.assertEqual(res.data["TrainingLock"]["LockLevel"], "Full")
        self.assertEqual(res.data["TrainingLock"]["CancelledSessionIDs"], [session_id])
        self.assertEqual(self.session(stage_id, day=TODAY + timedelta(days=2), load=5, expect=409)["code"],
                         "TRAINING_LOCK_FULL")
        res = vet.post(f"/api/horses/{horse_id}/training-locks", {"Reason": "x"}, format="json")
        self.assertEqual(res.data["code"], "LOCK_EXISTS")

    def test_urgent_report_stops_running_session(self):
        horse_id, plan, stage_id = self.ready_horse()
        sid = self.session(stage_id)["TrainingSessionID"]
        rider = self.client_for(self.rider)
        rider.post(f"/api/training-sessions/{sid}/start")
        res = rider.post(f"/api/horses/{horse_id}/health-reports", {
            "Severity": "Urgent", "Description": "Ngựa què chân sau phải khi phi", "TrainingSessionID": sid},
            format="json")
        self.assertTrue(res.data["StoppedSession"])
        self.assertEqual(TrainingSession.objects.get(pk=sid).status, "Cancelled")
        urgent = [n for n in self.client_for(self.vet).get("/api/notifications").data if n["Type"] == "HEALTH_REPORT"]
        self.assertEqual(urgent[0]["Priority"], "High")

    def test_lock_crud_and_validation(self):
        horse_id = self.approved_horse()
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/training-locks", {"Reason": "Theo dõi", "LockLevel": "Restricted"},
                       format="json")
        self.assertIn("MaxIntensity", res.data)
        res = vet.post(f"/api/horses/{horse_id}/training-locks", {
            "Reason": "Theo dõi", "LockLevel": "Restricted", "MaxIntensity": 40}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        lock_id = res.data["TrainingLockID"]
        res = vet.patch(f"/api/training-locks/{lock_id}", {"LockLevel": "Full"}, format="json")
        self.assertEqual(res.data["LockLevel"], "Full")
        self.assertIsNone(res.data["MaxIntensity"])
        locks = self.client_for(self.head).get("/api/training-locks?LockStatus=Active").data
        self.assertEqual([lk["TrainingLockID"] for lk in locks], [lock_id])
        self.assertEqual(self.client_for(self.other_vet).get(f"/api/training-locks/{lock_id}").status_code, 404)


class PreventiveCareTests(TrainingTestCase):
    def test_vaccinations_and_schedules(self):
        horse_id = self.approved_horse()
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/vaccinations", {
            "VaccineName": "Cúm ngựa (EIV)", "VaccinationDate": (TODAY + timedelta(days=3)).isoformat()},
            format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["Status"], "Scheduled")
        self.assertEqual(res.data["VetID"], self.vet.id)
        vac_id = res.data["VaccinationID"]
        res = vet.post(f"/api/horses/{horse_id}/vaccinations", {
            "VaccineName": "Uốn ván", "VaccinationDate": (TODAY - timedelta(days=2)).isoformat(),
            "ExternalVet": True}, format="json")
        self.assertIsNone(res.data["VetID"])
        self.assertTrue(res.data["IsOverdue"])
        self.assertEqual(len(vet.get("/api/vaccinations?DueWithinDays=7").data), 2)

        res = vet.patch(f"/api/vaccinations/{vac_id}", {
            "Status": "Completed", "NextDueDate": (TODAY + timedelta(days=180)).isoformat()}, format="json")
        self.assertEqual(res.data["Status"], "Completed")
        self.assertEqual(res.data["VetID"], self.vet.id)
        res = vet.patch(f"/api/vaccinations/{vac_id}", {"NextDueDate": "2000-01-01"}, format="json")
        self.assertIn("NextDueDate", res.data)

        res = vet.post(f"/api/horses/{horse_id}/medical-schedules", {
            "ScheduleType": "Farrier", "ScheduledDate": (TODAY + timedelta(days=1)).isoformat(),
            "ExternalVet": True}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        schedules = self.client_for(self.head).get(
            f"/api/medical-schedules?From={TODAY.isoformat()}&To={(TODAY + timedelta(days=7)).isoformat()}").data
        self.assertEqual(len(schedules), 1)
        self.assertEqual(vet.patch(f"/api/medical-schedules/{schedules[0]['MedicalScheduleID']}",
                                   {"Status": "Completed"}, format="json").data["Status"], "Completed")
        self.assertEqual(self.client_for(self.groom).post(f"/api/horses/{horse_id}/vaccinations", {},
                                                          format="json").status_code, 403)
        self.assertEqual(self.client_for(self.owner).get("/api/vaccinations").status_code, 403)

