"""Danh mục chuyên môn giống phần SEED DATA của sql/horse_v2.sql (test kiểm tra luôn khớp) và trainer mẫu."""
from datetime import date, timedelta
from decimal import Decimal

SPECIALIZATIONS = {
    "FLAT_RACING": "Flat Racing",
    "STEEPLECHASE_HURDLE": "Steeplechase / Hurdle Racing",
    "HARNESS_RACING": "Harness Racing",
    "ENDURANCE": "Endurance / Long-distance Racing",
    "OTHER": "Other",
}


def ensure_specializations():
    from .models import Specialization

    return {code: Specialization.objects.get_or_create(code=code, defaults={"name": name})[0]
            for code, name in SPECIALIZATIONS.items()}


# Trainer mẫu của seed_demo (đủ 3 cấp để thử gợi ý trainer). Tên giải / đơn vị cấp là dữ liệu mẫu.
#   specs: chuyên môn; start: ngày bắt đầu làm nghề; credentials: (loại, tên, đơn vị cấp, ngày cấp);
#   recent / earlier: (số lần ra đường đua, số lần về nhất, số lần vào top 3) trong 12 tháng gần nhất / trước đó.
DEMO_TRAINERS = {
    "trainer@equi.local": {
        "specs": ["FLAT_RACING"], "start": date(2013, 6, 1), "rating": Decimal("4.6"),
        "credentials": [
            ("License", "Giấy phép huấn luyện ngựa đua hạng A", "Hội đồng Đua ngựa (dữ liệu mẫu)", date(2014, 3, 10)),
            ("Certificate", "Chứng chỉ Dinh dưỡng & Thể lực ngựa đua", "Equi Racing Academy", date(2016, 9, 5)),
            ("Award", "Huấn luyện viên xuất sắc mùa giải 2024", "Equi Racing Club", date(2024, 12, 20)),
            ("Award", "Ngựa vô địch Cúp Mùa Xuân 2025", "Equi Racing Club", date(2025, 4, 6)),
        ],
        "recent": (40, 9, 18), "earlier": (200, 49, 95),
    },
    "trainer2@equi.local": {
        "specs": ["STEEPLECHASE_HURDLE", "FLAT_RACING"], "start": date(2019, 1, 15), "rating": Decimal("4.2"),
        "credentials": [
            ("Certificate", "Chứng chỉ Huấn luyện đua vượt rào", "Equi Racing Academy", date(2019, 5, 20)),
            ("Award", "Bằng khen huấn luyện viên trẻ 2022", "Equi Racing Club", date(2022, 11, 30)),
        ],
        "recent": (25, 4, 9), "earlier": (95, 18, 40),
    },
    "trainer3@equi.local": {
        "specs": ["ENDURANCE", "FLAT_RACING"], "start": date(2025, 3, 1), "rating": Decimal("3.5"),
        "credentials": [
            ("Certificate", "Chứng chỉ Huấn luyện ngựa cơ bản", "Equi Racing Academy", date(2025, 8, 1)),
        ],
        "recent": (8, 1, 3), "earlier": (0, 0, 0),
    },
}
RACE_NAMES = ["Cúp Mùa Xuân", "Cúp Phú Thọ", "Giải Nước Rút", "Cúp Mùa Thu", "Giải Ngựa Non", "Cúp Cuối Năm"]
RACE_CLASSES = ["Group 1", "Group 2", "Group 3", "Listed", "Handicap", "Maiden", "Handicap", "Other"]
DEMO_HORSE_NAMES = ["Sao Mai", "Gió Bấc", "Hắc Long", "Phi Vân", "Bão Lửa", "Thiên Mã", "Kim Ô", "Bạch Hổ"]


def demo_results(plan, first_day, last_day):
    """(số lần chạy, số lần nhất, số lần top 3) rải đều từ first_day đến last_day: [(ngày, thứ hạng, số ngựa)]."""
    starts, wins, places = plan
    rows = []
    span = max((last_day - first_day).days, 1)
    for i in range(starts):
        position = 1 if i < wins else (2 + i % 2 if i < places else 4 + i % 6)
        rows.append((last_day - timedelta(days=span * i // max(starts, 1)), position, 10 + i % 4))
    return rows


def seed_demo(club):
    """Gọi từ `python manage.py seed_demo` khi đã có Flow 2. Chạy lại không tạo trùng, không ghi đè dữ liệu đã có."""
    from apps.accounts.models import User

    from .models import TrainerCredential, TrainerProfile, TrainerRaceResult, TrainerSpecialization

    specializations = ensure_specializations()
    manager = User.objects.filter(email__iexact="headtrainer@equi.local").first()
    today = date.today()
    for email, info in DEMO_TRAINERS.items():
        trainer = User.objects.filter(email__iexact=email, club=club).first()
        if trainer is None:
            continue
        for code in info["specs"]:
            if not TrainerSpecialization.objects.filter(trainer=trainer, specialization=specializations[code]).exists():
                TrainerSpecialization.objects.create(trainer=trainer, specialization=specializations[code])
        if not TrainerProfile.objects.filter(trainer=trainer).exists():
            TrainerProfile.objects.create(trainer=trainer, career_start_date=info["start"],
                                          trainer_rating=info["rating"], updated_by=manager)
        if not TrainerCredential.objects.filter(trainer=trainer).exists():
            for kind, title, issued_by, issued in info["credentials"]:
                TrainerCredential.objects.create(trainer=trainer, credential_type=kind, title=title,
                                                 issued_by=issued_by, issued_date=issued, created_by=manager or trainer)
        if not TrainerRaceResult.objects.filter(trainer=trainer).exists():
            rows = demo_results(info["recent"], today - timedelta(days=360), today - timedelta(days=3))
            rows += demo_results(info["earlier"], info["start"] + timedelta(days=200), today - timedelta(days=370))
            TrainerRaceResult.objects.bulk_create([
                TrainerRaceResult(trainer=trainer, horse_name=DEMO_HORSE_NAMES[i % len(DEMO_HORSE_NAMES)], race_date=day,
                                  race_name=f"{RACE_NAMES[i % len(RACE_NAMES)]} {day.year}",
                                  race_class=RACE_CLASSES[i % len(RACE_CLASSES)], finish_position=position,
                                  field_size=size, created_by=manager or trainer)
                for i, (day, position, size) in enumerate(rows)
            ])
