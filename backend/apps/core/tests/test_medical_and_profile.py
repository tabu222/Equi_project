import re
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.apps import apps
from django.test import SimpleTestCase

from apps.core import flows
from apps.accounts.rbac import PERMISSIONS, ROLE_PERMISSIONS, ROLES
from apps.horses.models import Horse

from .helpers import Flow1TestCase


class MedicalRecordTests(Flow1TestCase):
    def pending_horse(self):
        horse_id = self.owner_creates_horse()
        self.submit_and_verify(horse_id)
        return horse_id

    def test_one_initial_exam_per_request(self):
        horse_id = self.pending_horse()
        vet = self.client_for(self.vet)
        self.assertEqual(vet.post(f"/api/horses/{horse_id}/medical-records", {"ExamType": "Initial Exam"},
                                  format="json").status_code, 201)
        res = self.client_for(self.vet2).post(f"/api/horses/{horse_id}/medical-records",
                                              {"ExamType": "Initial Exam"}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "INITIAL_EXAM_EXISTS")

    def test_only_creator_edits_draft_and_signed_is_locked(self):
        horse_id = self.pending_horse()
        record_id = self.vet_signs_initial_exam(horse_id)
        vet = self.client_for(self.vet)
        res = vet.patch(f"/api/medical-records/{record_id}", {"Diagnosis": "Sửa"}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "RECORD_SIGNED")
        self.assertEqual(vet.delete(f"/api/medical-records/{record_id}").status_code, 409)

        res = vet.post(f"/api/medical-records/{record_id}/amendments",
                       {"Reason": "Ghi nhầm cân nặng", "AmendedContent": "WeightKg đúng là 478.0"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        amendments = self.client_for(self.manager).get(f"/api/medical-records/{record_id}/amendments").data
        self.assertEqual(amendments[0]["Reason"], "Ghi nhầm cân nặng")
        self.assertEqual(amendments[0]["AmendedBy"], self.vet.id)

    def test_other_vet_cannot_touch_draft(self):
        horse_id = self.pending_horse()
        res = self.client_for(self.vet).post(f"/api/horses/{horse_id}/medical-records",
                                             {"ExamType": "Initial Exam"}, format="json")
        record_id = res.data["MedicalRecordID"]
        other = self.client_for(self.vet2)
        res = other.patch(f"/api/medical-records/{record_id}", {"Diagnosis": "x"}, format="json")
        self.assertEqual(res.data["code"], "NOT_RECORD_OWNER")
        self.assertEqual(other.post(f"/api/medical-records/{record_id}/sign").status_code, 409)

    def test_old_draft_cannot_be_signed_after_rejection_and_resubmission(self):
        horse_id = self.pending_horse()
        vet = self.client_for(self.vet)
        draft = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Initial Exam", "HealthStatus": "Healthy", "TrainingEligibility": "Eligible",
        }, format="json")
        self.assertEqual(draft.status_code, 201, draft.data)
        self.client_for(self.manager).post(f"/api/horses/{horse_id}/reject", {"Reason": "Missing documents"}, format="json")
        self.submit_and_verify(horse_id)
        response = vet.post(f"/api/medical-records/{draft.data['MedicalRecordID']}/sign")
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["code"], "INVALID_STATUS")
        self.assertEqual(vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Initial Exam",
        }, format="json").status_code, 201)

    def test_drafts_hidden_from_non_vets(self):
        horse_id = self.pending_horse()
        res = self.client_for(self.vet).post(f"/api/horses/{horse_id}/medical-records",
                                             {"ExamType": "Initial Exam"}, format="json")
        record_id = res.data["MedicalRecordID"]
        trainer = self.client_for(self.trainer)
        self.assertEqual(trainer.get(f"/api/horses/{horse_id}/medical-records").data, [])
        self.assertEqual(trainer.get(f"/api/medical-records/{record_id}").status_code, 404)
        self.assertEqual(trainer.post(f"/api/horses/{horse_id}/medical-records", {"ExamType": "Initial Exam"},
                                      format="json").status_code, 403)

    def test_restricted_needs_note_and_draft_can_be_deleted(self):
        horse_id = self.pending_horse()
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/medical-records", {
            "ExamType": "Initial Exam", "HealthStatus": "Monitor", "TrainingEligibility": "Restricted",
        }, format="json")
        self.assertEqual(res.status_code, 400)                 # giống CHECK CK_MedicalRecord_Restriction
        self.assertIn("RestrictionNote", res.data)
        res = vet.post(f"/api/horses/{horse_id}/medical-records", {"ExamType": "Initial Exam"}, format="json")
        record_id = res.data["MedicalRecordID"]
        res = vet.patch(f"/api/medical-records/{record_id}", {"TrainingEligibility": "Restricted"}, format="json")
        self.assertIn("RestrictionNote", res.data)
        self.assertEqual(vet.delete(f"/api/medical-records/{record_id}").status_code, 204)

    def test_validation(self):
        horse_id = self.pending_horse()
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/medical-records",
                       {"ExamType": "Initial Exam", "WeightKg": -1, "HealthStatus": "Great"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("WeightKg", res.data)
        self.assertIn("HealthStatus", res.data)

    def test_exams_after_intake(self):
        """Chỉ có Flow 1: chỉ khám đầu vào. Có Flow 3: ngựa đã tiếp nhận được khám định kỳ / chấn thương."""
        horse_id = self.pending_horse()
        vet = self.client_for(self.vet)
        res = vet.post(f"/api/horses/{horse_id}/medical-records", {"ExamType": "Routine Exam"}, format="json")
        self.assertEqual(res.status_code, 409)

        approved_id = self.approved_horse_with_new_chip()
        res = vet.post(f"/api/horses/{approved_id}/medical-records", {
            "ExamType": "Injury Exam", "HealthStatus": "Injured", "TrainingEligibility": "Not Eligible",
            "InjuryLocation": "Chân trước trái",
        }, format="json")
        if not flows.has_flow3():
            self.assertEqual(res.status_code, 409, res.data)
            self.assertEqual(res.data["code"], "EXAM_TYPE_UNAVAILABLE")
            self.assertEqual(Horse.objects.get(pk=approved_id).current_health_status, "Healthy")
            return
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data["RegistrationRequestID"])
        body = vet.post(f"/api/medical-records/{res.data['MedicalRecordID']}/sign").data
        self.assertEqual(Horse.objects.get(pk=approved_id).current_health_status, "Injured")
        self.assertEqual(body["TrainingLock"]["LockLevel"], "Full")       # Not Eligible -> tự khóa tập

    def approved_horse_with_new_chip(self):
        horse_id = self.owner_creates_horse(MicrochipNumber="985000000000777", HorseName="Breeze")
        self.submit_and_verify(horse_id)
        self.vet_signs_initial_exam(horse_id)
        self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-777"},
                                           format="json")
        return horse_id


