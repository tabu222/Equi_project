"""
Tạo dữ liệu demo để chạy thử frontend:  python manage.py seed_demo --password <mật-khẩu-dev>

- Bổ sung Role / Permission / RolePermission nếu thiếu (horse_v2.sql thường đã có sẵn).
- Tạo 1 CLB mẫu (đủ địa chỉ, điện thoại, email), 6 chuồng và 18 tài khoản (email @equi.local,
  họ tên người thật, có số điện thoại và địa chỉ): 1 Manager, 2 Head Trainer, 3 Trainer, 3 Work Rider, 3 Vet,
  3 Groom, 3 chủ ngựa. Có Flow 2: thêm chuyên môn và hồ sơ năng lực (kinh nghiệm, cấp độ...) cho 3 trainer.
  Có Flow 3: thêm lịch tiêm phòng, lịch đóng móng và 1 báo cáo sức khỏe đang chờ Vet.
  Có Flow 4: thêm vật tư trong kho (1 loại dưới mức tối thiểu để thấy cảnh báo).
- Tạo 6 ngựa mẫu của chủ ngựa mẫu, đi qua đúng luồng Flow 1 nên đủ các trạng thái để thử giao diện:
  3 ngựa Approved (có mã ngựa, chuồng, phiếu khám đầu vào), 1 PendingExam, 1 Submitted, 1 Draft.
- Tài khoản mẫu cũ đang thiếu CLB / số điện thoại / địa chỉ được điền bổ sung; tên cũ "Demo ..." đổi sang tên mới.
- Không có --password: tạo ngẫu nhiên một mật khẩu chung và in ra màn hình.
- Chạy lại nhiều lần được: dòng nào đã có thì giữ nguyên
  (thêm --reset-passwords nếu muốn đặt lại mật khẩu cho các tài khoản demo).

Không đưa mật khẩu demo lên GitHub; mỗi máy tự chạy lệnh này.
"""
import secrets
import os
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Club, Role, User, UserRole
from apps.accounts.rbac import ensure_rbac_seed
from apps.core import flows
from apps.horses import services as horse_services
from apps.horses.models import Horse, Stall
from apps.medical import services as medical_services
from apps.medical.models import MedicalRecord

CLUB_NAME = "Equi Racing Club"
OLD_CLUB_NAMES = ["Equi Demo Club"]          # tên CLB ở bản seed cũ: chạy lại thì đổi tên, không tạo CLB thứ hai
CLUB_INFO = {"address": "120 Lê Đại Hành, Phường 7, Quận 11, TP. Hồ Chí Minh", "phone": "02838551234",
             "email": "lienhe@equi.local", "status": "Active"}
# (email đăng nhập, họ tên, vai trò, số điện thoại, địa chỉ)
DEMO_USERS = [
    ("manager@equi.local", "Nguyễn Minh Khoa", "CLUB_MANAGER", "0903125478",
     "45 Nguyễn Chí Thanh, Phường 9, Quận 5, TP. Hồ Chí Minh"),
    ("headtrainer@equi.local", "Lê Hoàng Phúc", "HEAD_TRAINER", "0912346870",
     "18 Lạc Long Quân, Phường 3, Quận 11, TP. Hồ Chí Minh"),
    ("headtrainer2@equi.local", "Trương Văn Nghĩa", "HEAD_TRAINER", "0913572046",
     "105 Âu Cơ, Phường 14, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("trainer@equi.local", "Phạm Quốc Bảo", "TRAINER", "0938452116",
     "72 Hòa Hảo, Phường 4, Quận 10, TP. Hồ Chí Minh"),
    ("trainer2@equi.local", "Huỳnh Thị Mai", "TRAINER", "0939264851",
     "21 Tô Hiến Thành, Phường 13, Quận 10, TP. Hồ Chí Minh"),
    ("trainer3@equi.local", "Đặng Quang Vinh", "TRAINER", "0936807193",
     "58 Phan Xích Long, Phường 2, Quận Phú Nhuận, TP. Hồ Chí Minh"),
    ("rider@equi.local", "Võ Thanh Tùng", "WORK_RIDER", "0977215348",
     "9 Bình Thới, Phường 14, Quận 11, TP. Hồ Chí Minh"),
    ("rider2@equi.local", "Lâm Gia Bảo", "WORK_RIDER", "0978346120",
     "140 Minh Phụng, Phường 6, Quận 6, TP. Hồ Chí Minh"),
    ("rider3@equi.local", "Phan Ngọc Ánh", "WORK_RIDER", "0976518243",
     "36 Hậu Giang, Phường 2, Quận 6, TP. Hồ Chí Minh"),
    ("vet@equi.local", "Trần Thu Hà", "VETERINARIAN", "0908663192",
     "250 Lý Thường Kiệt, Phường 14, Quận 10, TP. Hồ Chí Minh"),
    ("vet2@equi.local", "Ngô Minh Tuấn", "VETERINARIAN", "0935718264",
     "14 Ngô Gia Tự, Phường 2, Quận 10, TP. Hồ Chí Minh"),
    ("vet3@equi.local", "Lê Thị Thu", "VETERINARIAN", "0907123456",
     "25 Nguyễn Văn Cừ, Phường 1, Quận 5, TP. Hồ Chí Minh"),
    ("groom@equi.local", "Đỗ Văn Lộc", "GROOM", "0962781405",
     "33 Tôn Thất Hiệp, Phường 13, Quận 11, TP. Hồ Chí Minh"),
    ("groom2@equi.local", "Nguyễn Văn Tài", "GROOM", "0963158027",
     "77 Ông Ích Khiêm, Phường 10, Quận 11, TP. Hồ Chí Minh"),
    ("groom3@equi.local", "Bùi Thị Hạnh", "GROOM", "0964902317",
     "12 Lò Siêu, Phường 16, Quận 11, TP. Hồ Chí Minh"),
    ("owner@equi.local", "Hoàng Gia Huy", "HORSE_OWNER", "0918034567",
     "86 Nguyễn Văn Trỗi, Phường 8, Quận Phú Nhuận, TP. Hồ Chí Minh"),
    ("owner2@equi.local", "Lý Thanh Sơn", "HORSE_OWNER", "0909123456",
     "12 Nguyễn Trãi, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh"),
    ("owner3@equi.local", "Trịnh Ngọc Diệp", "HORSE_OWNER", "0917465230",
     "190 Hai Bà Trưng, Phường Đa Kao, Quận 1, TP. Hồ Chí Minh"),
]
DEMO_STALLS = [("A01", "Standard"), ("A02", "Standard"), ("A03", "Standard"), ("A04", "Standard"),
               ("B01", "Foaling"), ("Q01", "Quarantine")]

