# equi-fe

Frontend React + Vite cho dự án Equi. Vite chạy mặc định tại `http://localhost:5173` và proxy request `/api` sang Django REST backend tại `http://127.0.0.1:8000`.

## Yêu cầu

- Node.js `^20.19.0` hoặc `>=22.12.0` (Node.js 24 cũng phù hợp)
- npm đi kèm Node.js
- Backend Django (thư mục `backend/` của repo) chạy tại cổng 8000

## Cài dependency và chạy bằng PowerShell

Mở terminal PowerShell riêng tại thư mục `equi-fe`:

```powershell
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

Truy cập `http://localhost:5173`. Khối **Connection check** hiển thị riêng trạng thái backend và database.

Repository dùng `package-lock.json`, vì vậy dùng `npm.cmd ci` để cài đúng phiên bản đã khóa. Dùng `npm.cmd` cũng tránh lỗi ExecutionPolicy chặn `npm.ps1` trên một số máy Windows.

## Biến môi trường Vite

File `.env.example` cung cấp hai giá trị mẫu:

- `VITE_API_BASE_URL=/api`: URL tập trung mà code frontend sử dụng.
- `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`: đích proxy chỉ dành cho Vite dev server.

Chỉ biến bắt đầu bằng `VITE_` mới được Vite đưa vào frontend; tuyệt đối không đặt mật khẩu database hoặc token bí mật ở đây. `.env.local` bị Git ignore. Cấu hình database (SQL Server) nằm trong file `.env` của backend Django, không thuộc frontend.

Với cấu hình dev mặc định, trình duyệt gọi `/api` qua Vite proxy. Backend dùng prefix `/api/` (xem `backend/config/urls.py`). Đăng nhập bằng tài khoản backend; access/refresh JWT được lưu cục bộ và gửi trong header Bearer. Không đặt token trong file môi trường Vite.

## Kiểm tra

```powershell
npm.cmd run lint
npm.cmd run build
```

Nếu muốn xem production build cục bộ:

```powershell
npm.cmd run preview
```

## Lỗi thường gặp

- `npm.ps1 cannot be loaded`: dùng `npm.cmd` như các lệnh phía trên.
- Backend hiển thị `DOWN`: chạy backend Django (thư mục `backend/`) trong terminal khác và kiểm tra cổng 8000.
- Backend `UP`, database `DOWN`: backend đã nhận request nhưng `SELECT 1` thất bại; kiểm tra SQL Server và file `.env` của backend (`DB_HOST`, `DB_ODBC_DRIVER`...).
- Backend chạy cổng khác: đổi `VITE_API_PROXY_TARGET` trong `.env.local`, rồi khởi động lại Vite.
- Đổi `.env.local` nhưng chưa có hiệu lực: dừng và chạy lại `npm.cmd run dev`.
