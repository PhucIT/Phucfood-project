"""Kiểm thử các ranh giới tiền, tài khoản và quyền truy cập bằng database kiểm thử MySQL (phuc_foodie_test)."""
import hashlib
import io
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import create_database_engine, init_schema
from server import create_app
from werkzeug.security import generate_password_hash

TEST_DB_CONFIG = {
    "TESTING": True,
    "MYSQL_DATABASE": "phuc_foodie_test",
    "SECRET_KEY": "test-only"
}

class FoodieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_database_engine(TEST_DB_CONFIG)
        init_schema(cls.engine, seed_products_if_empty=False)

    def setUp(self):
        # Dọn dẹp database test trước mỗi test case (chỉ thao tác trên phuc_foodie_test)
        with self.engine.begin() as conn:
            current_db = conn.execute(text("SELECT DATABASE()")).scalar()
            self.assertEqual(current_db, "phuc_foodie_test")
            conn.execute(text("DELETE FROM orders"))
            conn.execute(text("DELETE FROM sessions"))
            conn.execute(text("DELETE FROM user_identities"))
            conn.execute(text("DELETE FROM users"))
            conn.execute(text("DELETE FROM products"))
            conn.execute(text("DELETE FROM reset_tokens"))
            conn.execute(text("DELETE FROM rate_limits"))
            conn.execute(text("DELETE FROM delivery_zones"))
            conn.execute(text("ALTER TABLE user_identities AUTO_INCREMENT = 1"))
            conn.execute(text("ALTER TABLE users AUTO_INCREMENT = 1"))
            conn.execute(text("ALTER TABLE products AUTO_INCREMENT = 1"))
            conn.execute(text("ALTER TABLE delivery_zones AUTO_INCREMENT = 1"))
            default_sched_json = json.dumps({str(d): {"is_closed": False, "ranges": [{"open": "00:00", "close": "23:59"}]} for d in range(7)})
            conn.execute(
                text("UPDATE store_settings SET store_name = 'PHUC-FOODIE', address = '', phone = '', "
                     "is_paused = 0, pause_reason = '', delivery_time_min = NULL, delivery_time_max = NULL, "
                     "free_shipping_enabled = 1, free_shipping_threshold = 100000, default_shipping_fee = 15000, "
                     "schedule = :sched WHERE id = 1"),
                {"sched": default_sched_json}
            )

        # Seed 8 sản phẩm mẫu từ catalog.json vào database test với stock_quantity = 100
        catalog_path = Path(__file__).resolve().parents[1] / "catalog.json"
        items = json.loads(catalog_path.read_text(encoding="utf-8"))
        with self.engine.begin() as conn:
            for p in items:
                conn.execute(
                    text("INSERT INTO products (id, name, price, category, image, description, available, stock_quantity) "
                         "VALUES (:id, :name, :price, :category, :image, :description, 1, 100)"),
                    p
                )
            for name, email, phone, role in [
                ("Khách", "customer@example.test", "0900000001", "customer"),
                ("Chủ quán", "admin@example.test", "0900000002", "admin"),
                ("Khách khác", "other@example.test", "0900000003", "customer")
            ]:
                conn.execute(
                    text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                         "VALUES (:name, :email, :phone, :hash, :role)"),
                    {"name": name, "email": email, "phone": phone, "hash": generate_password_hash("TestPass!123"), "role": role}
                )

        self.app = create_app(TEST_DB_CONFIG)
        self.customer = self.app.test_client()
        self.admin = self.app.test_client()
        self.other = self.app.test_client()
        self.csrf = {}
        for c in [self.customer, self.other]:
            self.csrf[id(c)] = c.get("/api/session").json["csrfToken"]
        self.csrf[id(self.admin)] = self.admin.get("/api/admin/session").json["csrfToken"]
        for c, email in [(self.customer, "customer@example.test"), (self.other, "other@example.test")]:
            self.call(c, "POST", "/api/login", {"identifier": email, "password": "TestPass!123"})
        self.call(self.admin, "POST", "/api/admin/login", {"identifier": "admin@example.test", "password": "TestPass!123"})

    def call(self, c, method, path, data=None):
        r = c.open(path, method=method, json=data, headers={"X-CSRF-Token": self.csrf[id(c)]})
        if r.is_json and r.json.get("csrfToken"):
            self.csrf[id(c)] = r.json["csrfToken"]
        return r

    def order(self, **changes):
        p = {"requestKey": "request-unique-0000001", "items": [{"id": 1, "quantity": 1}], "customer": {"name": "Khách", "phone": "0900000001", "address": "123 đường kiểm thử", "note": ""}, "paymentMethod": "cod", "expectedTotal": 65000}
        p.update(changes)
        return p

    def place(self, **changes):
        return self.call(self.customer, "POST", "/api/orders", self.order(**changes))

    def test_registration_hash_and_role(self):
        r = self.call(self.customer, "POST", "/api/register", {"fullName": "Mới", "email": "new@example.test", "phone": "0900000004", "password": "SafePass!123", "terms": True, "role": "admin"})
        self.assertEqual(r.status_code, 201)
        with self.engine.connect() as conn:
            u = conn.execute(text("SELECT password_hash, role FROM users WHERE email='new@example.test'")).fetchone()
        self.assertNotEqual(u[0], "SafePass!123")
        self.assertEqual(u[1], "customer")

    def test_duplicate_registration(self):
        r = self.call(self.customer, "POST", "/api/register", {"fullName": "Mới", "email": "customer@example.test", "phone": "0900000004", "password": "SafePass!123", "terms": True})
        self.assertEqual(r.status_code, 409)

    def test_missing_csrf(self):
        self.assertEqual(self.customer.post("/api/logout", json={}).status_code, 403)

    def test_admin_denied(self):
        self.assertEqual(self.customer.get("/api/admin/orders").status_code, 403)
        self.assertEqual(self.call(self.customer, "PATCH", "/api/admin/products/1", {}).status_code, 403)

    def test_unauthorized_order(self):
        c = self.app.test_client()
        self.csrf[id(c)] = c.get("/api/session").json["csrfToken"]
        self.assertEqual(self.call(c, "POST", "/api/orders", self.order()).status_code, 401)

    def test_total_uses_server_prices(self):
        r = self.place(items=[{"id": 1, "quantity": 1, "price": 1}], totalPrice=1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["order"]["totalPrice"], 65000)

    def test_free_shipping_voucher(self):
        r = self.place(items=[{"id": 1, "quantity": 2}], voucherCode="FOOD20", expectedTotal=80000)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["order"]["shippingFee"], 0)
        self.assertEqual(r.json["order"]["discountAmount"], 20000)

    def test_voucher_minimum(self):
        self.assertEqual(self.place(voucherCode="FOOD20").status_code, 400)

    def test_no_payment(self):
        self.assertEqual(self.place(paymentMethod=None).status_code, 400)

    def test_demo_explicit_confirmation(self):
        self.assertEqual(self.place(paymentMethod="qr_demo").status_code, 400)
        r = self.place(paymentMethod="qr_demo", demoConfirmed=True)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["order"]["paymentStatus"], "demo_confirmed")

    def test_invalid_quantity_and_duplicate(self):
        for qty in [-1, 0, 100, 1.5, True]:
            self.assertEqual(self.place(items=[{"id": 1, "quantity": qty}]).status_code, 400)
        self.assertEqual(self.place(items=[{"id": 1, "quantity": 1}, {"id": 1, "quantity": 1}]).status_code, 400)

    def test_out_of_stock_and_price_change(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET available=0 WHERE id=1"))
        self.assertEqual(self.place().status_code, 409)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET available=1, price=55000 WHERE id=1"))
        self.assertEqual(self.place().status_code, 409)

    def test_idempotent_retry(self):
        a = self.place()
        b = self.place()
        self.assertEqual(a.json["order"]["id"], b.json["order"]["id"])
        self.assertEqual(len(self.customer.get("/api/orders").json["orders"]), 1)

    def test_customer_isolation(self):
        oid = self.place().json["order"]["id"]
        self.assertEqual(self.other.get("/api/orders").json["orders"], [])
        self.assertEqual(self.call(self.other, "POST", f"/api/orders/{oid}/cancel", {}).status_code, 409)

    def test_order_transitions_and_cod_paid(self):
        oid = self.place().json["order"]["id"]
        path = f"/api/admin/orders/{oid}"
        self.assertEqual(self.call(self.admin, "PATCH", path, {"state": "delivered"}).status_code, 409)
        for state in ["confirmed", "preparing", "delivering", "delivered"]:
            self.assertEqual(self.call(self.admin, "PATCH", path, {"state": state}).status_code, 200)
        order = self.customer.get("/api/orders").json["orders"][0]
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertEqual(self.call(self.admin, "PATCH", path, {"state": "pending"}).status_code, 409)

    def test_demo_not_recorded_as_paid(self):
        oid = self.place(paymentMethod="bank_transfer", demoConfirmed=True).json["order"]["id"]
        for state in ["confirmed", "preparing", "delivering", "delivered"]:
            self.call(self.admin, "PATCH", f"/api/admin/orders/{oid}", {"state": state})
        self.assertEqual(self.customer.get("/api/orders").json["orders"][0]["paymentStatus"], "demo_confirmed")

    def test_customer_cancel_only_pending(self):
        oid = self.place().json["order"]["id"]
        self.assertEqual(self.call(self.customer, "POST", f"/api/orders/{oid}/cancel", {}).status_code, 200)
        self.assertEqual(self.call(self.customer, "POST", f"/api/orders/{oid}/cancel", {}).status_code, 409)
        second = self.place(requestKey="request-unique-0000002").json["order"]["id"]
        self.call(self.admin, "PATCH", f"/api/admin/orders/{second}", {"state": "confirmed"})
        self.assertEqual(self.call(self.customer, "POST", f"/api/orders/{second}/cancel", {}).status_code, 409)

    def test_logout_revokes_session(self):
        cookie = (self.customer.get_cookie("foodie_customer_session") or self.customer.get_cookie("session")).value
        self.call(self.customer, "POST", "/api/logout", {})
        self.customer.set_cookie("foodie_customer_session", cookie)
        self.assertEqual(self.customer.get("/api/orders").status_code, 401)

    def test_password_reset_not_demo(self):
        with patch.dict(os.environ, {}, clear=True):
            r = self.call(self.customer, "POST", "/api/password/forgot", {"email": "customer@example.test"})
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("code", r.json)

    def test_reset_single_use_expiry_revokes(self):
        email = "customer@example.test"
        code = "654321"
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO reset_tokens (email, token_hash, expires, attempts) VALUES (:email, :hash, :exp, 0) "
                     "ON DUPLICATE KEY UPDATE token_hash=:hash, expires=:exp, attempts=0"),
                {"email": email, "hash": hashlib.sha256((email + code).encode()).hexdigest(), "exp": time.time() + 600}
            )
        p = {"email": email, "code": code, "password": "NewPass!123"}
        self.assertEqual(self.call(self.customer, "POST", "/api/password/reset", p).status_code, 200)
        self.assertEqual(self.customer.get("/api/orders").status_code, 401)
        self.assertEqual(self.call(self.customer, "POST", "/api/password/reset", p).status_code, 400)
        r = self.call(self.customer, "POST", "/api/login", {"identifier": email, "password": "NewPass!123"})
        self.assertEqual(r.status_code, 200)

    def test_admin_product_validation(self):
        p = {"name": "Món mới", "price": 25000, "category": "Đồ ăn", "image": "images/burger.jpg", "description": "Mô tả", "available": True}
        r = self.call(self.admin, "POST", "/api/admin/products", p)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.call(self.admin, "PATCH", f'/api/admin/products/{r.json["id"]}', {**p, "available": False}).status_code, 200)
        self.assertEqual(self.call(self.admin, "POST", "/api/admin/products", {**p, "image": "javascript:alert(1)"}).status_code, 400)

    def test_static_does_not_expose_database_or_source(self):
        for path in ["/data/foodie.db", "/server.py", "/catalog.json", "/requirements.txt", "/images/../server.py"]:
            self.assertEqual(self.customer.get(path).status_code, 404)
        for path in ["/", "/admin"]:
            response = self.customer.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_data_persists_restart(self):
        oid = self.place().json["order"]["id"]
        other_app = create_app(TEST_DB_CONFIG)
        c = other_app.test_client()
        cookie = (self.customer.get_cookie("foodie_customer_session") or self.customer.get_cookie("session")).value
        c.set_cookie("foodie_customer_session", cookie)
        self.assertEqual(c.get("/api/orders").json["orders"][0]["id"], oid)

    def test_rate_limit(self):
        for i in range(15):
            r = self.call(self.other, "POST", "/api/login", {"identifier": "no@example.test", "password": "bad"})
        self.assertEqual(r.status_code, 429)

    def test_parallel_customer_and_admin_sessions(self):
        # 1. Khởi tạo một client duy nhất với cùng cookie jar (mô phỏng 1 trình duyệt duy nhất mở 2 tab)
        browser = self.app.test_client()

        # 2. Lấy CSRF ban đầu của từng khu vực
        cust_csrf = browser.get("/api/session").json["csrfToken"]
        adm_csrf = browser.get("/api/admin/session").json["csrfToken"]

        # Chưa đăng nhập: cả hai đều None
        self.assertIsNone(browser.get("/api/session").json["user"])
        self.assertIsNone(browser.get("/api/admin/session").json["user"])

        # 3. Đăng nhập khách trước
        r_cust = browser.post(
            "/api/login",
            json={"identifier": "customer@example.test", "password": "TestPass!123"},
            headers={"X-CSRF-Token": cust_csrf}
        )
        self.assertEqual(r_cust.status_code, 200)
        cust_csrf = r_cust.json["csrfToken"]
        self.assertEqual(browser.get("/api/session").json["user"]["email"], "customer@example.test")

        # 4. Đăng nhập admin bằng tài khoản khách: PHẢI TỪ CHỐI 403 và KHÔNG làm mất phiên khách
        r_fail = browser.post(
            "/api/admin/login",
            json={"identifier": "customer@example.test", "password": "TestPass!123"},
            headers={"X-CSRF-Token": adm_csrf}
        )
        self.assertEqual(r_fail.status_code, 403)
        # Phiên khách vẫn còn nguyên vẹn
        self.assertEqual(browser.get("/api/session").json["user"]["email"], "customer@example.test")

        # 5. Đăng nhập admin bằng tài khoản admin chính xác
        r_adm = browser.post(
            "/api/admin/login",
            json={"identifier": "admin@example.test", "password": "TestPass!123"},
            headers={"X-CSRF-Token": adm_csrf}
        )
        self.assertEqual(r_adm.status_code, 200)
        adm_csrf = r_adm.json["csrfToken"]

        # 6. Kiểm tra CẢ HAI PHIÊN CÙNG TỒN TẠI trong cùng một trình duyệt
        cust_res = browser.get("/api/session").json
        adm_res = browser.get("/api/admin/session").json
        self.assertEqual(cust_res["user"]["email"], "customer@example.test")
        self.assertEqual(adm_res["user"]["email"], "admin@example.test")

        # Tải lại hai trang: phiên vẫn được giữ nguyên
        self.assertEqual(browser.get("/api/session").json["user"]["role"], "customer")
        self.assertEqual(browser.get("/api/admin/session").json["user"]["role"], "admin")

        # 7. Khách đặt đơn, admin đọc và xử lý được đơn
        order_payload = self.order(requestKey="request-parallel-0001")
        r_order = browser.post("/api/orders", json=order_payload, headers={"X-CSRF-Token": cust_csrf})
        self.assertEqual(r_order.status_code, 201)
        oid = r_order.json["order"]["id"]

        # Admin đọc đơn qua API quản trị
        adm_orders = browser.get("/api/admin/orders")
        self.assertEqual(adm_orders.status_code, 200)
        self.assertTrue(any(o["id"] == oid for o in adm_orders.json["orders"]))

        # Admin xử lý chuyển trạng thái đơn sang confirmed
        r_patch = browser.patch(
            f"/api/admin/orders/{oid}",
            json={"state": "confirmed"},
            headers={"X-CSRF-Token": adm_csrf}
        )
        self.assertEqual(r_patch.status_code, 200)

        # Khách xem lại đơn: trạng thái đã là confirmed
        my_orders = browser.get("/api/orders").json["orders"]
        matched = [o for o in my_orders if o["id"] == oid]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["orderStatus"], "confirmed")

        # 8. Kiểm tra phân quyền chéo:
        # Phiên admin không thể tự động dùng thay phiên khách khi khách chưa có phiên
        fresh_admin_only = self.app.test_client()
        fresh_adm_csrf = fresh_admin_only.get("/api/admin/session").json["csrfToken"]
        fresh_admin_only.post("/api/admin/login", json={"identifier": "admin@example.test", "password": "TestPass!123"}, headers={"X-CSRF-Token": fresh_adm_csrf})
        self.assertEqual(fresh_admin_only.get("/api/orders").status_code, 401)

        # CSRF khu vực này không dùng được cho khu vực kia
        self.assertEqual(browser.patch(f"/api/admin/orders/{oid}", json={"state": "preparing"}, headers={"X-CSRF-Token": cust_csrf}).status_code, 403)
        self.assertEqual(browser.post("/api/orders", json=self.order(requestKey="request-parallel-0002"), headers={"X-CSRF-Token": adm_csrf}).status_code, 403)

        # 9. Đăng xuất khách: admin vẫn hoạt động bình thường
        r_logout_cust = browser.post("/api/logout", json={}, headers={"X-CSRF-Token": cust_csrf})
        self.assertEqual(r_logout_cust.status_code, 200)
        self.assertIsNone(browser.get("/api/session").json["user"])
        # Admin vẫn còn phiên hoạt động
        self.assertEqual(browser.get("/api/admin/session").json["user"]["email"], "admin@example.test")
        self.assertEqual(browser.get("/api/admin/orders").status_code, 200)

        # 10. Đăng xuất admin: admin bị thu hồi
        r_logout_adm = browser.post("/api/admin/logout", json={}, headers={"X-CSRF-Token": adm_csrf})
        self.assertEqual(r_logout_adm.status_code, 200)
        self.assertIsNone(browser.get("/api/admin/session").json["user"])
        self.assertEqual(browser.get("/api/admin/orders").status_code, 401)

    def _create_dummy_image(self, fmt="PNG", size=(100, 100), color="red"):
        buf = io.BytesIO()
        img = Image.new("RGB", size, color=color)
        img.save(buf, format=fmt)
        buf.seek(0)
        return buf

    def test_admin_upload_image_and_security(self):
        # 1. Upload ảnh PNG hợp lệ bởi admin -> 201
        valid_buf = self._create_dummy_image(fmt="PNG")
        res = self.admin.post(
            "/api/admin/upload",
            data={"file": (valid_buf, "test_pic.png")},
            headers={"X-CSRF-Token": self.csrf[id(self.admin)]},
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("image", res.json)
        uploaded_path = res.json["image"]
        self.assertTrue(uploaded_path.startswith("uploads/"))
        # Kiểm tra ảnh có thể xem được qua GET /uploads/...
        img_res = self.customer.get("/" + uploaded_path)
        self.assertEqual(img_res.status_code, 200)
        img_res.close()

        # 2. Khách tải ảnh lên -> 403
        guest_buf = self._create_dummy_image()
        res_guest = self.customer.post(
            "/api/admin/upload",
            data={"file": (guest_buf, "guest.png")},
            headers={"X-CSRF-Token": self.csrf[id(self.customer)]},
            content_type="multipart/form-data"
        )
        self.assertEqual(res_guest.status_code, 403)

        # 3. File giả ảnh (file text đổi đuôi .png) -> 400
        fake_buf = io.BytesIO(b"Not an image file content at all")
        res_fake = self.admin.post(
            "/api/admin/upload",
            data={"file": (fake_buf, "fake.png")},
            headers={"X-CSRF-Token": self.csrf[id(self.admin)]},
            content_type="multipart/form-data"
        )
        self.assertEqual(res_fake.status_code, 400)

        # 4. File SVG hoặc thực thi -> 400
        svg_buf = io.BytesIO(b"<svg><circle cx='50' cy='50' r='40'/></svg>")
        res_svg = self.admin.post(
            "/api/admin/upload",
            data={"file": (svg_buf, "vector.svg")},
            headers={"X-CSRF-Token": self.csrf[id(self.admin)]},
            content_type="multipart/form-data"
        )
        self.assertEqual(res_svg.status_code, 400)

    def test_admin_add_and_update_product_inventory(self):
        # 1. Khách thử thêm món -> 403
        r_guest = self.call(self.customer, "POST", "/api/admin/products", {
            "name": "Món lậu", "price": 50000, "category": "Đồ ăn", "image": "images/burger.jpg",
            "description": "Thử hack", "available": True, "stock_quantity": 10
        })
        self.assertEqual(r_guest.status_code, 403)

        # 2. Admin thêm món thành công với ảnh upload và tồn kho 25
        valid_buf = self._create_dummy_image()
        up_res = self.admin.post(
            "/api/admin/upload",
            data={"file": (valid_buf, "dish.png")},
            headers={"X-CSRF-Token": self.csrf[id(self.admin)]},
            content_type="multipart/form-data"
        )
        saved_img = up_res.json["image"]

        add_res = self.call(self.admin, "POST", "/api/admin/products", {
            "name": "Bánh mì nướng bơ tỏi", "price": 35000, "category": "Đồ ăn",
            "image": saved_img, "description": "Thơm lừng giòn rụm",
            "available": True, "stock_quantity": 25
        })
        self.assertEqual(add_res.status_code, 201)
        new_pid = add_res.json["id"]

        # Kiểm tra món xuất hiện trong API danh sách món
        prod_list = self.customer.get("/api/products").json["products"]
        matched = [p for p in prod_list if p["id"] == new_pid][0]
        self.assertEqual(matched["name"], "Bánh mì nướng bơ tỏi")
        self.assertEqual(matched["stock_quantity"], 25)
        self.assertEqual(matched["available"], 1)

        # 3. Sửa món mà không gửi trường image -> giữ nguyên ảnh cũ
        edit_res = self.call(self.admin, "PATCH", f"/api/admin/products/{new_pid}", {
            "name": "Bánh mì nướng bơ tỏi đặc biệt", "price": 40000, "stock_quantity": 30
        })
        self.assertEqual(edit_res.status_code, 200)

        updated_p = [p for p in self.customer.get("/api/products").json["products"] if p["id"] == new_pid][0]
        self.assertEqual(updated_p["name"], "Bánh mì nướng bơ tỏi đặc biệt")
        self.assertEqual(updated_p["price"], 40000)
        self.assertEqual(updated_p["image"], saved_img)  # Giữ ảnh cũ
        self.assertEqual(updated_p["stock_quantity"], 30)

        # 4. Bật/tắt bán nhanh
        toggle_res = self.call(self.admin, "PATCH", f"/api/admin/products/{new_pid}", {"available": False})
        self.assertEqual(toggle_res.status_code, 200)
        toggled_p = [p for p in self.customer.get("/api/products").json["products"] if p["id"] == new_pid][0]
        self.assertEqual(toggled_p["available"], 0)

    def test_inventory_deduction_and_stock_boundaries(self):
        # Thiết lập món 1 có tồn kho = 3, available = 1
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET stock_quantity = 3, available = 1 WHERE id = 1"))

        # 1. Khách đặt 2 phần món 1 -> thành công, còn lại 1 phần
        r1 = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-1",
            items=[{"id": 1, "quantity": 2}],
            expectedTotal=100000
        ))
        self.assertEqual(r1.status_code, 201)

        with self.engine.connect() as conn:
            sq = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq, 1)

        # 2. Gửi lại đơn cũ cùng requestKey -> không trừ kho lần thứ 2
        r1_retry = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-1",
            items=[{"id": 1, "quantity": 2}],
            expectedTotal=100000
        ))
        self.assertEqual(r1_retry.status_code, 200)
        with self.engine.connect() as conn:
            sq_after_retry = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_after_retry, 1)

        # 3. Khách đặt quá số lượng tồn còn lại (yêu cầu 2 phần khi kho chỉ còn 1) -> 409
        r_over = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-over",
            items=[{"id": 1, "quantity": 2}],
            expectedTotal=100000
        ))
        self.assertEqual(r_over.status_code, 409)

        # 4. Khách đặt đúng 1 phần còn lại -> thành công, kho về 0
        r_last = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-last",
            items=[{"id": 1, "quantity": 1}],
            expectedTotal=65000
        ))
        self.assertEqual(r_last.status_code, 201)
        with self.engine.connect() as conn:
            sq_zero = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_zero, 0)

        # 5. Khách khác đặt khi kho đã = 0 -> 409
        r_empty = self.call(self.other, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-empty",
            items=[{"id": 1, "quantity": 1}],
            expectedTotal=65000
        ))
        self.assertEqual(r_empty.status_code, 409)

        # 6. Món cũ chưa thiết lập tồn kho (stock_quantity = NULL) -> từ chối 409
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET stock_quantity = NULL WHERE id = 2"))
        r_null_stock = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-null",
            items=[{"id": 2, "quantity": 1}],
            expectedTotal=75000
        ))
        self.assertEqual(r_null_stock.status_code, 409)

        # 7. Món tắt bán (available = 0) dù có tồn kho -> từ chối 409
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET stock_quantity = 50, available = 0 WHERE id = 3"))
        r_disabled = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-stock-order-disabled",
            items=[{"id": 3, "quantity": 1}],
            expectedTotal=60000
        ))
        self.assertEqual(r_disabled.status_code, 409)

    def test_inventory_multi_item_atomic_rollback(self):
        # Món 1 có 5 phần, món 2 có 1 phần
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET stock_quantity = 5, available = 1 WHERE id = 1"))
            conn.execute(text("UPDATE products SET stock_quantity = 1, available = 1 WHERE id = 2"))

        # Đơn yêu cầu món 1: 2 phần, món 2: 3 phần (món 2 bị thiếu)
        r = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-atomic-fail-0001",
            items=[{"id": 1, "quantity": 2}, {"id": 2, "quantity": 3}],
            expectedTotal=280000
        ))
        self.assertEqual(r.status_code, 409)

        # Kiểm tra rollback toàn bộ: món 1 vẫn nguyên 5 phần, món 2 vẫn nguyên 1 phần
        with self.engine.connect() as conn:
            sq1 = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
            sq2 = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 2")).scalar()
        self.assertEqual(sq1, 5)
        self.assertEqual(sq2, 1)

    def test_inventory_restoration_on_cancel(self):
        # Món 1 có tồn 10 phần
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE products SET stock_quantity = 10, available = 1 WHERE id = 1"))

        # 1. Khách đặt 4 phần -> tồn còn 6
        r_order = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-cancel-stock-1",
            items=[{"id": 1, "quantity": 4}],
            expectedTotal=200000
        ))
        self.assertEqual(r_order.status_code, 201)
        oid = r_order.json["order"]["id"]

        with self.engine.connect() as conn:
            sq_after = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_after, 6)

        # 2. Khách hủy đơn -> hoàn kho lại đúng 4 phần (tồn trở lại 10)
        r_cancel = self.call(self.customer, "POST", f"/api/orders/{oid}/cancel", {})
        self.assertEqual(r_cancel.status_code, 200)

        with self.engine.connect() as conn:
            sq_restored = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_restored, 10)

        # 3. Gửi lại yêu cầu hủy đơn đã hủy -> từ chối 409, kho không cộng lần 2
        r_cancel_again = self.call(self.customer, "POST", f"/api/orders/{oid}/cancel", {})
        self.assertEqual(r_cancel_again.status_code, 409)

        with self.engine.connect() as conn:
            sq_no_double = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_no_double, 10)

        # 4. Hủy đơn lịch sử cũ (stock_deducted = 0) -> KHÔNG hoàn kho
        old_order_id = "PF-OLD-TEST-ORDER"
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO orders (id, user_id, payload, created_at, request_key, state, stock_deducted) "
                     "VALUES (:id, 1, :payload, '2026-01-01T00:00:00', 'old-order-key', 'pending', 0)"),
                {
                    "id": old_order_id,
                    "payload": json.dumps({"items": [{"id": 1, "quantity": 5}]})
                }
            )

        r_cancel_old = self.call(self.customer, "POST", f"/api/orders/{old_order_id}/cancel", {})
        self.assertEqual(r_cancel_old.status_code, 200)

        # Tồn kho vẫn là 10 (không được tự động cộng 5 phần của đơn cũ chưa từng trừ)
        with self.engine.connect() as conn:
            sq_after_old_cancel = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_after_old_cancel, 10)

        # 5. Admin hủy đơn đã trừ kho -> hoàn kho chính xác
        r_order_adm = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="key-admin-cancel-stock",
            items=[{"id": 1, "quantity": 3}],
            expectedTotal=150000
        ))
        self.assertEqual(r_order_adm.status_code, 201)
        adm_oid = r_order_adm.json["order"]["id"]

        r_adm_cancel = self.admin.patch(
            f"/api/admin/orders/{adm_oid}",
            json={"state": "cancelled"},
            headers={"X-CSRF-Token": self.csrf[id(self.admin)]}
        )
        self.assertEqual(r_adm_cancel.status_code, 200)

        with self.engine.connect() as conn:
            sq_final = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq_final, 10)

    def test_store_settings_permissions_and_csrf(self):
        """1. Chỉ admin sửa được cấu hình, CSRF sai bị chặn, lưu và đọc lại sau khi cập nhật."""
        guest = self.app.test_client()
        # Khách vãng lai không thể sửa
        r_guest = guest.patch("/api/admin/store/settings", json={"storeName": "Hacker Store"})
        self.assertIn(r_guest.status_code, (401, 403))

        # Khách hàng đã đăng nhập không thể sửa
        r_cust = self.customer.patch("/api/admin/store/settings", json={"storeName": "Customer Store"},
                                     headers={"X-CSRF-Token": self.csrf[id(self.customer)]})
        self.assertEqual(r_cust.status_code, 403)

        # Admin không có CSRF token bị chặn 403
        r_no_csrf = self.admin.patch("/api/admin/store/settings", json={"storeName": "No CSRF Store"})
        self.assertEqual(r_no_csrf.status_code, 403)

        # Admin gửi đầy đủ CSRF token -> Thành công
        admin_csrf = self.csrf[id(self.admin)]
        r_admin = self.admin.patch(
            "/api/admin/store/settings",
            json={
                "storeName": "PHUC-FOODIE Sài Gòn",
                "phone": "0901234567",
                "address": "123 Đường 3/2, Quận 10",
                "deliveryTimeMin": 25,
                "deliveryTimeMax": 40,
                "freeShippingEnabled": True,
                "freeShippingThreshold": 150000
            },
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.assertEqual(r_admin.status_code, 200)

        # Khách đọc qua public API /api/store-info
        r_info = guest.get("/api/store-info")
        self.assertEqual(r_info.status_code, 200)
        data = r_info.json
        self.assertEqual(data["storeName"], "PHUC-FOODIE Sài Gòn")
        self.assertEqual(data["phone"], "0901234567")
        self.assertEqual(data["address"], "123 Đường 3/2, Quận 10")
        self.assertEqual(data["deliveryTimeMin"], 25)
        self.assertEqual(data["deliveryTimeMax"], 40)
        self.assertEqual(data["deliveryTimeText"], "25 - 40 phút (ước tính)")
        self.assertEqual(data["freeShippingThreshold"], 150000)

    def test_schedule_boundary_and_overnight(self):
        """2. Lịch từng ngày, ngày nghỉ, nhiều khoảng giờ và qua nửa đêm tại ranh giới giờ mở/đóng."""
        from server import check_store_open
        from zoneinfo import ZoneInfo
        from datetime import datetime

        # Lịch mẫu: Thứ 2 (day 0) mở 08:00 - 12:00 và 17:00 - 22:00
        # Thứ 6 (day 4) mở ca tối qua nửa đêm 18:00 - 02:00 (rạng sáng Thứ 7 - day 5)
        # Chủ Nhật (day 6) nghỉ cả ngày
        test_schedule = {
            "0": {"is_closed": False, "ranges": [{"open": "08:00", "close": "12:00"}, {"open": "17:00", "close": "22:00"}]},
            "1": {"is_closed": False, "ranges": [{"open": "09:00", "close": "21:00"}]},
            "2": {"is_closed": False, "ranges": [{"open": "09:00", "close": "21:00"}]},
            "3": {"is_closed": False, "ranges": [{"open": "09:00", "close": "21:00"}]},
            "4": {"is_closed": False, "ranges": [{"open": "18:00", "close": "02:00"}]},
            "5": {"is_closed": False, "ranges": [{"open": "10:00", "close": "22:00"}]},
            "6": {"is_closed": True, "ranges": []}
        }
        tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # 2.1 Thứ 2: Ranh giới ca sáng 08:00 - 12:00
        t_before_open = datetime(2026, 10, 12, 7, 59, 59, tzinfo=tz) # Thứ 2 07:59
        t_at_open = datetime(2026, 10, 12, 8, 0, 0, tzinfo=tz)      # Thứ 2 08:00
        t_mid_morning = datetime(2026, 10, 12, 10, 30, 0, tzinfo=tz)# Thứ 2 10:30
        t_at_close1 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=tz)   # Thứ 2 12:00 (đóng)
        t_break_time = datetime(2026, 10, 12, 14, 0, 0, tzinfo=tz)  # Thứ 2 14:00 (nghỉ trưa)

        self.assertFalse(check_store_open(test_schedule, t_before_open)[0])
        self.assertTrue(check_store_open(test_schedule, t_at_open)[0])
        self.assertTrue(check_store_open(test_schedule, t_mid_morning)[0])
        self.assertFalse(check_store_open(test_schedule, t_at_close1)[0])
        self.assertFalse(check_store_open(test_schedule, t_break_time)[0])

        # 2.2 Thứ 2: Ca chiều 17:00 - 22:00
        t_open2 = datetime(2026, 10, 12, 17, 0, 0, tzinfo=tz)       # Thứ 2 17:00
        t_before_close2 = datetime(2026, 10, 12, 21, 59, 59, tzinfo=tz) # Thứ 2 21:59
        t_at_close2 = datetime(2026, 10, 12, 22, 0, 0, tzinfo=tz)   # Thứ 2 22:00 (đóng)

        self.assertTrue(check_store_open(test_schedule, t_open2)[0])
        self.assertTrue(check_store_open(test_schedule, t_before_close2)[0])
        self.assertFalse(check_store_open(test_schedule, t_at_close2)[0])

        # 2.3 Thứ 6 qua nửa đêm: 18:00 Thứ 6 -> 02:00 Thứ 7
        t_fri_before = datetime(2026, 10, 16, 17, 59, tzinfo=tz)    # Thứ 6 17:59 (chưa mở)
        t_fri_open = datetime(2026, 10, 16, 18, 0, tzinfo=tz)       # Thứ 6 18:00 (bắt đầu mở)
        t_fri_midnight = datetime(2026, 10, 16, 23, 59, tzinfo=tz)  # Thứ 6 23:59 (đang mở)
        t_sat_early1 = datetime(2026, 10, 17, 0, 30, tzinfo=tz)     # Thứ 7 00:30 (ca đêm tiếp tục)
        t_sat_before_end = datetime(2026, 10, 17, 1, 59, tzinfo=tz) # Thứ 7 01:59 (đang mở)
        t_sat_at_end = datetime(2026, 10, 17, 2, 0, tzinfo=tz)      # Thứ 7 02:00 (hết ca đêm -> đóng)
        t_sat_after_night = datetime(2026, 10, 17, 5, 0, tzinfo=tz) # Thứ 7 05:00 (chưa đến ca sáng 10:00)

        self.assertFalse(check_store_open(test_schedule, t_fri_before)[0])
        self.assertTrue(check_store_open(test_schedule, t_fri_open)[0])
        self.assertTrue(check_store_open(test_schedule, t_fri_midnight)[0])
        self.assertTrue(check_store_open(test_schedule, t_sat_early1)[0])
        self.assertTrue(check_store_open(test_schedule, t_sat_before_end)[0])
        self.assertFalse(check_store_open(test_schedule, t_sat_at_end)[0])
        self.assertFalse(check_store_open(test_schedule, t_sat_after_night)[0])

        # 2.4 Chủ Nhật nghỉ cả ngày (day 6)
        t_sun = datetime(2026, 10, 18, 12, 0, tzinfo=tz)
        self.assertFalse(check_store_open(test_schedule, t_sun)[0])

    def test_pause_status_priority_over_schedule(self):
        """3. Tạm ngừng nhận đơn có ưu tiên cao hơn lịch mở cửa; chặn đặt đơn và không trừ kho."""
        guest = self.app.test_client()
        admin_csrf = self.csrf[id(self.admin)]
        # Bật tạm ngừng nhận đơn
        r_pause = self.admin.patch(
            "/api/admin/store/settings",
            json={"isPaused": True, "pauseReason": "Quán đang quá tải đơn, xin quay lại sau."},
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.assertEqual(r_pause.status_code, 200)

        # Public API báo status = paused
        r_info = guest.get("/api/store-info")
        self.assertEqual(r_info.json["status"], "paused")
        self.assertFalse(r_info.json["isOpen"])
        self.assertEqual(r_info.json["pauseReason"], "Quán đang quá tải đơn, xin quay lại sau.")

        # Khách vẫn xem được menu
        r_menu = guest.get("/api/products")
        self.assertEqual(r_menu.status_code, 200)
        self.assertGreater(len(r_menu.json["products"]), 0)

        # Đặt đơn bị chặn 409
        r_order = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="pause-test-key-12345",
            items=[{"id": 1, "quantity": 2}],
            expectedTotal=115000
        ))
        self.assertEqual(r_order.status_code, 409)
        self.assertIn("quá tải", r_order.json["error"])

        # Tồn kho không bị trừ
        with self.engine.connect() as conn:
            sq = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq, 100)

    def test_delivery_zones_management_and_order_flow(self):
        """4. Quản lý khu vực giao hàng, chặn xóa khu vực đã dùng trong đơn, kiểm tra khu vực bị tắt."""
        admin_csrf = self.csrf[id(self.admin)]

        # 4.1 Tạo 2 khu vực: Quận 1 (20k, active) và Quận 7 (35k, inactive)
        r_z1 = self.admin.post(
            "/api/admin/delivery-zones",
            json={"name": "Quận 1", "fee": 20000, "isActive": True},
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.assertEqual(r_z1.status_code, 201)
        z1_id = r_z1.json["id"]

        r_z2 = self.admin.post(
            "/api/admin/delivery-zones",
            json={"name": "Quận 7", "fee": 35000, "isActive": False},
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.assertEqual(r_z2.status_code, 201)
        z2_id = r_z2.json["id"]

        # 4.2 Khách đặt đơn không chọn khu vực -> Bị từ chối 400
        r_err_no_zone = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="zone-missing-key",
            items=[{"id": 1, "quantity": 1}],
            deliveryZoneId=None,
            expectedTotal=70000
        ))
        self.assertEqual(r_err_no_zone.status_code, 400)
        self.assertIn("khu vực", r_err_no_zone.json["error"].lower())

        # 4.3 Khách chọn khu vực đang bị tắt (Quận 7) -> Bị từ chối 400
        r_err_inactive = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="zone-inactive-key",
            items=[{"id": 1, "quantity": 1}],
            deliveryZoneId=z2_id,
            expectedTotal=85000
        ))
        self.assertEqual(r_err_inactive.status_code, 400)

        # 4.4 Khách chọn khu vực hợp lệ (Quận 1, phí 20k, subtotal 50k < 100k -> Tổng 70k)
        r_ok = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="zone-valid-key-12345",
            items=[{"id": 1, "quantity": 1}],
            deliveryZoneId=z1_id,
            expectedTotal=70000
        ))
        self.assertEqual(r_ok.status_code, 201)
        self.assertEqual(r_ok.json["order"]["deliveryZoneName"], "Quận 1")
        self.assertEqual(r_ok.json["order"]["shippingFee"], 20000)

        # 4.5 Admin cố xóa Quận 1 (đã có đơn sử dụng) -> Bị từ chối 400
        r_del_err = self.admin.delete(f"/api/admin/delivery-zones/{z1_id}", headers={"X-CSRF-Token": admin_csrf})
        self.assertEqual(r_del_err.status_code, 400)
        self.assertIn("tắt nhận giao thay vì xóa", r_del_err.json["error"])

        # 4.6 Tắt nhận giao Quận 1 -> Lúc này TẤT CẢ các khu vực đều bị tắt
        r_toggle = self.admin.patch(
            f"/api/admin/delivery-zones/{z1_id}",
            json={"isActive": False},
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.assertEqual(r_toggle.status_code, 200)

        # Khách cố đặt đơn khi tất cả khu vực bị tắt -> Bị từ chối 409
        r_all_off = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="zone-all-off-key",
            items=[{"id": 1, "quantity": 1}],
            deliveryZoneId=z1_id,
            expectedTotal=70000
        ))
        self.assertEqual(r_all_off.status_code, 409)
        self.assertIn("tất cả các khu vực", r_all_off.json["error"])

    def test_free_shipping_rules_and_voucher_interaction(self):
        """5. Phí giao và ngưỡng miễn phí: dưới/bằng/trên ngưỡng và bảo toàn tính trên subtotal trước voucher."""
        admin_csrf = self.csrf[id(self.admin)]
        # Cấu hình phí mặc định 15k, miễn phí từ 100k
        self.admin.patch(
            "/api/admin/store/settings",
            json={"freeShippingEnabled": True, "freeShippingThreshold": 100000},
            headers={"X-CSRF-Token": admin_csrf}
        )

        # 5.1 Đơn dưới ngưỡng (1 phần burger 50k < 100k) -> Phí 15k, Tổng 65k
        r_below = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="free-ship-below-key",
            items=[{"id": 1, "quantity": 1}],
            expectedTotal=65000
        ))
        self.assertEqual(r_below.status_code, 201)
        self.assertEqual(r_below.json["order"]["shippingFee"], 15000)
        self.assertEqual(r_below.json["order"]["totalPrice"], 65000)

        # 5.2 Đơn bằng ngưỡng (2 phần burger = 100k) -> Miễn phí giao 0đ, Tổng 100k
        r_exact = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="free-ship-exact-key",
            items=[{"id": 1, "quantity": 2}],
            expectedTotal=100000
        ))
        self.assertEqual(r_exact.status_code, 201)
        self.assertEqual(r_exact.json["order"]["shippingFee"], 0)
        self.assertEqual(r_exact.json["order"]["totalPrice"], 100000)

        # 5.3 Đơn trên ngưỡng có áp voucher:
        # 1 pizza (120k) -> Subtotal 120k >= 100k -> Miễn phí giao 0đ
        # Áp voucher FOOD20 (giảm 20% của 120k = 24k) -> Tổng = 120k - 24k = 96k
        # Chú ý: Sau voucher tổng chỉ còn 96k (< 100k), nhưng vẫn ĐƯỢC MIỄN PHÍ GIAO HÀNG vì tính trên tiền món (subtotal)!
        r_voucher = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="free-ship-voucher-key",
            items=[{"id": 2, "quantity": 2}],
            voucherCode="FOOD20",
            expectedTotal=96000
        ))
        self.assertEqual(r_voucher.status_code, 201)
        self.assertEqual(r_voucher.json["order"]["shippingFee"], 0)
        self.assertEqual(r_voucher.json["order"]["discountAmount"], 24000)
        self.assertEqual(r_voucher.json["order"]["totalPrice"], 96000)

        # 5.4 Client giả mạo expectedTotal -> Server từ chối 409
        r_fake_total = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey="free-ship-fake-key",
            items=[{"id": 1, "quantity": 1}],
            expectedTotal=50000 # Server tính ra 65000 (50k + 15k ship)
        ))
        self.assertEqual(r_fake_total.status_code, 409)

    def test_order_snapshot_immutability_and_idempotency_when_closed(self):
        """6. Bản chụp đơn hàng không bị thay đổi khi sửa cấu hình sau này; retry đơn khi đóng cửa không trừ kho."""
        admin_csrf = self.csrf[id(self.admin)]
        # Tạo khu vực và cấu hình thời gian giao
        r_z = self.admin.post(
            "/api/admin/delivery-zones",
            json={"name": "Khu A - Trung tâm", "fee": 18000, "isActive": True},
            headers={"X-CSRF-Token": admin_csrf}
        )
        zid = r_z.json["id"]
        self.admin.patch(
            "/api/admin/store/settings",
            json={"deliveryTimeMin": 20, "deliveryTimeMax": 30},
            headers={"X-CSRF-Token": admin_csrf}
        )

        # Tạo đơn ban đầu
        req_key = "idemp-snapshot-test-key"
        r_order = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey=req_key,
            items=[{"id": 1, "quantity": 2}],
            deliveryZoneId=zid,
            expectedTotal=100000 # 100k >= 100k miễn phí giao
        ))
        self.assertEqual(r_order.status_code, 201)
        ord_id = r_order.json["order"]["id"]
        self.assertEqual(r_order.json["order"]["deliveryZoneName"], "Khu A - Trung tâm")
        self.assertEqual(r_order.json["order"]["estimatedDeliveryTime"], "20 - 30 phút (ước tính)")

        with self.engine.connect() as conn:
            sq1 = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq1, 98) # 100 - 2

        # Admin sau đó đổi tên khu vực, đổi thời gian giao và TẠM NGỪNG nhận đơn
        self.admin.patch(
            f"/api/admin/delivery-zones/{zid}",
            json={"name": "Khu A - Ngoại ô VIP", "fee": 50000},
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.admin.patch(
            "/api/admin/store/settings",
            json={"deliveryTimeMin": 50, "deliveryTimeMax": 60, "isPaused": True, "pauseReason": "Đã nghỉ"},
            headers={"X-CSRF-Token": admin_csrf}
        )

        # Kiểm tra đơn cũ vẫn giữ nguyên bản chụp ban đầu
        with self.engine.connect() as conn:
            saved_row = conn.execute(text("SELECT payload FROM orders WHERE id = :id"), {"id": ord_id}).fetchone()
        saved_payload = json.loads(saved_row[0])
        self.assertEqual(saved_payload["deliveryZoneName"], "Khu A - Trung tâm")
        self.assertEqual(saved_payload["estimatedDeliveryTime"], "20 - 30 phút (ước tính)")

        # Client gửi lại (retry) đơn với cùng request_key khi cửa hàng ĐÃ TẠM NGỪNG
        r_retry = self.call(self.customer, "POST", "/api/orders", self.order(
            requestKey=req_key,
            items=[{"id": 1, "quantity": 2}],
            deliveryZoneId=zid,
            expectedTotal=100000
        ))
        self.assertEqual(r_retry.status_code, 200)
        self.assertEqual(r_retry.json["order"]["id"], ord_id)

        # Kho hàng KHÔNG bị trừ thêm lần nữa (vẫn là 98)
        with self.engine.connect() as conn:
            sq2 = conn.execute(text("SELECT stock_quantity FROM products WHERE id = 1")).scalar()
        self.assertEqual(sq2, 98)

if __name__ == "__main__":
    unittest.main()