class ProfileChangeTests(Flow1TestCase):
    def test_request_and_approve(self):
        horse_id = self.approved_horse()
        owner, manager = self.client_for(self.owner), self.client_for(self.manager)
        res = owner.patch(f"/api/horses/{horse_id}", {"CoatColor": "Grey"}, format="json")
        self.assertEqual(res.status_code, 409)               # đã Approved thì phải gửi yêu cầu

        res = owner.post(f"/api/horses/{horse_id}/profile-change-requests",
                         {"Changes": {"CoatColor": "Grey"}, "Reason": "Lông đổi màu theo tuổi"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        change_id = res.data["ProfileChangeRequestID"]
        self.assertEqual(res.data["ChangedFields"]["Changes"][0],
                         {"Field": "CoatColor", "OldValue": "Bay", "NewValue": "Grey"})

        res = owner.post(f"/api/horses/{horse_id}/profile-change-requests",
                         {"Changes": {"Breed": "X"}, "Reason": "y"}, format="json")
        self.assertEqual(res.data["code"], "PENDING_REQUEST_EXISTS")

        pending = manager.get("/api/profile-change-requests?Status=Pending").data
        self.assertEqual([p["ProfileChangeRequestID"] for p in pending], [change_id])
        self.assertEqual(owner.post(f"/api/profile-change-requests/{change_id}/approve").status_code, 403)

        res = manager.post(f"/api/profile-change-requests/{change_id}/approve", {}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["Status"], "Approved")
        self.assertEqual(owner.get(f"/api/horses/{horse_id}").data["CoatColor"], "Grey")

    def test_forbidden_fields_and_reject(self):
        horse_id = self.approved_horse()
        owner, manager = self.client_for(self.owner), self.client_for(self.manager)
        res = owner.post(f"/api/horses/{horse_id}/profile-change-requests",
                         {"Changes": {"HorseCode": "HACK"}, "Reason": "x"}, format="json")
        self.assertEqual(res.data["code"], "FIELD_NOT_EDITABLE")

        res = owner.post(f"/api/horses/{horse_id}/profile-change-requests",
                         {"Changes": {"SireName": "Other"}, "Reason": "x"}, format="json")
        change_id = res.data["ProfileChangeRequestID"]
        res = manager.post(f"/api/profile-change-requests/{change_id}/reject", {}, format="json")
        self.assertEqual(res.data["code"], "REVIEW_NOTE_REQUIRED")
        res = manager.post(f"/api/profile-change-requests/{change_id}/reject", {"ReviewNote": "Thiếu giấy tờ"},
                           format="json")
        self.assertEqual(res.data["Status"], "Rejected")
        self.assertEqual(owner.get(f"/api/horses/{horse_id}").data["SireName"], "Storm King")

    def test_other_club_manager_cannot_see(self):
        horse_id = self.approved_horse()
        self.client_for(self.owner).post(f"/api/horses/{horse_id}/profile-change-requests",
                                         {"Changes": {"Breed": "Arabian"}, "Reason": "x"}, format="json")
        self.assertEqual(self.client_for(self.other_manager).get("/api/profile-change-requests").data, [])


class RbacMatchesSqlTests(SimpleTestCase):
    """apps/accounts/rbac.py phải giống hệt phần SEED DATA trong sql/horse_v2.sql."""

    def test_rbac_matches_sql(self):
        sql = Path(settings.SQL_SCRIPT).read_text(encoding="utf-8")
        roles_block = sql.split("INSERT INTO dbo.Role ")[1].split("GO")[0]
        perms_block = sql.split("INSERT INTO dbo.Permission ")[1].split("GO")[0]
        mapping_block = sql.split("INSERT INTO dbo.RolePermission ")[1].split("GO")[0]

        sql_roles = re.findall(r"\('([A-Z_]+)',\s*N'", roles_block)
        sql_perms = re.findall(r"\('([A-Z_]+)',\s*N'", perms_block)
        sql_mapping = {}
        for role, perm in re.findall(r"\('([A-Z_]+)',\s*'([A-Z_]+)'\)", mapping_block):
            sql_mapping.setdefault(role, set()).add(perm)

        self.assertEqual(sql_roles, list(ROLES))
        self.assertEqual(sql_perms, PERMISSIONS)
        self.assertEqual(sql_mapping, {role: set(codes) for role, codes in ROLE_PERMISSIONS.items()})


@skipUnless(apps.is_installed("apps.training"), "Flow 2 training is not included in this checkout")
class SpecializationSeedMatchesSqlTests(SimpleTestCase):
    def test_specializations_match_sql(self):
        from apps.training.seed import SPECIALIZATIONS

        sql = Path(settings.SQL_SCRIPT).read_text(encoding="utf-8")
        block = sql.split("INSERT INTO dbo.Specialization ")[1].split("GO")[0]
        self.assertEqual(dict(re.findall(r"\('([A-Z_]+)',\s*N'([^']+)'", block)), SPECIALIZATIONS)
