"""Trainer tự xếp buổi tập cho ngựa mình; chốt giai đoạn; chủ ngựa xem kết quả huấn luyện + thông báo + email."""
from datetime import timedelta

from django.core import mail

from apps.training.models import TrainingPlan, TrainingPlanStage

from .base import TODAY, TrainingTestCase


def session_body(stage_id, rider, day=None, **extra):
    return {"TrainingPlanStageID": stage_id, "WorkRiderID": rider.id, "SessionDate": (day or TODAY).isoformat(),
            "StartTime": "06:00", "TrainingType": "Canter", "DurationPlannedMinutes": 45, "DistancePlannedKm": 3.5,
            "TrainingLoad": 30, **extra}


class TrainerSchedulingTests(TrainingTestCase):
    def test_trainer_schedules_only_own_horses(self):
        horse_id, plan, stage_id = self.ready_horse()
        trainer, trainer2, head = (self.client_for(u) for u in (self.trainer, self.trainer2, self.head))

        res = trainer.post("/api/training-sessions", session_body(stage_id, self.rider), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        sid = res.data["TrainingSessionID"]
        self.assertEqual(res.data["AssignedByHeadTrainerID"], self.trainer.id)   # lưu người xếp
        self.assertEqual(trainer2.post("/api/training-sessions", session_body(stage_id, self.rider2),
                                       format="json").status_code, 403)
        self.assertEqual(trainer2.patch(f"/api/training-sessions/{sid}", {"StartTime": "07:00"},
                                        format="json").status_code, 403)
        self.assertEqual(trainer2.post(f"/api/training-sessions/{sid}/cancel", {}, format="json").status_code, 403)
        self.assertEqual(trainer.patch(f"/api/training-sessions/{sid}", {"StartTime": "07:00"},
                                       format="json").data["StartTime"], "07:00:00")
        self.assertEqual(trainer.post(f"/api/training-sessions/{sid}/cancel", {"Reason": "Trời mưa"},
                                      format="json").data["Status"], "Cancelled")
        # Head Trainer vẫn xếp được cho mọi ngựa
        self.assertEqual(head.post("/api/training-sessions", session_body(stage_id, self.rider2),
                                   format="json").status_code, 201)

        # Work Rider ưu tiên: chỉ trainer phụ trách / Head Trainer
        body = {"WorkRiderID": self.rider.id, "Priority": 1}
        self.assertEqual(trainer2.post(f"/api/horses/{horse_id}/work-rider-preferences", body,
                                       format="json").status_code, 403)
        self.assertEqual(trainer.post(f"/api/horses/{horse_id}/work-rider-preferences", body,
                                      format="json").status_code, 201)

    def test_trainer_user_list_is_limited(self):
        trainer = self.client_for(self.trainer)
        riders = trainer.get("/api/users?RoleCode=WORK_RIDER")
        self.assertEqual(riders.status_code, 200)
        self.assertEqual({u["Email"] for u in riders.data}, {self.rider.email, self.rider2.email})
        self.assertEqual(trainer.get("/api/users?RoleCode=HORSE_OWNER").status_code, 403)
        emails = {u["Email"] for u in trainer.get("/api/users").data}
        self.assertNotIn(self.owner.email, emails)
        self.assertNotIn(self.manager.email, emails)


class OwnerReportTests(TrainingTestCase):
    def play(self, stage_id, rider=None, score=80, distance=3.4, review=True, comment="Ổn định"):
        """Trainer xếp -> rider tập, ghi kết quả -> (trainer đánh giá)."""
        rider = rider or self.rider
        res = self.client_for(self.trainer).post("/api/training-sessions", session_body(stage_id, rider),
                                                 format="json")
        self.assertEqual(res.status_code, 201, res.data)
        sid = res.data["TrainingSessionID"]
        rider_client = self.client_for(rider)
        rider_client.post(f"/api/training-sessions/{sid}/start")
        res = rider_client.post(f"/api/training-sessions/{sid}/result", {
            "ActualDurationMinutes": 44, "ActualDistanceKm": distance, "AvgSpeedKmh": 40, "MaxSpeedKmh": 52,
            "AvgHeartRate": 150, "MaxHeartRate": 190, "RecoveryMinutes": 12, "PerformanceScore": score,
            "RiderObservation": "Hơi nặng chân cuối buổi", "VideoUrl": "https://video.test/1"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        if review:
            res = self.client_for(self.trainer).post(f"/api/training-sessions/{sid}/review", {
                "Evaluation": "Good", "TrainerComment": comment}, format="json")
            self.assertEqual(res.status_code, 201, res.data)
        return sid

    def test_owner_sees_reviewed_sessions_summary_and_alerts(self):
        horse_id, plan, stage_id = self.ready_horse()
        plan_id = plan["TrainingPlanID"]
        TrainingPlanStage.objects.filter(pk=stage_id).update(distance_target_km=10)
        trainer, owner = self.client_for(self.trainer), self.client_for(self.owner)

        reviewed = self.play(stage_id, score=80, distance=3.4)
        waiting = self.play(stage_id, rider=self.rider2, score=60, review=False)
        cancelled = self.client_for(self.trainer).post("/api/training-sessions", session_body(
            stage_id, self.rider, StartTime="15:00", SequenceNo=3), format="json").data["TrainingSessionID"]
        trainer.post(f"/api/training-sessions/{cancelled}/cancel", {"Reason": "Trời mưa"}, format="json")
        stopped = self.client_for(self.trainer).post("/api/training-sessions", session_body(
            stage_id, self.rider2, StartTime="16:00", SequenceNo=4), format="json").data["TrainingSessionID"]
        with self.captureOnCommitCallbacks(execute=True):
            res = trainer.post(f"/api/training-sessions/{stopped}/stop", {"Reason": "Ngựa đi lệch chân trước"},
                               format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(any("[Khẩn]" in m.subject and self.owner.email in m.to for m in mail.outbox))

        # Danh sách buổi: không có buổi chưa được đánh giá
        rows = {r["TrainingSessionID"]: r for r in owner.get(f"/api/owner/horses/{horse_id}/training-sessions").data}
        self.assertEqual(set(rows), {reviewed, cancelled, stopped})
        self.assertEqual(rows[reviewed]["Evaluation"], "Good")
        self.assertEqual(rows[reviewed]["DistanceKm"], 3.4)
        self.assertEqual(rows[reviewed]["DurationMinutes"], 44)
        self.assertEqual(rows[cancelled]["Reason"], "Trời mưa")
        self.assertFalse(rows[cancelled]["IsStopped"])
        self.assertTrue(rows[stopped]["IsStopped"])
        self.assertIsNone(rows[stopped]["DistanceKm"])

        detail = owner.get(f"/api/owner/training-sessions/{reviewed}").data
        self.assertEqual(detail["TrainerComment"], "Ổn định")
        self.assertEqual(detail["AvgSpeedKmh"], 40)
        self.assertEqual(detail["RiderObservation"], "Hơi nặng chân cuối buổi")
        self.assertEqual(detail["VideoUrl"], "https://video.test/1")
        self.assertNotIn("SubstituteObservation", detail)
        self.assertEqual(owner.get(f"/api/owner/training-sessions/{waiting}").status_code, 404)

        # Tổng kết giáo án + giai đoạn đang chạy (tính đến hôm nay)
        body = owner.get(f"/api/owner/training-plans/{plan_id}").data
        summary = body["Summary"]
        self.assertEqual((summary["PlannedSessions"], summary["CompletedSessions"], summary["ReviewedSessions"],
                          summary["AwaitingReviewSessions"], summary["CancelledSessions"]), (4, 2, 1, 1, 2))
        self.assertEqual(summary["TotalDistanceKm"], 3.4)          # chỉ buổi đã đánh giá
        self.assertEqual(summary["Evaluations"]["Good"], 1)
        first, second = body["Stages"]
        self.assertEqual((first["StageState"], first["AsOf"]), ("InProgress", TODAY))
        self.assertEqual(first["Summary"]["DistanceProgressPercent"], 34.0)
        self.assertEqual((second["StageState"], second["Summary"]), ("NotStarted", None))
        self.assertEqual(len(owner.get(f"/api/owner/horses/{horse_id}/training-plans").data["Plans"]), 1)

        notes = {n["Type"]: n for n in owner.get("/api/notifications").data}
        self.assertIn("OWNER_PLAN_APPROVED", notes)
        self.assertIn("1 buổi", notes["OWNER_SESSIONS_REVIEWED"]["Title"])
        self.assertEqual(notes["OWNER_SESSION_STOPPED"]["Priority"], "High")

    def test_owner_cannot_see_other_horses_or_drafts(self):
        horse_id, plan, stage_id = self.ready_horse()
        other = self.client_for(self.other_owner)
        self.assertEqual(other.get(f"/api/owner/horses/{horse_id}/training-sessions").status_code, 404)
        self.assertEqual(other.get(f"/api/owner/training-plans/{plan['TrainingPlanID']}").status_code, 404)
        self.assertEqual(self.client_for(self.trainer).get(f"/api/owner/horses/{horse_id}/training-plans")
                         .status_code, 403)
        TrainingPlan.objects.filter(pk=plan["TrainingPlanID"]).update(approved_at=None, status="Draft")
        owner = self.client_for(self.owner)
        self.assertEqual(owner.get(f"/api/owner/horses/{horse_id}/training-plans").data["Plans"], [])
        self.assertEqual(owner.get(f"/api/owner/training-plans/{plan['TrainingPlanID']}").status_code, 404)

    def test_close_stage_and_complete_plan(self):
        horse_id, plan, stage_id = self.ready_horse()
        plan_id, second_id = plan["TrainingPlanID"], plan["Stages"][1]["TrainingPlanStageID"]
        trainer, owner = self.client_for(self.trainer), self.client_for(self.owner)
        url = f"/api/training-plan-stages/{stage_id}/close"

        pending = trainer.post("/api/training-sessions", session_body(stage_id, self.rider), format="json").data
        self.assertEqual(trainer.post(url, {}, format="json").data["code"], "SESSIONS_PENDING")
        trainer.post(f"/api/training-sessions/{pending['TrainingSessionID']}/cancel", {}, format="json")
        self.play(stage_id, score=70)
        self.assertEqual(self.client_for(self.trainer2).post(url, {}, format="json").status_code, 403)
        self.assertEqual(trainer.post(f"/api/training-plan-stages/{second_id}/close", {}, format="json")
                         .data["code"], "NOT_STARTED")

        # Giai đoạn hết hạn mà chưa chốt -> nhắc trainer
        TrainingPlanStage.objects.filter(pk=stage_id).update(end_date=TODAY - timedelta(days=1),
                                                             start_date=TODAY - timedelta(days=5))
        TrainingPlan.objects.filter(pk=plan_id).update(start_date=TODAY - timedelta(days=5))
        self.assertIn("STAGE_TO_CLOSE", {n["Type"] for n in trainer.get("/api/notifications").data})

        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            res = trainer.post(url, {"SummaryNote": "Ngựa thích nghi tốt"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["StageState"], "Closed")
        self.assertEqual(res.data["SummaryNote"], "Ngựa thích nghi tốt")
        self.assertEqual(res.data["Summary"]["ReviewedSessions"], 1)
        self.assertEqual(trainer.post(url, {}, format="json").data["code"], "ALREADY_CLOSED")
        message = next(m for m in mail.outbox if self.owner.email in m.to)
        self.assertIn("Tổng kết giai đoạn 1", message.subject)
        self.assertIn("Ngựa thích nghi tốt", message.body)
        self.assertNotIn("STAGE_TO_CLOSE", {n["Type"] for n in trainer.get("/api/notifications").data})
        self.assertIn("OWNER_STAGE_SUMMARY", {n["Type"] for n in owner.get("/api/notifications").data})

        # Kết thúc giáo án -> tổng kết cả giáo án cho chủ ngựa
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            res = trainer.post(f"/api/training-plans/{plan_id}/complete")
        self.assertEqual(res.data["Status"], "Completed")
        self.assertTrue(any(m.subject.startswith("[EquiTrack] Tổng kết giáo án") for m in mail.outbox))
        self.assertIn("OWNER_PLAN_SUMMARY", {n["Type"] for n in owner.get("/api/notifications").data})
        body = owner.get(f"/api/owner/training-plans/{plan_id}").data
        self.assertEqual(body["ProgressPercent"], 100.0)
        self.assertEqual([s["StageState"] for s in body["Stages"]], ["Closed", "NotStarted"])
