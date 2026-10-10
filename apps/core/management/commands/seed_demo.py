"""
Tạo dữ liệu demo để chạy thử frontend:  python manage.py seed_demo --password <mật-khẩu-dev>

- Bổ sung Role / Permission / RolePermission nếu thiếu (horse_v2.sql thường đã có sẵn).
- Bổ sung danh mục chuyên môn (Specialization) nếu thiếu.
- Tạo 1 CLB demo, 6 chuồng, vài vật tư trong kho và 1 tài khoản cho mỗi vai trò (email @equi.local);
  trainer demo có chuyên môn Flat Racing để Head Trainer phân công được ngay.
- Không có --password: tạo ngẫu nhiên một mật khẩu chung và in ra màn hình.
- Chạy lại nhiều lần được: dòng nào đã có thì giữ nguyên
  (thêm --reset-passwords nếu muốn đặt lại mật khẩu cho các tài khoản demo).

Không đưa mật khẩu demo lên GitHub; mỗi máy tự chạy lệnh này.
"""
import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Club, Role, User, UserRole
from apps.accounts.rbac import ensure_rbac_seed
from apps.care.models import InventoryItem
from apps.horses.models import Stall
from apps.training.models import TrainerSpecialization
from apps.training.seed import ensure_specializations

DEMO_CLUB = "Equi Demo Club"
DEMO_USERS = [
    ("manager@equi.local", "Demo Club Manager", "CLUB_MANAGER"),
    ("headtrainer@equi.local", "Demo Head Trainer", "HEAD_TRAINER"),
    ("trainer@equi.local", "Demo Trainer", "TRAINER"),
    ("rider@equi.local", "Demo Work Rider", "WORK_RIDER"),
    ("vet@equi.local", "Demo Veterinarian", "VETERINARIAN"),
    ("groom@equi.local", "Demo Groom", "GROOM"),
    ("owner@equi.local", "Demo Horse Owner", "HORSE_OWNER"),
]
DEMO_ITEMS = [("Yến mạch", "Food", "kg", 500, 100), ("Cỏ khô", "Food", "kg", 1000, 200),
              ("Băng chân", "Care Equipment", "cuộn", 40, 10), ("Thuốc sát trùng", "Medicine", "chai", 12, 5)]
DEMO_STALLS = [("A01", "Standard"), ("A02", "Standard"), ("A03", "Standard"), ("A04", "Standard"),
               ("B01", "Foaling"), ("Q01", "Quarantine")]


class Command(BaseCommand):
    help = "Tạo CLB, chuồng và tài khoản demo cho từng vai trò."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Mật khẩu chung cho các tài khoản demo (bỏ trống = ngẫu nhiên).")
        parser.add_argument("--reset-passwords", action="store_true",
                            help="Đặt lại mật khẩu cho các tài khoản demo đã tồn tại.")

    @transaction.atomic
    def handle(self, *args, **options):
        password = options.get("password") or secrets.token_urlsafe(9)
        reset = options["reset_passwords"]

        ensure_rbac_seed()
        specializations = ensure_specializations()
        club, _ = Club.objects.get_or_create(club_name=DEMO_CLUB, defaults={"address": "Demo", "status": "Active"})
        for number, stall_type in DEMO_STALLS:
            if not Stall.objects.filter(club=club, stall_number=number).exists():
                Stall.objects.create(club=club, stall_number=number, stall_type=stall_type)

        for name, item_type, unit, quantity, minimum in DEMO_ITEMS:
            if not InventoryItem.objects.filter(club=club, item_name=name).exists():
                item = InventoryItem(club=club, item_name=name, item_type=item_type, unit=unit, quantity=quantity,
                                     minimum_quantity=minimum)
                item.refresh_status()
                item.save()

        rows = []
        for email, full_name, role_code in DEMO_USERS:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = User.objects.create_user(email=email, password=password, full_name=full_name, club=club)
                state = "tạo mới"
            elif reset:
                user.set_password(password)
                user.save(update_fields=["password"])
                state = "đặt lại mật khẩu"
            else:
                state = "đã có (giữ mật khẩu cũ)"
            role = Role.objects.get(code=role_code)
            if not UserRole.objects.filter(user=user, role=role).exists():
                UserRole.objects.create(user=user, role=role)
            if role_code == "TRAINER" and not TrainerSpecialization.objects.filter(trainer=user).exists():
                TrainerSpecialization.objects.create(trainer=user, specialization=specializations["FLAT_RACING"])
            rows.append((role_code, email, state))

        self.stdout.write(self.style.SUCCESS(f"CLB demo: {club.club_name} (ClubID={club.id})"))
        for role_code, email, state in rows:
            self.stdout.write(f"  {role_code:<14} {email:<26} {state}")
        if any(state != "đã có (giữ mật khẩu cũ)" for _, _, state in rows):
            self.stdout.write(self.style.WARNING(f"Mật khẩu cho tài khoản vừa tạo / đặt lại: {password}"))
