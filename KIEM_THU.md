# Kết quả kiểm thử — PHUC-FOODIE (Tự Cập Nhật Đơn Hàng & Modular Monolith)

## TỔNG HỢP KIỂM THỬ: 111/111 TESTS PASS (100% OK)

1. **Bộ kiểm thử Google OAuth 2.0 / OpenID Connect (`tests/test_google_oauth.py`)**: **14/14 PASS (100% OK, ~9.6s)**
   - Lệnh chạy: `.\.venv\Scripts\python.exe -m unittest tests/test_google_oauth.py`
   - Xác minh chuyển hướng đăng nhập Google có đầy đủ `state` (chống CSRF) và `nonce` (chống replay ID token).
   - Xác minh callback hợp lệ tạo tài khoản khách (`role='customer'`), `phone=NULL`, `password_hash=NULL`, liên kết danh tính `user_identities` (`UNIQUE(provider, provider_id)`) và cấp cookie phiên `foodie_customer_session`.
   - Xác minh đăng nhập lại cùng `sub` không tạo bản ghi trùng lặp trong cả 2 bảng `users` và `user_identities`.
   - Xác minh email chưa xác minh (`email_verified: False`) thất bại an toàn, không tạo tài khoản hoặc phiên.
   - Xác minh người dùng bấm hủy (`error=access_denied`) chuyển hướng về trang chủ kèm thông báo thân thiện bằng tiếng Việt.
   - Xác minh state không khớp (`MismatchingStateError`) hoặc token không hợp lệ (`OAuthError`) thất bại an toàn, không lộ secret, token hay traceback.
   - Xác minh email đã tồn tại với tài khoản mật khẩu không tự động liên kết danh tính, yêu cầu đăng nhập bằng phương thức cũ.
   - Xác minh chặn xung đột với email tài khoản quản trị viên, tuyệt đối không cấp quyền admin hay đăng nhập vào tài khoản admin qua Google.
   - Xác minh phiên khách và phiên quản trị viên cùng tồn tại độc lập trong cùng một trình duyệt (Dual-session isolation).
   - Xác minh luồng đăng ký, đăng nhập mật khẩu và đăng xuất truyền thống vẫn hoạt động 100% không bị ảnh hưởng.
   - Xác minh tài khoản tạo qua Google không thể đăng nhập hoặc đặt lại mật khẩu bằng mật khẩu ngẫu nhiên (`password_hash IS NULL`).
   - Xác minh khi thiếu cấu hình OAuth (`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` rỗng), ứng dụng vẫn khởi động bình thường, cờ `googleAuthEnabled=False` và nút bấm phản hồi an toàn.
   - Xác minh `create_app()` nhiều lần hoàn toàn cô lập cấu hình OAuth, không dùng nhầm client của app khác.

2. **Bộ kiểm thử chính server (`tests/test_server.py`)**: **36/36 PASS (100% OK)**
   - Lệnh chạy: `.\.venv\Scripts\python.exe tests/test_server.py`
   - Xác minh toàn bộ hành vi cốt lõi: đăng ký tài khoản, đăng nhập khách/admin song song, kiểm tra CSRF riêng, bảo vệ quyền admin, upload ảnh kiểm tra MIME Pillow, kiểm tra ranh giới tiền và voucher, kiểm tra tồn kho nguyên tử (`FOR UPDATE`), hoàn kho khi hủy đơn, chuyển trạng thái đơn hàng, idempotency requestKey trả HTTP 200, giờ mở cửa theo múi giờ `Asia/Ho_Chi_Minh` và phân vùng giao hàng.

3. **Bộ kiểm thử toàn vẹn kiến trúc & sửa lỗi (`tests/test_refactor_integrity.py`)**: **8/8 PASS (100% OK)**
   - Lệnh chạy: `.\.venv\Scripts\python.exe tests/test_refactor_integrity.py`
   - Tự tạo fixture người dùng riêng, cô lập hoàn toàn trên database `phuc_foodie_test`, dispose engine và dọn thư mục tạm sau khi chạy.
   - Xác minh sửa lỗi mapping dọn ảnh, dọn dẹp ảnh mồ côi, CSP `blob:` trong `img-src`, phân lập upload giữa các app instance, bảo vệ file tĩnh không lộ `.env.mysql`, `.env`, `server.py`.

4. **Bộ kiểm thử giao diện & Tự cập nhật đơn hàng không cần F5 (`tests/test_ui.cjs`)**: **53/53 PASS (100% OK)**
   - Lệnh chạy: `npm test` (hoặc `node tests/test_ui.cjs`)
   - **Tự động cập nhật khách hàng (Customer Real-time Polling 8s)**:
     - Xác minh tự cập nhật trạng thái mới khi admin đổi trạng thái đơn (pending → preparing → delivering).
     - Xác minh thông báo toast nhẹ hiển thị đúng mã đơn và trạng thái mới.
     - Xác minh không phát thông báo lặp lại khi dữ liệu hoặc trạng thái không đổi.
     - Xác minh quản lý vòng đời: tab ẩn (`document.hidden = true`) dừng polling timer; tab hiển thị trở lại kích hoạt cập nhật tức thì.
     - Xác minh xử lý lỗi mạng: giữ nguyên thẻ đơn hàng đang hiển thị, hiển thị thanh trạng thái kết nối `customer-order-conn-status`, exponential backoff tăng dần lên tới 60s và tự phục hồi về 8s khi có mạng.
     - Xác minh đăng xuất dừng triệt để timer polling và xóa sạch trạng thái phiên.
   - **Tự động cập nhật quản trị viên (Admin Real-time Polling 8s)**:
     - Xác minh phát hiện đơn mới theo ID (`seenOrderIds` Set) khi khách đặt đơn.
     - Xác minh hiển thị cảnh báo trực quan thanh công cụ (`#new-orders-alert` "Có 1 đơn mới") và huy hiệu số lượng trên tab (`#orders-new-badge`).
     - Xác minh nút "✕ Đã xem" đặt lại số lượng đơn mới và ẩn cảnh báo.
     - Xác minh giữ nguyên bộ lọc trạng thái (`#status-filter`) khi dữ liệu tự động cập nhật, không bị reset về "Tất cả".
     - Xác minh chuyển đổi tab: chuyển khỏi tab Đơn hàng (`products`, `preview`, `settings`) lập tức dừng polling; quay lại tab Đơn hàng tự động tiếp tục ngay.
     - Xác minh lỗi mạng admin: không xóa bảng danh sách đơn hiện tại và hiển thị thông báo kết nối gọn gàng.
   - **Các tính năng UI trước đó**: 42 kiểm thử giao diện cốt lõi (catalog, search, category filter, modal detail, cart hydration, checkout zones, demo payment, Google login button, store preview, store settings dirty check) tiếp tục PASS 100%.

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
