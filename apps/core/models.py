from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """dbo.AuditLog: ai làm gì, lúc nào, trên đối tượng nào."""

    id = models.BigAutoField(primary_key=True, db_column="AuditLogID")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="UserID", related_name="+",
    )
    action_type = models.CharField(max_length=50, db_column="ActionType")
    entity_name = models.CharField(max_length=100, db_column="EntityName")
    entity_id = models.IntegerField(null=True, blank=True, db_column="EntityID")
    action_time = models.DateTimeField(default=timezone.now, db_column="ActionTime")
    details = models.TextField(null=True, blank=True, db_column="Details")

    class Meta:
        managed = False
        db_table = "AuditLog"
        ordering = ["-action_time", "-id"]
