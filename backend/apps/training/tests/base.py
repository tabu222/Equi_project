"""Dữ liệu dựng sẵn cho test Flow 2 (dùng lại ở test Flow 3, Flow 4)."""
from datetime import date, timedelta

from apps.training.models import Specialization, TrainerSpecialization

from apps.core.tests.helpers import Flow1TestCase

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
