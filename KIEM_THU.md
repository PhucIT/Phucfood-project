# Kết quả kiểm thử — PHUC-FOODIE (Tái cấu trúc Modular Monolith & Tính năng)

## TỔNG HỢP KIỂM THỬ SAU KHI SỬA LỖI & TÁI CẤU TRÚC: 85/85 TESTS PASS (100% OK)

1. **Bộ kiểm thử chính server (`tests/test_server.py`)**: **36/36 PASS (100% OK, ~31.5s)**
   - Lệnh chạy: `.\.venv\Scripts\python.exe tests/test_server.py`
   - Xác minh toàn bộ hành vi cốt lõi: đăng ký tài khoản, đăng nhập khách/admin song song, kiểm tra CSRF riêng, bảo vệ quyền admin, upload ảnh kiểm tra MIME Pillow, kiểm tra ranh giới tiền và voucher, kiểm tra tồn kho nguyên tử (`FOR UPDATE`), hoàn kho khi hủy đơn, chuyển trạng thái đơn hàng, idempotency requestKey trả HTTP 200, giờ mở cửa theo múi giờ `Asia/Ho_Chi_Minh` và phân vùng giao hàng.

2. **Bộ kiểm thử toàn vẹn kiến trúc & sửa lỗi (`tests/test_refactor_integrity.py`)**: **8/8 PASS (100% OK, ~2.5s)**
   - Lệnh chạy: `.\.venv\Scripts\python.exe tests/test_refactor_integrity.py`
   - Tự tạo fixture người dùng riêng, cô lập hoàn toàn trên database `phuc_foodie_test`, dispose engine và dọn thư mục tạm sau khi chạy.
   - Xác minh sửa lỗi mapping dọn ảnh: truy vấn `COUNT(*) AS cnt` đọc qua `res['cnt']` không lỗi.
   - Xác minh dọn dẹp ảnh mồ côi khi đổi ảnh và giữ nguyên ảnh dùng chung khi vẫn có món khác tham chiếu.
   - Xác minh header CSP cho phép `blob:` trong `img-src` để xem trước ảnh tải lên từ máy tính, không nới lỏng `script-src`.
   - Xác minh phân lập upload giữa hai app instance: App A không ghi vào hay đọc từ thư mục upload của App B.
   - Xác minh truyền `SECRET_KEY` trực tiếp không tạo file `session.key` trên đĩa.
   - Xác minh dual session khách/admin trong cùng cookie jar.
   - Xác minh cơ chế bảo vệ file tĩnh: chặn triệt để việc lộ file mã nguồn (`server.py`, `.env.mysql`, `.env`, `data/session.key`).
   - Xác minh endpoint `/api/store-info` trả đầy đủ cấu hình công khai và phân vùng giao hàng.

3. **Bộ kiểm thử giao diện & tương tác người dùng (`tests/test_ui.cjs`)**: **41/41 PASS (100% OK)**
   - Lệnh chạy: `npm run test:ui` (hoặc `node tests/test_ui.cjs`)
   - Xác minh 100% các kịch bản DOM/UI khách hàng và quản trị viên, tìm kiếm, lọc danh mục, mở/đóng modal chi tiết, giỏ hàng, đặt hàng, dirty check cảnh báo thay đổi cấu hình chưa lưu.

---

