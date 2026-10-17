"""
API y tế.
Flow 1 - phiếu khám: /vet/pending-initial-exams, /horses/<id>/medical-records, /medical-records/<id>[/sign|/amendments].
Flow 3 - Training Lock, thuốc điều trị, tiêm phòng, lịch y tế, báo cáo sức khỏe (xem docs/API.md mục 6).
"""
from datetime import date, timedelta

from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.params import date_param, flag_param, int_param
from apps.core.permissions import HasAnyPermission
from apps.core.serializers import fmt_datetime
from apps.horses.models import Horse, RegistrationRequest
from apps.horses.views import get_visible_horse

from . import services
from .models import HealthReport, MedicalRecord, MedicalSchedule, TrainingLock, Treatment, Vaccination
from .serializers import (
    ContentSerializer, HealthReportCreateSerializer, HealthReportNoteSerializer, HealthReportSerializer,
    MedicalRecordAmendmentSerializer, MedicalRecordSerializer, MedicalRecordWriteSerializer, MedicalScheduleSerializer,
    ReleaseLockSerializer, ResolveReportSerializer, SignSerializer, TrainingLockSerializer,
    TrainingLockWriteSerializer, TreatmentSerializer, VaccinationSerializer,
)

STAFF_VIEW = "HORSE_VIEW"
VET = "MEDICAL_MANAGE"
SIGN = "MEDICAL_SIGN"

def records_visible_to(user):
    """Nhân sự CLB thấy phiếu đã chốt của ngựa trong CLB; Vet thấy thêm phiếu nháp."""
    queryset = MedicalRecord.objects.select_related("vet", "horse").filter(horse__club_id=user.club_id)
    if not user.has_perm(VET):
        queryset = queryset.filter(record_status=MedicalRecord.RecordStatus.SIGNED)
    return queryset


def get_visible_record(user, record_id):
    record = records_visible_to(user).filter(pk=record_id).first()
    if record is None:
        raise NotFound("Không tìm thấy phiếu khám.")
    return record


