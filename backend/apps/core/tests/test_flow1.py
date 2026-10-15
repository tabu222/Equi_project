"""Flow 1: Đăng ký -> xác minh -> khám đầu vào -> duyệt -> (sửa lý lịch) -> lưu trữ."""
from apps.core.models import AuditLog
from apps.horses.models import Horse, RegistrationRequest, Stall, StallAssignment

from .helpers import Flow1TestCase, years_ago


class HappyPathTests(Flow1TestCase):
    def test_full_flow(self):
        owner, manager, vet = (self.client_for(u) for u in (self.owner, self.manager, self.vet))

        # 1. Owner tạo hồ sơ nháp
        horse_id = self.owner_creates_horse()
        horse = owner.get(f"/api/horses/{horse_id}").data
        self.assertEqual(horse["RegistrationStatus"], "Draft")
        self.assertEqual(horse["OwnerID"], self.owner.id)
        self.assertEqual(horse["ClubID"], self.club.id)
        self.assertFalse(horse["InitialExamSigned"])
        self.assertIsNone(horse["HorseCode"])
        self.assertEqual(horse["Owner"]["Email"], "owner@one.test")

        # 2. Owner sửa nháp rồi gửi
        res = owner.patch(f"/api/horses/{horse_id}", {"CoatColor": "Dark Bay"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["CoatColor"], "Dark Bay")
        res = owner.post(f"/api/horses/{horse_id}/submit")
        self.assertEqual(res.data["RegistrationStatus"], "Submitted")

        # 3. Manager xác minh -> chờ khám
        res = manager.post(f"/api/horses/{horse_id}/verify")
        self.assertEqual(res.data["RegistrationStatus"], "PendingExam")
        self.assertEqual(res.data["VerifiedBy"], self.manager.id)

        # 4. Vet trực thấy ngựa trong hàng chờ, khám, lưu nháp, chốt
        queue = vet.get("/api/vet/pending-initial-exams").data
        self.assertEqual([q["HorseID"] for q in queue], [horse_id])
        self.assertIsNone(queue[0]["DraftMedicalRecordID"])

        res = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Initial Exam", "WeightKg": 480.5, "HeightCm": 162, "Symptoms": "Không có",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        record_id = res.data["MedicalRecordID"]
        self.assertEqual(res.data["RecordStatus"], "Draft")
        self.assertEqual(res.data["WeightKg"], 480.5)
        self.assertEqual(vet.get("/api/vet/pending-initial-exams").data[0]["DraftMedicalRecordID"], record_id)

        res = vet.post(f"/api/medical-records/{record_id}/sign")
        self.assertEqual(res.status_code, 409)               # chưa có HealthStatus / TrainingEligibility
        self.assertEqual(res.data["code"], "MISSING_FIELDS")

        vet.patch(f"/api/medical-records/{record_id}", {
            "HealthStatus": "Healthy", "TrainingEligibility": "Eligible", "Conclusion": "Đạt",
        }, format="json")
        res = vet.post(f"/api/medical-records/{record_id}/sign")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["RecordStatus"], "Signed")
        self.assertEqual(vet.get("/api/vet/pending-initial-exams").data, [])

        horse = manager.get(f"/api/horses/{horse_id}").data
        self.assertTrue(horse["InitialExamSigned"])
        self.assertEqual(horse["CurrentHealthStatus"], "Healthy")

        # 5. Manager duyệt, cấp mã, xếp chuồng
        stalls = manager.get("/api/stalls?Status=Available").data
        self.assertEqual([s["StallNumber"] for s in stalls], ["A01"])
        res = manager.post(f"/api/horses/{horse_id}/approve",
                           {"HorseCode": "EQ-001", "StallID": self.stall.id, "ManagerNote": "OK"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["RegistrationStatus"], "Approved")
        self.assertEqual(res.data["HorseCode"], "EQ-001")
        self.assertEqual(res.data["CurrentStall"]["StallNumber"], "A01")
        self.assertEqual(Stall.objects.get(pk=self.stall.id).status, "Occupied")
        self.assertEqual(RegistrationRequest.objects.get(horse_id=horse_id).status, "Approved")

        # Owner chỉ thấy tóm tắt sức khỏe
        detail = owner.get(f"/api/horses/{horse_id}").data
        self.assertEqual(detail["HealthSummary"]["HealthStatus"], "Healthy")
        self.assertEqual(detail["HealthSummary"]["Conclusion"], "Đạt")
        self.assertEqual(owner.get(f"/api/horses/{horse_id}/medical-records").status_code, 403)

        # 6. Lưu trữ: trả chuồng
        res = manager.post(f"/api/horses/{horse_id}/archive", {"Reason": "Chủ ngựa chuyển CLB"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["RegistrationStatus"], "Archived")
        self.assertIsNone(res.data["CurrentStall"])
        self.assertEqual(Stall.objects.get(pk=self.stall.id).status, "Available")
        self.assertEqual(StallAssignment.objects.get(horse_id=horse_id).status, "Ended")

        # Audit log ghi đủ các bước
        actions = list(AuditLog.objects.filter(entity_name="Horse", entity_id=horse_id)
                       .values_list("action_type", flat=True))
        for expected in ("CREATE_HORSE", "SUBMIT_REGISTRATION", "VERIFY_REGISTRATION", "APPROVE_REGISTRATION",
                         "ARCHIVE_HORSE"):
            self.assertIn(expected, actions)
        self.assertEqual(manager.get(f"/api/horses/{horse_id}/audit-logs").status_code, 200)

    def test_manager_creates_on_behalf_of_owner(self):
        res = self.client_for(self.manager).post("/api/horses", self.horse_payload(OwnerID=self.owner.id),
                                                 format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["ClubID"], self.club.id)
        self.assertEqual(res.data["OwnerID"], self.owner.id)
        # Owner thấy ngựa Manager nhập hộ
        ids = [h["HorseID"] for h in self.client_for(self.owner).get("/api/horses").data]
        self.assertIn(res.data["HorseID"], ids)

    def test_manager_create_requires_owner(self):
        res = self.client_for(self.manager).post("/api/horses", self.horse_payload(), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("OwnerID", res.data)
        res = self.client_for(self.manager).post("/api/horses", self.horse_payload(OwnerID=self.vet.id),
                                                 format="json")
        self.assertEqual(res.status_code, 400)

    def test_owner_create_requires_active_club(self):
        owner = self.client_for(self.owner)
        self.assertEqual(owner.post("/api/horses", self.horse_payload(), format="json").status_code, 400)
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.inactive_club.id), format="json")
        self.assertEqual(res.status_code, 400)
        clubs = [c["ClubName"] for c in owner.get("/api/clubs").data]
        self.assertNotIn("Closed Club", clubs)


class SexClassTests(Flow1TestCase):
    def check(self, gender, dob, expected):
        horse = Horse(gender=gender, date_of_birth=dob)
        self.assertEqual(horse.sex_class, expected, (gender, dob))

    def test_sex_class(self):
        from datetime import date, timedelta

        today = date.today()
        self.check("Male", today - timedelta(days=100), "Foal")
        self.check("Female", today - timedelta(days=500), "Filly")
        self.check("Male", today - timedelta(days=800), "Colt")
        self.check("Male", date(today.year - 6, 1, 1), "Stallion")
        self.check("Female", date(today.year - 6, 1, 1), "Mare")
        self.check("Gelding", date(today.year - 6, 1, 1), "Gelding")
        self.check("Male", None, None)

    def test_sex_class_in_api(self):
        horse_id = self.owner_creates_horse(DateOfBirth=years_ago(6), Gender="Female")
        self.assertEqual(self.client_for(self.owner).get(f"/api/horses/{horse_id}").data["SexClass"], "Mare")


class RuleTests(Flow1TestCase):
    def test_all_profile_fields_required(self):
        owner = self.client_for(self.owner)
        for column in ("Breed", "DateOfBirth", "CoatColor", "Gender", "SireName", "DamName",
                       "MicrochipNumber", "PassportNumber"):
            for empty in (None, ""):
                res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, **{column: empty}),
                                 format="json")
                self.assertEqual(res.status_code, 400, (column, empty))
                self.assertIn(column, res.data)
        payload = self.horse_payload(ClubID=self.club.id)
        del payload["Breed"]
        res = owner.post("/api/horses", payload, format="json")
        self.assertEqual(res.data["Breed"], ["Cần nhập giống ngựa (Breed)."])
        horse_id = self.owner_creates_horse()
        res = owner.patch(f"/api/horses/{horse_id}", {"PassportNumber": None}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_microchip_and_passport_format(self):
        owner = self.client_for(self.owner)
        for bad in ("abc", "98500000000000", "9850000000000011", "98500000000000A"):
            res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, MicrochipNumber=bad,
                                                               PassportNumber="VN-777"), format="json")
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn("15 chữ số", res.data["MicrochipNumber"][0])
        for bad in ("abc", "VN 001", "VN_0001", "#12345"):
            res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, PassportNumber=bad),
                             format="json")
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn("PassportNumber", res.data)
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, MicrochipNumber="985 000 000 000 009",
                                                           PassportNumber="vn-tb-2021/9"), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["MicrochipNumber"], res.data["PassportNumber"]), ("985000000000009", "VN-TB-2021/9"))
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, MicrochipNumber="985000000000010",
                                                           PassportNumber="VN-TB-2021/9"), format="json")
        self.assertEqual(res.data["PassportNumber"], ["Số hộ chiếu / đăng ký đã được dùng cho một ngựa khác."])

    def test_pedigree_rules(self):
        owner = self.client_for(self.owner)
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, SireName="thunder"), format="json")
        self.assertIn("SireName", res.data)
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, DamName="Storm King"), format="json")
        self.assertIn("DamName", res.data)
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, DateOfBirth="1970-01-01"),
                         format="json")
        self.assertIn("DateOfBirth", res.data)

    def test_invalid_values(self):
        owner = self.client_for(self.owner)
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, Gender="Unknown"), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["Gender"], ["Giới tính phải là Male (đực), Female (cái) hoặc Gelding (đực đã thiến)."])
        res = owner.post("/api/horses", self.horse_payload(ClubID=self.club.id, DateOfBirth="2999-01-01"),
                         format="json")
        self.assertIn("DateOfBirth", res.data)

    def test_microchip_unique(self):
        self.owner_creates_horse()
        res = self.client_for(self.owner).post("/api/horses", self.horse_payload(ClubID=self.club.id),
                                               format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("MicrochipNumber", res.data)

    def test_cannot_edit_after_submit(self):
        horse_id = self.owner_creates_horse()
        self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        res = self.client_for(self.owner).patch(f"/api/horses/{horse_id}", {"HorseName": "X"}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "INVALID_STATUS")

    def test_approve_requires_signed_initial_exam(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-9"},
                                                 format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "INITIAL_EXAM_REQUIRED")

    def test_failed_exam_blocks_approval(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id, health="Injured", eligibility="Not Eligible")
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-9"},
                                                 format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "INITIAL_EXAM_FAILED")

    def test_reject_then_resubmit_needs_new_exam(self):
        owner, manager = self.client_for(self.owner), self.client_for(self.manager)
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id, health="Injured", eligibility="Not Eligible")
        self.assertTrue(manager.get(f"/api/horses/{horse_id}").data["InitialExamSigned"])

        res = manager.post(f"/api/horses/{horse_id}/reject", {"Reason": "Ngựa đang chấn thương"}, format="json")
        self.assertEqual(res.data["RegistrationStatus"], "Rejected")
        self.assertFalse(res.data["InitialExamSigned"])      # phiếu cũ thuộc lần nộp đã bị từ chối
        requests = owner.get(f"/api/horses/{horse_id}/registration-requests").data
        self.assertEqual(requests[0]["ManagerNote"], "Ngựa đang chấn thương")

        owner.patch(f"/api/horses/{horse_id}", {"Breed": "Arabian"}, format="json")
        self.submit_and_verify(horse_id)
        self.assertEqual(RegistrationRequest.objects.filter(horse_id=horse_id).count(), 2)
        self.assertFalse(manager.get(f"/api/horses/{horse_id}").data["InitialExamSigned"])
        self.vet_signs_initial_exam(horse_id)                 # lần nộp mới được khám lại
        res = manager.post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-002"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)

    def test_horse_code_unique_in_club(self):
        self.approved_horse()
        horse_id = self.owner_creates_horse(MicrochipNumber="985000000000002")
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "eq-001"},
                                                 format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "DUPLICATE_HORSE_CODE")

    def test_stall_must_be_available_and_in_club(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        manager = self.client_for(self.manager)
        res = manager.post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-1", "StallID": self.other_stall.id},
                           format="json")
        self.assertEqual(res.data["code"], "STALL_NOT_FOUND")
        Stall.objects.filter(pk=self.stall.id).update(status="Maintenance")
        res = manager.post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-1", "StallID": self.stall.id},
                           format="json")
        self.assertEqual(res.data["code"], "STALL_NOT_AVAILABLE")

    def test_wrong_order_actions(self):
        horse_id = self.owner_creates_horse()
        manager = self.client_for(self.manager)
        self.assertEqual(manager.post(f"/api/horses/{horse_id}/verify").status_code, 409)
        self.assertEqual(manager.post(f"/api/horses/{horse_id}/archive", {"Reason": "x"}, format="json").status_code,
                         409)
        res = self.client_for(self.vet).post(f"/api/horses/{horse_id}/medical-records",
                                             {"ExamType": "Initial Exam"}, format="json")
        self.assertEqual(res.status_code, 409)

    def test_reject_needs_reason(self):
        horse_id = self.owner_creates_horse()
        self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/reject", {}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Reason", res.data)


