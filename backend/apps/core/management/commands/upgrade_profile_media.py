"""Check/apply the additive SQL Server profile proposal schema upgrade."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection


class Command(BaseCommand):
    help = "Check profile media schema; use --apply to add missing columns without recreating tables."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply the additive SQL migration.")

    def handle(self, *args, **options):
        if connection.vendor != "microsoft":
            raise CommandError("This upgrade is for SQL Server only.")
        required = {"IsPrimary", "IsRetired", "IsProfileImage", "ReplacesDocumentID"}
        with connection.cursor() as cursor:
            cursor.execute("SELECT DB_NAME()")
            self.stdout.write(f"Database: {cursor.fetchone()[0]}")
            cursor.execute("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID('dbo.HorseDocument')")
            existing = {row[0] for row in cursor.fetchall()}
            if not existing:
                raise CommandError("HorseDocument does not exist. No changes applied.")
            cursor.execute("SELECT definition FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID('dbo.ProfileChangeRequest') AND name='CK_ProfileChangeRequest_Status'")
            row = cursor.fetchone()
            status_ready = row is not None and "Withdrawn" in row[0]
            missing = required - existing
            if not missing and status_ready:
                self.stdout.write(self.style.SUCCESS("Profile media schema is ready. No changes needed."))
                return
            self.stdout.write("Missing columns: " + (", ".join(sorted(missing)) or "none"))
            self.stdout.write(f"Withdrawn status supported: {status_ready}")
            if not options["apply"]:
                raise CommandError("Upgrade needed. Run: python manage.py upgrade_profile_media --apply")
            # Record original column values, not just row counts; never print their contents.
            originals = {}
            for table, pk in (("HorseDocument", "DocumentID"), ("ProfileChangeRequest", "ProfileChangeRequestID")):
                cursor.execute(f"SELECT name FROM sys.columns WHERE object_id=OBJECT_ID('dbo.{table}') ORDER BY column_id")
                columns = [row[0] for row in cursor.fetchall()]
                if not columns:
                    raise CommandError(f"{table} does not exist. No changes applied.")
                select = f"SELECT {', '.join('[' + col + ']' for col in columns)} FROM dbo.{table} ORDER BY [{pk}]"
                cursor.execute(select)
                originals[table] = (select, [tuple(row) for row in cursor.fetchall()])
            migration = Path(settings.SQL_SCRIPT).parent / "migrations" / "20261016_profile_change_media.sql"
            if not migration.is_file():
                raise CommandError("The additive migration file is missing. No changes applied.")
            try:
                # The reviewed SQL file owns its transaction and rolls back on SQL errors.
                cursor.execute(migration.read_text(encoding="utf-8"))
                while cursor.nextset():
                    pass
            except DatabaseError as exc:
                cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION")
                raise CommandError("The schema upgrade failed and was rolled back.") from exc
            cursor.execute("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID('dbo.HorseDocument')")
            if not required.issubset({row[0] for row in cursor.fetchall()}):
                raise CommandError("Schema verification failed after upgrade.")
            for table, (select, before) in originals.items():
                cursor.execute(select)
                after = [tuple(row) for row in cursor.fetchall()]
                if after != before:
                    raise CommandError(f"Original {table} data changed during upgrade. Check concurrent writes.")
                self.stdout.write(f"Preserved {table}: {len(after)} rows, all original column values unchanged.")
        self.stdout.write(self.style.SUCCESS("Profile media schema upgraded successfully."))