class PendingInitialExamView(APIView):
    """
    Giống view vw_PendingInitialExam trong SQL, nhưng giữ lại cả ngựa đã có phiếu NHÁP
    (Vet khám dở vẫn thấy để làm tiếp). DraftMedicalRecordID != null nghĩa là đang khám dở.
    """

    permission_classes = [HasAnyPermission(VET)]

    def get(self, request):
        now = timezone.now()
        requests = (
            RegistrationRequest.objects.filter(status=RegistrationRequest.Status.PENDING_EXAM,
                                               club_id=request.user.club_id)
            .select_related("horse")
            .annotate(signed=Exists(MedicalRecord.objects.filter(
                registration_request=OuterRef("pk"), exam_type=MedicalRecord.ExamType.INITIAL,
                record_status=MedicalRecord.RecordStatus.SIGNED)))
            .filter(signed=False, horse__registration_status=Horse.RegistrationStatus.PENDING_EXAM)
            .order_by("request_date")
        )
        result = []
        for item in requests:
            horse = item.horse
            draft = item.medical_records.filter(exam_type=MedicalRecord.ExamType.INITIAL).first()
            result.append({
                "RegistrationRequestID": item.id,
                "RequestDate": fmt_datetime(item.request_date),
                "WaitingHours": int((now - item.request_date).total_seconds() // 3600),
                "HorseID": horse.id,
                "HorseName": horse.horse_name,
                "MicrochipNumber": horse.microchip_number,
                "Breed": horse.breed,
                "Gender": horse.gender,
                "SexClass": horse.sex_class,
                "DateOfBirth": horse.date_of_birth,
                "VerifiedAt": fmt_datetime(horse.verified_at),
                "DraftMedicalRecordID": draft.id if draft else None,
                "DraftVetID": draft.vet_id if draft else None,
            })
        return Response(result)


class HorseMedicalRecordListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(VET)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, horse_id):
        horse = get_visible_horse(request.user, horse_id)
        records = records_visible_to(request.user).filter(horse=horse)
        if request.query_params.get("ExamType"):
            records = records.filter(exam_type=request.query_params["ExamType"])
        return Response(MedicalRecordSerializer(records, many=True).data)

    def post(self, request, horse_id):
        horse = get_visible_horse(request.user, horse_id)
        data = MedicalRecordWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        report_id = values.pop("HealthReportID", None)
        report = None
        if report_id:
            report = HealthReport.objects.filter(pk=report_id, horse__club_id=request.user.club_id).first()
            if report is None:
                raise ValidationError({"HealthReportID": ["Không tìm thấy báo cáo sức khỏe."]})
        record = services.create_record(horse, request.user, values, report)
        return Response(MedicalRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class MedicalRecordDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [HasAnyPermission(VET)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, record_id):
        return Response(MedicalRecordSerializer(get_visible_record(request.user, record_id)).data)

    def patch(self, request, record_id):
        record = get_visible_record(request.user, record_id)
        data = MedicalRecordWriteSerializer(record, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        values.pop("HealthReportID", None)
        record = services.update_record(record, request.user, values)
        return Response(MedicalRecordSerializer(record).data)

    def delete(self, request, record_id):
        services.delete_draft(get_visible_record(request.user, record_id), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MedicalRecordSignView(APIView):
    permission_classes = [HasAnyPermission(SIGN)]

    def post(self, request, record_id):
        """Body (tùy chọn, khám ngựa đã tiếp nhận): {"TrainingLock": {"Reason", "LockLevel", "MaxIntensity", ...}}"""
        record = get_visible_record(request.user, record_id)
        data = SignSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        lock_values = data.validated_data.get("TrainingLock")
        if lock_values and record.exam_type == MedicalRecord.ExamType.INITIAL:
            raise ValidationError({"TrainingLock": ["Khám đầu vào không tạo Training Lock."]})
        record, lock = services.sign_record(record, request.user, dict(lock_values) if lock_values else None)
        body = MedicalRecordSerializer(record).data
        body["TrainingLock"] = lock_body(lock) if lock else None
        return Response(body)


class MedicalRecordAmendmentView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(VET)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, record_id):
        record = get_visible_record(request.user, record_id)
        return Response(MedicalRecordAmendmentSerializer(record.amendments.select_related("amended_by"),
                                                         many=True).data)

    def post(self, request, record_id):
        record = get_visible_record(request.user, record_id)
        data = MedicalRecordAmendmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        amendment = services.add_amendment(record, request.user, v["reason"], v["amended_content"])
        return Response(MedicalRecordAmendmentSerializer(amendment).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Hỗ trợ
# ---------------------------------------------------------------------------
def club_object(model, user, pk, horse_path="horse__club_id", message="Không tìm thấy."):
    obj = model.objects.filter(pk=pk, **{horse_path: user.club_id}).first()
    if obj is None:
        raise NotFound(message)
    return obj


def lock_body(lock):
    body = TrainingLockSerializer(lock).data
    body["CancelledSessionIDs"] = getattr(lock, "cancelled_session_ids", [])
    return body


# ---------------------------------------------------------------------------
# Training Lock
# ---------------------------------------------------------------------------
class TrainingLockListView(APIView):
    """GET /api/training-locks?HorseID=&LockStatus=Active"""

    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request):
        locks = TrainingLock.objects.filter(horse__club_id=request.user.club_id).select_related("horse", "created_by")
        p = request.query_params
        if p.get("HorseID"):
            locks = locks.filter(horse_id=int_param(p, "HorseID"))
        if p.get("LockStatus"):
            locks = locks.filter(lock_status=p["LockStatus"])
        return Response(TrainingLockSerializer(locks, many=True).data)


class HorseTrainingLockView(APIView):
    """POST /api/horses/<HorseID>/training-locks - Vet khóa huấn luyện (tự hủy buổi tập bị ảnh hưởng)."""

    permission_classes = [HasAnyPermission("TRAINING_LOCK_MANAGE")]

    def post(self, request, horse_id):
        horse = get_visible_horse(request.user, horse_id)
        data = TrainingLockWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        lock = services.create_lock(horse, request.user, dict(data.validated_data))
        return Response(lock_body(lock), status=status.HTTP_201_CREATED)


class TrainingLockDetailView(APIView):
    """GET / PATCH /api/training-locks/<id> (PATCH: đổi mức, cường độ, ngày mở dự kiến)."""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [HasAnyPermission("TRAINING_LOCK_MANAGE")()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, lock_id):
        return Response(TrainingLockSerializer(club_object(TrainingLock, request.user, lock_id)).data)

    def patch(self, request, lock_id):
        lock = club_object(TrainingLock, request.user, lock_id)
        data = TrainingLockWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(lock_body(services.update_lock(lock, request.user, dict(data.validated_data))))


class TrainingLockReleaseView(APIView):
    """POST /api/training-locks/<id>/release {"Note"} - cần lần tái khám đã chốt cho phép tập."""

    permission_classes = [HasAnyPermission("TRAINING_LOCK_MANAGE")]

    def post(self, request, lock_id):
        lock = club_object(TrainingLock, request.user, lock_id)
        data = ReleaseLockSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        return Response(TrainingLockSerializer(services.release_lock(lock, request.user,
                                                                     data.validated_data.get("Note"))).data)


# ---------------------------------------------------------------------------
# Thuốc điều trị
# ---------------------------------------------------------------------------
class RecordTreatmentView(APIView):
    """GET / POST /api/medical-records/<id>/treatments"""

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(VET)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, record_id):
        record = get_visible_record(request.user, record_id)
        return Response(TreatmentSerializer(record.treatments.all(), many=True).data)

    def post(self, request, record_id):
        record = get_visible_record(request.user, record_id)
        data = TreatmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        treatment = services.add_treatment(record, request.user, dict(data.validated_data))
        return Response(TreatmentSerializer(treatment).data, status=status.HTTP_201_CREATED)


class TreatmentDetailView(APIView):
    """PATCH /api/treatments/<id> (ví dụ ghi EndDate khi ngưng thuốc)"""

    permission_classes = [HasAnyPermission(VET)]

    def patch(self, request, treatment_id):
        treatment = club_object(Treatment, request.user, treatment_id, "medical_record__horse__club_id")
        data = TreatmentSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(TreatmentSerializer(services.update_treatment(treatment, request.user,
                                                                      dict(data.validated_data))).data)


class HorseTreatmentView(APIView):
    """GET /api/horses/<HorseID>/treatments?WithdrawalActive=1 - thuốc đã dùng / còn trong thời gian ngưng thuốc."""

    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request, horse_id):
        horse = get_visible_horse(request.user, horse_id)
        items = Treatment.objects.filter(medical_record__horse=horse,
                                         medical_record__record_status=MedicalRecord.RecordStatus.SIGNED)
        if request.user.has_perm(VET):
            items = Treatment.objects.filter(medical_record__horse=horse)
        if flag_param(request.query_params, "WithdrawalActive"):
            items = items.filter(withdrawal_until__gte=date.today())
        return Response(TreatmentSerializer(items, many=True).data)


