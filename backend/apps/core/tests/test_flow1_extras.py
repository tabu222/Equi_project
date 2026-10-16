"""Flow 1 bổ sung: tải file giấy tờ, email thông báo, đăng nhập Google."""
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.horses.models import HorseDocument

from .helpers import Flow1TestCase

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def upload(name, content, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class DocumentUploadTests(Flow1TestCase):
    def test_owner_uploads_views_and_deletes_file(self):
        horse_id = self.owner_creates_horse()
        owner = self.client_for(self.owner)
        res = owner.post(f"/api/horses/{horse_id}/documents",
                         {"File": upload("ho-chieu.pdf", PDF), "DocumentType": "Passport"}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["IsUploadedFile"])
        self.assertEqual(res.data["DocumentName"], "ho-chieu.pdf")
        self.assertEqual(res.data["FileUrl"], f"/api/horse-documents/{res.data['DocumentID']}/file")
        doc_id = res.data["DocumentID"]

        # ảnh ngựa, đặt tên riêng
        res = owner.post(f"/api/horses/{horse_id}/documents", {
            "File": upload("IMG_001.png", PNG, "image/png"), "DocumentType": "Other", "DocumentName": "Ảnh ngựa",
        }, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["ContentType"], "image/png")

        # Owner và Manager CLB đều tải được file; người ngoài thì không
        for client in (owner, self.client_for(self.manager)):
            res = client.get(f"/api/horse-documents/{doc_id}/file")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(b"".join(res.streaming_content), PDF)
            self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertEqual(self.client_for(self.other_owner).get(f"/api/horse-documents/{doc_id}/file").status_code, 404)
        self.assertEqual(self.client_for(self.other_manager).get(f"/api/horse-documents/{doc_id}/file").status_code,
                         404)
        self.assertEqual(APIClient().get(f"/api/horse-documents/{doc_id}/file").status_code, 401)

        # xóa khi còn nháp: file trên ổ đĩa cũng bị xóa
        from apps.horses.documents import stored_path
        path = stored_path(HorseDocument.objects.get(pk=doc_id).file_url)
        self.assertTrue(path.exists())
        self.assertEqual(owner.delete(f"/api/horse-documents/{doc_id}").status_code, 204)
        self.assertFalse(path.exists())
        self.assertFalse(HorseDocument.objects.filter(pk=doc_id).exists())

    def test_owner_cannot_delete_after_submit_but_manager_can(self):
        horse_id = self.owner_creates_horse()
        owner = self.client_for(self.owner)
        doc_id = owner.post(f"/api/horses/{horse_id}/documents",
                            {"File": upload("a.pdf", PDF), "DocumentType": "Ownership Proof"},
                            format="multipart").data["DocumentID"]
        self.assertEqual(owner.post(f"/api/horses/{horse_id}/submit").status_code, 200)
        res = owner.delete(f"/api/horse-documents/{doc_id}")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "INVALID_STATUS")
        self.assertEqual(self.client_for(self.manager).delete(f"/api/horse-documents/{doc_id}").status_code, 204)

    def test_rejects_bad_files(self):
        horse_id = self.owner_creates_horse()
        owner = self.client_for(self.owner)
        cases = [
            upload("virus.exe", b"MZ\x90\x00", "application/octet-stream"),   # sai đuôi
            upload("fake.pdf", b"<html>not a pdf</html>"),                   # đổi đuôi
            upload("empty.pdf", b""),                                        # rỗng
        ]
        for file in cases:
            res = owner.post(f"/api/horses/{horse_id}/documents", {"File": file, "DocumentType": "Passport"},
                             format="multipart")
            self.assertEqual(res.status_code, 400, file.name)
            self.assertIn("File", res.data, file.name)
        res = owner.post(f"/api/horses/{horse_id}/documents", {"File": upload("a.pdf", PDF), "DocumentType": "Xyz"},
                         format="multipart")
        self.assertEqual(res.status_code, 400)
        with self.settings(UPLOAD_MAX_MB=0):
            res = owner.post(f"/api/horses/{horse_id}/documents",
                             {"File": upload("big.pdf", PDF), "DocumentType": "Passport"}, format="multipart")
            self.assertEqual(res.status_code, 400)
        self.assertFalse(HorseDocument.objects.exists())

    def test_hidden_document_not_downloadable_by_owner(self):
        horse_id = self.owner_creates_horse()
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/documents", {
            "File": upload("note.pdf", PDF), "DocumentType": "Other", "IsVisibleToOwner": "false",
        }, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertFalse(res.data["IsVisibleToOwner"])
        owner = self.client_for(self.owner)
        self.assertEqual(owner.get(f"/api/horse-documents/{res.data['DocumentID']}/file").status_code, 404)
        self.assertEqual(owner.get(f"/api/horses/{horse_id}/documents").data, [])


