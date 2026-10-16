# PHUC-FOODIE — Hướng dẫn cài đặt và vận hành (Backend MySQL Docker)

Dự án tiếp tục giữ nguyên HTML/CSS/JavaScript thuần, giao diện hiện đại. Backend sử dụng Python + Flask + SQLAlchemy + PyMySQL kết nối tới MySQL 8.4 chạy trên Docker Desktop.

---

## 1. Kiến trúc hệ thống và cơ sở dữ liệu

- **Kiến trúc Backend**: **Modular Monolith** chuẩn mực bên trong package `phuc_foodie/`, chuẩn bị ranh giới nghiệp vụ độc lập cho microservices tương lai.
  - Vẫn chạy chung một tiến trình ứng dụng Flask, một cơ sở dữ liệu MySQL và duy trì 100% hành vi hiện tại.
  - File `server.py` và `database.py` tại thư mục gốc đóng vai trò **compatibility facade** mỏng, đảm bảo các script và công cụ cũ không bị phá vỡ.
- **Frontend**: HTML5, CSS3, JavaScript thuần (Vanilla), phục vụ có kiểm soát từ thư mục gốc.
- **Backend API**: Python 3.10+ (Flask, Werkzeug, SQLAlchemy Core, PyMySQL).
- **Database chính**: MySQL 8.4 LTS chạy trên Docker container (`phuc_foodie_mysql`), lưu trữ dữ liệu bền vững bằng volume `phuc_foodie_mysql_data`.
- **Database kiểm thử**: `phuc_foodie_test` trong cùng container, dùng riêng cho test suite tự động, không ảnh hưởng dữ liệu thật.
- **Database cũ (Lưu trữ)**: `data/foodie.db` (SQLite) và các bản sao lưu tự động có dấu thời gian `data/foodie.db.bak_*`.

---

## 2. Chuẩn bị môi trường & Cài đặt

Mở PowerShell tại thư mục dự án (`C:\WebDoAn`):

```powershell
# 1. Tạo và kích hoạt môi trường ảo (nếu chưa có)
python -m venv .venv

# 2. Cài đặt các gói phụ thuộc (Flask, SQLAlchemy, PyMySQL, cryptography, python-dotenv, ...)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 3. Khởi động MySQL Docker

Đảm bảo **Docker Desktop** đang chạy trên máy tính Windows.

```powershell
# Khởi chạy MySQL Docker bằng cấu hình riêng
docker compose --env-file .env.mysql -f compose.mysql.yaml up -d

# Kiểm tra trạng thái container và healthcheck
docker compose --env-file .env.mysql -f compose.mysql.yaml ps
```
Trạng thái hiển thị `Up ... (healthy)` tại cổng `127.0.0.1:3308->3306/tcp`.

---

## 4. Chuyển đổi dữ liệu từ SQLite sang MySQL (Migration)

Dự án có sẵn công cụ chuyển dữ liệu an toàn kèm chế độ kiểm tra trước khi ghi và sao lưu tự động:

```powershell
# Bước 1: Kiểm tra tính toàn vẹn trước khi ghi (Dry run)
.\.venv\Scripts\python.exe migrate_sqlite_to_mysql.py --dry-run

# Bước 2: Thực hiện chuyển dữ liệu chính thức
.\.venv\Scripts\python.exe migrate_sqlite_to_mysql.py
```

*Lưu ý:* Công cụ tự động sao lưu file `data/foodie.db` với tên có thời gian, không sửa bản SQLite gốc và dừng lại an toàn nếu MySQL đã có dữ liệu để chống ghi đè/xung đột.

---

## 5. Chạy Website và Quản trị

### Khởi động server:
```powershell
.\.venv\Scripts\python.exe server.py
```

Mở trình duyệt:
- **Cửa hàng**: `http://127.0.0.1:5000`
- **Trang quản trị**: `http://127.0.0.1:5000/admin`

*(Hoặc nhấp đúp file `START_WINDOWS.bat` để chạy nhanh).*

### Tạo tài khoản quản trị mới (khi cần):
```powershell
.\.venv\Scripts\python.exe server.py --create-admin
```
Nhập họ tên, email, số điện thoại và mật khẩu quản trị theo lời nhắc.

---

## 6. Kết nối quản lý qua MySQL Workbench

Khi tạo kết nối mới trong **MySQL Workbench**:
- **Connection Method**: `Standard (TCP/IP)`
- **Hostname**: `127.0.0.1`
- **Port**: `3308`
- **Username**: `foodie_user` *(Tài khoản ứng dụng, bảo mật và chỉ cấp quyền trên database `phuc_foodie`)*
- **Default Schema**: `phuc_foodie`
- **Password**: Xem biến `MYSQL_PASSWORD` trong file `.env.mysql` trên máy của bạn.

