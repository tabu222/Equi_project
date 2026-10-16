from unittest.mock import patch

from django.db import DatabaseError, ProgrammingError

from apps.horses.models import Horse
from .helpers import Flow1TestCase


class DatabaseErrorResponseTests(Flow1TestCase):
    def test_missing_schema_returns_json_without_debug_traceback(self):
        horse_id = self.owner_creates_horse()
        with self.settings(DEBUG=True), patch(
            "apps.horses.views.HorseDocumentSerializer",
            side_effect=ProgrammingError("Invalid column name 'IsRetired'. private database diagnostics"),
        ):
            response = self.client_for(self.owner).get(f"/api/horses/{horse_id}/documents")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.data["code"], "DATABASE_ERROR")
        self.assertNotIn("IsRetired", str(response.data))
        self.assertNotIn("private database diagnostics", str(response.data))
        self.assertNotIn("Traceback", str(response.data))

    def test_handled_database_error_rolls_back_changes_in_request(self):
        before = Horse.objects.count()
        with patch("apps.horses.views.log_action", side_effect=DatabaseError("audit storage unavailable")):
            response = self.client_for(self.owner).post(
                "/api/horses", self.horse_payload(ClubID=self.club.id), format="json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], "DATABASE_ERROR")
        self.assertEqual(Horse.objects.count(), before)
