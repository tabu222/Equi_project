"""
Danh sách Role / Permission giống hệt phần SEED DATA trong sql/horse_v2.sql.

Trên SQL Server thật, dữ liệu này đã có sẵn sau khi chạy horse_v2.sql.
File này dùng để:
  - tạo dữ liệu khi chạy test bằng SQLite;
  - lệnh `seed_demo` bổ sung nếu thiếu (không ghi đè dữ liệu có sẵn).
Test `test_rbac_matches_sql` kiểm tra file này luôn khớp với horse_v2.sql.
"""

ROLES = {
    "CLUB_MANAGER": "Club Manager",
    "HEAD_TRAINER": "Head Trainer",
    "TRAINER": "Trainer",
    "WORK_RIDER": "Work Rider",
    "VETERINARIAN": "Veterinarian",
    "GROOM": "Groom / Stable Hand",
    "HORSE_OWNER": "Horse Owner",
}

PERMISSIONS = [
    "CLUB_MANAGE", "RBAC_MANAGE", "AUDIT_VIEW", "HORSE_VIEW", "HORSE_REGISTER", "HORSE_REGISTER_REVIEW",
    "HORSE_ARCHIVE", "PROFILE_EDIT_REQUEST", "PROFILE_EDIT_APPROVE", "HORSE_ASSESS", "TRAINER_ASSIGN",
    "TRAINING_PLAN_MANAGE", "TRAINING_PLAN_APPROVE", "TRAINING_SESSION_ASSIGN", "TRAINING_SESSION_SUPERVISE",
    "TRAINING_RESULT_UPDATE", "TRAINING_REVIEW", "HEALTH_REPORT", "MEDICAL_MANAGE", "MEDICAL_SIGN",
    "TRAINING_LOCK_MANAGE", "CARE_MANAGE", "DIET_MANAGE", "INVENTORY_REQUEST", "INVENTORY_MANAGE", "OWNER_VIEW",
]

ROLE_PERMISSIONS = {
    "CLUB_MANAGER": [
        "CLUB_MANAGE", "RBAC_MANAGE", "AUDIT_VIEW", "HORSE_VIEW", "HORSE_REGISTER_REVIEW",
        "HORSE_ARCHIVE", "PROFILE_EDIT_APPROVE", "INVENTORY_MANAGE",
    ],
    "HEAD_TRAINER": [
        "HORSE_VIEW", "HORSE_ASSESS", "TRAINER_ASSIGN", "TRAINING_PLAN_APPROVE", "TRAINING_SESSION_ASSIGN",
        "TRAINING_SESSION_SUPERVISE", "HEALTH_REPORT", "DIET_MANAGE", "INVENTORY_REQUEST",
    ],
    "TRAINER": [
        "HORSE_VIEW", "TRAINING_PLAN_MANAGE", "TRAINING_SESSION_ASSIGN", "TRAINING_SESSION_SUPERVISE",
        "TRAINING_REVIEW", "HEALTH_REPORT",
    ],
    "WORK_RIDER": ["HORSE_VIEW", "TRAINING_RESULT_UPDATE", "HEALTH_REPORT"],
    "VETERINARIAN": ["HORSE_VIEW", "MEDICAL_MANAGE", "MEDICAL_SIGN", "TRAINING_LOCK_MANAGE", "DIET_MANAGE"],
    "GROOM": ["HORSE_VIEW", "CARE_MANAGE", "HEALTH_REPORT", "INVENTORY_REQUEST"],
    "HORSE_OWNER": ["HORSE_REGISTER", "PROFILE_EDIT_REQUEST", "OWNER_VIEW"],
}


def ensure_rbac_seed() -> None:
    """Tạo Role / Permission / RolePermission nếu chưa có (không xóa, không sửa dòng có sẵn)."""
    from .models import AppPermission, Role, RolePermission

    roles = {}
    for code, name in ROLES.items():
        roles[code], _ = Role.objects.get_or_create(code=code, defaults={"name": name})
    perms = {}
    for code in PERMISSIONS:
        perms[code], _ = AppPermission.objects.get_or_create(code=code, defaults={"name": code})
    for role_code, codes in ROLE_PERMISSIONS.items():
        for perm_code in codes:
            if not RolePermission.objects.filter(role=roles[role_code], permission=perms[perm_code]).exists():
                RolePermission.objects.create(role=roles[role_code], permission=perms[perm_code])
