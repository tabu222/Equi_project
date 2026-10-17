"""Dữ liệu mẫu Flow 3 cho `python manage.py seed_demo`: lịch tiêm phòng, lịch đóng móng, 1 báo cáo sức khỏe đang mở."""
from datetime import date, timedelta

from django.utils import timezone


def seed_demo(club):
    """Chỉ tạo khi CLB chưa có dữ liệu y tế nào (chạy lại không trùng)."""
    from apps.accounts.models import User
    from apps.horses.models import Horse

    from .models import HealthReport, MedicalSchedule, Vaccination

    horses = {h.horse_name: h for h in Horse.objects.filter(club=club, registration_status="Approved")}
    if not horses or Vaccination.objects.filter(horse__club=club).exists():
        return
    vet = User.objects.filter(email__iexact="vet@equi.local").first()
    groom = User.objects.filter(email__iexact="groom@equi.local").first()
    today = date.today()
    first, *others = list(horses.values())
    Vaccination.objects.create(horse=first, vet=vet, vaccine_name="Cúm ngựa (Equine Influenza)",
                               vaccination_date=today - timedelta(days=180), next_due_date=today + timedelta(days=5),
                               status="Completed", note="Mũi nhắc lại 6 tháng")
    Vaccination.objects.create(horse=first, vet=vet, vaccine_name="Uốn ván (Tetanus)",
                               vaccination_date=today + timedelta(days=5), status="Scheduled")
    MedicalSchedule.objects.create(horse=others[0] if others else first, vet=None, schedule_type="Farrier",
                                   scheduled_date=today + timedelta(days=3), status="Scheduled",
                                   note="Thợ đóng móng ngoài CLB")
    if groom is not None and others:
        HealthReport.objects.create(horse=others[0], reported_by=groom, reported_at=timezone.now(), severity="Normal",
                                    description="Chân sau phải hơi sưng sau khi tắm, ăn uống bình thường")
