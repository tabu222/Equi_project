import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from apps.horses import documents as store
from apps.horses.models import Horse, HorseDocument, ProfileChangeRequest
from apps.horses.change_requests import COLUMNS
from .helpers import Flow1TestCase

PDF = b"%PDF-1.4\nproposal test\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


class ProfileProposalTests(Flow1TestCase):
    def setUp(self):
        self.horse = Horse.objects.create(
            club=self.club, owner=self.owner, registration_status="Approved",
            **{COLUMNS[k]: v for k, v in self.horse_payload().items()})
        self.owner_api = self.client_for(self.owner)
        self.manager_api = self.client_for(self.manager)
        self.url = f"/api/horses/{self.horse.id}/profile-change-requests"

    def document(self, name="current.pdf", user=None, visible=True, **extra):
        data = PNG if name.endswith(".png") else PDF
        return HorseDocument.objects.create(
            horse=self.horse, uploaded_by=user or self.owner,
            document_name=name, document_type="Other", is_visible_to_owner=visible,
            is_profile_image=name.endswith(".png"),
            file_url=store.save_upload(self.horse.id, SimpleUploadedFile(name, data)), **extra)

    def propose(self, changes=None, attachments=None, **extra):
        payload = {"Reason": "Đính chính theo giấy tờ", "Changes": changes or {}, **extra}
        if attachments is None:
            return self.owner_api.post(self.url, payload, format="json")
        files, metadata = {}, []
        for index, item in enumerate(attachments):
            item = dict(item)
            name = item.pop("name", "proposal.pdf")
            content = item.pop("content", PNG if name.endswith(".png") else PDF)
            key = f"file{index}"
            files[key] = SimpleUploadedFile(name, content)
            metadata.append({"FileKey": key, "DocumentName": name, "DocumentType": "Other", **item})
        return self.owner_api.post(self.url, {"Payload": json.dumps({**payload, "Attachments": metadata}), **files}, format="multipart")

    def approve(self, response):
        self.assertEqual(response.status_code, 201, response.data)
        return self.manager_api.post(f"/api/profile-change-requests/{response.data['ProfileChangeRequestID']}/approve", {}, format="json")

    def test_multiple_fields_normalized_and_unchanged_values_omitted(self):
        response = self.propose({"HorseName": "  Thunder II  ", "CoatColor": "Grey", "Breed": " Thoroughbred "})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual([i["Field"] for i in response.data["ChangedFields"]["Changes"]], ["HorseName", "CoatColor"])
        self.horse.refresh_from_db()
        self.assertEqual(self.horse.horse_name, "Thunder")
        self.assertEqual(self.approve(response).status_code, 200)
        self.horse.refresh_from_db()
        self.assertEqual((self.horse.horse_name, self.horse.coat_color), ("Thunder II", "Grey"))

    def test_unchanged_empty_and_protected_values_rejected(self):
        for changes, expected in [({"Breed": " Thoroughbred "}, 409), ({}, 409),
                                  ({"HorseName": ""}, 400), ({"CoatColor": None}, 400),
                                  ({"CurrentHealthStatus": "Healthy"}, 409),
                                  ({"OwnerID": str(self.other_owner.pk)}, 409),
                                  ({"DateOfBirth": "2999-01-01"}, 400)]:
            with self.subTest(changes=changes):
                self.assertEqual(self.propose(changes).status_code, expected)
        self.assertEqual(self.propose(attachments=[{"Purpose": "evidence"}]).status_code, 409)

    def test_avatar_only_staged_and_private_until_approval(self):
        old = self.document("current.png", is_primary=True)
        response = self.propose(attachments=[{"Purpose": "avatar", "name": "new.png"}])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(HorseDocument.objects.count(), 1)
        public = response.data["ChangedFields"]
        self.assertNotIn("Snapshot", public)
        self.assertNotIn("StoredFile", public["Attachments"][0])
        file_url = public["Attachments"][0]["FileUrl"]
        for client in (self.owner_api, self.manager_api):
            downloaded = client.get(file_url)
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(b"".join(downloaded.streaming_content), PNG)
            self.assertEqual(downloaded["Cache-Control"], "private, no-store")
        for client in (self.client_for(self.other_owner), self.client_for(self.other_manager)):
            self.assertEqual(client.get(file_url).status_code, 404)
        self.assertEqual(self.client_for(self.vet).get(file_url).status_code, 403)
        self.assertEqual(APIClient().get(file_url).status_code, 401)
        self.assertEqual(self.approve(response).status_code, 200)
        old.refresh_from_db()
        self.assertFalse(old.is_primary)
        self.assertEqual(HorseDocument.objects.get(is_primary=True).document_name, "new.png")
        self.assertTrue(store.stored_path(old.file_url).is_file())

    def test_add_documents_only_and_multiple_files(self):
        response = self.propose(attachments=[{"Purpose": "add"}, {"Purpose": "add", "name": "second.pdf"}])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(HorseDocument.objects.count(), 0)
        self.assertEqual(self.approve(response).status_code, 200)
        self.assertEqual(HorseDocument.objects.count(), 2)

    def test_replace_keeps_previous_file_and_version_relationship(self):
        old = self.document()
        response = self.propose(attachments=[{"Purpose": "replace", "ReplacesDocumentID": old.id, "Note": "Sửa ngày đăng ký"}])
        old.refresh_from_db()
        self.assertFalse(old.is_retired)
        self.assertEqual(self.approve(response).status_code, 200)
        old.refresh_from_db()
        self.assertTrue(old.is_retired)
        new = HorseDocument.objects.get(replaces_document=old)
        self.assertNotEqual(new.file_url, old.file_url)
        self.assertTrue(store.stored_path(old.file_url).is_file())
        self.assertEqual(self.owner_api.get(f"/api/horses/{self.horse.id}/documents").data[0]["DocumentID"], new.id)
        download = self.owner_api.get(f"/api/horse-documents/{old.id}/file")
        self.assertEqual(download.status_code, 200)
        download.close()
        self.assertEqual(self.manager_api.delete(f"/api/horse-documents/{old.id}").status_code, 409)
        self.assertEqual(self.manager_api.delete(f"/api/horse-documents/{new.id}").status_code, 409)

    def test_combined_proposal_applies_all_types_and_evidence_stays_private(self):
        old_avatar = self.document("old.png", is_primary=True)
        doc = self.document()
        proof = self.document("proof.pdf")
        response = self.propose({"CoatColor": "Grey"}, [
            {"Purpose": "avatar", "name": "avatar.png"}, {"Purpose": "image", "name": "gallery.png"},
            {"Purpose": "replace", "ReplacesDocumentID": doc.id}, {"Purpose": "add", "name": "extra.pdf"},
            {"Purpose": "evidence", "name": "proof-new.pdf"},
        ], RemoveImageIDs=[old_avatar.id], EvidenceDocumentIDs=[proof.id])
        self.assertEqual(self.approve(response).status_code, 200)
        self.horse.refresh_from_db(); old_avatar.refresh_from_db()
        self.assertEqual(self.horse.coat_color, "Grey")
        self.assertTrue(old_avatar.is_retired)
        self.assertFalse(HorseDocument.objects.filter(document_name="proof-new.pdf").exists())
        self.assertEqual(HorseDocument.objects.filter(is_retired=False).count(), 5)

    def test_existing_avatar_and_removal_rules(self):
        first = self.document("first.png", is_primary=True)
        second = self.document("second.png")
        self.assertEqual(self.propose(RemoveImageIDs=[first.id]).status_code, 400)
        self.assertEqual(self.propose(AvatarDocumentID=second.id, RemoveImageIDs=[second.id]).status_code, 400)
        response = self.propose(AvatarDocumentID=second.id, RemoveImageIDs=[first.id])
        self.assertEqual(self.approve(response).status_code, 200)
        second.refresh_from_db()
        self.assertTrue(second.is_primary)

    def test_add_gallery_images_preserves_current_avatar(self):
        old = self.document("old.png")  # legacy avatar: no explicit primary flag
        response = self.propose(attachments=[{"Purpose": "image", "name": "gallery.png"}])
        self.assertEqual(self.approve(response).status_code, 200)
        old.refresh_from_db()
        self.assertTrue(old.is_primary)

    def test_document_scan_is_not_a_profile_image_and_can_be_replaced(self):
        response = self.propose(attachments=[{"Purpose": "add", "name": "scan.png", "DocumentType": "Passport"}])
        self.assertEqual(self.approve(response).status_code, 200)
        scan = HorseDocument.objects.get(document_name="scan.png")
        self.assertFalse(scan.is_profile_image)
        response = self.propose(attachments=[{"Purpose": "replace", "ReplacesDocumentID": scan.id,
                                              "name": "scan-fixed.png"}])
        self.assertEqual(self.approve(response).status_code, 200)
        scan.refresh_from_db()
        self.assertTrue(scan.is_retired)

    def test_hidden_foreign_and_staff_documents_cannot_be_replaced(self):
        hidden = self.document(visible=False)
        staff = self.document(user=self.manager)
        protected = self.document()
        protected.document_type = "Contract"; protected.save()
        for doc, status in [(hidden, 400), (staff, 403), (protected, 403)]:
            self.assertEqual(self.propose(attachments=[{"Purpose": "replace", "ReplacesDocumentID": doc.id}]).status_code, status)
        self.assertEqual(self.propose({"Breed": "Arabian"}, EvidenceDocumentIDs=[hidden.id]).status_code, 400)
        self.assertEqual(self.propose({"Breed": "Arabian"}, EvidenceDocumentIDs=[999999]).status_code, 400)

    def test_owner_and_club_boundaries_and_request_immutability(self):
        self.assertEqual(self.client_for(self.other_owner).post(self.url, {"Changes": {"Breed": "X"}, "Reason": "test"}, format="json").status_code, 404)
        response = self.propose({"Breed": "Arabian"})
        change_url = f"/api/profile-change-requests/{response.data['ProfileChangeRequestID']}"
        self.assertEqual(self.client_for(self.other_owner).get(change_url).status_code, 404)
        self.assertEqual(self.client_for(self.other_manager).post(change_url + "/approve").status_code, 404)
        self.assertEqual(self.owner_api.post(change_url + "/approve").status_code, 403)
        self.assertEqual(self.owner_api.patch(change_url, {}, format="json").status_code, 405)

    def test_duplicate_returns_existing_request_id(self):
        first = self.propose({"Breed": "Arabian"})
        duplicate = self.propose({"CoatColor": "Grey"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(int(duplicate.data["RequestID"]), first.data["ProfileChangeRequestID"])
        self.assertEqual(duplicate.data["code"], "PENDING_REQUEST_EXISTS")

    def test_stale_profile_or_documents_rejected_before_any_apply(self):
        response = self.propose({"Breed": "Arabian"}, [{"Purpose": "add"}])
        Horse.objects.filter(pk=self.horse.id).update(coat_color="White")
        result = self.approve(response)
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.data["code"], "STALE_PROFILE")
        self.assertFalse(HorseDocument.objects.exists())
        self.horse.refresh_from_db()
        self.assertEqual(self.horse.breed, "Thoroughbred")
        Horse.objects.filter(pk=self.horse.id).update(coat_color="Bay")
        self.document()
        self.assertEqual(self.approve(response).data["code"], "STALE_PROFILE")

    def test_rejection_requires_reason_and_never_applies_files_or_fields(self):
        response = self.propose({"CoatColor": "Grey"}, [{"Purpose": "avatar", "name": "new.png"}])
        change_url = f"/api/profile-change-requests/{response.data['ProfileChangeRequestID']}"
        self.assertEqual(self.manager_api.post(change_url + "/reject", {"ReviewNote": " "}, format="json").status_code, 409)
        result = self.manager_api.post(change_url + "/reject", {"ReviewNote": "Cần thêm giấy tờ"}, format="json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["ReviewedBy"], self.manager.id)
        self.assertEqual(result.data["ReviewedByName"], self.manager.full_name)
        self.horse.refresh_from_db()
        self.assertEqual(self.horse.coat_color, "Bay")
        self.assertFalse(HorseDocument.objects.exists())
        self.assertEqual(self.approve(response).status_code, 409)

    def test_no_double_approval(self):
        response = self.propose(attachments=[{"Purpose": "add"}])
        self.assertEqual(self.approve(response).status_code, 200)
        self.assertEqual(self.approve(response).status_code, 409)
        self.assertEqual(HorseDocument.objects.count(), 1)

    def test_owner_can_withdraw_pending_then_create_new_request(self):
        response = self.propose({"CoatColor": "Grey"}, [{"Purpose": "add"}])
        change_url = f"/api/profile-change-requests/{response.data['ProfileChangeRequestID']}"
        self.assertEqual(self.client_for(self.other_owner).post(change_url + "/withdraw").status_code, 404)
        result = self.owner_api.post(change_url + "/withdraw")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["Status"], "Withdrawn")
        self.assertEqual(result.data["ReviewedBy"], self.owner.id)
        self.assertEqual(self.owner_api.post(change_url + "/withdraw").status_code, 409)
        self.assertEqual(self.approve(response).status_code, 409)
        self.assertFalse(HorseDocument.objects.exists())
        self.horse.refresh_from_db()
        self.assertEqual(self.horse.coat_color, "Bay")
        self.assertEqual(self.propose({"Breed": "Arabian"}).status_code, 201)

    def test_cannot_withdraw_an_approved_request(self):
        response = self.propose({"Breed": "Arabian"})
        self.assertEqual(self.approve(response).status_code, 200)
        self.assertEqual(self.owner_api.post(f"/api/profile-change-requests/{response.data['ProfileChangeRequestID']}/withdraw").status_code, 409)

    def test_disk_failure_during_upload_keeps_no_partial_file(self):
        root = store.media_root() / "horse-documents" / str(self.horse.id)
        before = set(root.glob("*"))
        with patch("django.core.files.uploadedfile.InMemoryUploadedFile.chunks", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.propose(attachments=[{"Purpose": "add"}])
        self.assertEqual(set(root.glob("*")), before)
        self.assertFalse(ProfileChangeRequest.objects.exists())

    def test_bad_file_size_type_signature_count_and_metadata(self):
        for name, content in [("virus.exe", b"MZ"), ("a.svg", b"<svg>"), ("fake.png", b"<html>"), ("empty.pdf", b"")]:
            response = self.propose(attachments=[{"Purpose": "add", "name": name, "content": content}])
            self.assertEqual(response.status_code, 400, response.data)
        with override_settings(UPLOAD_MAX_MB=0):
            self.assertEqual(self.propose(attachments=[{"Purpose": "add"}]).status_code, 400)
        with override_settings(CHANGE_REQUEST_MAX_FILES=1):
            self.assertEqual(self.propose(attachments=[{"Purpose": "add"}, {"Purpose": "add"}]).status_code, 400)
        self.assertEqual(self.propose(attachments=[{"Purpose": "avatar"}]).status_code, 400)  # PDF cannot be an avatar
        self.assertEqual(self.propose(attachments=[{"Purpose": "replace"}]).status_code, 400)
        result = self.owner_api.post(self.url, {"Payload": "bad-json"}, format="multipart")
        self.assertEqual(result.status_code, 400)
        self.assertFalse(ProfileChangeRequest.objects.exists())

    def test_failed_creation_cleans_files_and_rolls_back_request(self):
        root = store.media_root() / "horse-documents" / str(self.horse.id)
        before = set(root.glob("*"))
        with patch("apps.horses.change_requests.log_action", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.propose(attachments=[{"Purpose": "add"}])
        self.assertFalse(ProfileChangeRequest.objects.exists())
        self.assertEqual(set(root.glob("*")), before)

    def test_failed_approval_rolls_back_entire_change(self):
        response = self.propose({"CoatColor": "Grey"}, [{"Purpose": "add"}, {"Purpose": "add", "name": "second.pdf"}])
        actual_create = HorseDocument.objects.create
        calls = []

        def fail_second(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise RuntimeError("database unavailable")
            return actual_create(**kwargs)

        with patch("apps.horses.change_requests.HorseDocument.objects.create", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.approve(response)
        self.horse.refresh_from_db()
        self.assertEqual(self.horse.coat_color, "Bay")
        self.assertFalse(HorseDocument.objects.exists())
        self.assertEqual(ProfileChangeRequest.objects.get().status, "Pending")

    def test_legacy_request_without_snapshot_can_still_be_approved(self):
        request = ProfileChangeRequest.objects.create(horse=self.horse, requested_by=self.owner, changed_fields=json.dumps({
            "Reason": "Legacy", "Changes": [{"Field": "CoatColor", "OldValue": "Bay", "NewValue": "Grey"}]}))
        self.assertEqual(self.manager_api.post(f"/api/profile-change-requests/{request.id}/approve").status_code, 200)

    def test_approved_owner_upload_cannot_bypass_review_but_draft_keeps_flow(self):
        url = f"/api/horses/{self.horse.id}/documents"
        self.assertEqual(self.owner_api.post(url, {"File": SimpleUploadedFile("proof.pdf", PDF), "DocumentType": "Other"}, format="multipart").status_code, 409)
        self.horse.registration_status = "Draft"; self.horse.save()
        self.assertEqual(self.owner_api.post(url, {"File": SimpleUploadedFile("proof.pdf", PDF), "DocumentType": "Other"}, format="multipart").status_code, 201)
