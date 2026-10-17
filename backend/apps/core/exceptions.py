"""
Xử lý lỗi chung cho toàn bộ API.

Mọi lỗi trả về dạng JSON thống nhất:
    {"detail": "Câu thông báo tiếng Việt", "code": "MA_LOI"}
Riêng lỗi kiểm tra dữ liệu (thiếu trường, sai định dạng) trả về theo từng trường:
    {"HorseName": ["Trường này là bắt buộc."]}
"""
import re

from django.db import DatabaseError, IntegrityError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .i18n import is_english, translate_data


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


# Ràng buộc CHECK trong horse_v2.sql -> câu báo lỗi cụ thể (backend thường đã chặn trước bằng Python,
# đây là lớp cuối cùng khi dữ liệu sai lọt xuống database).
CHECK_MESSAGES = {
    "CK_Club_Status": "Trạng thái CLB chỉ được là Active hoặc Inactive.",
    "CK_User_Status": "Trạng thái tài khoản chỉ được là Active, Inactive hoặc Suspended.",
    "CK_Horse_Gender": "Giới tính ngựa phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến).",
    "CK_Horse_RegistrationStatus": "Trạng thái hồ sơ ngựa không hợp lệ.",
    "CK_Horse_HealthStatus": "Tình trạng sức khỏe ngựa không hợp lệ.",
    "CK_Horse_Archive": "Lưu trữ hồ sơ ngựa cần ghi thời điểm và người lưu trữ.",
    "CK_Horse_ApprovedHasCode": "Ngựa đã duyệt phải có mã ngựa (HorseCode).",
    "CK_HorseDocument_Type": "Loại tài liệu không hợp lệ (Passport, Microchip Certificate, Ownership Proof, "
                             "Handover Record, Contract, Other).",
    "CK_RegistrationRequest_Status": "Trạng thái hồ sơ tiếp nhận không hợp lệ.",
    "CK_ProfileChangeRequest_Status": "Trạng thái yêu cầu sửa lý lịch không hợp lệ.",
    "CK_ProfileChangeRequest_Review": "Duyệt / từ chối yêu cầu sửa lý lịch cần ghi người duyệt và thời điểm.",
    "CK_Stall_Status": "Trạng thái chuồng chỉ được là Available, Occupied hoặc Maintenance.",
    "CK_StallAssignment_Dates": "Ngày rời chuồng phải sau hoặc bằng ngày vào chuồng.",
    "CK_StallAssignment_Status": "Trạng thái xếp chuồng không hợp lệ.",
    "CK_Specialization_Status": "Trạng thái chuyên môn chỉ được là Active hoặc Inactive.",
    "CK_TrainerProfile_Rating": "Điểm đánh giá trainer (TrainerRating) phải từ 0 đến 5.",
    "CK_TrainerCredential_Type": "Loại giấy tờ phải là Degree, Certificate, License hoặc Award.",
    "CK_TrainerCredential_Dates": "Ngày hết hạn của giấy tờ phải sau hoặc bằng ngày cấp.",
    "CK_TrainerRaceResult_Class": "Hạng giải phải là Group 1, Group 2, Group 3, Listed, Handicap, Maiden hoặc Other.",
    "CK_TrainerRaceResult_Position": "Cuộc đua có ít nhất 2 ngựa; thứ hạng phải từ 1 đến số ngựa tham gia.",
    "CK_HorseAssessment_QualityScore": "Điểm đánh giá ngựa (QualityScore) phải từ 0 đến 100.",
    "CK_HorseAssessment_FitnessLevel": "Mức thể lực phải là Excellent, Good, Average hoặc Needs Monitoring.",
    "CK_HorseAssessment_DecisionStatus": "Kết luận đánh giá ngựa không hợp lệ.",
    "CK_TrainerHorseAssignment_Dates": "Ngày kết thúc phân công phải sau hoặc bằng ngày bắt đầu.",
    "CK_TrainerHorseAssignment_Status": "Trạng thái phân công trainer không hợp lệ.",
    "CK_HorseWorkRiderPreference_Dates": "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu (Work Rider ưu tiên).",
    "CK_HorseWorkRiderPreference_Priority": "Thứ tự ưu tiên Work Rider phải lớn hơn 0.",
    "CK_TrainingPlan_Dates": "Ngày kết thúc giáo án phải sau hoặc bằng ngày bắt đầu.",
    "CK_TrainingPlan_Intensity": "Cường độ giáo án phải là Low, Moderate, High hoặc Very High.",
    "CK_TrainingPlan_Status": "Trạng thái giáo án không hợp lệ.",
    "CK_TrainingPlan_Approval": "Giáo án gửi duyệt / đã duyệt phải có thời điểm gửi, người duyệt và thời điểm duyệt.",
    "CK_TrainingPlanStage_Order": "Thứ tự giai đoạn (StageOrder) phải lớn hơn 0.",
    "CK_TrainingPlanStage_Dates": "Ngày kết thúc giai đoạn phải sau hoặc bằng ngày bắt đầu.",
    "CK_TrainingPlanStage_Intensity": "Cường độ giai đoạn phải là Low, Moderate, High hoặc Very High.",
    "CK_TrainingSession_Sequence": "Thứ tự buổi tập trong ngày (SequenceNo) phải lớn hơn 0.",
    "CK_TrainingSession_Time": "Giờ kết thúc buổi tập phải sau hoặc bằng giờ bắt đầu.",
    "CK_TrainingSession_Duration": "Thời lượng dự kiến của buổi tập phải lớn hơn 0 phút.",
    "CK_TrainingSession_Distance": "Quãng đường dự kiến không được âm.",
    "CK_TrainingSession_Status": "Trạng thái buổi tập không hợp lệ.",
    "CK_TrainingResult_Performance": "Điểm thành tích (PerformanceScore) phải từ 0 đến 100.",
    "CK_TrainingResult_HeartRate": "Nhịp tim trung bình / tối đa phải lớn hơn 0.",
    "CK_TrainingResult_Distance": "Quãng đường thực tế không được âm.",
    "CK_TrainingReview_Evaluation": "Đánh giá buổi tập phải là Excellent, Good, Average hoặc Needs Improvement.",
    "CK_TrainingLock_Level": "Training Lock: mức khóa là Full hoặc Restricted; chỉ Restricted mới có MaxIntensity "
                             "và MaxIntensity không được âm.",
    "CK_TrainingLock_Dates": "Ngày kết thúc Training Lock phải sau hoặc bằng ngày bắt đầu.",
    "CK_TrainingLock_Status": "Gỡ Training Lock cần ghi ngày kết thúc và Vet gỡ khóa.",
    "CK_MedicalRecord_ExamType": "Loại khám phải là Initial Exam, Routine Exam, Injury Exam, Follow-up hoặc Emergency.",
    "CK_MedicalRecord_HealthStatus": "Tình trạng sức khỏe phải là Healthy, Monitor, Injured, Recovering hoặc Isolated.",
    "CK_MedicalRecord_TrainingEligibility": "Kết luận tập luyện phải là Eligible, Restricted hoặc Not Eligible.",
    "CK_MedicalRecord_Restriction": "Mức Restricted cần ghi rõ hạn chế tập (RestrictionNote).",
    "CK_MedicalRecord_Measures": "Cân nặng và chiều cao phải lớn hơn 0.",
    "CK_MedicalRecord_FollowUp": "Ngày tái khám phải sau hoặc bằng ngày khám.",
    "CK_MedicalRecord_RecordStatus": "Phiếu khám đã chốt phải có thời điểm chốt.",
    "CK_Treatment_Route": "Đường dùng thuốc phải là Oral, Injection, Topical, Inhalation hoặc Other.",
    "CK_Treatment_Dates": "Ngày kết thúc điều trị và ngày hết thời gian ngưng thuốc phải sau ngày bắt đầu.",
    "CK_Vaccination_Dates": "Ngày tiêm nhắc lại phải sau hoặc bằng ngày tiêm.",
    "CK_Vaccination_Status": "Trạng thái tiêm phòng không hợp lệ.",
    "CK_MedicalSchedule_Type": "Loại lịch y tế phải là Vaccination, Deworming, Farrier hoặc Routine Examination.",
    "CK_MedicalSchedule_Status": "Trạng thái lịch y tế không hợp lệ.",
    "CK_HealthReport_Severity": "Mức độ báo cáo sức khỏe phải là Urgent hoặc Normal.",
    "CK_HealthReport_Status": "Báo cáo sức khỏe: đang xử lý / đã xử lý phải có Vet; đã xử lý phải có thời điểm xử lý.",
    "CK_DietPlan_Dates": "Ngày kết thúc khẩu phần phải sau hoặc bằng ngày bắt đầu.",
    "CK_DietPlan_Status": "Trạng thái khẩu phần không hợp lệ.",
    "CK_DietMeal_Quantity": "Lượng thức ăn mỗi bữa phải lớn hơn 0.",
    "CK_CareTask_Type": "Loại việc chăm sóc phải là Feeding, Cleaning, Bathing hoặc Ice Leg Soak.",
    "CK_CareTask_Status": "Việc chăm sóc đã hoàn thành phải có thời điểm hoàn thành.",
    "CK_InventoryItem_Type": "Loại vật tư phải là Food, Medicine hoặc Care Equipment.",
    "CK_InventoryItem_Quantity": "Số lượng tồn kho và mức tối thiểu không được âm.",
    "CK_InventoryItem_Status": "Trạng thái vật tư không hợp lệ.",
    "CK_InventoryRequest_Status": "Trạng thái yêu cầu vật tư không hợp lệ.",
    "CK_InventoryRequestItem_Quantity": "Số lượng yêu cầu phải lớn hơn 0; số lượng duyệt không được âm "
                                        "và không vượt số lượng yêu cầu.",
}

