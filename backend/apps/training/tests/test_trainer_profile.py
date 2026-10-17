"""
Flow 2 - hồ sơ năng lực Trainer: kinh nghiệm (từ ngày bắt đầu làm nghề), cấp độ, thâm niên nghề (từ bằng cấp /
chứng chỉ), tỉ lệ thắng 12 tháng gần nhất (từ kết quả đua) và gợi ý trainer cho ngựa.
"""
import secrets
from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import User
from apps.training.models import TrainerProfile, TrainerRaceResult
from apps.training.profiles import credential_stats, experience_level, full_years, race_stats

from .base import TrainingTestCase

TODAY = date.today()


def years_ago(years, days=0):
    return date(TODAY.year - years, TODAY.month, min(TODAY.day, 28)) - timedelta(days=days)


class ProfileRuleTests(SimpleTestCase):
    def test_levels_by_years(self):
        expected = {0: "Junior", 2: "Junior", 3: "Intermediate", 5: "Intermediate", 6: "Senior", 10: "Senior",
                    11: "Expert", 25: "Expert"}
        for years, level in expected.items():
            self.assertEqual(experience_level(years), level, years)

    def test_years_count_full_years_only(self):
        self.assertEqual(full_years(years_ago(12, days=1)), 12)
        self.assertEqual(full_years(TODAY + timedelta(days=1)), 0)
        self.assertEqual(full_years(None), 0)

    def test_win_rate_uses_last_12_months_and_needs_10_starts(self):
        old = [(TODAY - timedelta(days=500), 1)] * 30                    # thắng nhiều nhưng đã lâu
        recent = [(TODAY - timedelta(days=10 + i), 1 if i < 3 else (2 if i < 6 else 5)) for i in range(12)]
        stats = race_stats(old + recent)
        self.assertEqual((stats["CareerStarts"], stats["CareerWins"]), (42, 33))
        self.assertEqual((stats["RecentStarts"], stats["RecentWins"]), (12, 3))
        self.assertEqual(stats["WinRate"], 25.0)                         # 3/12, không bị kéo lên bởi 30 trận cũ
        self.assertEqual(stats["PlaceRate"], 50.0)                       # 6/12 vào top 3
        few = race_stats([(TODAY - timedelta(days=5), 1)])
        self.assertIsNone(few["WinRate"])                                # 1/1 không tính là 100%
        self.assertIn("10", few["WinRateNote"])
        self.assertEqual(few["CareerWinRate"], 100.0)

    def test_seniority_from_earliest_qualification(self):
        stats = credential_stats([("Award", years_ago(20)), ("License", years_ago(9)), ("Certificate", years_ago(4))])
        self.assertEqual((stats["Seniority"], stats["QualificationCount"], stats["AwardCount"]), (9, 2, 1))
        self.assertIsNone(credential_stats([("Award", years_ago(3))])["Seniority"])   # bằng khen không tính thâm niên