class EmailTests(Flow1TestCase):
    def test_flow1_sends_emails(self):
        with self.captureOnCommitCallbacks(execute=True):
            horse_id = self.owner_creates_horse()
            self.submit_and_verify(horse_id)
            self.vet_signs_initial_exam(horse_id)
            self.client_for(self.manager).post(f"/api/horses/{horse_id}/approve", {"HorseCode": "EQ-009"},
                                               format="json")
        sent = [(m.to, m.subject) for m in mail.outbox]
        self.assertIn((["manager@one.test"], "[EquiTrack] Hồ sơ ngựa mới cần xác minh: Thunder"), sent)
        self.assertIn((["owner@one.test"], "[EquiTrack] Hồ sơ Thunder đã được xác minh"), sent)
        self.assertIn((["manager@one.test"], "[EquiTrack] Đã khám đầu vào: Thunder"), sent)
        self.assertIn((["owner@one.test"], "[EquiTrack] Ngựa Thunder đã được tiếp nhận"), sent)
        self.assertIn("EQ-009", mail.outbox[-1].body)

    def test_reject_email_has_reason(self):
        horse_id = self.owner_creates_horse()
        self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/reject",
                                                     {"Reason": "Thiếu giấy sở hữu"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(mail.outbox[-1].to, ["owner@one.test"])
        self.assertIn("Thiếu giấy sở hữu", mail.outbox[-1].body)

    def test_failed_action_sends_nothing_and_smtp_error_is_swallowed(self):
        horse_id = self.owner_creates_horse()
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/verify")  # còn Draft -> lỗi
        self.assertEqual(res.status_code, 409)
        self.assertEqual(mail.outbox, [])
        with mock.patch("apps.core.emails.send_mail", side_effect=OSError("smtp down")), \
                self.assertLogs("equi.email", level="ERROR"), self.captureOnCommitCallbacks(execute=True):
            res = self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        self.assertEqual(res.status_code, 200)  # mail lỗi không làm hỏng thao tác

    def test_demo_local_addresses_skipped_with_smtp(self):
        from apps.core import emails
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"), \
                mock.patch("apps.core.emails._send") as send, self.captureOnCommitCallbacks(execute=True):
            emails.send_email(["vet@equi.local"], "x", "y")
        send.assert_not_called()


GOOGLE_USER = {"email": "lan.nguyen@gmail.com", "name": "Nguyễn Thị Lan"}


@mock.patch("apps.accounts.views.verify_google_credential", return_value=GOOGLE_USER)
class GoogleLoginTests(Flow1TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_new_google_user_signs_up_as_owner(self, _verify):
        client = APIClient()
        res = client.post("/api/auth/google", {"Credential": "tok"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data, {"SignupRequired": True, "Email": "lan.nguyen@gmail.com",
                                    "FullName": "Nguyễn Thị Lan"})
        self.assertFalse(User.objects.filter(email="lan.nguyen@gmail.com").exists())

        res = client.post("/api/auth/google", {"Credential": "tok", "Phone": "0901234567", "Address": "Q1",
                                               "ClubID": self.club.id, "RoleCode": "CLUB_MANAGER"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["User"]["Roles"], ["HORSE_OWNER"])
        user = User.objects.get(email="lan.nguyen@gmail.com")
        self.assertFalse(user.has_usable_password())

        # lần sau bấm Google là vào thẳng
        res = client.post("/api/auth/google", {"Credential": "tok"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)

    def test_existing_staff_logs_in_with_google(self, verify):
        verify.return_value = {"email": "VET@one.test", "name": "x"}
        res = APIClient().post("/api/auth/google", {"Credential": "tok"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["User"]["Roles"], ["VETERINARIAN"])

    def test_signup_validation_and_suspended(self, verify):
        res = APIClient().post("/api/auth/google", {"Credential": "tok", "Phone": "12", "Address": "Q1",
                                                    "ClubID": self.club.id}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Phone", res.data)
        self.vet2.status = "Suspended"
        self.vet2.save()
        verify.return_value = {"email": "vet2@one.test", "name": "x"}
        self.assertEqual(APIClient().post("/api/auth/google", {"Credential": "tok"}, format="json").status_code, 401)


class GoogleConfigTests(Flow1TestCase):
    def test_disabled_without_client_id(self):
        with self.settings(GOOGLE_CLIENT_ID=""):
            res = APIClient().post("/api/auth/google", {"Credential": "tok"}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "GOOGLE_LOGIN_DISABLED")

    def test_bad_token_is_401(self):
        res = APIClient().post("/api/auth/google", {"Credential": "not-a-jwt"}, format="json")
        self.assertEqual(res.status_code, 401)


class LanguageTests(Flow1TestCase):
    def test_errors_in_english_with_header(self):
        client = APIClient()
        res = client.post("/api/auth/login", {"Email": "vet@one.test", "Password": "nope"}, format="json",
                          HTTP_X_LANGUAGE="en")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["detail"], "Wrong email or password, or the account is locked.")
        self.assertEqual(res["Content-Language"], "en")
        # mặc định vẫn tiếng Việt
        res = client.post("/api/auth/login", {"Email": "vet@one.test", "Password": "nope"}, format="json")
        self.assertEqual(res.data["detail"], "Email hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.")
        self.assertEqual(res["Content-Language"], "vi")

    def test_field_errors_patterns_and_drf_defaults(self):
        owner = self.client_for(self.owner)
        res = owner.post("/api/horses?lang=en", self.horse_payload(ClubID=self.club.id, MicrochipNumber="123",
                                                                 DateOfBirth="2999-01-01"), format="json")
        self.assertEqual(res.status_code, 400, res.data)
        self.assertTrue(res.data["MicrochipNumber"][0].startswith("Microchip number must be exactly 15 digits"))
        self.assertEqual(res.data["DateOfBirth"][0], "Date of birth cannot be in the future.")
        # câu mặc định của DRF cũng sang tiếng Anh
        res = APIClient().post("/api/auth/register", {}, format="json", HTTP_X_LANGUAGE="en")
        self.assertIn("This field is required.", str(res.data))
        # câu có phần thay đổi + code giữ nguyên
        horse_id = self.owner_creates_horse()
        res = self.client_for(self.manager).post(f"/api/horses/{horse_id}/verify", HTTP_X_LANGUAGE="en")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["detail"], "Cannot verify the record while the record is Draft.")
        self.assertEqual(res.data["code"], "INVALID_STATUS")

    def test_notifications_titles(self):
        horse_id = self.owner_creates_horse()
        self.client_for(self.owner).post(f"/api/horses/{horse_id}/submit")
        items = self.client_for(self.manager).get("/api/notifications", HTTP_X_LANGUAGE="en").data
        self.assertIn("Horse record awaiting verification", [i["Title"] for i in items])