# Tên cột thường gặp trong câu báo lỗi
COLUMN_LABELS = {
    "ClubID": "câu lạc bộ (ClubID)", "OwnerID": "chủ ngựa (OwnerID)", "HorseID": "ngựa (HorseID)",
    "UserID": "người dùng (UserID)", "VetID": "bác sĩ thú y (VetID)", "StallID": "chuồng (StallID)",
    "RoleID": "vai trò (RoleID)", "TrainerID": "trainer (TrainerID)", "WorkRiderID": "Work Rider (WorkRiderID)",
    "HorseName": "tên ngựa", "MicrochipNumber": "số microchip", "PassportNumber": "số hộ chiếu / đăng ký",
    "FullName": "họ tên", "Email": "email", "Phone": "số điện thoại", "Address": "địa chỉ",
}

_CHECK_RE = re.compile(r'CHECK constraint "?(\w+)"?')
_FK_RE = re.compile(r'(?:FOREIGN KEY|REFERENCE) constraint "(\w+)"')
_NULL_RE = re.compile(r"Cannot insert the value NULL into column '(\w+)', table '[\w.]*?(\w+)'")
_SQLITE_NULL_RE = re.compile(r"NOT NULL constraint failed: (\w+)\.(\w+)")
_DUPLICATE_RE = re.compile(r"(?:UNIQUE KEY constraint|unique index) '(\w+)'")
_TRUNCATE_RE = re.compile(r"truncated in table '[\w.]*?(\w+)', column '(\w+)'")