class TrainerProfileApiTests(TrainingTestCase):
    def head_client(self):
        return self.client_for(self.head)

    def test_full_profile_on_list_and_detail(self):
        head = self.head_client()
        row = next(t for t in head.get("/api/trainers").data if t["UserID"] == self.trainer.id)
        self.assertEqual((row["YearsOfExperience"], row["ExperienceLevel"], row["HasProfile"]), (0, "Junior", False))
        self.assertIsNone(row["Seniority"])

        res = head.patch(f"/api/trainers/{self.trainer.id}/profile",
                         {"CareerStartDate": years_ago(12, days=1).isoformat(), "TrainerRating": 4.6}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["YearsOfExperience"], res.data["ExperienceLevel"]), (12, "Expert"))
        self.assertEqual(res.data["ExperienceLevelName"], "Chuyên gia")

        res = head.post(f"/api/trainers/{self.trainer.id}/credentials", {
            "CredentialType": "License", "Title": "Giấy phép huấn luyện hạng A", "IssuedBy": "Hội đồng Đua ngựa",
            "IssuedDate": years_ago(9, days=1).isoformat()}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        head.post(f"/api/trainers/{self.trainer.id}/credentials", {
            "CredentialType": "Award", "Title": "HLV xuất sắc 2024", "IssuedDate": years_ago(1).isoformat()},
            format="json")
        horse_id = self.approved_horse()
        for i in range(10):
            res = head.post(f"/api/trainers/{self.trainer.id}/race-results", {
                "RaceDate": (TODAY - timedelta(days=20 + i)).isoformat(), "RaceName": f"Giải {i}",
                "RaceClass": "Handicap", "HorseID": horse_id, "FinishPosition": 1 if i < 2 else 4, "FieldSize": 10},
                format="json")
            self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["HorseName"], "Thunder")               # ngựa trong CLB: tự lấy tên
        self.assign(horse_id)

        row = next(t for t in head.get("/api/trainers").data if t["UserID"] == self.trainer.id)
        self.assertEqual((row["Seniority"], row["QualificationCount"], row["AwardCount"]), (9, 1, 1))
        self.assertEqual((row["CareerStarts"], row["CareerWins"], row["WinRate"]), (10, 2, 20.0))
        self.assertEqual((row["TrainerRating"], row["ActiveHorseCount"]), (4.6, 1))

        detail = self.client_for(self.trainer).get(f"/api/trainers/{self.trainer.id}").data  # trainer xem hồ sơ mình
        self.assertEqual(detail["ActiveHorses"][0]["HorseID"], horse_id)
        self.assertEqual(len(detail["Credentials"]), 2)
        self.assertEqual(len(detail["RecentRaceResults"]), 10)
        self.assertEqual(self.client_for(self.trainer).get(f"/api/trainers/{self.trainer2.id}").status_code, 403)
        self.assertEqual(self.client_for(self.rider).get(f"/api/trainers/{self.trainer.id}/race-results")
                         .status_code, 403)

    def test_outside_horse_and_delete(self):
        head = self.head_client()
        res = head.post(f"/api/trainers/{self.trainer.id}/race-results", {
            "RaceDate": TODAY.isoformat(), "RaceName": "Cúp Mùa Thu", "HorseName": "Ngựa ngoài CLB",
            "FinishPosition": 3, "FieldSize": 8}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data["HorseID"])
        self.assertEqual(head.delete(f"/api/trainer-race-results/{res.data['RaceResultID']}").status_code, 204)
        cred = head.post(f"/api/trainers/{self.trainer.id}/credentials", {
            "CredentialType": "Certificate", "Title": "Chứng chỉ", "IssuedDate": "2020-01-01"}, format="json").data
        self.assertEqual(head.delete(f"/api/trainer-credentials/{cred['CredentialID']}").status_code, 204)
        self.assertEqual(self.client_for(self.other_head).delete(f"/api/trainer-credentials/{cred['CredentialID']}")
                         .status_code, 404)

    def test_validation_and_permissions(self):
        head = self.head_client()
        url = f"/api/trainers/{self.trainer.id}"
        bad = [
            (f"{url}/race-results", {"RaceDate": TODAY.isoformat(), "RaceName": "x", "HorseName": "y",
                                     "FinishPosition": 9, "FieldSize": 8}, "FinishPosition"),
            (f"{url}/race-results", {"RaceDate": (TODAY + timedelta(days=2)).isoformat(), "RaceName": "x",
                                     "HorseName": "y", "FinishPosition": 1, "FieldSize": 8}, "RaceDate"),
            (f"{url}/race-results", {"RaceDate": TODAY.isoformat(), "RaceName": "x", "FinishPosition": 1,
                                     "FieldSize": 8}, "HorseName"),
            (f"{url}/credentials", {"CredentialType": "Medal", "Title": "x", "IssuedDate": "2020-01-01"},
             "CredentialType"),
            (f"{url}/credentials", {"CredentialType": "License", "Title": "x", "IssuedDate": "2020-01-01",
                                    "ExpiryDate": "2019-01-01"}, "ExpiryDate"),
        ]
        for path, body, field in bad:
            res = head.post(path, body, format="json")
            self.assertEqual(res.status_code, 400, (path, body))
            self.assertIn(field, res.data)
        res = head.patch(f"{url}/profile", {"TrainerRating": 5.5}, format="json")
        self.assertIn("TrainerRating", res.data)
        res = head.patch(f"{url}/profile", {"CareerStartDate": (TODAY + timedelta(days=1)).isoformat()},
                         format="json")
        self.assertIn("CareerStartDate", res.data)
        # trainer không tự sửa hồ sơ / tự thêm thành tích; trainer CLB khác thì không thấy
        trainer = self.client_for(self.trainer)
        self.assertEqual(trainer.patch(f"{url}/profile", {"TrainerRating": 5}, format="json").status_code, 403)
        self.assertEqual(trainer.post(f"{url}/credentials", {}, format="json").status_code, 403)
        self.assertEqual(self.client_for(self.other_head).patch(f"{url}/profile", {"TrainerRating": 3},
                                                                format="json").status_code, 404)
        self.assertEqual(head.patch(f"/api/trainers/{self.rider.id}/profile", {"TrainerRating": 3},
                                    format="json").status_code, 404)


