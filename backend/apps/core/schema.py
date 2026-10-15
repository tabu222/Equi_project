"""Swagger (drf-spectacular): API nào không khai báo serializer vẫn cho nhập body JSON tự do để test."""
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter

FREE_JSON = {"type": "object", "additionalProperties": True}


LANGUAGE_HEADER = OpenApiParameter(
    "X-Language", str, OpenApiParameter.HEADER, required=False, enum=["vi", "en"],
    description="Ngôn ngữ câu thông báo / lỗi: vi (mặc định) hoặc en.",
)


class EquiAutoSchema(AutoSchema):
    def get_override_parameters(self):
        return [*super().get_override_parameters(), LANGUAGE_HEADER]

    def _get_request_body(self, direction="request"):
        body = super()._get_request_body(direction)
        if body is None and self.method in ("POST", "PUT", "PATCH"):
            return {"content": {"application/json": {"schema": FREE_JSON}}}
        return body
