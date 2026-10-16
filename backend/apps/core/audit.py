import json

from .models import AuditLog


def log_action(user, action_type: str, entity, details=None) -> None:
    """Ghi một dòng vào dbo.AuditLog. entity là một model instance (Horse, MedicalRecord...)."""
    if details is not None and not isinstance(details, str):
        details = json.dumps(details, ensure_ascii=False, default=str)
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action_type=action_type,
        entity_name=entity._meta.db_table,
        entity_id=entity.pk,
        details=details,
    )
