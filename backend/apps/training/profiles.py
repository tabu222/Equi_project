"""
Hồ sơ năng lực Trainer và gợi ý Trainer cho ngựa. Các chỉ số đều TÍNH từ dữ liệu, không nhập tay:

YearsOfExperience  số năm làm nghề, tính từ CareerStartDate (ngày bắt đầu làm nghề) -> tự tăng theo thời gian.
ExperienceLevel    theo YearsOfExperience:  0-2 năm Junior · 3-5 Intermediate · 6-10 Senior · trên 10 Expert.
Seniority          thâm niên nghề ĐƯỢC CHỨNG MINH: số năm tính từ bằng cấp / chứng chỉ / giấy phép hành nghề
                   sớm nhất (TrainerCredential); kèm số giấy tờ và số bằng khen.
WinRate            giống "strike rate" của ngành đua: số lần về nhất / số lần ra đường đua trong 12 THÁNG GẦN NHẤT
                   (phong độ hiện tại). Chạy dưới 10 lần trong 12 tháng thì chưa tính (mẫu quá nhỏ, 1/1 = 100%).
PlaceRate          tỉ lệ về top 3 trong 12 tháng gần nhất (cùng điều kiện 10 lần).
CareerStarts/Wins  tổng cả sự nghiệp (mọi TrainerRaceResult); CareerWinRate = CareerWins / CareerStarts.

Gợi ý theo phiếu đánh giá ngựa gần nhất (HorseAssessment, DecisionStatus = Recommended):
    - chuyên môn của trainer phải khớp chuyên môn được đề xuất;
    - cấp độ tối thiểu theo QualityScore (ngựa càng tốt, càng nhắm giải lớn thì cần trainer càng kỳ cựu):
          QualityScore >= 85  -> Senior trở lên
          QualityScore >= 70  -> Intermediate trở lên
          còn lại / chưa chấm -> mọi cấp (Junior nhận để tích lũy kinh nghiệm)
    - xếp hạng: đủ điều kiện trước, rồi cấp độ cao hơn, ít ngựa đang phụ trách hơn, TrainerRating cao hơn.
"""
from datetime import date, timedelta

LEVELS = ["Junior", "Intermediate", "Senior", "Expert"]
LEVEL_NAMES_VI = {"Junior": "Mới vào nghề", "Intermediate": "Trung cấp", "Senior": "Kỳ cựu", "Expert": "Chuyên gia"}
RECENT_DAYS = 365          # cửa sổ tính WinRate / PlaceRate
MIN_RECENT_STARTS = 10     # tối thiểu số lần chạy trong cửa sổ để tính tỉ lệ
QUALIFICATION_TYPES = ("Degree", "Certificate", "License")


def full_years(start, today=None):
    """Số năm tròn từ ngày start đến hôm nay (0 nếu chưa có / ở tương lai)."""
    today = today or date.today()
    if start is None or start > today:
        return 0
    return today.year - start.year - ((today.month, today.day) < (start.month, start.day))


def experience_level(years) -> str:
    years = years or 0
    if years <= 2:
        return "Junior"
    if years <= 5:
        return "Intermediate"
    if years <= 10:
        return "Senior"
    return "Expert"


def level_rank(level) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


def percent(part, total):
    return round(part * 100 / total, 1) if total else None


def race_stats(results, today=None):
    """results: danh sách (race_date, finish_position). Trả về các chỉ số đua của trainer."""
    today = today or date.today()
    since = today - timedelta(days=RECENT_DAYS)
    recent = [pos for day, pos in results if day >= since]
    starts, wins = len(results), sum(1 for _, pos in results if pos == 1)
    recent_starts, recent_wins = len(recent), sum(1 for pos in recent if pos == 1)
    recent_places = sum(1 for pos in recent if pos <= 3)
    enough = recent_starts >= MIN_RECENT_STARTS
    return {
        "CareerStarts": starts,
        "CareerWins": wins,
        "CareerWinRate": percent(wins, starts),
        "RecentStarts": recent_starts,
        "RecentWins": recent_wins,
        "WinRate": percent(recent_wins, recent_starts) if enough else None,
        "PlaceRate": percent(recent_places, recent_starts) if enough else None,
        "WinRateNote": None if enough else
        f"Chưa đủ {MIN_RECENT_STARTS} lần ra đường đua trong 12 tháng ({recent_starts} lần) để tính tỉ lệ thắng.",
    }


def credential_stats(credentials, today=None):
    """credentials: danh sách (credential_type, issued_date). Seniority = năm từ giấy tờ chuyên môn sớm nhất."""
    qualification_dates = [day for kind, day in credentials if kind in QUALIFICATION_TYPES]
    first = min(qualification_dates) if qualification_dates else None
    return {
        "Seniority": full_years(first, today) if first else None,
        "SenioritySince": first,
        "QualificationCount": len(qualification_dates),
        "AwardCount": sum(1 for kind, _ in credentials if kind == "Award"),
    }


def profile_body(trainer, profile, active_horse_count, credentials=(), results=()):
    """Các trường hồ sơ trainer trả về cho frontend (cùng tên ở mọi API)."""
    start = profile.career_start_date if profile else None
    years = full_years(start)
    level = experience_level(years)
    return {
        "CareerStartDate": start,
        "YearsOfExperience": years,
        "ExperienceLevel": level,
        "ExperienceLevelName": LEVEL_NAMES_VI[level],
        **credential_stats(credentials),
        **race_stats(results),
        "TrainerRating": float(profile.trainer_rating) if profile and profile.trainer_rating is not None else None,
        "ActiveHorseCount": active_horse_count,
        "HasProfile": profile is not None,
    }


def required_level(assessment):
    """Cấp độ tối thiểu nên giao cho ngựa theo phiếu đánh giá (None = mọi cấp)."""
    score = getattr(assessment, "quality_score", None)
    if score is None:
        return None
    if score >= 85:
        return "Senior"
    if score >= 70:
        return "Intermediate"
    return None


def suggestion(body, specialization_ids, assessment):
    """Thêm IsSuggested / RequiredLevel / SuggestionReason cho một trainer theo phiếu đánh giá ngựa."""
    need = required_level(assessment)
    spec_ok = assessment is None or assessment.specialization_id in specialization_ids
    level_ok = need is None or level_rank(body["ExperienceLevel"]) >= level_rank(need)
    reasons = []
    if assessment is not None:
        reasons.append("Đúng chuyên môn được đề xuất" if spec_ok else "Không có chuyên môn được đề xuất")
    if need is None:
        reasons.append("Ngựa phù hợp mọi cấp trainer")
    elif level_ok:
        reasons.append(f"Đủ cấp độ cho ngựa này (cần {need} trở lên)")
    else:
        reasons.append(f"Ngựa này nên giao trainer {need} trở lên, trainer đang là {body['ExperienceLevel']}")
    return {
        "IsSuggested": spec_ok and level_ok,
        "MatchesSpecialization": spec_ok,
        "MatchesLevel": level_ok,
        "RequiredLevel": need,
        "SuggestionReason": "; ".join(reasons),
    }


def sort_key(row):
    return (not row.get("IsSuggested", True), -level_rank(row["ExperienceLevel"]), row["ActiveHorseCount"],
            -(row["TrainerRating"] or 0), row["FullName"])