class PermissionTests(Flow1TestCase):
    def test_role_limits(self):
        horse_id = self.owner_creates_horse()
        owner, vet, trainer = (self.client_for(u) for u in (self.owner, self.vet, self.trainer))
        self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        self.assertEqual(owner.post(f"/api/horses/{horse_id}/verify").status_code, 403)
        self.assertEqual(vet.post(f"/api/horses/{horse_id}/verify").status_code, 403)
        self.assertEqual(trainer.post("/api/horses", self.horse_payload(), format="json").status_code, 403)
        self.assertEqual(owner.get("/api/vet/pending-initial-exams").status_code, 403)
        self.assertEqual(trainer.get(f"/api/horses/{horse_id}").status_code, 200)   # nhân sự CLB xem được

    def test_owner_sees_only_own_horses(self):
        horse_id = self.owner_creates_horse()
        other = self.client_for(self.other_owner)
        self.assertEqual(other.get("/api/horses").data, [])
        self.assertEqual(other.get(f"/api/horses/{horse_id}").status_code, 404)
        self.assertEqual(other.patch(f"/api/horses/{horse_id}", {"HorseName": "X"}, format="json").status_code, 404)

    def test_other_club_is_isolated(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        other_manager, other_vet = self.client_for(self.other_manager), self.client_for(self.other_vet)
        self.assertEqual(other_manager.get("/api/horses").data, [])
        self.assertEqual(other_manager.post(f"/api/horses/{horse_id}/reject", {"Reason": "x"},
                                            format="json").status_code, 404)
        self.assertEqual(other_vet.get("/api/vet/pending-initial-exams").data, [])
        res = other_vet.post(f"/api/horses/{horse_id}/medical-records", {"ExamType": "Initial Exam"}, format="json")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self.client_for(self.manager).get("/api/horses?RegistrationStatus=PendingExam").data[0]
                         ["HorseID"], horse_id)

    def test_filters(self):
        horse_id = self.owner_creates_horse()
        manager = self.client_for(self.manager)
        self.assertEqual(len(manager.get("/api/horses?search=thund").data), 1)
        self.assertEqual(manager.get("/api/horses?RegistrationStatus=Approved").data, [])
        self.assertEqual(manager.get(f"/api/horses?OwnerID={self.owner.id}").data[0]["HorseID"], horse_id)


