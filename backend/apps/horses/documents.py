"""
Lưu file giấy tờ của hồ sơ ngựa (hộ chiếu, giấy chứng nhận microchip, giấy sở hữu, ảnh ngựa...).

- File lưu trên ổ đĩa của backend: MEDIA_ROOT/horse-documents/<HorseID>/<tên ngẫu nhiên>.<đuôi>
  (MEDIA_ROOT mặc định là thư mục media/ cạnh manage.py, đã có trong .gitignore).
- Cột HorseDocument.FileUrl lưu "upload:horse-documents/..." để phân biệt với link ngoài (https://...).
- Tải file về qua GET /api/horse-documents/<DocumentID>/file (phải đăng nhập, kiểm tra quyền xem ngựa),
  KHÔNG mở thư mục media ra internet.
"""
import mimetypes
import uuid
from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import ValidationError

UPLOAD_PREFIX = "upload:"
ALLOWED = {
    # đuôi file -> các "chữ ký" byte đầu file hợp lệ
    ".pdf": (b"%PDF",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}


def media_root() -> Path:
    return Path(settings.MEDIA_ROOT)


def max_bytes() -> int:
    return int(getattr(settings, "UPLOAD_MAX_MB", 10)) * 1024 * 1024


def validate_upload(file):
    ext = Path(file.name or "").suffix.lower()
    if ext not in ALLOWED:
        raise ValidationError({"File": ["Chỉ nhận file PDF, JPG, PNG hoặc WEBP."]})
    if file.size > max_bytes():
        raise ValidationError({"File": [f"File quá lớn, tối đa {getattr(settings, 'UPLOAD_MAX_MB', 10)} MB."]})
    if file.size == 0:
        raise ValidationError({"File": ["File rỗng."]})
    head = file.read(12)
    file.seek(0)
    if not any(head.startswith(sig) for sig in ALLOWED[ext]) or (ext == ".webp" and head[8:12] != b"WEBP"):
        raise ValidationError({"File": ["Nội dung file không đúng định dạng (file hỏng hoặc đổi đuôi)."]})
    return ext


def save_upload(horse_id: int, file) -> str:
    """Lưu file, trả về giá trị ghi vào cột FileUrl."""
    ext = validate_upload(file)
    relative = Path("horse-documents") / str(horse_id) / f"{uuid.uuid4().hex}{ext}"
    target = media_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target, "wb") as out:
            for chunk in file.chunks():
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return UPLOAD_PREFIX + relative.as_posix()


def is_upload(file_url: str | None) -> bool:
    return bool(file_url) and file_url.startswith(UPLOAD_PREFIX)


def stored_path(file_url: str) -> Path:
    """Đường dẫn thật trên ổ đĩa; chặn đường dẫn trỏ ra ngoài MEDIA_ROOT."""
    root = media_root().resolve()
    path = (root / file_url[len(UPLOAD_PREFIX):]).resolve()
    if root not in path.parents:
        raise ValidationError("Đường dẫn file không hợp lệ.")
    return path


def content_type(file_url: str) -> str:
    return mimetypes.guess_type(file_url)[0] or "application/octet-stream"


def delete_file(file_url: str | None):
    if is_upload(file_url):
        try:
            stored_path(file_url).unlink(missing_ok=True)
        except (OSError, ValidationError):
            pass
