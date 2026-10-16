# equi-fe

Frontend React + Vite cho dự án Equi. Vite chạy mặc định tại `http://localhost:5173` và proxy request `/api` sang Django REST backend tại `http://127.0.0.1:8000`.

## Yêu cầu

- Node.js `^20.19.0` hoặc `>=22.12.0` (Node.js 24 cũng phù hợp)
- npm đi kèm Node.js
- Backend tại `../backend` chạy ở cổng 8000

## Cài dependency và chạy bằng PowerShell

Mở terminal PowerShell riêng tại thư mục `C:\Equine_Project\frontend`:

```powershell
npm.cmd ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm.cmd run dev
```

Truy cập `http://localhost:5173`, vào `/login` để đăng nhập hoặc đăng ký Owner. Kiểm tra kết nối bằng `http://127.0.0.1:8000/api/health`.

Repository dùng `package-lock.json`, vì vậy dùng `npm.cmd ci` để cài đúng phiên bản đã khóa. Dùng `npm.cmd` cũng tránh lỗi ExecutionPolicy chặn `npm.ps1` trên một số máy Windows.

## Biến môi trường Vite

File `.env.example` cung cấp hai giá trị mẫu:

- `VITE_API_BASE_URL=/api`: URL tập trung mà code frontend sử dụng.
- `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`: đích proxy chỉ dành cho Vite dev server.

Chỉ biến bắt đầu bằng `VITE_` mới được Vite đưa vào frontend; tuyệt đối không đặt tài khoản MySQL, mật khẩu hoặc token bí mật ở đây. `.env.local` bị Git ignore. Các biến `DB_USERNAME` và `DB_PASSWORD` thuộc terminal chạy Spring Boot, không thuộc frontend; Spring Boot cũng không tự đọc `.env.local` của Vite.

Với cấu hình dev mặc định, trình duyệt gọi `/api` qua Vite proxy. Backend dùng prefix `/api/` (xác minh trong `equi-backend/config/urls.py`). Đăng nhập bằng tài khoản backend; access/refresh JWT được lưu cục bộ và gửi trong header Bearer. Không đặt token trong file môi trường Vite.

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
- Backend hiển thị `DOWN`: chạy `../backend` trong terminal khác và kiểm tra cổng 8000.
- Backend `UP`, database `DOWN`: backend đã nhận request nhưng `SELECT 1` thất bại; kiểm tra SQL Server, Windows/SQL Authentication và biến môi trường ở terminal backend.
- Backend chạy cổng khác: đổi `VITE_API_PROXY_TARGET` trong `.env.local`, rồi khởi động lại Vite.
- Đổi `.env.local` nhưng chưa có hiệu lực: dừng và chạy lại `npm.cmd run dev`.

## Flow 1 đã tích hợp

Login/Register giữ màu Equi, animation chuyển form, responsive và reduced motion từ ZIP. Đăng ký dùng API công khai đã có, bổ sung địa chỉ và CLB theo serializer; không cho chọn vai trò. Thành công mới chuyển về đăng nhập, không lưu mật khẩu hoặc dữ liệu nghiệp vụ vào localStorage.

Các trang dùng chung `apiClient.ts`, `horseApi.ts`, `userApi.ts`. Các bản JS trùng và form Vet JSX không có nơi sử dụng đã được gỡ sau khi chuyển `CreateHorse` sang TS. Token chỉ dùng các khóa `equi.access-token`, `equi.refresh-token`; logout cũng dọn khóa cũ. Các file mock còn lại không được import vào luồng chạy.

Contract theo route/serializer backend: [backend/docs/API.md](../backend/docs/API.md). Owner tạo/sửa/gửi hồ sơ và theo dõi yêu cầu sửa; Manager xác minh/từ chối/tiếp nhận/xếp chuồng/duyệt sửa/lưu trữ; Vet lưu/mở lại nháp và ký phiếu của mình. Không có bước Manager phân công Vet. Vai trò khác hiển thị thông báo chưa có dashboard Flow 1.

Khi đăng ký mới, Owner có thể chọn ảnh/tài liệu trước khi lưu; frontend tạo bản nháp rồi gửi multipart `File`, `DocumentType`, `DocumentName` qua `POST /horses/{id}/documents`. Các loại giấy tờ dùng enum backend (`Passport`, `Microchip Certificate`, `Ownership Proof`, `Handover Record`, `Contract`, `Other`); backend nhận PDF/JPG/JPEG/PNG/WebP, giới hạn mặc định 10 MB có thể cấu hình trên server. Hồ sơ đã tiếp nhận dùng yêu cầu cập nhật và Manager duyệt như phần bên dưới. File đã lưu được xem/tải qua API xác thực, và xóa gọi API theo quyền/trạng thái backend.

```powershell
npm.cmd run build
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:api
```

`test:api` kiểm tra adapter thật với HTTP giả lập: role, payload, validation, 403, refresh đồng thời, lỗi mạng, logout trong lúc refresh và public registration. Nó không thay thế kiểm thử FE–BE/SQL Server thật.

## Yêu cầu cập nhật hồ sơ Owner

Trang `/owner/horses/:horseId/correction-request` hỗ trợ nhiều trường, chọn / tải ảnh đại diện,
thêm / đề nghị gỡ ảnh, minh chứng, bổ sung và thay phiên bản tài liệu trong một yêu cầu.
File chỉ tải khi gửi, cùng metadata trong một multipart request; file chờ duyệt chưa nằm trong
danh sách tài liệu chính. Lịch sử hỗ trợ xem chi tiết, rút yêu cầu chờ và tạo lại từ yêu cầu bị từ chối.
Manager so sánh trước/sau và xử lý toàn bộ yêu cầu. Router dùng data router của React Router hiện có
để cảnh báo khi điều hướng khỏi form chưa gửi, kể cả Back/Forward.

Giới hạn file lấy từ API cấu hình của backend. Các trường lý lịch hiện tại đều bắt buộc theo
serializer; chưa hỗ trợ xóa nội dung. Chưa có trường xuất xứ, đặc điểm nhận dạng, ghi chú Owner,
ngày cấp hoặc ngày hết hạn tài liệu trong model. Không bổ sung các trường này vào form hoặc database.

Kiểm thử trình duyệt dùng Chromium thật và API Django thật trên SQLite tạm riêng:

```powershell
# Terminal 1, từ backend/ (khởi động fixture mới cho mỗi lần chạy):
.venv/Scripts/python.exe -m apps.core.tests.browser_fixture
# Terminal 2, từ frontend/:
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8001'
npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
# Terminal 3, từ frontend/:
$env:BROWSER_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node tests/profile-proposal.browser.mjs
```

Script kiểm tra đăng nhập Owner/Manager, hai trường + năm file, cảnh báo rời trang, lỗi mạng / thử lại,
desktop/mobile không tràn ngang, hồ sơ giữ nguyên khi chờ, Manager duyệt và Owner rút yêu cầu.
Ảnh chụp được lưu trong thư mục tạm được in sau khi chạy. Fixture không kết nối database dự án.