class DocumentTests(Flow1TestCase):
    def test_documents(self):
        horse_id = self.owner_creates_horse()
        owner, manager = self.client_for(self.owner), self.client_for(self.manager)
        res = owner.post(f"/api/horses/{horse_id}/documents", {
            "DocumentName": "Hộ chiếu", "DocumentType": "Passport", "FileUrl": "https://files.example/p.pdf",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["IsVisibleToOwner"])

        res = manager.post(f"/api/horses/{horse_id}/documents", {
            "DocumentName": "Ghi chú nội bộ", "DocumentType": "Other", "FileUrl": "https://files.example/n.pdf",
            "IsVisibleToOwner": False,
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(len(manager.get(f"/api/horses/{horse_id}/documents").data), 2)
        self.assertEqual(len(owner.get(f"/api/horses/{horse_id}/documents").data), 1)


class StallTests(Flow1TestCase):
    def test_stall_management_and_move(self):
        manager = self.client_for(self.manager)
        res = manager.post("/api/stalls", {"StallNumber": "A02", "StallType": "Standard"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        a02 = res.data["StallID"]
        self.assertEqual(manager.post("/api/stalls", {"StallNumber": "a02"}, format="json").data["code"],
                         "DUPLICATE_STALL")
        self.assertEqual(manager.patch(f"/api/stalls/{a02}", {"Status": "Occupied"}, format="json").status_code, 400)

        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        manager.post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-1", "StallID": self.stall.id},
                     format="json")
        self.assertEqual(manager.patch(f"/api/stalls/{self.stall.id}", {"Status": "Maintenance"}, format="json")
                         .data["code"], "STALL_OCCUPIED")
        res = manager.post(f"/api/horses/{horse_id}/move-stall", {"StallID": a02}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["CurrentStall"]["StallNumber"], "A02")
        stalls = {s["StallNumber"]: s for s in manager.get("/api/stalls").data}
        self.assertEqual(stalls["A01"]["Status"], "Available")
        self.assertEqual(stalls["A02"]["CurrentHorse"]["HorseID"], horse_id)
        self.assertEqual(self.client_for(self.vet).post("/api/stalls", {"StallNumber": "X"}, format="json")
                         .status_code, 403)