# ---------------------------------------------------------------------------
# Tiêm phòng, lịch y tế
# ---------------------------------------------------------------------------
def _vet_values(request, values):
    external = values.pop("ExternalVet", False)
    if external:
        values["vet"] = None       # bác sĩ ngoài không có tài khoản
    elif "vet" not in values:
        values["vet"] = request.user
    return values


class VaccinationListView(APIView):
    """
    GET  /api/vaccinations?HorseID=&Status=&DueWithinDays=14   (DueWithinDays: sắp tới hạn / quá hạn)
    POST /api/horses/<HorseID>/vaccinations (cùng view, xem urls)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(VET)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, horse_id=None):
        items = Vaccination.objects.filter(horse__club_id=request.user.club_id).select_related("horse", "vet")
        p = request.query_params
        if horse_id or p.get("HorseID"):
            items = items.filter(horse_id=horse_id or int_param(p, "HorseID"))
        if p.get("Status"):
            items = items.filter(status=p["Status"])
        if p.get("DueWithinDays"):
            limit = date.today() + timedelta(days=int_param(p, "DueWithinDays"))
            items = items.filter(Q(status="Scheduled", vaccination_date__lte=limit)
                                 | Q(status="Completed", next_due_date__lte=limit))
        return Response(VaccinationSerializer(items, many=True).data)

    def post(self, request, horse_id=None):
        if horse_id is None:
            raise ValidationError({"HorseID": ["Gọi POST /api/horses/<HorseID>/vaccinations."]})
        horse = get_visible_horse(request.user, horse_id)
        data = VaccinationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        vaccination = services.save_vaccination(request.user, _vet_values(request, dict(data.validated_data)),
                                                horse=horse)
        return Response(VaccinationSerializer(vaccination).data, status=status.HTTP_201_CREATED)


class VaccinationDetailView(APIView):
    """PATCH /api/vaccinations/<id> - ví dụ {"Status": "Completed", "NextDueDate": "2027-04-01"}"""

    permission_classes = [HasAnyPermission(VET)]

    def patch(self, request, vaccination_id):
        vaccination = club_object(Vaccination, request.user, vaccination_id)
        data = VaccinationSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if "ExternalVet" not in request.data:
            values.pop("ExternalVet", None)
            values["vet"] = vaccination.vet
        return Response(VaccinationSerializer(services.save_vaccination(
            request.user, _vet_values(request, values), vaccination)).data)


class MedicalScheduleListView(APIView):
    """
    GET  /api/medical-schedules?From=&To=&HorseID=&Status=&ScheduleType=
    POST /api/horses/<HorseID>/medical-schedules
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(VET)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, horse_id=None):
        items = MedicalSchedule.objects.filter(horse__club_id=request.user.club_id).select_related("horse", "vet")
        p = request.query_params
        if horse_id or p.get("HorseID"):
            items = items.filter(horse_id=horse_id or int_param(p, "HorseID"))
        if p.get("From"):
            items = items.filter(scheduled_date__gte=date_param(p, "From"))
        if p.get("To"):
            items = items.filter(scheduled_date__lte=date_param(p, "To"))
        if p.get("Status"):
            items = items.filter(status=p["Status"])
        if p.get("ScheduleType"):
            items = items.filter(schedule_type=p["ScheduleType"])
        return Response(MedicalScheduleSerializer(items, many=True).data)

    def post(self, request, horse_id=None):
        if horse_id is None:
            raise ValidationError({"HorseID": ["Gọi POST /api/horses/<HorseID>/medical-schedules."]})
        horse = get_visible_horse(request.user, horse_id)
        data = MedicalScheduleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        schedule = services.save_schedule(request.user, _vet_values(request, dict(data.validated_data)), horse=horse)
        return Response(MedicalScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)


