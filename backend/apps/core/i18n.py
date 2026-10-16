"""
Song ngữ cho API: câu thông báo mặc định tiếng Việt, gửi kèm header `X-Language: en` (hoặc `?lang=en`)
thì backend trả câu tiếng Anh.

- Áp dụng cho: thông báo lỗi (detail, lỗi từng trường), tiêu đề thông báo (GET /api/notifications),
  câu mặc định của Django / DRF ("This field is required."...).
- KHÔNG đổi: mã lỗi (`code`), tên trường JSON, giá trị trạng thái (Draft, Approved...) và dữ liệu người dùng nhập.
- Câu chưa có trong EN thì giữ tiếng Việt. Thêm câu mới: thêm một dòng vào EN (hoặc PATTERNS nếu câu có phần thay đổi).

Không dùng Accept-Language của trình duyệt: trình duyệt tiếng Anh mà giao diện đang tiếng Việt thì lỗi sẽ lệch ngôn ngữ.
Frontend chủ động gửi X-Language theo nút VI / EN.
"""
import re

from django.utils import translation

SUPPORTED = ("vi", "en")
DEFAULT = "vi"


def request_language(request) -> str:
    value = (request.GET.get("lang") or request.headers.get("X-Language") or "").strip().lower()[:2]
    return value if value in SUPPORTED else DEFAULT