# Ngựa mẫu: (thông tin lý lịch, trạng thái cần đạt, mã ngựa, chuồng, cân nặng kg, chiều cao cm)
DEMO_HORSES = [
    (dict(horse_name="Sao Mai", breed="Thoroughbred", date_of_birth=date(2021, 3, 12), gender="Female",
          coat_color="Nâu đỏ (Bay)", sire_name="Northern Ridge", dam_name="Morning Dew",
          microchip_number="985141000123401", passport_number="VN-TB-2021-0142"),
     "Approved", "EQ-001", "A01", 465, 162),
    (dict(horse_name="Gió Bấc", breed="Thoroughbred", date_of_birth=date(2019, 5, 2), gender="Male",
          coat_color="Hạt dẻ (Chestnut)", sire_name="Silver Gale", dam_name="River Song",
          microchip_number="985141000123402", passport_number="VN-TB-2019-0087"),
     "Approved", "EQ-002", "A02", 510, 166),
    (dict(horse_name="Hắc Long", breed="Arabian", date_of_birth=date(2018, 9, 20), gender="Gelding",
          coat_color="Đen (Black)", sire_name="Desert Shadow", dam_name="Night Lily",
          microchip_number="985141000123403", passport_number="VN-AR-2018-0031"),
     "Approved", "EQ-003", "A03", 430, 152),
    (dict(horse_name="Bạch Vân", breed="Arabian", date_of_birth=date(2022, 1, 15), gender="Female",
          coat_color="Xám (Grey)", sire_name="White Falcon", dam_name="Cloud Dancer",
          microchip_number="985141000123404", passport_number="VN-AR-2022-0005"),
     "PendingExam", None, None, None, None),
    (dict(horse_name="Tia Chớp", breed="Quarter Horse", date_of_birth=date(2020, 7, 8), gender="Male",
          coat_color="Nâu (Brown)", sire_name="Thunder Road", dam_name="Prairie Rose",
          microchip_number="985141000123405", passport_number="VN-QH-2020-0012"),
     "Submitted", None, None, None, None),
    (dict(horse_name="Hoàng Kim", breed="Thoroughbred", date_of_birth=date(2022, 4, 30), gender="Male",
          coat_color="Vàng (Palomino)", sire_name="Golden Era", dam_name="Sunny Bay",
          microchip_number="985141000123406", passport_number="VN-TB-2022-0063"),
     "Draft", None, None, None, None),
]


