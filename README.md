# Equi backend – Racehorse Training & Management System

Backend Python Django REST cho đồ án SWP391. Database SQL Server tạo bằng `sql/horse_v2.sql`.

- Phạm vi: đủ **4 flow** trên toàn bộ 37 bảng của `horse_v2.sql`, đăng nhập JWT, phân quyền theo bảng `Role` / `Permission`:
  - **Flow 1 – tiếp nhận ngựa**: đăng ký, xác minh, khám đầu vào, duyệt, chuồng, sửa lý lịch, lưu trữ.
  - **Flow 2 – huấn luyện**: đánh giá ngựa, phân công Trainer, giáo án (Head Trainer duyệt), buổi tập, Substitute Trainer, kết quả, đánh giá.
  - **Flow 3 – y tế**: báo cáo sức khỏe, phiếu khám (nháp / chốt / đính chính), Training Lock, thuốc, tiêm phòng, lịch y tế.
  - **Flow 4 – chăm sóc**: khẩu phần (Vet duyệt), việc chăm sóc của Groom, kho vật tư.
  - Thông báo cho từng vai trò (`GET /api/notifications`).
- Hợp đồng API cho frontend: [`docs/API.md`](docs/API.md). Code mẫu cho frontend: [`docs/frontend/`](docs/frontend).

## Cấu trúc

```
config/            cấu hình Django (settings.py đọc .env)
apps/core/         lỗi chung, kiểm tra quyền, audit log, thông báo, /api/health, lệnh seed_demo, test
apps/accounts/     Club, Role, Permission, User, đăng nhập
apps/horses/       Flow 1: Horse, giấy tờ, hồ sơ tiếp nhận, yêu cầu sửa lý lịch, chuồng
apps/training/     Flow 2: chuyên môn, đánh giá, phân công, giáo án, buổi tập, kết quả, đánh giá buổi tập
apps/medical/      Flow 3: phiếu khám, đính chính, Training Lock, thuốc, tiêm phòng, lịch y tế, báo cáo sức khỏe
apps/care/         Flow 4: khẩu phần, việc chăm sóc, kho vật tư
sql/horse_v2.sql   script tạo database (bản chốt)
docs/              API.md + code mẫu frontend
```

Mỗi app tách: `models.py` (bảng), `serializers.py` (JSON vào / ra), `services.py` (luật nghiệp vụ), `views.py` (API), `urls.py`.

Model đều `managed = False`: **bảng do `horse_v2.sql` tạo, Django không tạo / sửa bảng**.
Không chạy `python manage.py migrate` / `makemigrations`.

## Cài đặt (Windows)

Cần có:

1. Python 3.12 hoặc 3.13 (khi cài nhớ tick **Add python.exe to PATH**).
2. SQL Server (Express được) + SSMS.
3. **Microsoft ODBC Driver 18 for SQL Server** (tải từ trang Microsoft, bản x64).

### Bước 1. Tạo database

Mở SSMS → **File → Open → File...** → chọn `sql/horse_v2.sql` → **Execute** (F5).
Script tạo database `RacehorseTrainingManagement` kèm 7 vai trò, 26 quyền.

### Bước 2. Cài thư viện Python

Mở PowerShell trong thư mục dự án:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Nếu PowerShell báo không cho chạy script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` rồi chạy lại dòng Activate.

### Bước 3. Tạo file `.env`

```powershell
copy .env.example .env
```

Mở `.env`, sửa:

- `DB_HOST`: giống ô **Server name** khi đăng nhập SSMS (ví dụ `localhost\SQLEXPRESS` hoặc `localhost`).
- `DB_USER` / `DB_PASSWORD`: **để trống** nếu SSMS đăng nhập bằng *Windows Authentication*; nếu dùng tài khoản SQL (`sa`...) thì điền vào.
- `DJANGO_SECRET_KEY`: tạo bằng `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

> `.env` chứa mật khẩu nên **không commit lên GitHub** (đã có trong `.gitignore`, repo đang Public).

### Bước 4. Kiểm tra kết nối và tạo tài khoản demo

