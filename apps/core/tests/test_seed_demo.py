"""Lệnh seed_demo: dữ liệu mẫu đủ trạng thái, chạy lại không trùng, tự sửa tài khoản thiếu CLB."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Club, User
from apps.accounts.rbac import ensure_rbac_seed
from apps.horses.models import Horse, StallAssignment
from apps.horses.serializers import PROFILE_FIELDS


def seed(*args):
    call_command("seed_demo", "--password", "seed-test-password", *args, stdout=StringIO())


class SeedDemoTests(TestCase):
    def test_creates_real_names_and_sample_horses(self):
        seed()
        manager = User.objects.get(email="manager@equi.local")
        self.assertFalse(manager.full_name.startswith("Demo"))
        self.assertIsNotNone(manager.club_id)
        self.assertFalse(Club.objects.filter(club_name__icontains="demo").exists())

        statuses = sorted(Horse.objects.values_list("registration_status", flat=True))
        self.assertEqual(statuses, ["Approved", "Approved", "Approved", "Draft", "PendingExam", "Submitted"])
        approved = Horse.objects.filter(registration_status="Approved")
        self.assertTrue(all(h.horse_code for h in approved))
        self.assertEqual(StallAssignment.objects.filter(status="Active").count(), 3)
        self.assertEqual(set(approved.values_list("current_health_status", flat=True)), {"Healthy"})

        # dữ liệu thật: không để trống thông tin người dùng / lý lịch ngựa
        for user in User.objects.all():
            self.assertTrue(all([user.full_name, user.phone, user.address, user.club_id]), user.email)
        for horse in Horse.objects.all():
            self.assertTrue(all(getattr(horse, attr) for attr in PROFILE_FIELDS), horse.horse_name)
        club = Club.objects.get()
        self.assertTrue(all([club.address, club.phone, club.email]))

        seed()  # chạy lại: không tạo trùng
        self.assertEqual(Horse.objects.count(), 6)
        self.assertEqual(Club.objects.count(), 1)

    def test_repairs_old_seed_without_club(self):
        ensure_rbac_seed()
        Club.objects.create(club_name="Equi Demo Club", address="Demo")
        User.objects.create_user(email="manager@equi.local", password="x", full_name="Demo Club Manager")
        seed()
        manager = User.objects.get(email="manager@equi.local")
        club = Club.objects.get()
        self.assertEqual(club.club_name, "Equi Racing Club")
        self.assertEqual(manager.club_id, club.id)
        self.assertEqual(manager.full_name, "Nguyễn Minh Khoa")
        self.assertTrue(manager.phone and manager.address)
        self.assertNotEqual(club.address, "Demo")
        self.assertTrue(manager.check_password("x"))  # không có --reset-passwords thì giữ mật khẩu


class ManagerWithoutClubTests(TestCase):
    def test_clear_error_instead_of_db_integrity(self):
        seed()
        manager = User.objects.get(email="manager@equi.local")
        owner = User.objects.get(email="owner@equi.local")
        User.objects.filter(pk=manager.pk).update(club=None)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(manager).access_token}")
        res = client.post("/api/horses", {
            "HorseName": "Silver Comet", "OwnerID": owner.pk, "Breed": "Thoroughbred", "DateOfBirth": "2020-03-15",
            "Gender": "Male", "CoatColor": "Hạt dẻ", "SireName": "Storm King", "DamName": "Lady Rain",
            "MicrochipNumber": "985141000999001", "PassportNumber": "VN-TB-2020-0999"}, format="json")
        self.assertEqual(res.status_code, 409, res.data)
        self.assertEqual(res.data["code"], "USER_NO_CLUB")
