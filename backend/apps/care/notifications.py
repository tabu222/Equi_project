"""Thông báo Flow 4 (gộp vào GET /api/notifications khi đã có Flow 4)."""
from datetime import date

from .models import CareTask, DietPlan, InventoryItem, InventoryRequest


def care_items(user, make_item):
    """Manager: yêu cầu vật tư, vật tư sắp hết. Vet: khẩu phần chờ duyệt. Head Trainer: khẩu phần bị trả về.
    Groom: việc chăm sóc tới hạn."""
    perms, club, today = user.permission_codes, user.club_id, date.today()
    items = []
    if "INVENTORY_MANAGE" in perms:  # Club Manager
        for req in InventoryRequest.objects.filter(club_id=club, status="Pending").select_related("requested_by"):
            items.append(make_item("INVENTORY_REQUEST", f"Yêu cầu vật tư của {req.requested_by.full_name}",
                                   "InventoryRequest", req.id, at=req.request_date, message=req.reason))
        for item in InventoryItem.objects.filter(club_id=club, status__in=("Low Stock", "Out of Stock")):
            items.append(make_item("LOW_STOCK", f"{item.item_name}: {item.status} ({item.quantity} {item.unit})",
                                   "InventoryItem", item.id, urgent=item.status == "Out of Stock"))
    if "MEDICAL_MANAGE" in perms and "DIET_MANAGE" in perms:  # Vet duyệt khẩu phần
        for plan in DietPlan.objects.filter(horse__club_id=club, status="Pending").select_related("horse"):
            items.append(make_item("DIET_TO_REVIEW", "Khẩu phần chờ Vet duyệt", "DietPlan", plan.id, plan.horse,
                                   plan.created_at))
    if "TRAINING_PLAN_APPROVE" in perms:  # Head Trainer lập khẩu phần
        for plan in DietPlan.objects.filter(horse__club_id=club, created_by=user, status="Rejected"):
            items.append(make_item("DIET_RETURNED", "Khẩu phần bị Vet trả về", "DietPlan", plan.id, plan.horse,
                                   plan.created_at, message=plan.vet_note))
    if "CARE_MANAGE" in perms:  # Groom
        for task in CareTask.objects.filter(groom=user, status="Pending",
                                            scheduled_at__date__lte=today).select_related("horse"):
            items.append(make_item("CARE_TASK", f"{task.task_type} lúc {task.scheduled_at:%H:%M %d/%m}", "CareTask",
                                   task.id, task.horse, task.scheduled_at, task.scheduled_at.date() < today))
    return items
