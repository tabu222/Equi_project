# Equi backend – Racehorse Training & Management System

Django REST backend for the Equi project, running at http://127.0.0.1:8000.

- Scope: all **4 flows** over all 37 tables of `horse_v2.sql`, JWT login, permissions from the `Role` / `Permission` tables:
  - **Flow 1 – Horse intake**: registration, verification, intake examination, approval, stalls, profile changes, archiving.
  - **Flow 2 – Training**: horse assessment, trainer assignment, training plans (approved by the Head Trainer), training sessions, Substitute Trainer, results, reviews.
  - **Flow 3 – Medical**: health reports, medical records (draft / signed / amendment), Training Lock, treatments, vaccinations, medical schedules.
  - **Flow 4 – Care**: diet plans (approved by the Vet), Groom care tasks, inventory.
  - Notifications for each role (`GET /api/notifications`).
- API contract for the frontend: [`docs/API.md`](docs/API.md).

## Project structure

```
config/            Django settings
apps/core/         shared code (errors, permissions, notifications, tests)
apps/accounts/     users, roles, login
apps/horses/       Flow 1 – Horse intake
apps/training/     Flow 2 – Training
apps/medical/      Flow 3 – Medical
apps/care/         Flow 4 – Care
sql/horse_v2.sql   database script
docs/API.md        API contract
```

Each app is split into: `models.py` (tables), `serializers.py` (JSON in / out), `services.py` (business rules), `views.py` (API), `urls.py`.

All models are `managed = False`: **the tables are created by `horse_v2.sql`; Django never creates or alters tables**.
Do not run `python manage.py migrate` / `makemigrations`.

## Setup (Windows)

Requirements: Python 3.12+, SQL Server + SSMS, Microsoft ODBC Driver 17 or 18 for SQL Server.

1. Open `sql/horse_v2.sql` in SSMS and run it (F5) to create the database.
2. Open PowerShell in the project folder and run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

3. Edit `.env` for your machine (see the comments in the file), then:

```powershell
python manage.py seed_demo --password <your-dev-password>
python manage.py runserver 8000
```

Check: <http://127.0.0.1:8000/api/health> → `{"backend": "UP", "database": "UP"}`.
If it shows `"database": "DOWN"`, check `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_ODBC_DRIVER` in `.env`.

Do not write passwords in source code or the README, and never commit `.env`.

Demo accounts created by `seed_demo` (all with the password you entered): `manager@equi.local`, `headtrainer@equi.local`,
`trainer@equi.local`, `rider@equi.local`, `vet@equi.local`, `groom@equi.local`, `owner@equi.local`.

## Running the tests

78 tests, using in-memory SQLite (no SQL Server needed):

```powershell
python manage.py test --settings=config.settings_test
```

## Notes

- Create users with `seed_demo` or `POST /api/users`, not with SQL `INSERT`
  (passwords must be hashed by Django).
- Every data change is logged in the `AuditLog` table.