## CHI TIẾT CÁC BÀI TEST CHUYÊN SÂU:
  - **Quyền & CSRF**: Chỉ admin mới có quyền xem và cập nhật cấu hình `/api/admin/store/settings` và `/api/admin/delivery-zones`. Mọi thao tác PATCH/POST/DELETE thiếu hoặc sai CSRF đều bị chặn 403. Khách vãng lai và tài khoản khách thường bị từ chối truy cập.
  - **Lưu cấu hình & Khởi động lại**: Cấu hình tên quán, địa chỉ, hotline, thời gian giao tối thiểu/tối đa, cờ tạm ngưng, lý do, miễn phí giao, ngưỡng và lịch tuần được lưu vào bảng `store_settings` trong MySQL và duy trì nguyên vẹn sau khi server khởi động lại.
  - **Kiểm tra giờ mở cửa theo múi giờ `Asia/Ho_Chi_Minh`**:
    - Hỗ trợ ca làm việc ban ngày (ví dụ 08:00 - 22:00) và kiểm tra chính xác ranh giới phút bắt đầu và phút kết thúc.
    - Hỗ trợ ca đêm mở qua nửa đêm (ví dụ 18:00 đến 02:00 sáng hôm sau).
    - Hỗ trợ ngày nghỉ bán cả ngày (`is_closed: true`).
    - Khi đóng cửa, khách hàng vẫn xem được danh sách món nhưng bị chặn đặt đơn với mã lỗi 409 kèm lý do lịch hoạt động; không trừ kho và không xóa giỏ.
  - **Trạng thái tạm ngừng nhận đơn (is_paused)**: Có **ưu tiên cao nhất** so với lịch mở cửa. Khi bật tạm ngừng, đơn hàng bị chặn 409 kèm thông báo lý do tùy chỉnh của admin.
  - **Quản lý khu vực giao hàng (Delivery Zones)**:
    - Admin thêm/sửa tên khu vực, phí giao không âm và bật/tắt nhận giao.
    - Khi có khu vực: Khách bắt buộc phải chọn khu vực hợp lệ. Chọn khu vực đang tắt nhận giao bị từ chối 400.
    - Phí giao theo khu vực được backend tự tính và xác thực, không tin cậy dữ liệu client gửi.
    - Chặn xóa vĩnh viễn khu vực đã từng có đơn hàng (`usedInOrders > 0`), nhắc admin chuyển sang tắt nhận giao thay vì xóa.
    - Khi tất cả khu vực đều bị tắt: Chặn tạo đơn mới 409, không tự ý quay về chế độ không giới hạn khu vực.
  - **Phí giao hàng & Ngưỡng miễn phí (Free Shipping Rules)**:
    - Giữ mặc định ban đầu: 15.000đ khi chưa cấu hình khu vực, miễn phí từ 100.000đ.
    - **Quy tắc cốt lõi**: Ngưỡng miễn phí giao hàng được tính trên **tổng tiền món (subtotal) trước khi trừ voucher**. Đơn hàng có subtotal >= 100k sau khi trừ voucher còn 96k vẫn được miễn phí giao 0đ.
    - Client giả mạo tổng tiền hoặc phí giao hàng bị server phát hiện và từ chối 409.
  - **Bản chụp đơn hàng (Snapshot Immutability) & Tính lũy thừa (Idempotency)**:
    - Đơn hàng lưu bản chụp bất biến: `deliveryZoneId`, `deliveryZoneName`, `estimatedDeliveryTime`, `subtotalPrice`, `shippingFee`, `discountAmount`, `totalPrice`.
    - Việc admin thay đổi tên khu vực, đổi phí, hoặc tạm ngừng nhận đơn sau này không làm thay đổi các đơn hàng đã đặt trong lịch sử.
    - Retry cùng `requestKey` của đơn đã thành công lập tức trả về thông tin đơn cũ kể cả khi quán vừa đóng cửa hoặc tạm ngừng; tuyệt đối không trừ kho lần 2.
  - **Kế thừa các kiểm thử cũ**: Toàn bộ 30 kiểm thử trước đó (đăng ký, đăng nhập song song, upload ảnh an toàn MIME Pillow, tồn kho nguyên tử, hủy đơn hoàn kho, chuyển trạng thái COD, rate limit, bảo vệ static files) tiếp tục PASS 100%.

- **41/41 kiểm thử JavaScript/DOM bằng jsdom**: **PASS (100% OK)**
  - Chạy bằng: `node tests/test_ui.cjs`.
  - **Khách hàng (`index.html`)**:
    - Banner thương hiệu hiển thị tên quán, hotline, địa chỉ, giờ hoạt động và huy hiệu trạng thái hoạt động ("🟢 Đang nhận đơn" / "🔴 Tạm ngừng nhận đơn" / "🕒 Ngoài giờ hoạt động").
    - Form checkout hiển thị menu chọn khu vực giao hàng (`#customer-zone`).
    - Thay đổi khu vực giao hàng tự động cập nhật phí giao và tổng thanh toán trong bảng chi tiết đơn hàng.
    - Modal đặt hàng thành công hiển thị bản chụp tên khu vực giao và thời gian giao ước tính.
    - XSS escaping dữ liệu hiển thị (ghi chú khách, tên khu vực).
  - **Quản trị viên (`admin.html`)**:
    - Tab "Cấu hình cửa hàng" mở panel cấu hình hoàn chỉnh ngay trong khung admin.
    - Hiển thị đầy đủ thông tin cửa hàng, hotline, địa chỉ, công tắc tạm ngừng, lý do, thời gian giao tối thiểu/tối đa, công tắc và ngưỡng miễn phí giao hàng.
    - Bảng khu vực giao hàng hiển thị đúng danh sách, mức phí, trạng thái nhận giao và các nút hành động (Sửa, Bật/Tắt giao, Xóa).
    - Mở và đóng modal thêm/sửa khu vực giao hàng (`#zone-dialog`).
    - Biểu mẫu lịch tuần hiển thị đủ 7 ngày với các ca làm việc.
    - Kiểm thử cảnh báo thay đổi chưa lưu (dirty check): Chuyển tab hoặc bấm đăng xuất khi form cấu hình có thay đổi chưa lưu sẽ hiển thị cảnh báo; từ chối sẽ giữ nguyên tab hiện tại, đồng ý mới chuyển tab.

- **An toàn Cơ sở dữ liệu MySQL**:
  - Toàn bộ kiểm thử tự động chỉ tương tác với cơ sở dữ liệu `phuc_foodie_test`.
  - Cơ sở dữ liệu chính `phuc_foodie` được bảo toàn nguyên vẹn, không chạy lại migration SQLite, không drop table hay volume.
  - Bảng `store_settings` và `delivery_zones` được tạo thông qua migration bổ sung chạy an toàn và có thể chạy lại nhiều lần (idempotent).

- **Ghi chú về kiểm chứng trực quan**:
  - Trình duyệt tự động Playwright gặp lỗi tải driver từ mạng AzureEdge (`404 Not Found`) trong môi trường hiện tại; do đó bố cục thực tế được kiểm chứng đầy đủ thông qua 41 bài test DOM/JavaScript giả lập và thẩm định CSS media queries cho mobile 390px, chưa chạy trực quan bằng Playwright driver.