Các câu lệnh SQL hữu ích để kiểm tra dữ liệu trong Workbench:
```sql
USE phuc_foodie;

-- Xem danh sách món ăn
SELECT id, name, price, category, available FROM products ORDER BY id;

-- Xem danh sách tài khoản
SELECT id, full_name, email, phone, role FROM users;

-- Xem danh sách đơn hàng mới nhất
SELECT id, user_id, state, created_at, request_key FROM orders ORDER BY created_at DESC;
```

---

## 7. Chạy kiểm thử tự động (Test Suite)

### Kiểm thử Backend (36 test):
```powershell
.\.venv\Scripts\python.exe tests/test_server.py
```
*Tất cả 36 test chạy độc lập trên database `phuc_foodie_test`, kiểm tra toàn diện cấu hình cửa hàng, giờ hoạt động/qua nửa đêm, tạm ngừng nhận đơn, CRUD khu vực giao hàng, chặn xóa khu vực đã có đơn, tính phí theo subtotal trước voucher, chống giả tiền client, bảo toàn snapshot đơn cũ, trừ/hoàn kho nguyên tử, và các quyền admin/CSRF.*

### Kiểm thử Giao diện / DOM (41 test):
```powershell
node tests/test_ui.cjs
```
*Kiểm tra luồng giỏ hàng, nhãn tồn kho, modal chi tiết, form upload ảnh admin, xem cửa hàng trong admin, tab cấu hình cửa hàng, dialog khu vực giao hàng, dirty checking thay đổi chưa lưu, banner trạng thái quán trên trang chủ, và chọn khu vực giao hàng khi checkout.*

---

## 8. Hướng dẫn trải nghiệm Đăng nhập song song (2 Tab trong 1 Trình duyệt)

Hệ thống đã phân tách hoàn toàn cơ chế phiên của Khách và Quản trị viên:
- **Khách hàng** dùng cookie `foodie_customer_session` và CSRF token khách.
- **Quản trị viên** dùng cookie `foodie_admin_session` và CSRF token quản trị.
- Hai phiên độc lập tuyệt đối, không ghi đè nhau, không chia sẻ CSRF và đăng xuất một bên không ảnh hưởng bên còn lại.

---

## 9. Hướng dẫn Cấu hình cửa hàng & Khu vực giao hàng (Tính năng mới)

### A. Thiết lập thông tin cửa hàng & Giờ mở cửa:
1. Mở trang quản trị: `http://127.0.0.1:5000/admin`, chọn tab **Cấu hình cửa hàng**.
2. **Thông tin cửa hàng**: Điền Tên cửa hàng, Hotline, Địa chỉ. Thông tin sẽ hiển thị trên banner trang chủ và biên nhận đơn.
3. **Trạng thái nhận đơn**:
   - Khi quán quá tải, tích vào **Tạm ngừng nhận đơn** và nhập lý do/thông báo cho khách.
   - Trạng thái này có **ưu tiên cao nhất**: dù đang trong giờ mở cửa, khách vẫn chỉ xem được menu nhưng không thể đặt đơn mới (kho và giỏ không đổi).
4. **Lịch hoạt động theo tuần (Múi giờ Asia/Ho_Chi_Minh)**:
   - Từng ngày trong tuần có thể bật mở cửa hoặc tắt làm ngày nghỉ (`💤 Nghỉ bán cả ngày`).
   - Mỗi ngày có thể thiết lập nhiều khung giờ làm việc (`+ Thêm khung giờ`).
   - Hỗ trợ ca đêm mở qua nửa đêm sang rạng sáng hôm sau (ví dụ: `18:00` đến `02:00` sáng).
5. **Thời gian giao hàng ước tính**:
   - Nhập số phút tối thiểu và tối đa (ví dụ: `25` - `40` phút).
6. **Miễn phí giao hàng**:
   - Bật/tắt miễn phí giao hàng theo giá trị đơn và chỉnh ngưỡng (mặc định 100.000đ).
   - **Quy tắc**: Ngưỡng được tính trên tổng tiền món (**subtotal trước khi trừ mã giảm giá**).
7. Bấm **Lưu cấu hình cửa hàng**. Biểu mẫu có tính năng bảo vệ thay đổi chưa lưu (dirty check).

### B. Quản lý phân vùng giao hàng (Delivery Zones):
1. Tại phần **5. Khu vực giao hàng** trong tab Cấu hình cửa hàng:
   - Bấm **+ Thêm khu vực** -> Nhập Tên (ví dụ: `Quận 1`, `Bán kính 3km`) và Phí giao (ví dụ: `20000`).
   - Có thể bật/tắt nhận giao từng khu vực bằng nút **Tắt giao** / **Bật giao**.
   - Nếu khu vực đã từng có đơn hàng trong lịch sử: hệ thống bảo toàn tính toàn vẹn và **ngăn chặn xóa vĩnh viễn** (nút Xóa bị vô hiệu hóa, chỉ cho phép tắt giao).