def _label(column):
    return COLUMN_LABELS.get(column, column)


def friendly_db_error(exc: Exception):
    """Dịch lỗi database (trigger, CHECK, khóa ngoại, NULL, trùng, quá dài) thành (câu tiếng Việt, mã lỗi)."""
    text = str(exc)
    for code, message in TRIGGER_MESSAGES.items():
        if code in text:
            return message, TRIGGER_CODES[code]
    for name, message in CONSTRAINT_MESSAGES.items():
        if name in text:
            return message, name
    match = _CHECK_RE.search(text)
    if match:
        name = match.group(1)
        return CHECK_MESSAGES.get(name, f"Dữ liệu không hợp lệ (vi phạm ràng buộc {name})."), name
    match = _NULL_RE.search(text) or _SQLITE_NULL_RE.search(text)
    if match:
        if _NULL_RE.search(text):
            column, table = match.group(1), match.group(2)
        else:
            table, column = match.group(1), match.group(2)
        return f"Thiếu dữ liệu bắt buộc: {_label(column)} (bảng {table}) không được để trống.", "REQUIRED_VALUE_MISSING"
    match = _FK_RE.search(text)
    if match:
        name = match.group(1)
        parts = name.split("_")
        target = parts[-1] if len(parts) >= 3 else name
        if "REFERENCE constraint" in text:
            return f"Không xóa được vì dữ liệu này đang được dùng ở nơi khác ({name}).", "IN_USE"
        return f"Không tìm thấy dữ liệu liên quan: {target} không tồn tại ({name}).", "RELATED_NOT_FOUND"
    match = _DUPLICATE_RE.search(text)
    if match:
        return f"Dữ liệu bị trùng với một bản ghi đã có ({match.group(1)}).", "DUPLICATE"
    match = _TRUNCATE_RE.search(text)
    if match:
        return f"{_label(match.group(2)).capitalize()} quá dài so với giới hạn của database.", "VALUE_TOO_LONG"
    if "would be truncated" in text:
        return "Có giá trị nhập vào quá dài so với giới hạn của database.", "VALUE_TOO_LONG"
    return None


def api_exception_handler(exc, context):
    response = _build_error_response(exc, context)
    if response is not None and is_english():
        response.data = translate_data(response.data)  # header X-Language: en
    return response


def _build_error_response(exc, context):
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
        set_rollback()
        known = friendly_db_error(exc)
        if known:
            message, code = known
            return Response({"detail": message, "code": code}, status=status.HTTP_409_CONFLICT)
        if isinstance(exc, IntegrityError):
            return Response(
                {"detail": "Dữ liệu vi phạm ràng buộc của database.", "code": "DB_INTEGRITY"},
                status=status.HTTP_409_CONFLICT,
            )
        # Do not let Django's debug traceback become the API error body.
        return Response(
            {"detail": "Không thể đọc hoặc lưu dữ liệu. Vui lòng thử lại hoặc liên hệ quản lý hệ thống.",
             "code": "DATABASE_ERROR"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return None
