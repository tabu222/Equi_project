"""Lệnh seed_demo: dữ liệu mẫu đủ trạng thái, chạy lại không trùng, tự sửa tài khoản thiếu CLB."""
from io import StringIO
import secrets

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Club, User, UserRole
from apps.accounts.rbac import ensure_rbac_seed
from apps.horses.models import Horse, Stall, StallAssignment, RegistrationRequest
from apps.horses.serializers import PROFILE_FIELDS
from apps.medical.models import MedicalRecord


def seed(*args):
    # "--password=..." (một đối số): mật khẩu ngẫu nhiên có thể bắt đầu bằng "-" làm argparse hiểu nhầm là tùy chọn
    call_command("seed_demo", f"--password={secrets.token_urlsafe(18)}", *args, stdout=StringIO())


class SeedDemoTests(TestCase):
    def test_rerun_preserves_passwords_data_and_all_counts(self):
        seed()
        manager = User.objects.get(email="manager@equi.local")
        old_password = secrets.token_urlsafe(18)
        manager.set_password(old_password)
        manager.phone = "0901112233"
        manager.address = "Existing contact address"
        manager.save()
        old_hash = manager.password
        models = (Club, User, UserRole, Horse, Stall, StallAssignment, RegistrationRequest, MedicalRecord)
        before = [model.objects.count() for model in models]
        horses_before = list(Horse.objects.values())
        seed()
        manager.refresh_from_db()
        self.assertEqual([model.objects.count() for model in models], before)
        self.assertEqual(list(Horse.objects.values()), horses_before)
        self.assertEqual(manager.password, old_hash)
        self.assertTrue(manager.check_password(old_password))
        self.assertEqual(manager.phone, "0901112233")
        self.assertEqual(manager.address, "Existing contact address")

    def test_explicit_reset_only_changes_demo_passwords(self):
        seed()
        old_password, new_password = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
        outsider = User.objects.create_user(email="existing@example.test", password=old_password, full_name="Existing")
        call_command("seed_demo", password=new_password, reset_passwords=True, stdout=StringIO())
        self.assertTrue(User.objects.get(email="manager@equi.local").check_password(new_password))
        outsider.refresh_from_db()
        self.assertTrue(outsider.check_password(old_password))

    def test_existing_email_is_matched_case_insensitively(self):
        ensure_rbac_seed()
        User.objects.create_user(email="MANAGER@equi.local", password=secrets.token_urlsafe(18), full_name="Existing")
        seed()
        self.assertEqual(User.objects.filter(email__iexact="manager@equi.local").count(), 1)
        self.assertEqual(User.objects.count(), 18)

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

        # 2 Vet trong CLB; phiếu khám mẫu do Vet thứ nhất ký
        vets = User.objects.filter(roles__code="VETERINARIAN", club=manager.club)
        self.assertEqual(sorted(vets.values_list("email", flat=True)),
                         ["vet2@equi.local", "vet3@equi.local", "vet@equi.local"])
        # đủ người cho mỗi vai trò, mỗi trainer một chuyên môn khác nhau
        self.assertEqual(User.objects.count(), 18)
        for code, count in {"CLUB_MANAGER": 1, "HEAD_TRAINER": 2, "TRAINER": 3, "WORK_RIDER": 3, "GROOM": 3,
                            "HORSE_OWNER": 3}.items():
            self.assertEqual(User.objects.filter(roles__code=code).count(), count, code)
        self.assertEqual(set(MedicalRecord.objects.values_list("vet__email", flat=True)), {"vet@equi.local"})

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
