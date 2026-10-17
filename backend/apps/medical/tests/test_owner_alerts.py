"""Flow 3 báo chủ ngựa: ngựa bị khóa tập / được mở khóa (chuông + email); sức khỏe trong tổng kết huấn luyện."""
from django.core import mail

from apps.training.tests.base import TrainingTestCase


class OwnerLockAlertTests(TrainingTestCase):
    def test_lock_and_release_reach_owner(self):
        horse_id, plan, stage_id = self.ready_horse()
        vet, owner = self.client_for(self.vet), self.client_for(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            res = vet.post(f"/api/horses/{horse_id}/training-locks", {
                "Reason": "Viêm gân", "LockLevel": "Restricted", "MaxIntensity": 20}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        lock_id = res.data["TrainingLockID"]
        message = next(m for m in mail.outbox if self.owner.email in m.to)
        self.assertIn("[Khẩn]", message.subject)
        self.assertIn("Viêm gân", message.body)
        notes = {n["Type"]: n for n in owner.get("/api/notifications").data}
        self.assertEqual(notes["OWNER_TRAINING_LOCKED"]["Priority"], "High")

        # Tổng kết huấn luyện có phần sức khỏe khi đã có Flow 3
        health = owner.get(f"/api/owner/training-plans/{plan['TrainingPlanID']}").data["Summary"]["Health"]
        self.assertEqual((health["TrainingLockCount"], health["IsLockedNow"]), (1, True))

        record = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Follow-up", "HealthStatus": "Healthy", "TrainingEligibility": "Eligible",
            "Conclusion": "Hết viêm"}, format="json").data
        vet.post(f"/api/medical-records/{record['MedicalRecordID']}/sign")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            res = vet.post(f"/api/training-locks/{lock_id}/release", {"Note": "Tái khám đạt"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(any("được tập lại" in m.subject for m in mail.outbox))
        types = {n["Type"] for n in owner.get("/api/notifications").data}
        self.assertIn("OWNER_TRAINING_UNLOCKED", types)
        self.assertNotIn("OWNER_TRAINING_LOCKED", types)
        self.assertEqual(self.client_for(self.other_owner).get("/api/notifications").data, [])
