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
    "apps.core",
    "apps.accounts",
    "apps.horses",
    "apps.training",
    "apps.medical",
    "apps.care",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
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
}

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
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = False  # cột DATETIME2 trong SQL Server lưu giờ địa phương, không có múi giờ

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
