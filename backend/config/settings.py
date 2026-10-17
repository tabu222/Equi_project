"""
Cấu hình Django cho backend Equi (Racehorse Training & Management System).

- Database: SQL Server, database tạo bằng sql/horse_v2.sql. Django KHÔNG tạo / sửa bảng
  (mọi model đều managed = False). Không chạy `python manage.py migrate` trên SQL Server.
- API trả JSON với tên khóa đúng bằng tên cột trong database (HorseID, HorseName, ...)
  và giá trị trạng thái đúng như database (Draft, PendingExam, Approved, ...).
- Mật khẩu, tên database... đọc từ biến môi trường hoặc file .env (không ghi vào code).
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Script tạo database: sql/ ở thư mục gốc repo (cạnh backend/ và frontend/); bản cũ để trong backend/sql/
SQL_SCRIPT = next((p for p in (BASE_DIR.parent / "sql" / "horse_v2.sql", BASE_DIR / "sql" / "horse_v2.sql")
                   if p.exists()), BASE_DIR.parent / "sql" / "horse_v2.sql")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEV_SECRET_KEY = "dev-only-insecure-key-change-me-in-env-file-0000"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or DEV_SECRET_KEY
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise RuntimeError("Đặt DJANGO_SECRET_KEY trong .env trước khi chạy với DJANGO_DEBUG=False.")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.horses",
    "apps.medical",    # Flow 1: phiếu khám đầu vào
    "apps.training",   # Flow 2: huấn luyện
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.i18n.LanguageMiddleware",  # X-Language: en -> câu thông báo tiếng Anh
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False  # frontend gọi /api/horses/5 (không có dấu / ở cuối)

# ---------------------------------------------------------------------------
# Database: SQL Server qua mssql-django
#   DB_USER để trống  -> đăng nhập bằng Windows Authentication (giống SSMS mặc định)
#   DB_USER có giá trị -> đăng nhập bằng tài khoản SQL Server (sa, ...)
# ---------------------------------------------------------------------------
_db_options = {
    "driver": os.getenv("DB_ODBC_DRIVER", "ODBC Driver 18 for SQL Server"),
    # ODBC Driver 18 bật mã hóa mặc định; máy dev dùng chứng chỉ tự ký nên cần dòng này.
    "extra_params": os.getenv("DB_EXTRA_PARAMS", "TrustServerCertificate=yes"),
}

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.getenv("DB_NAME", "RacehorseTrainingManagement"),
        "HOST": os.getenv("DB_HOST", r"localhost\SQLEXPRESS"),
        "PORT": os.getenv("DB_PORT", ""),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "OPTIONS": _db_options,
        "ATOMIC_REQUESTS": True,  # mỗi request là một transaction: lỗi giữa chừng thì không lưu dở dang
    }
}

# ---------------------------------------------------------------------------
# Người dùng = bảng dbo.[User]; quyền = Role / Permission / RolePermission / UserRole
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": False,  # cân nặng trả về dạng số 480.5, không phải chuỗi "480.5"
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "DEFAULT_SCHEMA_CLASS": "apps.core.schema.EquiAutoSchema",
}

# Swagger để test API trên trình duyệt: http://127.0.0.1:8000/api/docs
# (bấm Authorize, dán access token lấy từ POST /api/auth/login)
SPECTACULAR_SETTINGS = {
    "TITLE": "Equi API",
    "DESCRIPTION": "Backend Django REST cho đồ án SWP391. Chi tiết từng API: docs/API.md.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
    "DISABLE_ERRORS_AND_WARNINGS": True,
}

TEMPLATES = [  # chỉ dùng cho trang Swagger
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "UPDATE_LAST_LOGIN": False,  # bảng User không có cột LastLogin
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Frontend dev chạy qua Vite proxy (cùng origin) nên thường không cần CORS;
# vẫn cho phép sẵn cổng Vite để gọi thẳng khi cần.
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = (*default_headers, "x-language")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

# File giấy tờ tải lên (hộ chiếu, giấy sở hữu, ảnh ngựa...). Không commit thư mục này lên Git.
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT") or BASE_DIR / "media")
UPLOAD_MAX_MB = int(os.getenv("UPLOAD_MAX_MB", "10"))
CHANGE_REQUEST_MAX_FILES = int(os.getenv("CHANGE_REQUEST_MAX_FILES", "12"))
DATA_UPLOAD_MAX_NUMBER_FILES = CHANGE_REQUEST_MAX_FILES
DATA_UPLOAD_MAX_MEMORY_SIZE = (UPLOAD_MAX_MB * CHANGE_REQUEST_MAX_FILES + 1) * 1024 * 1024

# ---------- Email (Gmail SMTP) ----------
# Gmail: bật xác minh 2 bước, tạo "App password" (16 ký tự) rồi điền 2 dòng EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
# trong .env. Để trống thì email chỉ in ra cửa sổ chạy backend (dùng khi demo / dev).
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").replace(" ", "")
EMAIL_TIMEOUT = 15
EMAIL_BACKEND = ("django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
                 else "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL") or (
    f"EquiTrack <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "EquiTrack <no-reply@equi.local>")
EMAIL_ASYNC = env_bool("EMAIL_ASYNC", True)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ---------- Đăng nhập bằng Google ----------
# Client ID lấy ở Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web application).
# Frontend dùng CÙNG giá trị này (VITE_GOOGLE_CLIENT_ID). Để trống = tắt đăng nhập Google.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = False  # cột DATETIME2 trong SQL Server lưu giờ địa phương, không có múi giờ

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
MIGRATION_MODULES = {"auth": None, "contenttypes": None}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