class MedicalScheduleDetailView(APIView):
    """PATCH /api/medical-schedules/<id>"""

    permission_classes = [HasAnyPermission(VET)]

    def patch(self, request, schedule_id):
        schedule = club_object(MedicalSchedule, request.user, schedule_id)
        data = MedicalScheduleSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if "ExternalVet" not in request.data:
            values.pop("ExternalVet", None)
            values["vet"] = schedule.vet
        return Response(MedicalScheduleSerializer(services.save_schedule(
            request.user, _vet_values(request, values), schedule)).data)


# ---------------------------------------------------------------------------
# Báo cáo sức khỏe
# ---------------------------------------------------------------------------
REPORTERS = ("HEALTH_REPORT",)


def reports_visible_to(user):
    return HealthReport.objects.filter(horse__club_id=user.club_id).select_related(
        "horse", "reported_by", "vet").prefetch_related("notes__note_by", "reported_by__roles")


class HealthReportListView(APIView):
    """
    GET /api/health-reports?Status=&Severity=&HorseID=&open=1&mine=1
        Vet: hàng chờ (open=1) - Urgent trước, cũ trước.
    GET /api/horses/<HorseID>/health-reports?open=1  - xem báo cáo chưa xử lý trước khi báo (tránh báo trùng)
    POST /api/horses/<HorseID>/health-reports        - Groom / Work Rider / Trainer / Head Trainer báo sự cố
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasAnyPermission(*REPORTERS)()]
        return [HasAnyPermission(STAFF_VIEW)()]

    def get(self, request, horse_id=None):
        reports = reports_visible_to(request.user)
        p = request.query_params
        if horse_id or p.get("HorseID"):
            reports = reports.filter(horse_id=horse_id or int_param(p, "HorseID"))
        if p.get("Status"):
            reports = reports.filter(status=p["Status"])
        if p.get("Severity"):
            reports = reports.filter(severity=p["Severity"])
        if flag_param(p, "mine"):
            reports = reports.filter(reported_by=request.user)
        if flag_param(p, "open"):
            reports = reports.exclude(status=HealthReport.Status.RESOLVED).annotate(
                priority=Case(When(severity="Urgent", then=Value(1)), default=Value(2), output_field=IntegerField())
            ).order_by("priority", "reported_at", "id")
        return Response(HealthReportSerializer(reports, many=True).data)

    def post(self, request, horse_id=None):
        if horse_id is None:
            raise ValidationError({"HorseID": ["Gọi POST /api/horses/<HorseID>/health-reports."]})
        horse = get_visible_horse(request.user, horse_id)
        data = HealthReportCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        report = services.create_health_report(horse, request.user, dict(data.validated_data))
        body = HealthReportSerializer(reports_visible_to(request.user).get(pk=report.pk)).data
        body["StoppedSession"] = report.stopped_session
        return Response(body, status=status.HTTP_201_CREATED)


def get_report(user, report_id):
    report = reports_visible_to(user).filter(pk=report_id).first()
    if report is None:
        raise NotFound("Không tìm thấy báo cáo sức khỏe.")
    return report


class HealthReportDetailView(APIView):
    permission_classes = [HasAnyPermission(STAFF_VIEW)]

    def get(self, request, report_id):
        return Response(HealthReportSerializer(get_report(request.user, report_id)).data)


class HealthReportNoteView(APIView):
    """POST /api/health-reports/<id>/notes {"Content"} - người phát hiện sau thêm ghi chú thay vì báo trùng."""

    permission_classes = [HasAnyPermission("HEALTH_REPORT", VET)]

    def post(self, request, report_id):
        report = get_report(request.user, report_id)
        data = ContentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        note = services.add_report_note(report, request.user, data.validated_data["Content"])
        return Response(HealthReportNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class HealthReportTakeView(APIView):
    """POST /api/health-reports/<id>/take - Vet trực nhận ca (Reported -> Reviewing)."""

    permission_classes = [HasAnyPermission(VET)]

    def post(self, request, report_id):
        report = services.take_report(get_report(request.user, report_id), request.user)
        return Response(HealthReportSerializer(get_report(request.user, report.pk)).data)


class HealthReportResolveView(APIView):
    """POST /api/health-reports/<id>/resolve {"VetNote", "MedicalRecordID"?}"""

    permission_classes = [HasAnyPermission(VET)]

    def post(self, request, report_id):
        report = get_report(request.user, report_id)
        data = ResolveReportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        record = None
        if v.get("MedicalRecordID"):
            record = MedicalRecord.objects.filter(pk=v["MedicalRecordID"], horse__club_id=request.user.club_id).first()
            if record is None:
                raise ValidationError({"MedicalRecordID": ["Không tìm thấy phiếu khám."]})
        services.resolve_report(report, request.user, v.get("VetNote"), record)
        return Response(HealthReportSerializer(get_report(request.user, report.pk)).data)