2. **Hành vi checkout phía khách hàng**:
   - Nếu chưa tạo khu vực: Quán giữ cách tính phí mặc định (15.000đ, miễn phí từ 100.000đ), có thông báo gợi ý admin cấu hình.
   - Nếu đã tạo khu vực: Bắt buộc khách phải chọn khu vực trong danh sách đang nhận giao. Phí giao và tổng tiền cập nhật trực tiếp theo khu vực đã chọn.
   - Nếu tất cả khu vực đều bị tắt: Chặn tạo đơn mới và thông báo rõ cho khách, không tự ý quay về chế độ không giới hạn.

### C. Kịch bản thử nghiệm toàn trình:
Thử nghiệm luồng: **Cấu hình khu vực → khách đặt đơn → đơn lưu snapshot → admin đổi cấu hình / tạm ngừng → đơn cũ giữ nguyên & retry đơn không trừ kho thêm**:
1. **Bước 1**: Trong Admin -> Tab Cấu hình cửa hàng -> Thêm khu vực `Quận 10` với phí `18000`. Cài đặt thời gian giao `20` - `30` phút.
2. **Bước 2**: Sang trang khách (`http://127.0.0.1:5000`) -> Banner hiển thị rõ thông tin hotline, địa chỉ, giờ hoạt động.
3. **Bước 3**: Chọn 1 Burger bò (50k) -> Vào Checkout -> Dropdown khu vực hiện `Quận 10 (18.000đ)`. Bảng tóm tắt cập nhật phí giao 18.000đ, tổng tiền 68.000đ. Đặt đơn -> Thành công. Modal xác nhận hiển thị rõ khu vực `Quận 10` và thời gian giao `20 - 30 phút (ước tính)`.
4. **Bước 4**: Admin vào Cấu hình đổi phí `Quận 10` lên `35000` và tích **Tạm ngừng nhận đơn** ("Quán nghỉ giải lao").
5. **Bước 5**: Kiểm tra đơn cũ trong Lịch sử đơn: Vẫn giữ nguyên phí 18.000đ và thời gian ban đầu.
6. **Bước 6**: Thử gửi lại cùng `requestKey` của đơn cũ: Server trả về đúng đơn cũ mà không trừ kho lần hai, dù quán hiện đang tạm ngừng nhận đơn.

---

## 10. Hướng dẫn Quản lý món, Upload ảnh từ máy tính & Tồn kho

### A. Cách Admin nhập tồn kho cho các món cũ:
1. Mở trang quản trị: `http://127.0.0.1:5000/admin` và đăng nhập.
2. Chọn tab **Thực đơn**.
3. Các món cũ sẽ hiển thị trạng thái `Kho: Chưa nhập tồn kho` (để bảo toàn dữ liệu, hệ thống không tự đặt số giả). Khách chưa thể đặt các món này cho đến khi admin thiết lập số lượng tồn.
4. Bấm nút **Chỉnh sửa** trên món muốn bán -> Nhập số lượng vào ô **Số lượng tồn kho** (ví dụ: `50`) -> Bấm **Lưu món**.
5. Món sẽ ngay lập tức chuyển sang trạng thái sẵn sàng phục vụ cho khách hàng.

### B. Kịch bản thử nghiệm toàn trình:
Thử nghiệm luồng: **Thêm món + chọn ảnh → nhập tồn 3 → khách đặt 2 → còn 1 → hủy đơn → trở lại 3 → tắt bán**:

1. **Bước 1: Admin thêm món mới kèm ảnh và tồn kho**:
   - Ở tab Quản trị (`http://127.0.0.1:5000/admin`), chọn tab **Thực đơn** -> bấm **Thêm món**.
   - Nhập Tên món: `Bánh mì chảo đặc biệt`, Giá: `45000`, Danh mục: `Đồ ăn`.
   - Nhập **Số lượng tồn kho**: `3`.
   - Tại mục "Tải ảnh từ máy tính", chọn một file ảnh bất kỳ (`.jpg`, `.png`, hoặc `.webp`). Khung xem trước sẽ hiển thị ảnh ngay lập tức.
   - Bấm **Lưu món**: Ảnh được upload lên server vào thư mục `uploads/` và món mới xuất hiện trong danh sách với nhãn `Còn 3 phần`.

