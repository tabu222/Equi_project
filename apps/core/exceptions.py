"""
Xử lý lỗi chung cho toàn bộ API.

Mọi lỗi trả về dạng JSON thống nhất:
    {"detail": "Câu thông báo tiếng Việt", "code": "MA_LOI"}
Riêng lỗi kiểm tra dữ liệu (thiếu trường, sai định dạng) trả về theo từng trường:
    {"HorseName": ["Trường này là bắt buộc."]}
"""
from django.db import DatabaseError, IntegrityError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class BusinessRuleError(APIException):
    """Vi phạm luật nghiệp vụ, ví dụ duyệt hồ sơ khi ngựa chưa được khám."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Thao tác không hợp lệ với trạng thái hiện tại."
    default_code = "BUSINESS_RULE"

    def __init__(self, detail=None, code=None):
        super().__init__(detail or self.default_detail, code or self.default_code)


# Lỗi do trigger trong horse_v2.sql (THROW 5100x). Backend cũng tự kiểm tra trước bằng Python
# và trả về cùng mã lỗi (code), nên frontend chỉ cần xử lý một kiểu.
TRIGGER_MESSAGES = {
    "51001": "Không thể kích hoạt giáo án vì ngựa đang bị khóa tập (Full).",
    "51002": "Không thể xếp buổi tập vì ngựa đang bị khóa tập (Full).",
    "51003": "Buổi tập vượt quá cường độ cho phép khi ngựa đang bị hạn chế tập (Restricted).",
    "51004": "Bệnh án đã chốt không được sửa hoặc xóa. Hãy thêm phiếu đính chính.",
}
TRIGGER_CODES = {
    "51001": "TRAINING_LOCK_FULL",
    "51002": "TRAINING_LOCK_FULL",
    "51003": "TRAINING_LOCK_RESTRICTED",
    "51004": "RECORD_SIGNED",
}

# Lỗi do ràng buộc UNIQUE / index trong horse_v2.sql
CONSTRAINT_MESSAGES = {
    "UQ_User_Email": "Email đã được sử dụng.",
    "UX_Horse_MicrochipNumber": "Số microchip đã tồn tại ở một ngựa khác.",
    "UX_Horse_Club_HorseCode": "Mã ngựa đã tồn tại trong câu lạc bộ.",
    "UX_MedicalRecord_OneInitialExamPerRequest": "Hồ sơ tiếp nhận này đã có phiếu khám đầu vào.",
    "UX_StallAssignment_OneActivePerStall": "Chuồng này đang có ngựa khác.",
    "UX_StallAssignment_OneActivePerHorse": "Ngựa này đang ở một chuồng khác.",
    "UX_TrainerHorseAssignment_OneActivePerHorse": "Ngựa này đã có trainer phụ trách.",
    "UX_TrainingLock_OneActivePerHorse": "Ngựa này đã có một Training Lock đang hiệu lực.",
    "UQ_TrainingSession_RiderSlot": "Work Rider đã có buổi tập khác ở cùng ngày và cùng thứ tự (SequenceNo).",
    "UQ_TrainingPlanStage_Order": "Thứ tự giai đoạn (StageOrder) bị trùng trong giáo án.",
    "UQ_TrainingResult_Session": "Buổi tập này đã có kết quả.",
    "UQ_InventoryRequestItem": "Một vật tư chỉ được ghi một lần trong yêu cầu.",
    "UQ_Stall_Club_Number": "Số chuồng đã tồn tại trong câu lạc bộ.",
}


def friendly_db_error(exc: Exception):
    text = str(exc)
    for code, message in TRIGGER_MESSAGES.items():
        if code in text:
            return message, TRIGGER_CODES[code]
    for name, message in CONSTRAINT_MESSAGES.items():
        if name in text:
            return message, name
    return None


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict) and "detail" in response.data:
            response.data.setdefault("code", getattr(exc, "default_code", "ERROR"))
            codes = getattr(exc, "get_codes", None)
            if callable(codes):
                got = codes()
                if isinstance(got, str):
                    response.data["code"] = got.upper()
        return response

    if isinstance(exc, DatabaseError):
        known = friendly_db_error(exc)
        if known:
            message, code = known
            return Response({"detail": message, "code": code}, status=status.HTTP_409_CONFLICT)
        if isinstance(exc, IntegrityError):
            return Response(
                {"detail": "Dữ liệu vi phạm ràng buộc của database.", "code": "DB_INTEGRITY"},
                status=status.HTTP_409_CONFLICT,
            )
    return None
