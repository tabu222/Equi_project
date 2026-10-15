from rest_framework.test import APIClient, APITestCase

from .helpers import TEST_PASSWORD, Flow1TestCase


class AuthTests(Flow1TestCase):
    def test_health_is_public(self):
        res = APIClient().get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"backend": "UP", "database": "UP"})

    def test_login_returns_tokens_and_permissions(self):
        res = APIClient().post("/api/auth/login", {"Email": "VET@one.test", "Password": TEST_PASSWORD},
                               format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("access", res.data)
        self.assertEqual(res.data["User"]["Roles"], ["VETERINARIAN"])
        self.assertIn("MEDICAL_SIGN", res.data["User"]["Permissions"])
        self.assertNotIn("PasswordHash", res.data["User"])

        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(me.get("/api/auth/me").data["Email"], "vet@one.test")

    def test_wrong_password(self):
        res = APIClient().post("/api/auth/login", {"Email": "vet@one.test", "Password": "nope"}, format="json")
        self.assertEqual(res.status_code, 401)
        self.assertIn("code", res.data)

    def test_suspended_user_cannot_login(self):
        self.vet2.status = "Suspended"
        self.vet2.save()
        res = APIClient().post("/api/auth/login", {"Email": "vet2@one.test", "Password": TEST_PASSWORD},
                               format="json")
        self.assertEqual(res.status_code, 401)

    def test_api_requires_token(self):
        self.assertEqual(APIClient().get("/api/horses").status_code, 401)

    def test_manager_creates_owner_account(self):
        res = self.client_for(self.manager).post("/api/users", {
            "FullName": "Chủ ngựa mới", "Email": "new.owner@one.test", "Phone": "0900000000",
            "Address": "Q1, TP.HCM",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["Roles"], ["HORSE_OWNER"])
        self.assertEqual(res.data["ClubID"], self.club.id)
        self.assertTrue(res.data["TemporaryPassword"])

        owners = self.client_for(self.manager).get("/api/users?RoleCode=HORSE_OWNER").data
        self.assertIn("new.owner@one.test", [u["Email"] for u in owners])

    def test_owner_cannot_list_users(self):
        self.assertEqual(self.client_for(self.owner).get("/api/users").status_code, 403)

    def test_duplicate_email_rejected(self):
        res = self.client_for(self.manager).post("/api/users", {"FullName": "X", "Email": "OWNER@one.test"},
                                                 format="json")
        self.assertEqual(res.status_code, 400)


class SeedDemoTests(Flow1TestCase):
    def test_seed_demo_is_repeatable(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("seed_demo", "--password", "demo-pass-123", stdout=out)
        self.assertIn("demo-pass-123", out.getvalue())
        call_command("seed_demo", stdout=StringIO())          # chạy lại không lỗi, không trùng dữ liệu
        res = APIClient().post("/api/auth/login", {"Email": "vet@equi.local", "Password": "demo-pass-123"},
                               format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["User"]["Roles"], ["VETERINARIAN"])


class SwaggerTests(APITestCase):
    def test_swagger_page_and_schema_are_public(self):
        self.assertEqual(self.client.get("/api/docs").status_code, 200)
        res = self.client.get("/api/schema")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"/api/auth/login", res.content)
