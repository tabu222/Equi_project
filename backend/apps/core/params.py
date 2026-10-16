"""Đọc tham số query (?HorseID=5&From=2026-10-01) an toàn: sai định dạng -> lỗi 400 thay vì 500."""
from datetime import date

from rest_framework.exceptions import ValidationError


def int_param(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({name: ["Phải là số nguyên."]})


def date_param(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({name: ["Ngày không hợp lệ, dùng dạng YYYY-MM-DD."]})


def flag_param(params, name) -> bool:
    return str(params.get(name, "")).lower() in ("1", "true", "yes")