class LanguageMiddleware:
    """Bật ngôn ngữ theo X-Language / ?lang= cho từng request; trả header Content-Language."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request_language(request)
        request.LANGUAGE_CODE = language
        with translation.override(language):
            response = self.get_response(request)
        response.headers["Content-Language"] = language
        return response


def is_english() -> bool:
    return (translation.get_language() or DEFAULT).startswith("en")


EN = {
    # ---------- tài khoản / đăng nhập ----------
    "Email hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.": "Wrong email or password, or the account is locked.",
    "Email đã được sử dụng.": "This email is already in use.",
    "Cần nhập số điện thoại (Phone).": "Please enter a phone number (Phone).",
    "Cần nhập địa chỉ (Address).": "Please enter an address (Address).",
    "Số điện thoại không hợp lệ: 10 số bắt đầu bằng 0 (vd 0901234567) hoặc dạng +84 (vd +84901234567).":
        "Invalid phone number: 10 digits starting with 0 (e.g. 0901234567) or +84 (e.g. +84901234567).",
    "RoleCode không tồn tại.": "RoleCode does not exist.",
    "Cần nhập mật khẩu.": "Please enter a password.",
    "Mật khẩu phải có ít nhất 6 ký tự.": "Password must be at least 6 characters.",
    "Cần chọn câu lạc bộ.": "Please select a club.",
    "Câu lạc bộ không tồn tại hoặc đã ngừng hoạt động.": "The club does not exist or is inactive.",
    "Bạn không có quyền xem người dùng này.": "You are not allowed to view this user.",
    "Thiếu Credential từ Google.": "Missing Credential from Google.",
    "Máy chủ chưa bật đăng nhập Google (thiếu GOOGLE_CLIENT_ID trong .env).":
        "Google sign-in is not enabled on the server (GOOGLE_CLIENT_ID missing in .env).",
    "Tài khoản Google này chưa xác minh email.": "This Google account has not verified its email.",
    "Không xác minh được tài khoản Google, vui lòng thử lại.": "Could not verify the Google account, please try again.",
    "Bạn không có quyền thực hiện thao tác này.": "You do not have permission to do this.",
    # ---------- giấy tờ ----------
    "Chỉ nhận file PDF, JPG, PNG hoặc WEBP.": "Only PDF, JPG, PNG or WEBP files are accepted.",
    "File rỗng.": "The file is empty.",
    "Nội dung file không đúng định dạng (file hỏng hoặc đổi đuôi).":
        "The file content does not match its type (corrupted or renamed file).",
    "Đường dẫn file không hợp lệ.": "Invalid file path.",
    "Cần chọn file.": "Please choose a file.",
    "Cần chọn loại giấy tờ.": "Please select a document type.",
    "Loại giấy tờ không hợp lệ.": "Invalid document type.",
    "Không tìm thấy giấy tờ.": "Document not found.",
    "Bạn không được thêm giấy tờ cho ngựa này.": "You are not allowed to add documents to this horse.",
    "Ngựa đã lưu trữ, không thêm giấy tờ được.": "The horse is archived; documents cannot be added.",
    "Bạn không được xóa giấy tờ của ngựa này.": "You are not allowed to delete this horse's documents.",
    "Chỉ xóa được giấy tờ do chính bạn tải lên.": "You can only delete documents you uploaded.",
    "Hồ sơ đã gửi, không xóa giấy tờ được nữa.": "The record has been submitted; documents can no longer be deleted.",
    "Giấy tờ đang là bằng chứng của yêu cầu sửa lý lịch, không xóa được.":
        "This document is evidence for a profile change request and cannot be deleted.",
    "Giấy tờ này là link ngoài, mở bằng FileUrl.": "This document is an external link; open it with FileUrl.",
    "Không tìm thấy file trên máy chủ.": "File not found on the server.",
    "Loại tài liệu không hợp lệ (Passport, Microchip Certificate, Ownership Proof, Handover Record, Contract, Other).":
        "Invalid document type (Passport, Microchip Certificate, Ownership Proof, Handover Record, Contract, Other).",
    # ---------- hồ sơ ngựa ----------
    "Ngày sinh không được ở tương lai.": "Date of birth cannot be in the future.",
    "Số microchip phải gồm đúng 15 chữ số (chuẩn ISO 11784/11785; 3 số đầu là mã quốc gia hoặc nhà sản xuất), "
    "vd 985141000123401.":
        "Microchip number must be exactly 15 digits (ISO 11784/11785; the first 3 digits are the country or "
        "manufacturer code), e.g. 985141000123401.",
    "Số microchip đã tồn tại ở một ngựa khác.": "This microchip number already belongs to another horse.",
    "Số hộ chiếu / đăng ký chỉ gồm chữ, số, dấu '-' hoặc '/', dài 5-50 ký tự, vd VN-TB-2021-0142.":
        "Passport / registration number may only contain letters, digits, '-' or '/', 5-50 characters, "
        "e.g. VN-TB-2021-0142.",
    "Số hộ chiếu / đăng ký đã được dùng cho một ngựa khác.":
        "This passport / registration number is already used by another horse.",
    "Tên ngựa cha không được trùng tên chính con ngựa này.": "The sire name cannot be the same as the horse name.",
    "Tên ngựa mẹ không được trùng tên chính con ngựa này.": "The dam name cannot be the same as the horse name.",
    "Tên ngựa cha và ngựa mẹ không được giống nhau.": "The sire and dam names cannot be the same.",
    "Cần nhập ngày sinh (DateOfBirth).": "Please enter the date of birth (DateOfBirth).",
    "Ngày sinh phải theo dạng YYYY-MM-DD, vd 2021-03-12.": "Date of birth must be YYYY-MM-DD, e.g. 2021-03-12.",
    "Cần chọn giới tính (Gender).": "Please select the sex (Gender).",
    "Giới tính phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến).": "Sex must be Male, Female or Gelding.",
    "Giới tính ngựa phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến).": "Sex must be Male, Female or Gelding.",
    "tên ngựa (HorseName)": "horse name (HorseName)",
    "giống ngựa (Breed)": "breed (Breed)",
    "màu lông (CoatColor)": "coat color (CoatColor)",
    "tên ngựa cha (SireName)": "sire name (SireName)",
    "tên ngựa mẹ (DamName)": "dam name (DamName)",
    "số microchip (MicrochipNumber)": "microchip number (MicrochipNumber)",
    "số hộ chiếu / đăng ký (PassportNumber)": "passport / registration number (PassportNumber)",
    "Không tìm thấy ngựa.": "Horse not found.",
    "Bạn không được sửa hồ sơ ngựa này.": "You are not allowed to edit this horse record.",
    "Bạn không được gửi hồ sơ ngựa này.": "You are not allowed to submit this horse record.",
    "Tài khoản của bạn chưa thuộc câu lạc bộ nào (ClubID trống) nên chưa tạo được ngựa.":
        "Your account does not belong to any club (ClubID is empty), so you cannot create horses.",
    "Manager tạo hồ sơ cần chọn chủ ngựa (OwnerID).": "Please select the horse owner (OwnerID).",
    "Không tìm thấy chủ ngựa với OwnerID này.": "No horse owner found with this OwnerID.",
    "Cần chọn câu lạc bộ đang hoạt động (ClubID).": "Please select an active club (ClubID).",
    "Ngựa chưa có phiếu khám đầu vào đã chốt.": "The horse has no signed intake exam yet.",
    "Kết quả khám đầu vào không đạt (sức khỏe phải là Healthy hoặc Monitor và không bị cấm tập). Hãy từ chối hồ sơ.":
        "The intake exam did not pass (health must be Healthy or Monitor and the horse must not be barred from "
        "training). Reject the record.",
    "Mã ngựa đã tồn tại trong câu lạc bộ.": "This horse code already exists in the club.",
    "Ngựa này đang có một yêu cầu sửa lý lịch chờ duyệt.": "This horse already has a pending profile change request.",
    "Chưa có trường nào cần sửa.": "No field to change.",
    "Tài liệu bằng chứng không thuộc ngựa này.": "The evidence document does not belong to this horse.",
    "Yêu cầu này đã được xử lý.": "This request has already been processed.",
    "Cần ghi lý do từ chối (ReviewNote).": "Please enter a rejection reason (ReviewNote).",
    "Chỉ chủ ngựa được gửi yêu cầu sửa lý lịch.": "Only the horse owner can request profile changes.",
    "Trạng thái hồ sơ ngựa không hợp lệ.": "Invalid horse registration status.",
    "Tình trạng sức khỏe ngựa không hợp lệ.": "Invalid horse health status.",
    "Ngựa đã duyệt phải có mã ngựa (HorseCode).": "An approved horse must have a horse code (HorseCode).",
    "Trạng thái hồ sơ tiếp nhận không hợp lệ.": "Invalid registration request status.",
    "Trạng thái yêu cầu sửa lý lịch không hợp lệ.": "Invalid profile change request status.",
    "sửa lý lịch": "edit the profile",
    "gửi hồ sơ": "submit the record",
    "xác minh hồ sơ": "verify the record",
    "từ chối hồ sơ": "reject the record",
    "duyệt hồ sơ": "approve the record",
    "lưu trữ hồ sơ": "archive the record",
    "gửi yêu cầu sửa lý lịch": "request a profile change",
    "xếp chuồng": "assign a stall",
    # ---------- chuồng ----------
    "Không tìm thấy chuồng.": "Stall not found.",
    "Cần chọn chuồng.": "Please select a stall.",
    "Số chuồng đã tồn tại trong câu lạc bộ.": "This stall number already exists in the club.",
    "Chuồng đang có ngựa, chuyển ngựa đi trước khi đổi trạng thái.":
        "The stall is occupied; move the horse out before changing its status.",
    "Chuồng không tồn tại trong câu lạc bộ.": "The stall does not exist in this club.",
    "Chuồng này không còn trống.": "This stall is no longer available.",
    "Chuồng này đang có ngựa khác.": "This stall already has another horse.",
    "Ngựa này đang ở một chuồng khác.": "This horse is already in another stall.",
    "Occupied do hệ thống tự đặt khi xếp ngựa vào chuồng.": "Occupied is set automatically when a horse is assigned.",
    # ---------- khám đầu vào ----------
    "Chỉ khám đầu vào khi hồ sơ ngựa đang chờ khám (PendingExam).":
        "Intake exams are only possible while the record is awaiting an exam (PendingExam).",
    "Không tìm thấy hồ sơ tiếp nhận đang chờ khám.": "No intake record awaiting an exam was found.",
    "Hồ sơ tiếp nhận này đã có phiếu khám đầu vào.": "This intake already has an intake exam.",
    "Ngựa chưa được tiếp nhận nên chỉ được lập phiếu khám đầu vào.":
        "The horse has not been accepted yet, so only an intake exam is allowed.",
    "Phiếu khám đã chốt không được sửa. Hãy thêm phiếu đính chính.":
        "A signed exam record cannot be edited. Add an amendment instead.",
    "Chỉ Vet lập phiếu mới được sửa / chốt phiếu nháp này.": "Only the vet who started this draft can edit or sign it.",
    "Không được đổi loại khám. Hãy xóa phiếu nháp và lập phiếu mới.":
        "The exam type cannot be changed. Delete the draft and start a new one.",
    "Phiếu nháp thì sửa trực tiếp, không cần phiếu đính chính.": "Edit a draft directly; no amendment is needed.",
    "Mức Restricted cần ghi rõ hạn chế tập (RestrictionNote).": "Restricted requires a training restriction (RestrictionNote).",
    "Cân nặng phải lớn hơn 0.": "Weight must be greater than 0.",
    "Chiều cao phải lớn hơn 0.": "Height must be greater than 0.",
    "Không được âm.": "Must not be negative.",
    "Ngày tái khám không được trước ngày khám.": "The follow-up date cannot be before the exam date.",
    "Không tìm thấy phiếu khám.": "Exam record not found.",
    "Bệnh án đã chốt không được sửa hoặc xóa. Hãy thêm phiếu đính chính.":
        "A signed medical record cannot be edited or deleted. Add an amendment instead.",
    "Loại khám phải là Initial Exam, Routine Exam, Injury Exam, Follow-up hoặc Emergency.":
        "Exam type must be Initial Exam, Routine Exam, Injury Exam, Follow-up or Emergency.",
    "Tình trạng sức khỏe phải là Healthy, Monitor, Injured, Recovering hoặc Isolated.":
        "Health status must be Healthy, Monitor, Injured, Recovering or Isolated.",
    "Kết luận tập luyện phải là Eligible, Restricted hoặc Not Eligible.":
        "Training eligibility must be Eligible, Restricted or Not Eligible.",
    "Cân nặng và chiều cao phải lớn hơn 0.": "Weight and height must be greater than 0.",
    "Ngày tái khám phải sau hoặc bằng ngày khám.": "The follow-up date must be on or after the exam date.",
    "Phiếu khám đã chốt phải có thời điểm chốt.": "A signed exam record must have a signing time.",
    # ---------- chung ----------
    "Thao tác không hợp lệ với trạng thái hiện tại.": "This action is not allowed in the current state.",
    "Không tìm thấy.": "Not found.",
    "Phải là số nguyên.": "Must be a whole number.",
    "Ngày không hợp lệ, dùng dạng YYYY-MM-DD.": "Invalid date, use YYYY-MM-DD.",
    "Có giá trị nhập vào quá dài so với giới hạn của database.": "A value is too long for the database.",
    "Dữ liệu vi phạm ràng buộc của database.": "The data violates a database constraint.",
    "câu lạc bộ (ClubID)": "club (ClubID)",
    "chủ ngựa (OwnerID)": "horse owner (OwnerID)",
    "ngựa (HorseID)": "horse (HorseID)",
    "người dùng (UserID)": "user (UserID)",
    "bác sĩ thú y (VetID)": "veterinarian (VetID)",
    "chuồng (StallID)": "stall (StallID)",
    "vai trò (RoleID)": "role (RoleID)",
    "tên ngựa": "horse name",
    "số microchip": "microchip number",
    "số hộ chiếu / đăng ký": "passport / registration number",
    "họ tên": "full name",
    "số điện thoại": "phone number",
    "địa chỉ": "address",
    # ---------- tiêu đề thông báo (GET /api/notifications) ----------
    "Hồ sơ ngựa chờ xác minh": "Horse record awaiting verification",
    "Vet đã khám đầu vào, chờ duyệt tiếp nhận": "Intake exam done, awaiting approval",
    "Yêu cầu sửa lý lịch chờ duyệt": "Profile change request awaiting review",
    "Ngựa chờ khám đầu vào": "Horse awaiting intake exam",
    "Phiếu khám nháp chưa chốt": "Unsigned draft exam record",
    "Hồ sơ ngựa bị từ chối, cần sửa và gửi lại": "Horse record rejected; edit and resubmit",
    "Khẩu phần chờ Vet duyệt": "Diet plan awaiting vet review",
    "Trainer đề nghị điều chỉnh giáo án": "Trainer requested a training plan adjustment",
    "Khẩu phần bị Vet trả về": "Diet plan returned by the vet",
    "Giáo án bị trả về": "Training plan returned",
    "Cần ghi nhận xét buổi tập đã giám sát thay": "Add notes for the session you supervised as substitute",
    "Buổi tập chờ đánh giá": "Training session awaiting review",
}

PATTERNS = [
    (re.compile(r"^Không thể (.+) khi hồ sơ đang ở trạng thái (.+)\.$"),
     lambda m: f"Cannot {translate_text(m[1])} while the record is {m[2]}."),
    (re.compile(r"^Cần nhập đủ thông tin trước khi gửi: (.+)\.$"),
     lambda m: f"Fill in these fields before submitting: {m[1]}."),
    (re.compile(r"^Cần nhập đủ trước khi chốt phiếu: (.+)\.$"), lambda m: f"Fill in these fields before signing: {m[1]}."),
    (re.compile(r"^Không được xin sửa các trường: (.+)\. Chỉ được: (.+)\.$"),
     lambda m: f"These fields cannot be changed: {m[1]}. Allowed: {m[2]}."),
    (re.compile(r"^Ngày sinh không hợp lệ: ngựa không thể quá (\d+) tuổi\.$"),
     lambda m: f"Invalid date of birth: a horse cannot be older than {m[1]}."),
    (re.compile(r"^File quá lớn, tối đa (\d+) MB\.$"), lambda m: f"File too large, maximum {m[1]} MB."),
    (re.compile(r"^Cần chọn người dùng đang hoạt động trong CLB có vai trò (.+)\.$"),
     lambda m: f"Select an active club member with the role {m[1]}."),
    (re.compile(r"^Thiếu dữ liệu bắt buộc: (.+) \(bảng (.+)\) không được để trống\.$"),
     lambda m: f"Missing required data: {translate_text(m[1])} (table {m[2]}) cannot be empty."),
    (re.compile(r"^Không tìm thấy dữ liệu liên quan: (.+) không tồn tại \((.+)\)\.$"),
     lambda m: f"Related data not found: {translate_text(m[1])} does not exist ({m[2]})."),
    (re.compile(r"^Dữ liệu bị trùng với một bản ghi đã có \((.+)\)\.$"),
     lambda m: f"This duplicates an existing record ({m[1]})."),
    (re.compile(r"^(.+) quá dài so với giới hạn của database\.$"),
     lambda m: f"{translate_text(m[1]).capitalize()} is too long for the database."),
    (re.compile(r"^Dữ liệu không hợp lệ \(vi phạm ràng buộc (.+)\)\.$"),
     lambda m: f"Invalid data (violates constraint {m[1]})."),
    (re.compile(r"^Không xóa được vì dữ liệu này đang được dùng ở nơi khác \((.+)\)\.$"),
     lambda m: f"Cannot delete: this data is used elsewhere ({m[1]})."),
    (re.compile(r"^Báo cáo sức khỏe \((.+)\) - (.+)$"), lambda m: f"Health report ({m[1]}) - {m[2]}"),
    (re.compile(r"^Yêu cầu sửa lý lịch: (.+)$"), lambda m: f"Profile change request: {m[1]}"),
    (re.compile(r"^Yêu cầu vật tư của (.+)$"), lambda m: f"Supply request from {m[1]}"),
    (re.compile(r"^Giáo án của (.+) chờ duyệt$"), lambda m: f"Training plan by {m[1]} awaiting approval"),
    (re.compile(r"^Tiêm (.+)$"), lambda m: f"Vaccination: {m[1]}"),
    (re.compile(r"^Lịch (.+)$"), lambda m: f"Schedule: {m[1]}"),
    (re.compile(r"^Cần nhập (.+)\.$"), lambda m: f"Please enter {translate_text(m[1])}."),  # để cuối: câu chung
]


def translate_text(text: str) -> str:
    """Câu tiếng Việt -> tiếng Anh; chưa có bản dịch thì trả lại nguyên văn."""
    if not isinstance(text, str) or not text:
        return text
    if text in EN:
        return EN[text]
    for pattern, build in PATTERNS:
        match = pattern.match(text)
        if match:
            return build(match)
    return text


def translate_data(data, key=None):
    """Dịch các chuỗi trong dict / list lỗi trả về (giữ nguyên tên khóa và trường `code`)."""
    if key == "code":
        return data
    if isinstance(data, dict):
        return {k: translate_data(v, k) for k, v in data.items()}
    if isinstance(data, list):
        return [translate_data(item, key) for item in data]
    if isinstance(data, str):
        translated = translate_text(str(data))
        if translated is not data and hasattr(data, "code"):  # ErrorDetail: giữ code của DRF
            from rest_framework.exceptions import ErrorDetail
            return ErrorDetail(translated, code=data.code)
        return translated
    return data
