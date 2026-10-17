"""Email Flow 3 gửi chủ ngựa: ngựa bị Vet khóa tập / được mở khóa (gửi sau khi lưu database, lỗi không làm hỏng thao tác)."""
from apps.core.emails import send_email

LEVEL_TEXT = {"Full": "dừng tập hoàn toàn", "Restricted": "chỉ được tập nhẹ"}


def _owner(horse):
    return [horse.owner.email] if horse.owner_id and horse.owner.email else []


def _label(horse):
    return f"{horse.horse_name}" + (f" ({horse.horse_code})" if horse.horse_code else "")


def lock_created(lock):
    horse = lock.horse
    end = f"\nDự kiến mở khóa: {lock.lock_end_date:%d/%m/%Y}" if lock.lock_end_date else ""
    send_email(_owner(horse), f"[Khẩn] {horse.horse_name} tạm dừng huấn luyện", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Bác sĩ thú y {lock.created_by.full_name} đã khóa huấn luyện {_label(horse)}: "
        f"{LEVEL_TEXT.get(lock.lock_level, lock.lock_level)}.\n"
        f"Lý do: {lock.reason}\n"
        f"Từ: {lock.lock_start_date:%d/%m/%Y}{end}\n\n"
        "Các buổi tập trong thời gian này được câu lạc bộ điều chỉnh. Bạn sẽ được báo khi ngựa được tập lại."
    ))


def lock_released(lock):
    horse = lock.horse
    send_email(_owner(horse), f"{horse.horse_name} được tập lại", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Sau khi tái khám đạt, bác sĩ thú y {lock.released_by.full_name} đã mở khóa huấn luyện cho {_label(horse)}.\n"
        "Ngựa tiếp tục tập theo giáo án; kết quả từng buổi xem trong mục Huấn luyện."
    ))
