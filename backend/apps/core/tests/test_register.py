"""Chủ ngựa tự đăng ký tài khoản ở trang đăng nhập: POST /api/auth/register."""
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import AuditLog

from .helpers import Flow1TestCase


class OwnerRegisterTests(Flow1TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # reset bộ đếm chống spam giữa các test

    def payload(self, **extra):
        data = {"FullName": "Nguyễn Văn An", "Email": "An.Owner@one.test", "Phone": "0901234567",
                "Address": "Q1, TP.HCM", "Password": "matkhau1", "ClubID": self.club.id}
        data.update(extra)
        return data

    def test_register_creates_owner_and_logs_in(self):
        res = APIClient().post("/api/auth/register", self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIn("access", res.data)
        self.assertEqual(res.data["User"]["Roles"], ["HORSE_OWNER"])
        self.assertEqual(res.data["User"]["ClubID"], self.club.id)
        self.assertIn("HORSE_REGISTER", res.data["User"]["Permissions"])

        user = User.objects.get(email="an.owner@one.test")
        self.assertTrue(user.check_password("matkhau1"))
        self.assertTrue(AuditLog.objects.filter(action_type="REGISTER_OWNER", entity_id=user.pk).exists())

        # đăng nhập lại bằng tài khoản vừa tạo
        login = APIClient().post("/api/auth/login", {"Email": "an.owner@one.test", "Password": "matkhau1"},
                                 format="json")
        self.assertEqual(login.status_code, 200, login.data)

        # token dùng được ngay: tạo hồ sơ ngựa nháp của chính mình
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(client.get("/api/horses").status_code, 200)

        # Manager CLB thấy chủ ngựa mới trong danh sách để chọn khi nhập hộ
        owners = self.client_for(self.manager).get("/api/users?RoleCode=HORSE_OWNER").data
        self.assertIn("an.owner@one.test", [u["Email"] for u in owners])

    def test_cannot_choose_other_role(self):
        res = APIClient().post("/api/auth/register", self.payload(RoleCode="CLUB_MANAGER"), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["User"]["Roles"], ["HORSE_OWNER"])

    def test_validation_errors(self):
        client = APIClient()
        cases = {
            "Email": self.payload(Email="OWNER@one.test"),  # trùng email đã có
            "Password": self.payload(Password="123"),
            "Phone": self.payload(Phone="12345"),
            "ClubID": self.payload(ClubID=99999),
        }
        for field, body in cases.items():
            res = client.post("/api/auth/register", body, format="json")
            self.assertEqual(res.status_code, 400, field)
            self.assertIn(field, str(res.data), field)
        missing = self.payload()
        del missing["ClubID"]
        self.assertEqual(client.post("/api/auth/register", missing, format="json").status_code, 400)
        self.assertFalse(User.objects.filter(email="an.owner@one.test").exists())

    def test_club_list_is_public(self):
        res = APIClient().get("/api/clubs")
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.club.id, [c["ClubID"] for c in res.data])
