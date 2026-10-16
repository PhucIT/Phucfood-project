"""Kiểm thử tính toàn vẹn chuyên sâu sau khi tái cấu trúc thành Modular Monolith.
Hoàn toàn độc lập, tự tạo fixture trên database kiểm thử `phuc_foodie_test`,
dọn dẹp engine, và kiểm tra triệt để:
- Không lỗi mapping khi dọn ảnh (res['cnt']).
- Dọn ảnh mồ côi và giữ lại ảnh dùng chung.
- Cho phép blob: trong CSP header.
- Phân lập thư mục upload và data giữa các app instance.
- Không tạo session.key trên đĩa khi có SECRET_KEY.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from sqlalchemy import text
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phuc_foodie import create_app
from phuc_foodie.config import PROJECT_ROOT
from phuc_foodie.extensions import get_db
from phuc_foodie.infrastructure.database import create_database_engine
from phuc_foodie.modules.catalog.images import cleanup_unused_image, process_and_save_image
from phuc_foodie.modules.catalog.service import CatalogService

TEST_DB_CONFIG = {
    "TESTING": True,
    "MYSQL_DATABASE": "phuc_foodie_test",
    "SECRET_KEY": "test-integrity-secret-key-123456",
}


def _make_dummy_image_bytes(format="JPEG", size=(100, 100), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


class RefactorIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="phuc_test_integrity_")).resolve()
        cls.upload_dir = cls.temp_dir / "uploads"
        cls.data_dir = cls.temp_dir / "data"
        cls.upload_dir.mkdir(parents=True, exist_ok=True)
        cls.data_dir.mkdir(parents=True, exist_ok=True)

        cls.engine = create_database_engine(TEST_DB_CONFIG)

        # 1. Bảo vệ an toàn: Tuyệt đối chỉ thao tác trên phuc_foodie_test
        with cls.engine.connect() as conn:
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
            assert db_name == "phuc_foodie_test", f"Bảo vệ an toàn: đang kết nối vào {db_name}, không phải phuc_foodie_test!"

        # 2. Tự tạo fixture người dùng riêng biệt cho bộ test này (không phụ thuộc test khác)
        cls.cust_email = "integrity_cust@integrity.test"
        cls.admin_email = "integrity_admin@integrity.test"
        cls.password = "TestPass!123"
        pwd_hash = generate_password_hash(cls.password)

        with cls.engine.begin() as conn:
            # Dọn dẹp tài khoản cũ nếu có
            conn.execute(
                text("DELETE FROM users WHERE email IN (:c, :a)"),
                {"c": cls.cust_email, "a": cls.admin_email}
            )
            conn.execute(
                text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                     "VALUES ('Integrity Cust', :c, '0988000001', :h, 'customer')"),
                {"c": cls.cust_email, "h": pwd_hash}
            )
            conn.execute(
                text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                     "VALUES ('Integrity Admin', :a, '0988000002', :h, 'admin')"),
                {"a": cls.admin_email, "h": pwd_hash}
            )

    @classmethod
    def tearDownClass(cls):
        # Dọn dẹp fixture và giải phóng kết nối
        try:
            with cls.engine.begin() as conn:
                db_name = conn.execute(text("SELECT DATABASE()")).scalar()
                if db_name == "phuc_foodie_test":
                    conn.execute(
                        text("DELETE FROM users WHERE email LIKE '%@integrity.test'")
                    )
                    conn.execute(
                        text("DELETE FROM products WHERE name LIKE 'Integrity Test Product%'")
                    )
        finally:
            cls.engine.dispose()
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.app = create_app({
            **TEST_DB_CONFIG,
            "UPLOAD_FOLDER": str(self.upload_dir),
            "PHUC_DATA_DIR": str(self.data_dir),
        })
        self.client = self.app.test_client()

    def test_factory_isolation(self):
        """Kiểm tra Application Factory tạo nhiều app độc lập, không dùng nhầm config."""
        app1 = create_app({**TEST_DB_CONFIG, "SECRET_KEY": "key-1", "CUSTOM_TAG": "tag1"})
        app2 = create_app({**TEST_DB_CONFIG, "SECRET_KEY": "key-2", "CUSTOM_TAG": "tag2"})
        self.assertEqual(app1.config["CUSTOM_TAG"], "tag1")
        self.assertEqual(app2.config["CUSTOM_TAG"], "tag2")
        self.assertNotEqual(app1.config["SECRET_KEY"], app2.config["SECRET_KEY"])

    def test_secret_key_no_disk_io_when_explicit(self):
        """Khi SECRET_KEY được truyền vào factory, không tạo session.key trên đĩa."""
        separate_data_dir = self.temp_dir / "empty_data"
        separate_data_dir.mkdir(parents=True, exist_ok=True)
        key_file = separate_data_dir / "session.key"

        app = create_app({
            **TEST_DB_CONFIG,
            "SECRET_KEY": "explicit-key-no-disk",
            "DATA_DIR": str(separate_data_dir),
        })
        self.assertEqual(app.config["SECRET_KEY"], "explicit-key-no-disk")
        # File session.key không được tạo ra trên đĩa
        self.assertFalse(key_file.exists())

    def test_dual_sessions_in_same_cookie_jar(self):
        """Kiểm tra phiên khách và phiên admin độc lập trong cùng một cookie jar."""
        c = self.app.test_client()
        r_sess = c.get("/api/session")
        csrf_cust = r_sess.json["csrfToken"]
        r_asess = c.get("/api/admin/session")
        csrf_admin = r_asess.json["csrfToken"]
        self.assertNotEqual(csrf_cust, csrf_admin)

        # Đăng nhập khách
        r_login_c = c.post(
            "/api/login",
            json={"identifier": self.cust_email, "password": self.password},
            headers={"X-CSRF-Token": csrf_cust},
        )
        self.assertEqual(r_login_c.status_code, 200)

        # Đăng nhập admin trong cùng cookie jar
        r_login_a = c.post(
            "/api/admin/login",
            json={"identifier": self.admin_email, "password": self.password},
            headers={"X-CSRF-Token": csrf_admin},
        )
        self.assertEqual(r_login_a.status_code, 200)

        # Kiểm tra phiên song song
        chk_c = c.get("/api/session")
        self.assertEqual(chk_c.json["user"]["email"], self.cust_email)
        self.assertEqual(chk_c.json["user"]["role"], "customer")

        chk_a = c.get("/api/admin/session")
        self.assertEqual(chk_a.json["user"]["email"], self.admin_email)
        self.assertEqual(chk_a.json["user"]["role"], "admin")

        # Khách đăng xuất không làm mất phiên admin
        c.post("/api/logout", json={}, headers={"X-CSRF-Token": chk_c.json["csrfToken"]})
        self.assertIsNone(c.get("/api/session").json["user"])
        self.assertEqual(c.get("/api/admin/session").json["user"]["email"], self.admin_email)

    def test_csp_header_allows_blob_images(self):
        """CSP header phải cho phép blob: trong img-src và không nới lỏng script-src."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertIn("img-src 'self' data: blob:;", csp)
        self.assertIn("script-src 'self' 'unsafe-inline';", csp)
        self.assertIn("default-src 'self';", csp)

    def test_static_asset_security_and_protection(self):
        """Kiểm tra chỉ cho phép các tệp tĩnh được chỉ định, chặn mã nguồn và file bí mật."""
        c = self.client
        self.assertEqual(c.get("/").status_code, 200)
        self.assertEqual(c.get("/admin").status_code, 200)
        self.assertEqual(c.get("/script.js").status_code, 200)
        self.assertEqual(c.get("/admin.js").status_code, 200)

        # Thử truy cập tệp nhạy cảm -> phải trả về 404
        self.assertEqual(c.get("/server.py").status_code, 404)
        self.assertEqual(c.get("/.env.mysql").status_code, 404)
        self.assertEqual(c.get("/.env").status_code, 404)
        self.assertEqual(c.get("/database.py").status_code, 404)
        self.assertEqual(c.get("/data/session.key").status_code, 404)
        self.assertEqual(c.get("/phuc_foodie/config.py").status_code, 404)

    def test_two_apps_isolated_uploads_and_serving(self):
        """Hai app độc lập có thư mục upload riêng: App B không thể đọc ảnh của App A."""
        dir_a = self.temp_dir / "uploads_app_a"
        dir_b = self.temp_dir / "uploads_app_b"
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        app_a = create_app({**TEST_DB_CONFIG, "UPLOAD_DIR": str(dir_a), "SECRET_KEY": "key-a"})
        app_b = create_app({**TEST_DB_CONFIG, "UPLOAD_DIR": str(dir_b), "SECRET_KEY": "key-b"})

        client_a = app_a.test_client()
        client_b = app_b.test_client()

        # Tạo ảnh trực tiếp trong thư mục của app A
        filename_a = "app_a_only_image.jpg"
        (dir_a / filename_a).write_bytes(_make_dummy_image_bytes())

        # Client A tải được ảnh
        res_a = client_a.get(f"/uploads/{filename_a}")
        self.assertEqual(res_a.status_code, 200)

        # Client B truy cập cùng tên file trong thư mục của mình -> không có -> 404
        res_b = client_b.get(f"/uploads/{filename_a}")
        self.assertEqual(res_b.status_code, 404)

        # Đảm bảo không tạo file trong thư mục gốc WebDoAn/uploads
        self.assertFalse((PROJECT_ROOT / "uploads" / filename_a).exists())

    def test_cleanup_unused_image_mapping_and_retention(self):
        """Kiểm tra dọn dẹp ảnh mồ côi (không lỗi res['cnt']) và không xóa ảnh đang dùng chung."""
        upload_test_dir = self.temp_dir / "uploads_cleanup_test"
        upload_test_dir.mkdir(parents=True, exist_ok=True)

        solo_filename = "solo_cleanup_test.jpg"
        shared_filename = "shared_cleanup_test.jpg"

        file_solo = upload_test_dir / solo_filename
        file_shared = upload_test_dir / shared_filename
        file_solo.write_bytes(_make_dummy_image_bytes(color=(10, 20, 30)))
        file_shared.write_bytes(_make_dummy_image_bytes(color=(40, 50, 60)))

        solo_path = f"uploads/{solo_filename}"
        shared_path = f"uploads/{shared_filename}"

        app = create_app({**TEST_DB_CONFIG, "UPLOAD_DIR": str(upload_test_dir)})

        with app.app_context():
            db_conn = get_db()
            with self.engine.begin() as conn:
                # Tạo 3 món kiểm thử
                res1 = conn.execute(
                    text("INSERT INTO products (name, price, category, image, description, available, stock_quantity) "
                         "VALUES ('Integrity Test Product Solo', 35000, 'Đồ ăn', :img, 'Desc', 1, 10)"),
                    {"img": solo_path}
                )
                p_solo_id = res1.lastrowid

                res2 = conn.execute(
                    text("INSERT INTO products (name, price, category, image, description, available, stock_quantity) "
                         "VALUES ('Integrity Test Product Shared 1', 40000, 'Đồ ăn', :img, 'Desc', 1, 10)"),
                    {"img": shared_path}
                )
                p_shared1_id = res2.lastrowid

                res3 = conn.execute(
                    text("INSERT INTO products (name, price, category, image, description, available, stock_quantity) "
                         "VALUES ('Integrity Test Product Shared 2', 45000, 'Đồ ăn', :img, 'Desc', 1, 10)"),
                    {"img": shared_path}
                )
                p_shared2_id = res3.lastrowid

            # 1. Cập nhật món solo sang ảnh mới -> ảnh solo cũ phải bị xóa khỏi đĩa và KHÔNG lỗi
            CatalogService.update_product(
                db_conn,
                p_solo_id,
                {"name": "Integrity Test Product Solo Updated", "image": "images/burger.jpg"},
                upload_test_dir
            )
            self.assertFalse(file_solo.exists(), "Ảnh mồ côi solo phải bị xóa khi không còn ai dùng")

            # 2. Cập nhật món shared 1 sang ảnh khác -> ảnh shared VẪN CÒN vì món shared 2 đang dùng
            CatalogService.update_product(
                db_conn,
                p_shared1_id,
                {"name": "Integrity Test Product Shared 1 Updated", "image": "images/pizza.jpg"},
                upload_test_dir
            )
            self.assertTrue(file_shared.exists(), "Ảnh dùng chung KHÔNG được xóa khi vẫn còn món khác tham chiếu")

            # 3. Cập nhật tiếp món shared 2 sang ảnh khác -> lúc này ảnh shared mới bị xóa
            CatalogService.update_product(
                db_conn,
                p_shared2_id,
                {"name": "Integrity Test Product Shared 2 Updated", "image": "images/chicken.jpg"},
                upload_test_dir
            )
            self.assertFalse(file_shared.exists(), "Ảnh dùng chung phải bị xóa khi món cuối cùng đổi ảnh")

    def test_public_store_info(self):
        """Kiểm tra API /api/store-info trả đầy đủ cấu hình và phân vùng giao hàng."""
        r = self.client.get("/api/store-info")
        self.assertEqual(r.status_code, 200)
        data = r.json
        self.assertIn("storeName", data)
        self.assertIn("status", data)
        self.assertIn("deliveryZones", data)
        self.assertIn("freeShippingThreshold", data)


if __name__ == "__main__":
    unittest.main()
