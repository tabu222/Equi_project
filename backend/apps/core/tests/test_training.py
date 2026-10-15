"""Flow 2: đánh giá -> phân công -> giáo án (duyệt) -> buổi tập -> kết quả -> đánh giá."""
from datetime import date, timedelta

from apps.medical.models import TrainingLock
from apps.training.models import Specialization, TrainerSpecialization, TrainingSession

from .helpers import Flow1TestCase

TODAY = date.today()


class TrainingTestCase(Flow1TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.head = cls.make_user("head@one.test", "HEAD_TRAINER", cls.club)
        cls.trainer2 = cls.make_user("trainer2@one.test", "TRAINER", cls.club)
        cls.rider = cls.make_user("rider@one.test", "WORK_RIDER", cls.club)
        cls.rider2 = cls.make_user("rider2@one.test", "WORK_RIDER", cls.club)
        cls.groom = cls.make_user("groom@one.test", "GROOM", cls.club)
        cls.other_head = cls.make_user("head@two.test", "HEAD_TRAINER", cls.other_club)
        cls.flat = Specialization.objects.create(code="FLAT_RACING", name="Flat Racing")
        cls.endurance = Specialization.objects.create(code="ENDURANCE", name="Endurance")
        TrainerSpecialization.objects.create(trainer=cls.trainer, specialization=cls.flat)
        TrainerSpecialization.objects.create(trainer=cls.trainer2, specialization=cls.flat)

    # ---------- dựng sẵn ----------
    def assign(self, horse_id):
        res = self.client_for(self.head).post("/api/trainer-assignments", {
            "HorseID": horse_id, "TrainerID": self.trainer.id, "SpecializationID": self.flat.id}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data["TrainerHorseAssignmentID"]

    def active_plan(self, horse_id):
        trainer = self.client_for(self.trainer)
        res = trainer.post("/api/training-plans", {
            "HorseID": horse_id, "Goal": "Chuẩn bị giải tháng 12", "StartDate": TODAY.isoformat(),
            "EndDate": (TODAY + timedelta(days=60)).isoformat(), "OverallIntensity": "Moderate",
            "Stages": [
                {"StageName": "Nền tảng", "StartDate": TODAY.isoformat(),
                 "EndDate": (TODAY + timedelta(days=20)).isoformat(), "Intensity": "Low", "TrainingLoad": 30},
                {"StageName": "Tăng tốc", "StartDate": (TODAY + timedelta(days=21)).isoformat(),
                 "Intensity": "High", "TrainingLoad": 70},
            ],
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        plan = res.data
        self.assertEqual(trainer.post(f"/api/training-plans/{plan['TrainingPlanID']}/submit").status_code, 200)
        res = self.client_for(self.head).post(f"/api/training-plans/{plan['TrainingPlanID']}/approve", {},
                                              format="json")
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def session(self, stage_id, day=None, load=30, rider=None, substitute=None, expect=201):
        body = {"TrainingPlanStageID": stage_id, "WorkRiderID": (rider or self.rider).id,
                "SessionDate": (day or TODAY).isoformat(), "StartTime": "06:00", "TrainingType": "Canter",
                "DurationPlannedMinutes": 45, "DistancePlannedKm": 3.5, "TrainingLoad": load}
        if substitute:
            body["SubstituteTrainerID"] = substitute.id
        res = self.client_for(self.head).post("/api/training-sessions", body, format="json")
        self.assertEqual(res.status_code, expect, res.data)
        return res.data

    def ready_horse(self):
        horse_id = self.approved_horse()
        self.assign(horse_id)
        plan = self.active_plan(horse_id)
        return horse_id, plan, plan["Stages"][0]["TrainingPlanStageID"]


class AssignmentTests(TrainingTestCase):
    def test_assessment_and_assignment(self):
        horse_id = self.approved_horse()
        head = self.client_for(self.head)
        res = head.post(f"/api/horses/{horse_id}/assessments", {
            "SpecializationID": self.flat.id, "QualityScore": 82.5, "FitnessLevel": "Good",
            "AssessmentNote": "Sải chân dài, hợp đường ngắn"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        first = res.data["AssessmentID"]
        res = head.post(f"/api/horses/{horse_id}/assessments", {"SpecializationID": self.flat.id,
                                                                "QualityScore": 85}, format="json")
        statuses = {a["AssessmentID"]: a["DecisionStatus"]
                    for a in head.get(f"/api/horses/{horse_id}/assessments").data}
        self.assertEqual(statuses[first], "Superseded")
        self.assertEqual(statuses[res.data["AssessmentID"]], "Recommended")

        trainers = head.get(f"/api/trainers?SpecializationID={self.flat.id}").data
        self.assertEqual({t["UserID"] for t in trainers}, {self.trainer.id, self.trainer2.id})

        res = head.post("/api/trainer-assignments", {"HorseID": horse_id, "TrainerID": self.trainer.id,
                                                     "SpecializationID": self.endurance.id}, format="json")
        self.assertEqual(res.data["code"], "SPECIALIZATION_MISMATCH")
        assignment_id = self.assign(horse_id)
        res = head.post("/api/trainer-assignments", {"HorseID": horse_id, "TrainerID": self.trainer2.id,
                                                     "SpecializationID": self.flat.id}, format="json")
        self.assertEqual(res.data["code"], "ALREADY_ASSIGNED")
        res = head.post(f"/api/trainer-assignments/{assignment_id}/end", {"Reason": "Đổi trainer"}, format="json")
        self.assertEqual(res.data["Status"], "Ended")
        res = head.post("/api/trainer-assignments", {"HorseID": horse_id, "TrainerID": self.trainer2.id,
                                                     "SpecializationID": self.flat.id}, format="json")
        self.assertEqual(res.status_code, 201)

    def test_trainer_specialization_management(self):
        head = self.client_for(self.head)
        res = head.post(f"/api/trainers/{self.trainer.id}/specializations", {"SpecializationID": self.endurance.id},
                        format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(head.delete(f"/api/trainers/{self.trainer.id}/specializations/{self.endurance.id}")
                         .status_code, 204)
        self.assign(self.approved_horse())
        res = head.delete(f"/api/trainers/{self.trainer.id}/specializations/{self.flat.id}")
        self.assertEqual(res.data["code"], "IN_USE")
        self.assertEqual(head.post(f"/api/trainers/{self.rider.id}/specializations",
                                   {"SpecializationID": self.flat.id}, format="json").status_code, 404)

    def test_rules(self):
        horse_id = self.owner_creates_horse()          # chưa Approved
        head = self.client_for(self.head)
        res = head.post("/api/trainer-assignments", {"HorseID": horse_id, "TrainerID": self.trainer.id,
                                                     "SpecializationID": self.flat.id}, format="json")
        self.assertEqual(res.data["code"], "HORSE_NOT_APPROVED")
        approved = self.approved_horse_2()
        res = head.post("/api/trainer-assignments", {"HorseID": approved, "TrainerID": self.rider.id,
                                                     "SpecializationID": self.flat.id}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("TrainerID", res.data)
        self.assertEqual(self.client_for(self.trainer).post("/api/trainer-assignments", {}, format="json")
                         .status_code, 403)
        self.assertEqual(self.client_for(self.other_head).get("/api/trainer-assignments").data, [])

    def approved_horse_2(self):
        horse_id = self.owner_creates_horse(MicrochipNumber="985000000000555", HorseName="Second")
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-555"},
                                           format="json")
        return horse_id

    def test_work_rider_preferences(self):
        horse_id = self.approved_horse()
        head = self.client_for(self.head)
        res = head.post(f"/api/horses/{horse_id}/work-rider-preferences",
                        {"WorkRiderID": self.rider.id, "Priority": 1, "Note": "Quen ngựa"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(head.post(f"/api/horses/{horse_id}/work-rider-preferences",
                                   {"WorkRiderID": self.rider.id}, format="json").data["code"], "ALREADY_EXISTS")
        self.assertEqual(len(self.client_for(self.rider).get(f"/api/horses/{horse_id}/work-rider-preferences")
                             .data), 1)
        head.post(f"/api/work-rider-preferences/{res.data['PreferenceID']}/end")
        self.assertEqual(head.get(f"/api/horses/{horse_id}/work-rider-preferences").data, [])


class PlanTests(TrainingTestCase):
    def test_plan_approval_flow(self):
        horse_id = self.approved_horse()
        self.assign(horse_id)
        trainer, head = self.client_for(self.trainer), self.client_for(self.head)
        res = self.client_for(self.trainer2).post("/api/training-plans", {
            "HorseID": horse_id, "StartDate": TODAY.isoformat()}, format="json")
        self.assertEqual(res.data["code"], "NOT_PLAN_OWNER")

        res = trainer.post("/api/training-plans", {"HorseID": horse_id, "Goal": "G", "StartDate": TODAY.isoformat(),
                                                   "EndDate": (TODAY + timedelta(days=30)).isoformat()}, format="json")
        plan_id = res.data["TrainingPlanID"]
        self.assertEqual(res.data["Status"], "Draft")
        self.assertEqual(trainer.post(f"/api/training-plans/{plan_id}/submit").data["code"], "NO_STAGES")
        res = trainer.post(f"/api/training-plans/{plan_id}/stages", {
            "StageName": "Ngoài khung", "StartDate": (TODAY + timedelta(days=40)).isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)
        res = trainer.post(f"/api/training-plans/{plan_id}/stages", {
            "StageName": "Khởi động", "StartDate": TODAY.isoformat(), "TrainingLoad": 20}, format="json")
        self.assertEqual(res.data["StageOrder"], 1)
        stage_id = res.data["TrainingPlanStageID"]
        self.assertEqual(trainer.patch(f"/api/training-plan-stages/{stage_id}", {"Goal": "Làm quen"},
                                       format="json").data["Goal"], "Làm quen")

        trainer.post(f"/api/training-plans/{plan_id}/submit")
        self.assertEqual(trainer.patch(f"/api/training-plans/{plan_id}", {"Goal": "x"}, format="json")
                         .data["code"], "INVALID_STATUS")
        self.assertEqual(trainer.post(f"/api/training-plans/{plan_id}/approve").status_code, 403)
        res = head.post(f"/api/training-plans/{plan_id}/return", {}, format="json")
        self.assertEqual(res.data["code"], "REVIEW_NOTE_REQUIRED")
        res = head.post(f"/api/training-plans/{plan_id}/return", {"ReviewNote": "Tăng thời gian hồi phục"},
                        format="json")
        self.assertEqual(res.data["Status"], "Draft")
        pending = head.get("/api/training-plans?Status=Pending Approval").data
        self.assertEqual(pending, [])

        trainer.post(f"/api/training-plans/{plan_id}/submit")
        res = head.post(f"/api/training-plans/{plan_id}/approve", {"ReviewNote": "OK"}, format="json")
        self.assertEqual(res.data["Status"], "Active")
        self.assertEqual(res.data["ApprovedByHeadTrainerID"], self.head.id)

    def test_revise_replaces_active_plan(self):
        horse_id, plan, stage_id = self.ready_horse()
        future = self.session(stage_id, TODAY + timedelta(days=2))
        trainer, head = self.client_for(self.trainer), self.client_for(self.head)
        res = trainer.post(f"/api/training-plans/{plan['TrainingPlanID']}/revise")
        self.assertEqual(res.status_code, 201, res.data)
        new_id = res.data["TrainingPlanID"]
        self.assertEqual(len(res.data["Stages"]), 2)
        self.assertEqual(trainer.post(f"/api/training-plans/{plan['TrainingPlanID']}/revise").data["code"],
                         "DRAFT_EXISTS")
        trainer.post(f"/api/training-plans/{new_id}/submit")
        head.post(f"/api/training-plans/{new_id}/approve", {}, format="json")
        self.assertEqual(head.get(f"/api/training-plans/{plan['TrainingPlanID']}").data["Status"], "Completed")
        self.assertEqual(TrainingSession.objects.get(pk=future["TrainingSessionID"]).status, "Cancelled")

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


class SessionTests(TrainingTestCase):
    def test_full_session_flow(self):
        horse_id, plan, stage_id = self.ready_horse()
        s = self.session(stage_id)
        sid = s["TrainingSessionID"]
        self.assertEqual(s["SequenceNo"], 1)
        self.assertEqual(s["SupervisingTrainerID"], self.trainer.id)
        self.assertFalse(s["IsSubstitute"])
        self.assertEqual(s["HorseID"], horse_id)

        rider, trainer, head = (self.client_for(u) for u in (self.rider, self.trainer, self.head))
        self.assertEqual([x["TrainingSessionID"] for x in rider.get("/api/training-sessions?mine=1").data], [sid])
        self.assertEqual([x["TrainingSessionID"] for x in trainer.get("/api/training-sessions?mine=1").data], [sid])
        self.assertEqual(self.client_for(self.rider2).post(f"/api/training-sessions/{sid}/start").data["code"],
                         "NOT_SESSION_RIDER")
        self.assertEqual(rider.post(f"/api/training-sessions/{sid}/result", {}, format="json").data["code"],
                         "INVALID_STATUS")
        self.assertEqual(rider.post(f"/api/training-sessions/{sid}/start").data["Status"], "In Progress")
        res = rider.post(f"/api/training-sessions/{sid}/result", {
            "ActualDurationMinutes": 44, "ActualDistanceKm": 3.4, "AvgSpeedKmh": 28.5, "AvgHeartRate": 150,
            "MaxHeartRate": 190, "RecoveryMinutes": 12, "PerformanceScore": 78,
            "RiderObservation": "Ngựa hơi nặng chân phải cuối buổi"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["Status"], "Completed")
        self.assertEqual(res.data["Result"]["PerformanceScore"], 78)
        self.assertIsNotNone(res.data["EndTime"])

        self.assertEqual(self.client_for(self.trainer2).post(f"/api/training-sessions/{sid}/review", {
            "Evaluation": "Good"}, format="json").data["code"], "NOT_ASSIGNED_TRAINER")
        res = trainer.post(f"/api/training-sessions/{sid}/review", {"Evaluation": "Good",
                                                                    "AdjustmentRequired": True}, format="json")
        self.assertEqual(res.status_code, 400)
        res = trainer.post(f"/api/training-sessions/{sid}/review", {
            "Evaluation": "Good", "TrainerComment": "Ổn", "AdjustmentRequired": True,
            "AdjustmentNote": "Giảm cự ly tuần sau"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        reviews = head.get("/api/training-reviews?AdjustmentRequired=1").data
        self.assertEqual(reviews[0]["HorseID"], horse_id)
        dash = head.get(f"/api/training-dashboard?HorseID={horse_id}").data[0]
        self.assertEqual(dash["TrainerID"], self.trainer.id)
        self.assertEqual(dash["LatestPerformanceScore"], 78)
        self.assertFalse(dash["IsTrainingLocked"])

    def test_substitute_trainer(self):
        _, _, stage_id = self.ready_horse()
        s = self.session(stage_id, substitute=self.trainer2)
        sid = s["TrainingSessionID"]
        self.assertTrue(s["IsSubstitute"])
        self.assertEqual(s["SupervisingTrainerID"], self.trainer2.id)
        # Chọn chính trainer phụ trách thì không tính là Substitute
        res = self.client_for(self.head).patch(f"/api/training-sessions/{sid}",
                                               {"SubstituteTrainerID": self.trainer.id}, format="json")
        self.assertFalse(res.data["IsSubstitute"])
        self.client_for(self.head).patch(f"/api/training-sessions/{sid}", {"SubstituteTrainerID": self.trainer2.id},
                                         format="json")
        sub = self.client_for(self.trainer2)
        self.assertEqual(sub.get("/api/training-sessions?mine=1").data[0]["TrainingSessionID"], sid)
        self.assertEqual(self.client_for(self.trainer).get("/api/training-sessions?mine=1").data, [])
        self.client_for(self.rider).post(f"/api/training-sessions/{sid}/start")
        res = sub.post(f"/api/training-sessions/{sid}/substitute-observation",
                       {"SubstituteObservation": "Ngựa chạy đều, hơi lệch nhịp vòng cuối"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        res = self.client_for(self.rider).post(f"/api/training-sessions/{sid}/result",
                                               {"RiderObservation": "Tốt"}, format="json")
        self.assertEqual(res.data["Result"]["SubstituteObservation"], "Ngựa chạy đều, hơi lệch nhịp vòng cuối")
        self.assertEqual(res.data["Result"]["RiderObservation"], "Tốt")
        self.assertEqual(self.client_for(self.trainer).post(f"/api/training-sessions/{sid}/substitute-observation",
                                                            {"SubstituteObservation": "x"}, format="json")
                         .data["code"], "NOT_SUBSTITUTE")

    def test_scheduling_rules(self):
        horse_id, plan, stage_id = self.ready_horse()
        self.session(stage_id)
        second = self.session(stage_id)                          # tự lấy SequenceNo = 2
        self.assertEqual(second["SequenceNo"], 2)
        res = self.client_for(self.head).post("/api/training-sessions", {
            "TrainingPlanStageID": stage_id, "WorkRiderID": self.rider.id, "SessionDate": TODAY.isoformat(),
            "StartTime": "09:00", "TrainingType": "Walk", "SequenceNo": 1}, format="json")
        self.assertEqual(res.data["code"], "RIDER_SLOT_TAKEN")
        self.session(stage_id, day=TODAY - timedelta(days=1), expect=400)            # ngày đã qua
        self.session(stage_id, day=TODAY + timedelta(days=25), expect=400)           # ngoài giai đoạn
        res = self.client_for(self.head).post("/api/training-sessions", {
            "TrainingPlanStageID": stage_id, "WorkRiderID": self.groom.id, "SessionDate": TODAY.isoformat(),
            "StartTime": "09:00", "TrainingType": "Walk"}, format="json")
        self.assertIn("WorkRiderID", res.data)
        self.assertEqual(self.client_for(self.trainer).post("/api/training-sessions", {}, format="json")
                         .status_code, 403)

    def test_lock_rules_for_sessions(self):
        horse_id, plan, stage_id = self.ready_horse()
        TrainingLock.objects.create(horse_id=horse_id, created_by=self.vet, reason="Hồi phục",
                                    lock_level="Restricted", max_intensity=35, lock_start_date=TODAY - timedelta(days=1))
        self.assertEqual(self.session(stage_id, load=50, expect=409)["code"], "TRAINING_LOCK_RESTRICTED")
        self.assertEqual(self.session(stage_id, load=None, expect=409)["code"], "TRAINING_LOCK_RESTRICTED")
        self.session(stage_id, load=30)
        dash = self.client_for(self.head).get(f"/api/training-dashboard?HorseID={horse_id}").data[0]
        self.assertEqual(dash["LockLevel"], "Restricted")
        self.assertEqual(dash["MaxIntensity"], 35)
        TrainingLock.objects.filter(horse_id=horse_id).update(lock_level="Full", max_intensity=None)
        self.assertEqual(self.session(stage_id, load=10, expect=409)["code"], "TRAINING_LOCK_FULL")

    def test_stop_and_cancel(self):
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

        other = self.session(stage_id)["TrainingSessionID"]
        self.assertEqual(self.client_for(self.head).post(f"/api/training-sessions/{other}/missed").data["Status"],
                         "Missed")
        third = self.session(stage_id, day=TODAY + timedelta(days=1))["TrainingSessionID"]
        self.assertEqual(self.client_for(self.head).post(f"/api/training-sessions/{third}/missed").data["code"],
                         "NOT_YET")
        self.assertEqual(self.client_for(self.head).post(f"/api/training-sessions/{third}/cancel", {},
                                                         format="json").data["Status"], "Cancelled")

    def test_end_assignment_cancels_open_work(self):
        horse_id, plan, stage_id = self.ready_horse()
        sid = self.session(stage_id, day=TODAY + timedelta(days=1))["TrainingSessionID"]
        assignment = self.client_for(self.head).get(f"/api/trainer-assignments?HorseID={horse_id}&Status=Active").data[0]
        self.client_for(self.head).post(f"/api/trainer-assignments/{assignment['TrainerHorseAssignmentID']}/end",
                                        {}, format="json")
        self.assertEqual(TrainingSession.objects.get(pk=sid).status, "Cancelled")
        self.assertEqual(self.client_for(self.head).get(f"/api/training-plans/{plan['TrainingPlanID']}")
                         .data["Status"], "Cancelled")

    def test_archive_horse_ends_training(self):
        horse_id, plan, stage_id = self.ready_horse()
        sid = self.session(stage_id, day=TODAY + timedelta(days=1))["TrainingSessionID"]
        self.client_for(self.manager).post(f"/api/horses/{horse_id}/archive", {"Reason": "Rời CLB"}, format="json")
        self.assertEqual(TrainingSession.objects.get(pk=sid).status, "Cancelled")
        self.assertEqual(self.client_for(self.head).get(f"/api/trainer-assignments?HorseID={horse_id}").data[0]
                         ["Status"], "Ended")