class TrainerSuggestionTests(TrainingTestCase):
    """Ngựa tốt (QualityScore cao) nên giao trainer kỳ cựu; ngựa bình thường thì trainer mới cũng được."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        TrainerProfile.objects.create(trainer=cls.trainer, career_start_date=years_ago(12, days=1))
        TrainerProfile.objects.create(trainer=cls.trainer2, career_start_date=years_ago(1, days=1))

    def assess(self, horse_id, score):
        res = self.client_for(self.head).post(f"/api/horses/{horse_id}/assessments", {
            "SpecializationID": self.flat.id, "QualityScore": score, "FitnessLevel": "Good"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)

    def test_top_horse_needs_senior_trainer(self):
        horse_id = self.approved_horse()
        self.assess(horse_id, 92)
        rows = self.client_for(self.head).get(f"/api/trainers?HorseID={horse_id}").data
        self.assertEqual([r["UserID"] for r in rows], [self.trainer.id, self.trainer2.id])  # phù hợp xếp trước
        expert, junior = rows
        self.assertTrue(expert["IsSuggested"])
        self.assertEqual(expert["RequiredLevel"], "Senior")
        self.assertFalse(junior["IsSuggested"])
        self.assertTrue(junior["MatchesSpecialization"])
        self.assertFalse(junior["MatchesLevel"])
        self.assertIn("Senior", junior["SuggestionReason"])

        # Head Trainer vẫn giao được cho trainer mới, nhưng có cảnh báo
        res = self.client_for(self.head).post("/api/trainer-assignments", {
            "HorseID": horse_id, "TrainerID": self.trainer2.id, "SpecializationID": self.flat.id}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["TrainerExperienceLevel"], "Junior")
        self.assertEqual(res.data["LevelWarning"], "Ngựa này nên giao trainer Senior trở lên, trainer đang là Junior.")

    def test_ordinary_horse_fits_every_level(self):
        horse_id = self.approved_horse()
        self.assess(horse_id, 60)
        rows = self.client_for(self.head).get(f"/api/trainers?HorseID={horse_id}").data
        self.assertTrue(all(r["IsSuggested"] for r in rows))
        self.assertTrue(all(r["RequiredLevel"] is None for r in rows))
        res = self.client_for(self.head).post("/api/trainer-assignments", {
            "HorseID": horse_id, "TrainerID": self.trainer2.id, "SpecializationID": self.flat.id}, format="json")
        self.assertIsNone(res.data["LevelWarning"])

    def test_wrong_specialization_is_not_suggested(self):
        horse_id = self.approved_horse()
        self.client_for(self.head).post(f"/api/horses/{horse_id}/assessments", {
            "SpecializationID": self.endurance.id, "QualityScore": 50}, format="json")
        rows = self.client_for(self.head).get(f"/api/trainers?HorseID={horse_id}").data
        self.assertTrue(rows and not any(r["IsSuggested"] for r in rows))
        self.assertFalse(rows[0]["MatchesSpecialization"])


class SeedTrainerProfileTests(TestCase):
    def test_seed_demo_creates_trainer_profiles(self):
        call_command("seed_demo", f"--password={secrets.token_urlsafe(18)}", stdout=StringIO())
        token_head = User.objects.get(email="headtrainer@equi.local")
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(token_head).access_token}")
        rows = {r["Email"]: r for r in client.get("/api/trainers").data}
        expert, senior, junior = rows["trainer@equi.local"], rows["trainer2@equi.local"], rows["trainer3@equi.local"]
        self.assertEqual([r["ExperienceLevel"] for r in (expert, senior, junior)], ["Expert", "Senior", "Junior"])
        self.assertEqual((expert["CareerStarts"], expert["CareerWins"], expert["WinRate"]), (240, 58, 22.5))
        self.assertEqual(expert["AwardCount"], 2)
        self.assertGreaterEqual(expert["Seniority"], 12)
        self.assertIsNone(junior["WinRate"])                              # mới chạy 8 lần
        count = TrainerRaceResult.objects.count()
        call_command("seed_demo", f"--password={secrets.token_urlsafe(18)}", stdout=StringIO())  # chạy lại không trùng
        self.assertEqual(TrainerRaceResult.objects.count(), count)
        self.assertEqual(TrainerProfile.objects.count(), 3)
