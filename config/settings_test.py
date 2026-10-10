"""
Settings để chạy test KHÔNG cần SQL Server:
    python manage.py test --settings=config.settings_test

- Dùng SQLite trong bộ nhớ, tắt migrations, test runner tạm bật managed=True để tạo bảng.
- SQLite không có trigger / view / filtered index của horse_v2.sql. Các luật nghiệp vụ chính
  vẫn được backend kiểm tra bằng Python nên test vẫn có ý nghĩa; riêng phần do trigger
  của SQL Server đảm nhận thì cần chạy thử trên SQL Server thật.
"""
from .settings import *  # noqa: F401,F403


class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:", "ATOMIC_REQUESTS": True}}
MIGRATION_MODULES = _DisableMigrations()
TEST_RUNNER = "apps.core.test_runner.UnmanagedModelTestRunner"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # test chạy nhanh hơn

# Ẩn log "Bad Request / Conflict ..." khi test cố tình gửi request sai
LOGGING = {"version": 1, "disable_existing_loggers": False,
           "loggers": {"django.request": {"level": "CRITICAL"}}}

SECRET_KEY = "test-only-secret-key-not-used-anywhere-else-000000"
