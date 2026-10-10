"""Danh mục chuyên môn giống phần SEED DATA của sql/horse_v2.sql (test kiểm tra luôn khớp)."""

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