2. **Bước 2: Khách đặt 2 phần**:
   - Chuyển sang tab Khách (`http://127.0.0.1:5000`), tải lại trang (F5).
   - Thấy món `Bánh mì chảo đặc biệt` hiển thị nhãn xanh **Còn 3 phần**.
   - Bấm vào món -> Chọn số lượng là `2` -> Thêm vào giỏ.
   - Tiến hành Checkout -> Chọn COD -> Bấm **Xác nhận đặt hàng**.
   - Đặt hàng thành công!

3. **Bước 3: Kiểm tra tồn kho còn 1**:
   - Xem lại danh sách món ở trang khách (hoặc tab admin): món giờ đây hiển thị nhãn **Còn 1 phần**.
   - Thử thêm `2` phần vào giỏ -> Hệ thống báo lỗi và chặn lại vì kho chỉ còn `1` phần.

4. **Bước 4: Khách hủy đơn -> Kho tự động hoàn lại 3**:
   - Ở trang khách, mở menu **Lịch sử đơn**.
   - Thấy đơn vừa đặt đang ở trạng thái `Chờ xác nhận` -> Bấm nút **Hủy đơn**.
   - Sau khi hủy đơn, tải lại trang: số lượng tồn của món tự động hoàn lại thành **Còn 3 phần**.

5. **Bước 5: Admin tắt bán nhanh**:
   - Ở tab Admin, tại thẻ món `Bánh mì chảo đặc biệt`, bấm nút **Tắt bán** (nút bật/tắt nhanh).
   - Món lập tức chuyển sang nhãn **Tạm ngừng bán**.
   - Sang trang khách tải lại: nút thêm món bị vô hiệu hóa kèm nhãn **Tạm ngừng bán**, khách không thể đặt dù kho vẫn còn 3 phần.


---

## 8. Cấu trúc thư mục Modular Monolith (`phuc_foodie/`)
 
```
WebDoAn/
  server.py                        # Entry point mỏng & compatibility facade (re-export create_app, CLI)
  database.py                      # Facade tương thích kết nối và schema
  wsgi.py                          # WSGI entry point cho Gunicorn
  START_WINDOWS.bat                # Khởi động nhanh trên Windows
  Dockerfile, compose.yaml         # Dockerfile & Compose (hỗ trợ volume uploads & appuser)
  compose.mysql.yaml               # MySQL 8.4 Docker service
  phuc_foodie/                     # Package backend chính
    __init__.py                    # Application factory create_app(), đăng ký middleware, Blueprints
    config.py                      # PROJECT_ROOT (C:\WebDoAn), data_dir, upload_dir, secret_key
    extensions.py                  # Quản lý connection SQLAlchemy trên g.db và teardown request
    cli.py                         # Lệnh --create-admin tương tác
    common/                        # Xử lý lỗi ApiError và hàm validate payload/text/password
    security/                      # Session độc lập (customer/admin), CSRF check, permissions, rate-limit
    infrastructure/                # Kết nối DatabaseConnection (SQLAlchemy Core) và schema MySQL
    modules/
      auth/                        # Đăng ký, đăng nhập khách/admin, đổi mật khẩu, revoke sessions
      catalog/                     # Quản lý món ăn, upload ảnh an toàn Pillow, tồn kho
      orders/                      # Đặt đơn nguyên tử, hủy đơn, voucher, snapshot & chuyển trạng thái
      store/                       # Thông tin cửa hàng, giờ mở cửa theo tuần, phân vùng giao hàng
    web/                           # Phục vụ index.html, admin.html và tài nguyên tĩnh có kiểm soát
  images/                          # Ảnh mẫu mặc định
  uploads/                         # Ảnh món ăn do admin tải lên
  data/                            # Thư mục chứa session key và backup sqlite cũ
  tests/                           # Bộ kiểm thử tự động backend và UI
```

| Thành phần | Nhiệm vụ |
|---|---|
| `phuc_foodie/` | Toàn bộ mã nguồn ứng dụng phân chia theo ranh giới nghiệp vụ độc lập |
| `server.py` | Entry point máy chủ `python server.py` và CLI `--create-admin` |
| `database.py` | Facade re-export `DatabaseConnection`, `create_database_engine`, `init_schema` |
| `wsgi.py` | Điểm nạp ứng dụng WSGI cho Gunicorn/Docker container |
| `index.html`, `script.js`, `style.css` | Giao diện và tương tác trang bán hàng của khách |
| `admin.html`, `admin.js`, `admin.css` | Trang quản trị: đơn hàng, món ăn, xem cửa hàng, cấu hình quán |
| `api.js` | Tầng gọi API từ frontend tới backend |
| `catalog.json` | Dữ liệu 8 món ăn gốc |
| `tests/` | Bộ kiểm thử tự động backend (`test_server.py`, `test_refactor_integrity.py`) và UI (`test_ui.cjs`) |

