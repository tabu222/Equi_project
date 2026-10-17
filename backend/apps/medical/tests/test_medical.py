"""Flow 3: báo cáo sức khỏe -> Vet khám -> Training Lock -> điều trị -> tái khám -> mở khóa; tiêm phòng, lịch y tế."""
from datetime import timedelta

from django.test import TestCase

from apps.horses.models import Horse
from apps.medical.models import HealthReport, TrainingLock
from apps.training.models import TrainingSession

from apps.training.tests.base import TODAY, TrainingTestCase


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


class TrainingLockTests(TrainingTestCase):
    """Training Lock (Flow 3) chặn giáo án / buổi tập của Flow 2."""

    def test_full_lock_blocks_activation(self):
        horse_id = self.approved_horse()
        self.assign(horse_id)
        TrainingLock.objects.create(horse_id=horse_id, created_by=self.vet, reason="Chấn thương", lock_level="Full",
                                    lock_start_date=TODAY - timedelta(days=1))
        trainer = self.client_for(self.trainer)
        res = trainer.post("/api/training-plans", {
            "HorseID": horse_id, "StartDate": TODAY.isoformat(),
            "Stages": [{"StageName": "A", "StartDate": TODAY.isoformat()}]}, format="json")
        plan_id = res.data["TrainingPlanID"]
        trainer.post(f"/api/training-plans/{plan_id}/submit")
        res = self.client_for(self.head).post(f"/api/training-plans/{plan_id}/approve", {}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "TRAINING_LOCK_FULL")

    def test_lock_rules_for_sessions(self):
        horse_id, plan, stage_id = self.ready_horse()
        TrainingLock.objects.create(horse_id=horse_id, created_by=self.vet, reason="Hồi phục",
                                    lock_level="Restricted", max_intensity=35, lock_start_date=TODAY - timedelta(days=1))
        self.assertEqual(self.session(stage_id, load=50, expect=409)["code"], "TRAINING_LOCK_RESTRICTED")
        self.assertEqual(self.session(stage_id, load=None, expect=409)["code"], "TRAINING_LOCK_RESTRICTED")
        self.session(stage_id, load=30)
        dash = self.client_for(self.head).get(f"/api/training-dashboard?HorseID={horse_id}").data[0]
        self.assertTrue(dash["IsTrainingLocked"])
        self.assertEqual(dash["LockLevel"], "Restricted")
        self.assertEqual(dash["MaxIntensity"], 35)
        TrainingLock.objects.filter(horse_id=horse_id).update(lock_level="Full", max_intensity=None)
        self.assertEqual(self.session(stage_id, load=10, expect=409)["code"], "TRAINING_LOCK_FULL")

    def test_stop_session_and_report_health(self):
        horse_id, plan, stage_id = self.ready_horse()
        sid = self.session(stage_id)["TrainingSessionID"]
        self.client_for(self.rider).post(f"/api/training-sessions/{sid}/start")
        self.assertEqual(self.client_for(self.trainer2).post(f"/api/training-sessions/{sid}/stop",
                                                             {"Reason": "x"}, format="json").status_code, 403)
        res = self.client_for(self.trainer).post(f"/api/training-sessions/{sid}/stop", {
            "Reason": "Ngựa đi lệch chân trước", "ReportHealth": True, "Severity": "Urgent"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["Status"], "Cancelled")
        report = self.client_for(self.vet).get(f"/api/health-reports/{res.data['HealthReportID']}").data
        self.assertEqual(report["Severity"], "Urgent")
        self.assertEqual(report["TrainingSessionID"], sid)


class ExamAfterIntakeTests(TrainingTestCase):
    """Có Flow 3: Vet lập phiếu khám định kỳ / chấn thương cho ngựa đã tiếp nhận."""

    def pending_horse(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        return horse_id

    def test_routine_exam_only_after_approval(self):
        horse_id = self.pending_horse()
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/medical-records", {"ExamType": "Routine Exam"}, format="json")
        self.assertEqual(res.status_code, 409)

        approved_id = self.approved_horse_with_new_chip()
        res = vet.post(f"/api/horses/{approved_id}/medical-records", {
            "ExamType": "Injury Exam", "HealthStatus": "Injured", "TrainingEligibility": "Not Eligible",
            "InjuryLocation": "Chân trước trái",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data["RegistrationRequestID"])
        vet.post(f"/api/medical-records/{res.data['MedicalRecordID']}/sign")
        self.assertEqual(Horse.objects.get(pk=approved_id).current_health_status, "Injured")

    def approved_horse_with_new_chip(self):
        horse_id = self.owner_creates_horse(MicrochipNumber="985000000000777", HorseName="Breeze")
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-777"},
                                           format="json")
        return horse_id


class MedicalRegressionTests(TrainingTestCase):
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

    def test_bad_query_params_return_400(self):
        self.assertEqual(self.client_for(self.head).get("/api/vaccinations?DueWithinDays=x").status_code, 400)


class SeedMedicalTests(TestCase):
    def test_seed_demo_adds_medical_samples_once(self):
        import secrets
        from io import StringIO

        from django.core.management import call_command

        from apps.medical.models import MedicalSchedule, Vaccination

        call_command("seed_demo", f"--password={secrets.token_urlsafe(18)}", stdout=StringIO())
        counts = (Vaccination.objects.count(), MedicalSchedule.objects.count(), HealthReport.objects.count())
        self.assertEqual(counts, (2, 1, 1))
        call_command("seed_demo", f"--password={secrets.token_urlsafe(18)}", stdout=StringIO())
        self.assertEqual((Vaccination.objects.count(), MedicalSchedule.objects.count(), HealthReport.objects.count()),
                         counts)
