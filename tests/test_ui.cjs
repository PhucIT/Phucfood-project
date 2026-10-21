const { JSDOM } = require('jsdom');
const fs = require('fs');
const assert = require('assert');
const vm = require('vm');
const path = require('path');

const root = path.resolve(__dirname, '..') + path.sep;
const products = JSON.parse(fs.readFileSync(root + 'catalog.json')).map(p => ({
  ...p,
  available: 1,
  stock_quantity: 50
}));

let passed = 0;
function check(message, fn) {
  fn();
  passed++;
  console.log('PASS ' + message);
}

async function run() {
  // ==========================================
  // PHẦN 1: GIAO DIỆN KHÁCH HÀNG (index.html)
  // ==========================================
  const dom = new JSDOM(fs.readFileSync(root + 'index.html', 'utf8'), {
    url: 'http://localhost/',
    runScripts: 'outside-only',
    pretendToBeVisual: true
  });
  const w = dom.window;
  w.HTMLElement.prototype.scrollIntoView = function () {};
  w.HTMLElement.prototype.focus = function () {};
  w.confirm = () => true;
  w.alert = () => {};

  let created = 0;
  let orderList = [];
  let loggedIn = false;

  w.fetch = async (reqPath, opts = {}) => {
    let data = {};
    let status = 200;
    const body = opts.body ? JSON.parse(opts.body) : {};

    if (reqPath === '/api/session') {
      data = { user: null, csrfToken: 'test-csrf' };
    }
    if (reqPath === '/api/products') {
      data = { products };
    }
    if (reqPath === '/api/store-info') {
      data = {
        storeName: 'PHUC-FOODIE Sài Gòn',
        phone: '0901234567',
        address: '123 Đường 3/2, Quận 10',
        isOpen: true,
        isPaused: false,
        pauseReason: '',
        todaySchedule: '08:00 - 22:00',
        deliveryTimeMin: 25,
        deliveryTimeMax: 40,
        freeShippingEnabled: true,
        freeShippingThreshold: 100000,
        defaultShippingFee: 15000,
        hasDeliveryZones: true,
        allZonesInactive: false,
        deliveryZones: [
          { id: 1, name: 'Quận 1', fee: 20000, isActive: 1 },
          { id: 2, name: 'Quận 3', fee: 25000, isActive: 1 }
        ]
      };
    }
    if (reqPath === '/api/login') {
      loggedIn = true;
      data = { user: { id: 1, fullName: 'Khách thử', email: 'test@example.test', phone: '0900000001' }, csrfToken: 'next' };
    }
    if (reqPath === '/api/register') {
      data = { message: 'Đã tạo' };
    }
    if (reqPath === '/api/orders' && opts.method === 'POST') {
      created++;
      const order = {
        id: 'PF-TEST',
        items: [{ id: 1, name: 'Burger', price: 50000, quantity: 1, subtotal: 50000 }],
        customerName: body.customer.name,
        customerPhone: body.customer.phone,
        customerAddress: body.customer.address,
        customerNote: '<img src=x onerror=alert(1)>',
        deliveryZoneId: body.deliveryZoneId,
        deliveryZoneName: 'Quận 1',
        estimatedDeliveryTime: '25 - 40 phút (ước tính)',
        subtotalPrice: 50000,
        shippingFee: 20000,
        discountAmount: 0,
        totalPrice: 70000,
        orderTime: '08/10/2026',
        status: 'Chờ xác nhận',
        orderStatus: 'pending',
        paymentMethod: body.paymentMethod,
        paymentStatus: 'pending'
      };
      data = { order };
      orderList = [order];
    } else if (reqPath === '/api/orders') {
      data = { orders: orderList };
    }
    if (reqPath === '/api/logout') {
      loggedIn = false;
      data = { csrfToken: 'logged-out' };
    }
    return { ok: status < 400, status, json: async () => data };
  };

  // Giỏ hàng lưu trước khi server trả sản phẩm
  w.localStorage.setItem('phuc_foodie_cart_v2', JSON.stringify([{ id: 1, quantity: 2 }]));

  vm.runInContext(fs.readFileSync(root + 'script.js', 'utf8'), dom.getInternalVMContext());
  vm.runInContext(fs.readFileSync(root + 'api.js', 'utf8'), dom.getInternalVMContext());
  await new Promise(r => setTimeout(r, 60));

  check('Khởi tạo tải 8 món từ server', () => assert.equal(w.document.querySelectorAll('.product-card').length, 8));

  check('Banner cửa hàng hiển thị tên, số điện thoại, địa chỉ và huy hiệu trạng thái', () => {
    const banner = w.document.getElementById('store-status-banner');
    assert.ok(banner.textContent.includes('PHUC-FOODIE Sài Gòn'));
    assert.ok(banner.textContent.includes('0901234567'));
    assert.ok(banner.textContent.includes('123 Đường 3/2'));
    assert.ok(banner.textContent.includes('Đang nhận đơn'));
  });

  const sIn = w.document.getElementById('search-input');
  sIn.value = 'Pizza';
  sIn.dispatchEvent(new w.Event('input'));
  check('Tìm kiếm món ăn lọc đúng theo từ khóa', () => assert.equal(w.document.querySelectorAll('.product-card').length, 1));
  sIn.value = '';
  sIn.dispatchEvent(new w.Event('input'));

  w.document.querySelector('[data-category="Nước uống"]').click();
  check('Lọc theo danh mục Nước uống', () => assert.equal(w.document.querySelectorAll('.product-card').length, 3));
  w.document.querySelector('[data-category="Tất cả"]').click();

  w.openProductModal(1);
  check('Modal chi tiết món mở đúng thông tin', () => assert.equal(w.document.getElementById('modal-product-name').textContent, 'Burger bò'));
  w.increaseModalQuantity();
  check('Tăng số lượng trong modal', () => assert.equal(w.document.getElementById('modal-qty-value').textContent, '2'));
  w.closeProductModal();
  check('Đóng modal chi tiết món', () => assert.equal(w.document.getElementById('product-modal').style.display, 'none'));

  check('Giỏ lưu trên thiết bị không bị xóa khi khởi động', () => assert.equal(w.document.getElementById('cart-count').textContent, 2));
  check('Các hàm inline tồn tại', () => {
    for (const n of ['selectPaymentMethod', 'closeOrderSuccessModal', 'handleOrderSuccessOverlayClick', 'confirmOrder']) {
      assert.equal(typeof w[n], 'function');
    }
  });

  w.showRegisterForm();
  for (const [id, value] of Object.entries({
    'reg-name': 'Mới',
    'reg-email': 'new@example.test',
    'reg-phone': '0900000004',
    'reg-password': 'TestPass123',
    'reg-confirm-password': 'TestPass123'
  })) {
    w.document.getElementById(id).value = value;
  }
  w.document.getElementById('reg-terms').checked = true;
  await w.handleRegister();
  check('Đăng ký dùng đúng trường form và chuyển sang đăng nhập', () => assert.equal(w.document.getElementById('login-identifier').value, 'new@example.test'));

  check('Nút Tiếp tục với Google tồn tại và trỏ tới /api/auth/google', () => {
    const googleBtn = w.document.getElementById('btn-google-login');
    assert.ok(googleBtn, 'Nút Google phải tồn tại');
    assert.equal(googleBtn.getAttribute('href'), '/api/auth/google');
    assert.ok(googleBtn.textContent.includes('Tiếp tục với Google'));
  });

  w.document.getElementById('login-password').value = 'TestPass123';
  await w.handleLogin();
  check('Thông tin phiên hiện trên header', () => assert.ok(w.document.getElementById('user-display-text').textContent.includes('Khách thử')));

  w.decreaseQuantity(1);
  w.checkout();
  check('Checkout tự điền tên và SĐT', () => assert.equal(w.document.getElementById('customer-phone').value, '0900000001'));

  check('Checkout hiển thị danh sách khu vực giao hàng', () => {
    const zoneSelect = w.document.getElementById('customer-zone');
    assert.ok(zoneSelect.options.length >= 3); // 1 placeholder + 2 khu vực
  });

  // Chọn Quận 1 (phí 20k)
  const zoneSelect = w.document.getElementById('customer-zone');
  zoneSelect.value = '1';
  w.handleZoneChange();
  w.document.getElementById('customer-address').value = 'Số 10 Lê Lợi, Phường Bến Nghé';

  check('Phí giao theo khu vực cập nhật vào bảng chi tiết thanh toán', () => {
    const summary = w.document.getElementById('checkout-price-details');
    assert.ok(summary.textContent.includes('20.000đ'));
    assert.ok(summary.textContent.includes('Quận 1'));
  });

  await w.confirmOrder();
  check('Chưa chọn thanh toán không gửi đơn', () => assert.equal(created, 0));

  w.selectPaymentMethod('qr_demo');
  await w.confirmOrder();
  check('DEMO cần xác nhận', () => assert.equal(created, 0));

  w.selectPaymentMethod('cod');
  await w.confirmOrder();
  check('Đơn thành công hiện modal và xóa giỏ', () => {
    assert.equal(created, 1);
    assert.equal(w.document.getElementById('order-success-modal').style.display, 'flex');
    assert.equal(w.document.getElementById('cart-count').textContent, '0');
  });

  check('Modal thành công hiển thị bản chụp khu vực và thời gian giao dự kiến', () => {
    assert.equal(w.document.getElementById('success-order-zone').textContent, 'Quận 1');
    assert.equal(w.document.getElementById('success-order-est-time').textContent, '25 - 40 phút (ước tính)');
  });

  check('Dữ liệu đơn được escape để tránh XSS', () => {
    assert.equal(w.document.querySelector('#order-history-list img'), null);
    assert.ok(w.document.getElementById('order-history-list').textContent.includes('<img'));
  });

  w.closeOrderSuccessModal();

  // ==========================================
  // KIỂM THỬ TỰ ĐỘNG CẬP NHẬT ĐƠN HÀNG KHÁCH
  // ==========================================
  // 1. Admin đổi trạng thái đơn -> Khách nhận thông báo toast nhẹ và cập nhật DOM
  orderList[0].orderStatus = 'preparing';
  orderList[0].status = 'Đang chuẩn bị';
  await w.refreshOrders({ isAuto: true });
  check('Khách tự cập nhật trạng thái đơn mới và nhận thông báo toast', () => {
    const badge = w.document.querySelector('.order-status-badge');
    assert.ok(badge && badge.textContent.includes('Đang chuẩn bị'));
    const toasts = w.document.querySelectorAll('.toast-title');
    const toast = toasts[toasts.length - 1];
    assert.ok(toast && toast.textContent.includes('PF-TEST'));
  });

  // 2. Không thông báo trùng lặp khi trạng thái không thay đổi
  const toastCountBefore = w.document.querySelectorAll('.toast').length;
  await w.refreshOrders({ isAuto: true });
  check('Không phát thông báo lặp nếu trạng thái đơn hàng không thay đổi', () => {
    const toastCountAfter = w.document.querySelectorAll('.toast').length;
    assert.equal(toastCountAfter, toastCountBefore);
  });

  // 3. Tab bị ẩn thì dừng timer, khi tab hiện lại thì tiếp tục cập nhật
  Object.defineProperty(w.document, 'hidden', { value: true, configurable: true, writable: true });
  w.document.dispatchEvent(new w.Event('visibilitychange'));
  check('Tab bị ẩn sẽ dừng timer polling của khách', () => {
    assert.equal(w.getCustomerPollTimer(), null);
  });

  Object.defineProperty(w.document, 'hidden', { value: false, configurable: true, writable: true });
  orderList[0].orderStatus = 'delivering';
  orderList[0].status = 'Đang giao';
  w.document.dispatchEvent(new w.Event('visibilitychange'));
  await new Promise(r => setTimeout(r, 20));
  check('Tab hiện lại sẽ tiếp tục cập nhật ngay lập tức', () => {
    const badge = w.document.querySelector('.order-status-badge');
    assert.ok(badge && badge.textContent.includes('Đang giao'));
  });

  // 4. Lỗi mạng trong auto-poll: danh sách đơn không bị xóa và hiển thị cảnh báo kết nối
  const origCustomerFetch = w.fetch;
  w.fetch = async () => { throw new TypeError('Network error'); };
  await w.refreshOrders({ isAuto: true });
  check('Lỗi mạng trong polling không xóa danh sách đơn hàng và hiển thị trạng thái kết nối', () => {
    assert.ok(w.document.querySelector('.order-card'));
    const connStatus = w.document.getElementById('customer-order-conn-status');
    assert.equal(connStatus.hidden, false);
    assert.ok(connStatus.textContent.includes('Mất kết nối server'));
  });
  w.fetch = origCustomerFetch;

  await w.logoutUser();
  check('Đăng xuất ẩn lịch sử đơn', () => assert.ok(w.document.getElementById('order-history-list').textContent.includes('Đăng nhập')));
  check('Không tạo khóa LocalStorage mật khẩu/phiên', () => {
    assert.equal(w.localStorage.getItem('phuc_foodie_users'), null);
    assert.equal(w.localStorage.getItem('phuc_foodie_current_user'), null);
  });
  check('Thẻ món ăn hiển thị nhãn tồn kho', () => assert.ok(w.document.querySelector('.product-stock-tag').textContent.includes('Còn 50 phần')));
  dom.window.close();

  // ==========================================
  // PHẦN 2: GIAO DIỆN QUẢN TRỊ (admin.html)
  // ==========================================
  const admin = new JSDOM(fs.readFileSync(root + 'admin.html', 'utf8'), {
    url: 'http://localhost/admin',
    runScripts: 'outside-only',
    pretendToBeVisual: true
  });
  const aw = admin.window;
  aw.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  aw.HTMLDialogElement.prototype.close = function () { this.open = false; };

  aw.fetch = async (reqPath) => {
    if (reqPath === '/api/admin/session' || reqPath === '/api/session') {
      return { ok: true, status: 200, json: async () => ({ user: { id: 1, fullName: 'Admin', role: 'admin' }, csrfToken: 'test' }) };
    }
    if (reqPath === '/api/admin/orders') {
      return { ok: true, status: 200, json: async () => ({ orders: orderList }) };
    }
    if (reqPath === '/api/admin/store/settings') {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          settings: {
            id: 1,
            store_name: 'PHUC-FOODIE Sài Gòn',
            phone: '0901234567',
            address: '123 Đường 3/2, Quận 10',
            is_paused: 0,
            pause_reason: '',
            delivery_time_min: 25,
            delivery_time_max: 40,
            free_shipping_enabled: 1,
            free_shipping_threshold: 100000,
            default_shipping_fee: 15000,
            schedule: {
              "0": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] },
              "1": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] },
              "2": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] },
              "3": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] },
              "4": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] },
              "5": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] },
              "6": { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] }
            }
          },
          zones: [
            { id: 1, name: 'Quận 1', fee: 20000, isActive: 1, usedInOrders: 3 },
            { id: 2, name: 'Quận 3', fee: 25000, isActive: 1, usedInOrders: 0 }
          ]
        })
      };
    }
    return { ok: true, status: 200, json: async () => ({ products }) };
  };

  vm.runInContext(fs.readFileSync(root + 'admin.js', 'utf8'), admin.getInternalVMContext());
  await new Promise(r => setTimeout(r, 40));

  check('Trang quản trị tải đơn và 8 món', () => {
    assert.equal(aw.document.getElementById('dashboard').hidden, false);
    assert.equal(aw.document.querySelectorAll('.product').length, 8);
    assert.equal(aw.document.querySelectorAll('.order').length, 1);
  });
  check('Thống kê chỉ tính COD đã thu', () => assert.equal(aw.document.getElementById('revenue').textContent, '0đ'));
  check('Danh sách món admin có nút bật tắt bán và hiển thị tồn kho', () => {
    assert.ok(aw.document.querySelector('[data-toggle]'));
    assert.ok(aw.document.querySelector('.product-body .hint').textContent.includes('Còn 50 phần'));
  });
  check('Form admin có trường upload file và tồn kho', () => {
    assert.ok(aw.document.getElementById('product-file'));
    assert.ok(aw.document.getElementById('product-stock'));
    assert.ok(aw.document.getElementById('product-preview'));
  });

  // Tab Xem cửa hàng bên trong Admin
  aw.document.getElementById('header-preview-btn').click();
  check('Nút Xem cửa hàng trên header chuyển sang tab Xem cửa hàng vẫn giữ khung admin', () => {
    assert.equal(aw.document.getElementById('preview-panel').hidden, false);
    assert.equal(aw.document.getElementById('orders-panel').hidden, true);
    assert.equal(aw.document.getElementById('products-panel').hidden, true);
    assert.equal(aw.document.querySelectorAll('.preview-card').length, 8);
  });
  check('Xem cửa hàng hiển thị đủ ảnh, tên, giá, danh mục, mô tả, tồn kho và trạng thái bán', () => {
    const firstPreview = aw.document.querySelector('.preview-card');
    assert.ok(firstPreview.querySelector('.preview-img-wrap img'));
    assert.ok(firstPreview.querySelector('.preview-card-title').textContent.length > 0);
    assert.ok(firstPreview.querySelector('.preview-card-price').textContent.includes('đ'));
    assert.ok(firstPreview.querySelector('.product-badge').textContent.length > 0);
    assert.ok(firstPreview.querySelector('.preview-card-desc'));
    assert.ok(firstPreview.querySelector('.preview-stock-tag').textContent.includes('Còn 50 phần'));
    assert.ok(firstPreview.querySelector('.preview-card-status').textContent.includes('Đang mở bán'));
    assert.ok(firstPreview.querySelector('.btn-preview-edit'));
    assert.ok(firstPreview.querySelector('.btn-preview-view'));
  });

  // Mở modal xem chi tiết món từ card preview
  const firstViewBtn = aw.document.querySelector('.btn-preview-view');
  firstViewBtn.click();
  check('Mở modal chi tiết món trong xem cửa hàng', () => {
    assert.equal(aw.document.getElementById('preview-detail-dialog').open, true);
    assert.ok(aw.document.getElementById('preview-detail-name').textContent.length > 0);
    assert.ok(aw.document.getElementById('preview-detail-stock').textContent.includes('Còn 50 phần'));
  });
  aw.document.getElementById('close-preview-detail').click();
  check('Đóng modal chi tiết món trong xem cửa hàng', () => {
    assert.equal(aw.document.getElementById('preview-detail-dialog').open, false);
  });

  // Tìm kiếm trong xem cửa hàng
  const prevSearch = aw.document.getElementById('preview-search');
  prevSearch.value = 'Pizza';
  prevSearch.dispatchEvent(new aw.Event('input'));
  check('Tìm kiếm món trong xem cửa hàng lọc chính xác', () => {
    assert.equal(aw.document.querySelectorAll('.preview-card').length, 1);
  });
  // Nhấn Escape xóa từ khóa tìm kiếm
  prevSearch.dispatchEvent(new aw.KeyboardEvent('keydown', { key: 'Escape' }));
  check('Phím Escape xóa từ khóa tìm kiếm và khôi phục danh sách', () => {
    assert.equal(prevSearch.value, '');
    assert.equal(aw.document.querySelectorAll('.preview-card').length, 8);
  });

  // Lọc danh mục trong xem cửa hàng
  aw.document.querySelector('#preview-categories [data-category="Nước uống"]').click();
  check('Lọc danh mục Nước uống trong xem cửa hàng', () => {
    assert.equal(aw.document.querySelectorAll('.preview-card').length, 3);
  });
  aw.document.querySelector('#preview-categories [data-category="Tất cả"]').click();

  // ==========================================
  // PHẦN 3: TAB CẤU HÌNH CỬA HÀNG VÀ GIAO HÀNG
  // ==========================================
  aw.document.getElementById('settings-tab').click();
  check('Tab Cấu hình cửa hàng mở đúng panel cấu hình', () => {
    assert.equal(aw.document.getElementById('settings-panel').hidden, false);
    assert.equal(aw.document.getElementById('settings-store-name').value, 'PHUC-FOODIE Sài Gòn');
    assert.equal(aw.document.getElementById('settings-store-phone').value, '0901234567');
    assert.equal(aw.document.getElementById('settings-store-address').value, '123 Đường 3/2, Quận 10');
    assert.equal(aw.document.getElementById('settings-delivery-min').value, '25');
    assert.equal(aw.document.getElementById('settings-delivery-max').value, '40');
  });

  check('Bảng khu vực giao hàng hiển thị đúng 2 khu vực', () => {
    const rows = aw.document.querySelectorAll('#zone-list-container tbody tr');
    assert.equal(rows.length, 2);
    assert.ok(rows[0].textContent.includes('Quận 1'));
    assert.ok(rows[0].textContent.includes('20.000đ'));
    assert.ok(rows[0].textContent.includes('Đang nhận giao'));
  });

  check('Biểu mẫu lịch hoạt động hiển thị đủ 7 ngày với các ca làm việc', () => {
    const dayCards = aw.document.querySelectorAll('.schedule-day-card');
    assert.equal(dayCards.length, 7);
  });

  // Mở modal thêm khu vực
  aw.document.getElementById('btn-add-zone').click();
  check('Mở modal thêm khu vực giao hàng', () => {
    assert.equal(aw.document.getElementById('zone-dialog').open, true);
    assert.equal(aw.document.getElementById('zone-title').textContent, 'Thêm khu vực giao hàng');
  });
  aw.document.getElementById('btn-cancel-zone').click();
  check('Đóng modal thêm khu vực', () => {
    assert.equal(aw.document.getElementById('zone-dialog').open, false);
  });

  // Dirty check trên Cấu hình cửa hàng khi có thay đổi chưa lưu
  let confirmAsked = false;
  aw.confirm = () => { confirmAsked = true; return false; }; // Admin từ chối huỷ
  const storeNameInput = aw.document.getElementById('settings-store-name');
  storeNameInput.value = 'PHUC-FOODIE VIP Đã Sửa';
  storeNameInput.dispatchEvent(new aw.Event('input'));

  aw.document.getElementById('orders-tab').click();
  check('Chuyển tab khi cấu hình có thay đổi chưa lưu sẽ cảnh báo và giữ nguyên tab nếu từ chối', () => {
    assert.equal(confirmAsked, true);
    assert.equal(aw.document.getElementById('settings-panel').hidden, false); // Vẫn ở settings
  });

  confirmAsked = false;
  aw.document.getElementById('logout').click();
  check('Bấm Đăng xuất khi cấu hình chưa lưu cũng bị chặn nếu không xác nhận', () => {
    assert.equal(confirmAsked, true);
    assert.equal(aw.document.getElementById('dashboard').hidden, false);
  });

  // Admin đồng ý rời đi
  aw.confirm = () => true;
  aw.document.getElementById('orders-tab').click();
  check('Admin xác nhận rời đi thì chuyển tab thành công', () => {
    assert.equal(aw.document.getElementById('orders-panel').hidden, false);
  });

  // ==========================================
  // KIỂM THỬ TỰ ĐỘNG CẬP NHẬT ĐƠN HÀNG ADMIN
  // ==========================================
  // 1. Phát hiện đơn mới theo ID và hiển thị thông báo trực quan Có N đơn mới
  orderList.push({
    id: 'PF-NEW-999',
    items: [{ id: 2, name: 'Trà đào', price: 25000, quantity: 2, subtotal: 50000 }],
    customerName: 'Khách Vip',
    customerPhone: '0911223344',
    customerAddress: '456 Lê Lợi, Q1',
    customerNote: 'Giao nhanh',
    deliveryZoneName: 'Quận 1',
    estimatedDeliveryTime: '20 phút',
    subtotalPrice: 50000,
    shippingFee: 20000,
    discountAmount: 0,
    totalPrice: 70000,
    orderTime: '08/10/2026',
    status: 'Chờ xác nhận',
    orderStatus: 'pending',
    paymentMethod: 'cod',
    paymentStatus: 'pending'
  });

  await aw.pollAdminOrders();
  check('Admin phát hiện đơn mới theo ID và hiển thị thông báo trực quan Có N đơn mới', () => {
    const alertEl = aw.document.getElementById('new-orders-alert');
    const countEl = aw.document.getElementById('new-orders-count');
    const badgeEl = aw.document.getElementById('orders-new-badge');
    assert.equal(alertEl.hidden, false);
    assert.equal(countEl.textContent, '1');
    assert.equal(badgeEl.hidden, false);
    assert.equal(badgeEl.textContent, '1');
  });

  // 2. Bấm "Đã xem" ẩn cảnh báo đơn mới
  aw.document.getElementById('btn-dismiss-new-orders').click();
  check('Bấm ẩn cảnh báo đơn mới sẽ reset số lượng và ẩn badge', () => {
    assert.equal(aw.document.getElementById('new-orders-alert').hidden, true);
    assert.equal(aw.document.getElementById('orders-new-badge').hidden, true);
  });

  // 3. Giữ bộ lọc trạng thái khi tự cập nhật
  aw.document.getElementById('status-filter').value = 'delivered';
  aw.document.getElementById('status-filter').dispatchEvent(new aw.Event('change'));
  await aw.pollAdminOrders();
  check('Giữ nguyên bộ lọc trạng thái khi tự cập nhật đơn hàng admin', () => {
    assert.equal(aw.document.getElementById('status-filter').value, 'delivered');
  });
  aw.document.getElementById('status-filter').value = 'all';
  aw.document.getElementById('status-filter').dispatchEvent(new aw.Event('change'));

  // 4. Chuyển sang tab khác dừng polling đơn hàng admin
  aw.document.getElementById('products-tab').click();
  check('Chuyển sang tab khác dừng polling đơn hàng admin', () => {
    assert.equal(aw.getAdminOrdersPollTimer(), null);
  });

  // 5. Quay lại tab đơn hàng tự khôi phục polling ngay
  aw.document.getElementById('orders-tab').click();
  check('Quay lại tab đơn hàng admin tự khôi phục polling ngay', () => {
    assert.equal(aw.document.getElementById('orders-panel').hidden, false);
    assert.equal(aw.document.getElementById('orders-tab').classList.contains('active'), true);
  });

  // 6. Lỗi mạng admin: không xóa danh sách đơn và hiển thị cảnh báo kết nối
  const origAdminFetch = aw.fetch;
  aw.fetch = async (reqPath) => {
    if (reqPath === '/api/admin/orders') throw new TypeError('Network down');
    return origAdminFetch(reqPath);
  };
  await aw.pollAdminOrders();
  check('Lỗi mạng không xóa danh sách đơn admin và hiển thị cảnh báo kết nối', () => {
    assert.ok(aw.document.querySelectorAll('.order').length > 0);
    const conn = aw.document.getElementById('admin-order-conn-status');
    assert.equal(conn.hidden, false);
    assert.ok(conn.textContent.includes('Mất kết nối'));
  });
  aw.fetch = origAdminFetch;

  aw.stopAdminOrdersPolling();
  admin.window.close();
  console.log(`${passed} kiểm thử JavaScript/DOM PASS`);
}

run().catch(e => {
  console.error(e);
  process.exit(1);
});
