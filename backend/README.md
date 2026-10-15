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
2. Open PowerShell in the `backend` folder and run:

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

Test the API in the browser with **Swagger**: open <http://127.0.0.1:8000/api/docs>,
call `POST /api/auth/login` (Try it out), copy the `access` token, click **Authorize** and paste it.
After that every API can be called from the page. Postman also works: import <http://127.0.0.1:8000/api/schema>.

Do not write passwords in source code or the README, and never commit `.env`.

Demo accounts created by `seed_demo` (all with the password you entered):

| Role | Accounts |
|---|---|
| Club Manager | `manager@equi.local` |
| Head Trainer | `headtrainer@equi.local`, `headtrainer2@equi.local` |
| Trainer | `trainer@equi.local` (Flat Racing), `trainer2@equi.local` (Steeplechase), `trainer3@equi.local` (Endurance) |
| Work Rider | `rider@equi.local`, `rider2@equi.local`, `rider3@equi.local` |
| Vet | `vet@equi.local`, `vet2@equi.local`, `vet3@equi.local` |
| Groom | `groom@equi.local`, `groom2@equi.local`, `groom3@equi.local` |
| Horse Owner | `owner@equi.local`, `owner2@equi.local`, `owner3@equi.local` |

There are several vets: any vet in the club can take an intake exam, but only the vet who opened a draft record can edit or sign it.
It also creates 6 sample horses for `owner@equi.local` (3 Approved, 1 PendingExam, 1 Submitted, 1 Draft).
All accounts have a real name, phone number and address; every horse has a full profile (no empty fields).
Running it again is safe: nothing is duplicated, and old accounts get their missing club / phone / address and real names.

## Language (VI / EN)

API messages are Vietnamese by default. The frontend sends `X-Language: en` (or `?lang=en`) to get English
error messages and notification titles. Translations live in `apps/core/i18n.py`.

## Optional: email, Google sign-in, uploads

- **Emails** (new horse to verify, verified, exam signed, approved, rejected, account created): without settings they are
  printed in the backend window. To send real mail through Gmail, fill `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`
  (a Gmail *App password*) in `.env`.
- **Sign in with Google**: set `GOOGLE_CLIENT_ID` in `.env` and the same value as `VITE_GOOGLE_CLIENT_ID` in `frontend/.env`.
- **Uploaded documents** are stored in `media/` (ignored by Git). Run `pip install -r requirements.txt` again after
  pulling: Google sign-in needs `google-auth`.

## Running the tests

106 tests, using in-memory SQLite (no SQL Server needed):

```powershell
python manage.py test --settings=config.settings_test
```

## Notes

- Horse owners can sign up themselves on the login page (`POST /api/auth/register`); club staff accounts are created by the Manager (`POST /api/users`).
- Create users with `seed_demo`, `POST /api/auth/register` or `POST /api/users`, not with SQL `INSERT`
  (passwords must be hashed by Django).
- Every data change is logged in the `AuditLog` table.
