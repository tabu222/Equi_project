from django.apps import apps
from django.test.runner import DiscoverRunner


class UnmanagedModelTestRunner(DiscoverRunner):
    """Bật tạm managed=True cho mọi model nghiệp vụ để SQLite test tạo được bảng."""

    def setup_test_environment(self, *args, **kwargs):
        self._unmanaged = [m for m in apps.get_models() if not m._meta.managed]
        for model in self._unmanaged:
            model._meta.managed = True
        super().setup_test_environment(*args, **kwargs)

    def teardown_test_environment(self, *args, **kwargs):
        super().teardown_test_environment(*args, **kwargs)
        for model in self._unmanaged:
            model._meta.managed = False
