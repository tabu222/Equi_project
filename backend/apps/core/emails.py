"""
Gửi email thông báo (Gmail SMTP). Cấu hình trong .env:

    EMAIL_HOST_USER=ten.clb@gmail.com
    EMAIL_HOST_PASSWORD=<App Password 16 ký tự của Gmail, KHÔNG phải mật khẩu Gmail>

- Chưa cấu hình: email được IN RA CỬA SỔ CHẠY BACKEND (console) để xem khi demo.
- Đã cấu hình Gmail: gửi thật; bỏ qua địa chỉ demo đuôi ".local" (không tồn tại ngoài đời).
- Gửi SAU KHI lưu database thành công (on_commit) và chạy luồng nền, nên mail lỗi / chậm
  không làm hỏng hay chậm thao tác của người dùng; lỗi chỉ ghi log.
"""
import logging
import threading
from contextlib import contextmanager

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

logger = logging.getLogger("equi.email")
_state = threading.local()


@contextmanager
def suppressed():
    """Tắt gửi mail trong khối lệnh (vd. seed_demo tạo dữ liệu mẫu)."""
    previous = getattr(_state, "off", False)
    _state.off = True
    try:
        yield
    finally:
        _state.off = previous


def _deliverable(address: str | None) -> bool:
    if not address or "@" not in address:
        return False
    using_smtp = settings.EMAIL_BACKEND.endswith("smtp.EmailBackend")
    return not (using_smtp and address.lower().endswith(".local"))


def _send(recipients, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
    except Exception:  # noqa: BLE001 - mail lỗi không được làm hỏng nghiệp vụ
        logger.exception("Không gửi được email '%s' tới %s", subject, recipients)


def send_email(recipients, subject: str, body: str):
    if getattr(_state, "off", False):
        return
    recipients = sorted({r.strip().lower() for r in recipients if _deliverable(r)})
    if not recipients:
        return
    footer = f"\n\n—\nEquiTrack · {settings.FRONTEND_URL}\nEmail tự động, vui lòng không trả lời."
    full_subject = f"[EquiTrack] {subject}"

    def dispatch():
        if getattr(settings, "EMAIL_ASYNC", True):
            threading.Thread(target=_send, args=(recipients, full_subject, body + footer), daemon=True).start()
        else:
            _send(recipients, full_subject, body + footer)

    transaction.on_commit(dispatch)


def _managers_of(club_id):
    from apps.accounts.models import User
    return User.objects.filter(club_id=club_id, roles__code="CLUB_MANAGER", status="Active") \
        .values_list("email", flat=True)


def _horse_label(horse):
    return f"{horse.horse_name}" + (f" ({horse.horse_code})" if horse.horse_code else f" (hồ sơ #{horse.pk})")


# ---------------- tài khoản ----------------
def account_registered(user):
    send_email([user.email], "Tạo tài khoản thành công", (
        f"Chào {user.full_name},\n\n"
        "Tài khoản chủ ngựa của bạn trên EquiTrack đã được tạo.\n"
        "Bạn có thể đăng nhập để đăng ký hồ sơ ngựa và theo dõi tình trạng xét duyệt."
    ))


def account_created_by_manager(user, manager):
    send_email([user.email], "Câu lạc bộ đã tạo tài khoản cho bạn", (
        f"Chào {user.full_name},\n\n"
        f"{manager.full_name} đã tạo tài khoản EquiTrack cho bạn với email {user.email}.\n"
        "Mật khẩu tạm sẽ được câu lạc bộ báo riêng. Nếu email này là Gmail, bạn cũng có thể "
        "bấm \"Đăng nhập với Google\" mà không cần mật khẩu."
    ))


# ---------------- Flow 1: hồ sơ ngựa ----------------
def registration_submitted(horse):
    send_email(_managers_of(horse.club_id), f"Hồ sơ ngựa mới cần xác minh: {horse.horse_name}", (
        f"Chủ ngựa {horse.owner.full_name} vừa gửi hồ sơ {_horse_label(horse)}.\n"
        "Vui lòng vào mục Danh sách ngựa → Cần xử lý để kiểm tra giấy tờ và xác minh."
    ))


def registration_verified(horse):
    send_email([horse.owner.email], f"Hồ sơ {horse.horse_name} đã được xác minh", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Hồ sơ {_horse_label(horse)} đã qua bước kiểm tra giấy tờ.\n"
        "Bước tiếp theo: bác sĩ thú y trực ca sẽ khám sức khỏe đầu vào cho ngựa."
    ))


def initial_exam_signed(record):
    horse = record.horse
    send_email(_managers_of(horse.club_id), f"Đã khám đầu vào: {horse.horse_name}", (
        f"Bác sĩ {record.vet.full_name} đã chốt phiếu khám đầu vào cho {_horse_label(horse)}.\n"
        f"Kết luận sức khỏe: {record.health_status} · Khả năng tập: {record.training_eligibility}.\n"
        "Vui lòng vào trang Xử lý Flow 1 để duyệt hoặc từ chối hồ sơ."
    ))


def registration_approved(horse):
    send_email([horse.owner.email], f"Ngựa {horse.horse_name} đã được tiếp nhận", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Câu lạc bộ đã tiếp nhận ngựa {horse.horse_name}. Mã ngựa: {horse.horse_code}.\n"
        "Bạn có thể xem hồ sơ và tình trạng sức khỏe trong mục Ngựa của tôi."
    ))


def registration_rejected(horse, reason):
    send_email([horse.owner.email], f"Hồ sơ {horse.horse_name} chưa được tiếp nhận", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Hồ sơ {_horse_label(horse)} chưa được tiếp nhận.\n"
        f"Lý do: {reason}\n\n"
        "Bạn có thể sửa hồ sơ, bổ sung giấy tờ rồi gửi lại."
    ))
