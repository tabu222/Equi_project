"""
Luật nghiệp vụ Flow 4 - chăm sóc và dinh dưỡng.

Khẩu phần:  Head Trainer lập (Pending) ──Vet approve──> Approved ──Vet adjust──> Adjusted
                 ^                 │ Vet reject (kèm VetNote)
                 └── sửa, gửi lại ─┘ Rejected
            Khẩu phần mới được duyệt -> khẩu phần cũ trùng thời gian kết thúc hôm trước ngày khẩu phần mới (hoặc Expired).
Việc chăm sóc: Head Trainer / Manager giao cho Groom, hoặc Groom tự tạo. Pending -> Completed / Skipped.
Vật tư:     Groom / Head Trainer gửi yêu cầu (Pending) -> Manager duyệt (trừ kho) / từ chối; người gửi hủy được.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import require_club_user, user_has_any
from apps.horses.models import Horse

from .models import CareTask, DietMeal, DietPlan, InventoryItem, InventoryRequest, InventoryRequestItem

D = DietPlan.Status
IN_FORCE = (D.APPROVED, D.ADJUSTED)
CARE_ASSIGNERS = ("TRAINER_ASSIGN", "CLUB_MANAGE")   # Head Trainer, Club Manager


def _ensure_horse(horse):
    if horse.registration_status != Horse.RegistrationStatus.APPROVED:
        raise BusinessRuleError("Chỉ áp dụng cho ngựa đang ở CLB (Approved).", "HORSE_NOT_APPROVED")


# ---------------------------------------------------------------------------
# Khẩu phần
# ---------------------------------------------------------------------------
def current_diet_plan(horse, on_day=None):
    on_day = on_day or date.today()
    from django.db.models import Q

    return (horse.diet_plans.filter(status__in=IN_FORCE, start_date__lte=on_day)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=on_day)).order_by("-start_date", "-id").first())


def _check_plan_dates(start, end):
    if end and end < start:
        raise ValidationError({"EndDate": ["Ngày kết thúc phải sau ngày bắt đầu."]})


def _replace_meals(plan, meals):
    if not meals:
        raise ValidationError({"Meals": ["Khẩu phần cần ít nhất một bữa ăn."]})
    plan.meals.all().delete()
    for meal in meals:
        DietMeal.objects.create(diet_plan=plan, **meal)


def create_diet_plan(horse, user, values, meals):
    _ensure_horse(horse)
    _check_plan_dates(values["start_date"], values.get("end_date"))
    plan = DietPlan.objects.create(horse=horse, created_by=user, status=D.PENDING, created_at=timezone.now(),
                                   **values)
    _replace_meals(plan, meals)
    log_action(user, "CREATE_DIET_PLAN", plan, {"HorseID": horse.pk})
    return plan


def update_diet_plan(plan, user, values, meals=None):
    """Head Trainer sửa khẩu phần đang chờ duyệt hoặc bị trả về -> gửi lại (Pending)."""
    if plan.status not in (D.PENDING, D.REJECTED):
        raise BusinessRuleError("Chỉ sửa được khẩu phần đang chờ duyệt hoặc bị trả về.", "INVALID_STATUS")
    for attr, value in values.items():
        setattr(plan, attr, value)
    _check_plan_dates(plan.start_date, plan.end_date)
    plan.status = D.PENDING
    plan.save()
    if meals is not None:
        _replace_meals(plan, meals)
    log_action(user, "UPDATE_DIET_PLAN", plan)
    return plan


def approve_diet_plan(plan, user, note=None):
    if plan.status != D.PENDING:
        raise BusinessRuleError("Khẩu phần không ở trạng thái chờ duyệt.", "INVALID_STATUS")
    if plan.created_by_id == user.pk:
        raise BusinessRuleError("Người lập khẩu phần không tự duyệt.", "SELF_APPROVAL")
    # Khẩu phần đang áp dụng bị trùng thời gian: bắt đầu trước -> kết thúc vào hôm trước ngày khẩu phần mới;
    # bắt đầu cùng ngày hoặc sau -> Expired. Khẩu phần mới bắt đầu trong tương lai thì khẩu phần hiện tại vẫn dùng tới hôm đó.
    expired, shortened = [], []
    for old in plan.horse.diet_plans.filter(status__in=IN_FORCE).exclude(pk=plan.pk):
        overlaps = (old.end_date is None or old.end_date >= plan.start_date) and \
                   (plan.end_date is None or old.start_date <= plan.end_date)
        if not overlaps:
            continue
        if old.start_date < plan.start_date:
            old.end_date = plan.start_date - timedelta(days=1)
            old.save(update_fields=["end_date"])
            shortened.append(old.id)
        else:
            old.status = D.EXPIRED
            old.save(update_fields=["status"])
            expired.append(old.id)
    plan.status = D.APPROVED
    plan.reviewed_by = user
    plan.approved_at = timezone.now()
    plan.vet_note = note or plan.vet_note
    plan.save(update_fields=["status", "reviewed_by", "approved_at", "vet_note"])
    log_action(user, "APPROVE_DIET_PLAN", plan, {"ExpiredDietPlanIDs": expired, "ShortenedDietPlanIDs": shortened})
    return plan


def reject_diet_plan(plan, user, note):
    if plan.status != D.PENDING:
        raise BusinessRuleError("Khẩu phần không ở trạng thái chờ duyệt.", "INVALID_STATUS")
    if not note:
        raise ValidationError({"VetNote": ["Cần ghi lý do trả về."]})
    plan.status = D.REJECTED
    plan.reviewed_by = user
    plan.vet_note = note
    plan.save(update_fields=["status", "reviewed_by", "vet_note"])
    log_action(user, "REJECT_DIET_PLAN", plan, {"VetNote": note})
    return plan


def adjust_diet_plan(plan, user, note, values=None, meals=None):
    """Vet điều chỉnh khẩu phần đang áp dụng (vd ngựa dị ứng, đang điều trị)."""
    if plan.status not in IN_FORCE:
        raise BusinessRuleError("Chỉ điều chỉnh khẩu phần đang áp dụng.", "INVALID_STATUS")
    if not note:
        raise ValidationError({"VetNote": ["Cần ghi lý do điều chỉnh."]})
    for attr, value in (values or {}).items():
        setattr(plan, attr, value)
    _check_plan_dates(plan.start_date, plan.end_date)
    plan.status = D.ADJUSTED
    plan.reviewed_by = user
    plan.vet_note = note
    plan.save()
    if meals is not None:
        _replace_meals(plan, meals)
    log_action(user, "ADJUST_DIET_PLAN", plan, {"VetNote": note})
    return plan


# ---------------------------------------------------------------------------
# Việc chăm sóc
# ---------------------------------------------------------------------------
def is_care_assigner(user) -> bool:
    return user_has_any(user, *CARE_ASSIGNERS)


def create_care_task(horse, user, values, groom_id=None):
    _ensure_horse(horse)
    if is_care_assigner(user):
        groom = require_club_user(groom_id, horse.club_id, "GROOM", field="GroomID")
        assigned_by = user
    else:
        # Groom tự tạo việc cho mình
        groom, assigned_by = user, None
    task = CareTask.objects.create(horse=horse, groom=groom, assigned_by=assigned_by, status=CareTask.Status.PENDING,
                                   **values)
    log_action(user, "CREATE_CARE_TASK", task, {"HorseID": horse.pk, "GroomID": groom.pk})
    return task


def _ensure_task_manager(task, user):
    allowed = (task.assigned_by_id == user.pk or (task.assigned_by_id is None and task.groom_id == user.pk)
               or is_care_assigner(user))
    if not allowed:
        raise BusinessRuleError("Bạn không được sửa việc chăm sóc này.", "NOT_TASK_OWNER")


def update_care_task(task, user, values, groom_id=None):
    if task.status != CareTask.Status.PENDING:
        raise BusinessRuleError("Chỉ sửa được việc chưa làm (Pending).", "INVALID_STATUS")
    _ensure_task_manager(task, user)
    if groom_id is not None:
        if not is_care_assigner(user):
            raise BusinessRuleError("Chỉ Head Trainer / Manager được đổi Groom.", "NOT_TASK_OWNER")
        task.groom = require_club_user(groom_id, task.horse.club_id, "GROOM", field="GroomID")
    for attr, value in values.items():
        setattr(task, attr, value)
    task.save()
    log_action(user, "UPDATE_CARE_TASK", task)
    return task


def _append_note(task, text):
    if text:
        task.note = ((task.note or "") + ("\n" if task.note else "") + text)[:1000]


def complete_care_task(task, user, note=None):
    if task.groom_id != user.pk:
        raise BusinessRuleError("Chỉ Groom được giao mới xác nhận hoàn thành.", "NOT_TASK_GROOM")
    if task.status != CareTask.Status.PENDING:
        raise BusinessRuleError("Việc này đã xử lý.", "INVALID_STATUS")
    task.status = CareTask.Status.COMPLETED
    task.completed_at = timezone.now()
    _append_note(task, note)
    task.save(update_fields=["status", "completed_at", "note"])
    log_action(user, "COMPLETE_CARE_TASK", task)
    return task


def skip_care_task(task, user, reason):
    if task.groom_id != user.pk:
        _ensure_task_manager(task, user)
    if task.status != CareTask.Status.PENDING:
        raise BusinessRuleError("Việc này đã xử lý.", "INVALID_STATUS")
    if not reason:
        raise ValidationError({"Reason": ["Cần ghi lý do bỏ qua."]})
    task.status = CareTask.Status.SKIPPED
    _append_note(task, f"[Bỏ qua] {reason}")
    task.save(update_fields=["status", "note"])
    log_action(user, "SKIP_CARE_TASK", task, {"Reason": reason})
    return task


# ---------------------------------------------------------------------------
# Kho vật tư
# ---------------------------------------------------------------------------
def save_item(user, values, item=None, club_id=None):
    item = item or InventoryItem(club_id=club_id, quantity=Decimal("0"))
    reactivate = values.pop("reactivate", False)
    for attr, value in values.items():
        setattr(item, attr, value)
    if item.minimum_quantity is not None and item.minimum_quantity < 0:
        raise ValidationError({"MinimumQuantity": ["Không được âm."]})
    if item.quantity < 0:
        raise ValidationError({"Quantity": ["Không được âm."]})
    if reactivate and item.status == InventoryItem.Status.INACTIVE:
        item.status = InventoryItem.Status.AVAILABLE
    item.refresh_status()
    created = item.pk is None
    item.save()
    log_action(user, "CREATE_INVENTORY_ITEM" if created else "UPDATE_INVENTORY_ITEM", item)
    return item


def adjust_stock(item, user, change, note=None):
    """Nhập kho (change > 0) hoặc điều chỉnh giảm (change < 0, vd hư hỏng). Lịch sử ghi ở AuditLog."""
    new_quantity = item.quantity + change
    if new_quantity < 0:
        raise BusinessRuleError(f"Tồn kho chỉ còn {item.quantity} {item.unit}.", "INSUFFICIENT_STOCK")
    item.quantity = new_quantity
    item.refresh_status()
    item.save(update_fields=["quantity", "status"])
    log_action(user, "ADJUST_STOCK", item, {"Change": change, "Quantity": item.quantity, "Note": note})
    return item


def create_inventory_request(user, reason, items):
    if not items:
        raise ValidationError({"Items": ["Cần ít nhất một vật tư."]})
    seen = set()
    rows = []
    for entry in items:
        item = InventoryItem.objects.filter(pk=entry["InventoryItemID"], club_id=user.club_id).first()
        if item is None or item.status == InventoryItem.Status.INACTIVE:
            raise ValidationError({"Items": [f"Vật tư #{entry['InventoryItemID']} không tồn tại hoặc đã ngưng dùng."]})
        if item.pk in seen:
            raise ValidationError({"Items": ["Một vật tư chỉ được ghi một lần trong yêu cầu."]})
        seen.add(item.pk)
        rows.append((item, entry))
    request = InventoryRequest.objects.create(club_id=user.club_id, requested_by=user, request_date=timezone.now(),
                                              status=InventoryRequest.Status.PENDING, reason=reason or None)
    for item, entry in rows:
        InventoryRequestItem.objects.create(request=request, item=item,
                                            requested_quantity=entry["RequestedQuantity"],
                                            note=entry.get("Note") or None)
    log_action(user, "CREATE_INVENTORY_REQUEST", request, {"ItemCount": len(rows)})
    return request


def _ensure_pending(request):
    if request.status != InventoryRequest.Status.PENDING:
        raise BusinessRuleError("Yêu cầu này đã được xử lý.", "INVALID_STATUS")


def approve_inventory_request(request, user, approved=None):
    """
    Manager duyệt và xuất kho. approved: {InventoryItemID: ApprovedQuantity}; bỏ trống = duyệt đủ số yêu cầu.
    ApprovedQuantity = 0 nghĩa là không cấp vật tư đó.
    """
    _ensure_pending(request)
    approved = approved or {}
    lines = list(request.items.select_related("item"))
    unknown = set(approved) - {line.item_id for line in lines}
    if unknown:
        raise ValidationError({"Items": [f"Vật tư #{', #'.join(map(str, unknown))} không có trong yêu cầu."]})
    for line in lines:
        quantity = approved.get(line.item_id, line.requested_quantity)
        if quantity < 0 or quantity > line.requested_quantity:
            raise ValidationError({"Items": [f"Số lượng duyệt của '{line.item.item_name}' phải từ 0 đến "
                                             f"{line.requested_quantity}."]})
        item = InventoryItem.objects.get(pk=line.item_id)
        if quantity > item.quantity:
            raise BusinessRuleError(f"Không đủ '{item.item_name}' trong kho (còn {item.quantity} {item.unit}).",
                                    "INSUFFICIENT_STOCK")
        line.approved_quantity = quantity
    for line in lines:
        line.save(update_fields=["approved_quantity"])
        item = InventoryItem.objects.get(pk=line.item_id)
        item.quantity -= line.approved_quantity
        item.refresh_status()
        item.save(update_fields=["quantity", "status"])
    request.status = InventoryRequest.Status.APPROVED
    request.approved_by = user
    request.approved_at = timezone.now()
    request.save(update_fields=["status", "approved_by", "approved_at"])
    log_action(user, "APPROVE_INVENTORY_REQUEST", request,
               {str(line.item_id): str(line.approved_quantity) for line in lines})
    return request


def reject_inventory_request(request, user, note):
    _ensure_pending(request)
    if not note:
        raise ValidationError({"Note": ["Cần ghi lý do từ chối."]})
    request.status = InventoryRequest.Status.REJECTED
    request.approved_by = user          # người xử lý
    request.approved_at = timezone.now()
    request.save(update_fields=["status", "approved_by", "approved_at"])
    log_action(user, "REJECT_INVENTORY_REQUEST", request, {"Note": note})
    return request


def cancel_inventory_request(request, user):
    _ensure_pending(request)
    if request.requested_by_id != user.pk:
        raise BusinessRuleError("Chỉ người gửi mới hủy được yêu cầu.", "NOT_REQUESTER")
    request.status = InventoryRequest.Status.CANCELLED
    request.save(update_fields=["status"])
    log_action(user, "CANCEL_INVENTORY_REQUEST", request)
    return request
