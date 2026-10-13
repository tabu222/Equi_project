"""Swagger (drf-spectacular): API nào không khai báo serializer vẫn cho nhập body JSON tự do để test."""
from drf_spectacular.openapi import AutoSchema

FREE_JSON = {"type": "object", "additionalProperties": True}


class EquiAutoSchema(AutoSchema):
    def _get_request_body(self, direction="request"):
        body = super()._get_request_body(direction)
        if body is None and self.method in ("POST", "PUT", "PATCH"):
            return {"content": {"application/json": {"schema": FREE_JSON}}}
        return body
