"""Flow 1 endpoints recovered from b6f1e4b; Flow 3 routes are not enabled."""
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.permissions import HasAnyPermission
from apps.core.serializers import fmt_datetime
from apps.horses.models import Horse, RegistrationRequest
from apps.horses.views import get_visible_horse
from . import services
from .models import MedicalRecord
from .serializers import MedicalRecordSerializer, MedicalRecordWriteSerializer, MedicalRecordAmendmentSerializer
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
        record = services.create_record(horse, request.user, values)
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
        record = services.update_record(record, request.user, values)
        return Response(MedicalRecordSerializer(record).data)

    def delete(self, request, record_id):
        services.delete_draft(get_visible_record(request.user, record_id), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MedicalRecordSignView(APIView):
    permission_classes = [HasAnyPermission(SIGN)]

    def post(self, request, record_id):
        if request.data:
            raise ValidationError({"detail": "Chốt khám đầu vào không nhận thêm dữ liệu."})
        record, _ = services.sign_record(get_visible_record(request.user, record_id), request.user)
        body = MedicalRecordSerializer(record).data
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