class Command(BaseCommand):
    help = "Tạo CLB, chuồng và tài khoản demo cho từng vai trò."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Mật khẩu chung cho các tài khoản demo (bỏ trống = ngẫu nhiên).")
        parser.add_argument("--reset-passwords", action="store_true",
                            help="Đặt lại mật khẩu cho các tài khoản demo đã tồn tại.")

    @transaction.atomic
    def handle(self, *args, **options):
        password = options.get("password") or os.getenv("EQUI_DEMO_PASSWORD") or secrets.token_urlsafe(12)
        reset = options["reset_passwords"]

        ensure_rbac_seed()
        club = self.ensure_club()
        for number, stall_type in DEMO_STALLS:
            if not Stall.objects.filter(club=club, stall_number=number).exists():
                Stall.objects.create(club=club, stall_number=number, stall_type=stall_type)

        rows = []
        for email, full_name, role_code, phone, address in DEMO_USERS:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = User.objects.create_user(email=email, password=password, full_name=full_name, club=club,
                                                phone=phone, address=address)
                state = "tạo mới"
            else:
                changed = []
                if user.club_id is None:              # tài khoản thiếu CLB thì không tạo ngựa / phân công được
                    user.club = club
                    changed.append("club")
                if user.full_name.startswith("Demo "):  # tên cũ kiểu "Demo Club Manager"
                    user.full_name = full_name
                    changed.append("full_name")
                for attr, value in (("phone", phone), ("address", address)):
                    if not getattr(user, attr):         # dữ liệu cũ để trống -> điền thông tin thật
                        setattr(user, attr, value)
                        changed.append(attr)
                if reset:
                    user.set_password(password)
                    changed.append("password")
                if changed:
                    user.save(update_fields=changed)
                state = "đặt lại mật khẩu" if reset else "đã có (giữ mật khẩu cũ)"
            role = Role.objects.get(code=role_code)
            if not UserRole.objects.filter(user=user, role=role).exists():
                UserRole.objects.create(user=user, role=role)
            rows.append((role_code, email, state))

        horses = self.ensure_horses(club)
        if flows.has_training():  # Flow 2: chuyên môn + hồ sơ năng lực của 3 trainer mẫu
            from apps.training.seed import seed_demo as seed_training
            seed_training(club)
        if flows.has_flow3():  # Flow 3: lịch tiêm phòng, lịch y tế, 1 báo cáo sức khỏe đang mở
            from apps.medical.seed import seed_demo as seed_medical
            seed_medical(club)
        if flows.has_care():  # Flow 4: vật tư trong kho
            from apps.care.seed import seed_demo as seed_care
            seed_care(club)

        self.stdout.write(self.style.SUCCESS(f"CLB mẫu: {club.club_name} (ClubID={club.id})"))
        for role_code, email, state in rows:
            self.stdout.write(f"  {role_code:<14} {email:<26} {state}")
        if any(state != "đã có (giữ mật khẩu cũ)" for _, _, state in rows):
            self.stdout.write(self.style.WARNING(f"Mật khẩu cho tài khoản vừa tạo / đặt lại: {password}"))
        if horses:
            self.stdout.write(f"Ngựa mẫu vừa tạo: {', '.join(horses)}")

    def ensure_club(self):
        club = Club.objects.filter(club_name=CLUB_NAME).first()
        if club is None:
            club = Club.objects.filter(club_name__in=OLD_CLUB_NAMES).first()
            if club is not None:
                club.club_name = CLUB_NAME
        if club is None:
            return Club.objects.create(club_name=CLUB_NAME, **CLUB_INFO)
        for attr, value in CLUB_INFO.items():       # điền thông tin còn trống, giữ nguyên thông tin đã có
            if not getattr(club, attr) or getattr(club, attr) == "Demo":
                setattr(club, attr, value)
        club.save()
        return club

    def ensure_horses(self, club):
        """Tạo ngựa mẫu qua đúng các bước Flow 1. Ngựa nào đã có (cùng tên, cùng chủ) thì bỏ qua."""
        users = {email: User.objects.get(email__iexact=email) for email, *_ in DEMO_USERS}
        owner, manager, vet = users["owner@equi.local"], users["manager@equi.local"], users["vet@equi.local"]
        created = []
        for info, target, code, stall_number, weight, height in DEMO_HORSES:
            if Horse.objects.filter(owner=owner, horse_name=info["horse_name"]).exists():
                continue
            horse = Horse(club=club, owner=owner, **info)
            horse.save()
            if target != "Draft":
                horse_services.submit(horse, owner)
            if target in ("PendingExam", "Approved"):
                horse_services.verify(horse, manager)
            if target == "Approved":
                record = medical_services.create_record(horse, vet, {
                    "exam_type": MedicalRecord.ExamType.INITIAL, "weight_kg": weight, "height_cm": height,
                    "health_status": "Healthy", "training_eligibility": "Eligible",
                    "conclusion": "Sức khỏe tốt, đạt yêu cầu tiếp nhận.",
                })
                medical_services.sign_record(record, vet)
                stall = Stall.objects.filter(club=club, stall_number=stall_number, status="Available").first()
                if stall is not None and stall.assignments.filter(status="Active").exists():
                    stall = None
                if Horse.objects.filter(club=club, horse_code=code).exists():
                    code = f"{code}-{horse.pk}"
                horse_services.approve(horse, manager, code, stall.pk if stall else None)
            created.append(f"{horse.horse_name} ({target})")
        return created
