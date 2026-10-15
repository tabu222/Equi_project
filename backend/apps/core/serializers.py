from django.core.exceptions import FieldDoesNotExist
from rest_framework import serializers


class DBColumnModelSerializer(serializers.ModelSerializer):
    """
    ModelSerializer dùng TÊN CỘT TRONG DATABASE làm tên khóa JSON.

    Trong Python, model đặt tên theo kiểu snake_case (horse_name, owner...) và khai báo
    db_column="HorseName", "OwnerID"... Serializer này đổi tên khóa JSON thành đúng
    db_column, nên API nhận / trả {"HorseName": ..., "OwnerID": ...} giống hệt database.
    Khi khai báo Meta.fields vẫn ghi theo tên Python (horse_name, owner...),
    hàm kiểm tra cũng viết theo tên Python (validate_horse_name).
    """

    def get_fields(self):
        fields = super().get_fields()
        model = self.Meta.model
        renamed = {}
        for name, field in fields.items():
            key = name
            try:
                model_field = model._meta.get_field(name)
                column = getattr(model_field, "db_column", None) or getattr(model_field, "column", None)
                if column:
                    key = column
            except FieldDoesNotExist:
                pass
            if key != name:
                if field.source is None:
                    field.source = name
                # DRF gọi validate_<tên khóa JSON>; cho phép viết validate_<tên python> như bình thường
                validator = getattr(self, f"validate_{name}", None)
                if validator is not None and not hasattr(self, f"validate_{key}"):
                    setattr(self, f"validate_{key}", validator)
            renamed[key] = field
        return renamed


def db_column(model, field_name: str) -> str:
    """Tên cột database của một field (dùng khi tự tạo JSON hoặc báo lỗi)."""
    field = model._meta.get_field(field_name)
    return field.db_column or field.column


_DATETIME = serializers.DateTimeField()


def fmt_datetime(value):
    """Định dạng ngày giờ giống các trường serializer (2026-10-10T08:30:00) cho JSON tự dựng."""
    return _DATETIME.to_representation(value) if value else None
