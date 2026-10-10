"""Dữ liệu dựng sẵn cho test (chạy trên SQLite, xem config/settings_test.py)."""
from datetime import date

from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Club, Role, User, UserRole
from apps.accounts.rbac import ensure_rbac_seed
from apps.horses.models import Stall

TEST_PASSWORD = "test-only-password"


class Flow1TestCase(APITestCase):
    """Hai CLB, mỗi vai trò một tài khoản ở CLB 1, thêm Manager / Vet của CLB 2 để thử cách ly dữ liệu."""

    @classmethod
    def setUpTestData(cls):
        ensure_rbac_seed()
        cls.club = Club.objects.create(club_name="Club One")
        cls.other_club = Club.objects.create(club_name="Club Two")
        cls.inactive_club = Club.objects.create(club_name="Closed Club", status="Inactive")

        cls.manager = cls.make_user("manager@one.test", "CLUB_MANAGER", cls.club)
        cls.vet = cls.make_user("vet@one.test", "VETERINARIAN", cls.club)
        cls.vet2 = cls.make_user("vet2@one.test", "VETERINARIAN", cls.club)
        cls.trainer = cls.make_user("trainer@one.test", "TRAINER", cls.club)
        cls.owner = cls.make_user("owner@one.test", "HORSE_OWNER", cls.club)
        cls.other_owner = cls.make_user("owner2@one.test", "HORSE_OWNER", None)
        cls.other_manager = cls.make_user("manager@two.test", "CLUB_MANAGER", cls.other_club)
        cls.other_vet = cls.make_user("vet@two.test", "VETERINARIAN", cls.other_club)

        cls.stall = Stall.objects.create(club=cls.club, stall_number="A01")
        cls.other_stall = Stall.objects.create(club=cls.other_club, stall_number="Z01")

    @staticmethod
    def make_user(email, role_code, club):
        user = User.objects.create_user(email=email, password=TEST_PASSWORD, full_name=email.split("@")[0],
                                        club=club)
        UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))
        return user

    def client_for(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
        return client

    # ---------- các bước Flow 1 dùng lại nhiều lần ----------
    def horse_payload(self, **extra):
        payload = {
            "HorseName": "Thunder", "Breed": "Thoroughbred", "DateOfBirth": "2021-03-10",
            "CoatColor": "Bay", "Gender": "Male", "SireName": "Storm King", "DamName": "Lady Rain",
            "MicrochipNumber": "985000000000001", "PassportNumber": "VN-001",
        }
        payload.update(extra)
        return payload

    def owner_creates_horse(self, **extra):
        res = self.client_for(self.owner).post("/api/horses", self.horse_payload(ClubID=self.club.id, **extra),
                                               format="json")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data["HorseID"]

    def submit_and_verify(self, horse_id):
        res = self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        self.assertEqual(res.status_code, 200, res.data)
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/verify")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["RegistrationStatus"], "PendingExam")

    def vet_signs_initial_exam(self, horse_id, health="Healthy", eligibility="Eligible", vet=None):
        client = self.client_for(vet or self.vet)
        res = client.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Initial Exam", "WeightKg": 480.5, "HeightCm": 162.0, "Symptoms": "Không có",
            "Diagnosis": "Bình thường", "Conclusion": "Đủ điều kiện", "HealthStatus": health,
            "TrainingEligibility": eligibility,
            "RestrictionNote": "Chỉ tập nhẹ" if eligibility == "Restricted" else None,
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        record_id = res.data["MedicalRecordID"]
        res = client.post(f"/api/medical-records/{record_id}/sign")
        self.assertEqual(res.status_code, 200, res.data)
        return record_id

    def approved_horse(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-001"},
                                                 format="json")
        self.assertEqual(res.status_code, 200, res.data)
        return horse_id


def years_ago(years, month=1, day=1):
    return date(date.today().year - years, month, day).isoformat()