```powershell
python manage.py check
python manage.py seed_demo --password <mật-khẩu-dev-tự-chọn>
```

`seed_demo` tạo CLB *Equi Demo Club*, 6 chuồng, vài vật tư trong kho và một tài khoản cho mỗi vai trò
(trainer demo có sẵn chuyên môn Flat Racing để phân công được ngay):
`manager@equi.local`, `headtrainer@equi.local`, `trainer@equi.local`, `rider@equi.local`,
`vet@equi.local`, `groom@equi.local`, `owner@equi.local` (cùng mật khẩu vừa nhập).
Chạy lại nhiều lần không bị trùng; thêm `--reset-passwords` để đặt lại mật khẩu.

### Bước 5. Chạy server

```powershell
python manage.py runserver 8000
```

Mở <http://localhost:8000/api/health> → thấy `{"backend": "UP", "database": "UP"}` là xong.

## Chạy cùng frontend (`equi-fe`)

Trong thư mục frontend tạo file `.env.local`:

```
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://localhost:8000
```

Rồi `npm run dev` và mở <http://localhost:5173>. Vite chuyển các request `/api/...` sang backend.
Frontend cần đổi tên trường / trạng thái và các hàm gọi API theo [`docs/API.md` mục 5](docs/API.md#5-frontend-cần-sửa-gì).

## Thử API nhanh (PowerShell)

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/auth/login `
  -ContentType "application/json" -Body '{"Email":"manager@equi.local","Password":"<mật-khẩu-dev>"}'
$h = @{ Authorization = "Bearer " + $login.access }
Invoke-RestMethod -Uri http://localhost:8000/api/horses -Headers $h
```

## Chạy test

Test dùng SQLite trong bộ nhớ, **không cần SQL Server**:

```powershell
python manage.py test --settings=config.settings_test
```

Có 78 test, chia theo nhóm:

- **Luồng chính**: Flow 1–4 chạy từ đầu đến cuối, kể cả Substitute Trainer, Training Lock và kho vật tư.
- **Quyền và cách ly dữ liệu**: phân quyền theo vai trò; dữ liệu tách riêng giữa các CLB và giữa các chủ ngựa.
- **Khớp với `sql/horse_v2.sql`** (kiểm tra bằng cách đọc file SQL):
  - đủ 37 bảng có model, tên cột trùng khớp, cột NOT NULL;
  - giá trị trạng thái trùng với các CHECK;
  - dữ liệu Role / Permission / Specialization trùng với phần seed.

SQLite không có trigger / view của SQL Server. Backend tự kiểm tra lại bằng Python đúng các luật mà trigger làm
(Training Lock chặn buổi tập / giáo án, tự hủy buổi tập khi khóa, phiếu đã chốt không sửa được), nên test vẫn có ý nghĩa;
tuy vậy vẫn nên thử lại các thao tác chính trên SQL Server thật.

## Ghi chú kỹ thuật

- JSON dùng đúng tên cột database (`HorseName`, `RegistrationStatus`...): xem `DBColumnModelSerializer` trong `apps/core/serializers.py`.
- Mật khẩu lưu ở cột `User.PasswordHash` dạng hash của Django (`pbkdf2_sha256$...`). Không nhập mật khẩu trực tiếp bằng SQL; dùng `seed_demo` hoặc API `POST /api/users`.
- Mỗi request là một transaction (`ATOMIC_REQUESTS`): lỗi giữa chừng thì không lưu dở dang.
- Lỗi do trigger SQL Server (`THROW 51001`–`51004`) và unique index được dịch sang câu tiếng Việt trong `apps/core/exceptions.py`
  (mã lỗi giống hệt khi backend tự phát hiện trước, vd `TRAINING_LOCK_FULL`).
- Bảng không có cột cho một số thông tin (lý do từ chối yêu cầu vật tư, lịch sử nhập / xuất kho, thời điểm tạo Training Lock):
  backend lấy từ `AuditLog`, không đổi database.
- Mọi thao tác thay đổi dữ liệu ghi vào bảng `AuditLog`.
