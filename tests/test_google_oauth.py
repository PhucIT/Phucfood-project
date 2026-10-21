"""Kiểm thử toàn diện luồng Google OAuth 2.0 / OpenID Connect (PHUC-FOODIE).
Chỉ thực hiện ghi/xóa dữ liệu test trên database phuc_foodie_test.
Mock dịch vụ Google OAuth cho kiểm thử tự động, độc lập hoàn toàn với tài khoản Google thật.
"""
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, unquote, urlparse

from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from sqlalchemy import text
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phuc_foodie import create_app
from phuc_foodie.infrastructure.database import create_database_engine
from phuc_foodie.infrastructure.schema import init_schema

TEST_DB_CONFIG = {
    "TESTING": True,
    "MYSQL_DATABASE": "phuc_foodie_test",
    "SECRET_KEY": "test-secret-key-oauth-isolated",
    "GOOGLE_CLIENT_ID": "mock-google-client-id.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "mock-google-client-secret",
    "GOOGLE_REDIRECT_URI": "http://127.0.0.1:5000/api/auth/google/callback",
}


class GoogleOAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_database_engine(TEST_DB_CONFIG)
        init_schema(cls.engine, seed_products_if_empty=False)

    def setUp(self):
        # Xác minh nghiêm ngặt SELECT DATABASE() là phuc_foodie_test trước khi xóa
        with self.engine.begin() as conn:
            current_db = conn.execute(text("SELECT DATABASE()")).scalar()
            self.assertEqual(current_db, "phuc_foodie_test", "Chỉ được phép dọn dẹp dữ liệu trên phuc_foodie_test!")
            conn.execute(text("DELETE FROM orders"))
            conn.execute(text("DELETE FROM sessions"))
            conn.execute(text("DELETE FROM user_identities"))
            conn.execute(text("DELETE FROM users"))
            conn.execute(text("DELETE FROM reset_tokens"))
            conn.execute(text("DELETE FROM rate_limits"))
            conn.execute(text("ALTER TABLE user_identities AUTO_INCREMENT = 1"))
            conn.execute(text("ALTER TABLE users AUTO_INCREMENT = 1"))

        # Thư mục tạm độc lập cho mỗi test case
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app_config = dict(TEST_DB_CONFIG)
        self.app_config["DATA_DIR"] = Path(self.temp_dir.name)
        self.app_config["UPLOAD_DIR"] = Path(self.temp_dir.name) / "uploads"
        self.app = create_app(self.app_config)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Chuyển hướng đăng nhập có state và nonce
    def test_google_redirect_contains_state_and_nonce(self):
        res = self.client.get("/api/auth/google")
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location", "")
        self.assertTrue(location.startswith("https://accounts.google.com/o/oauth2/v2/auth"))

        parsed = urlparse(location)
        params = parse_qs(parsed.query)

        self.assertIn("client_id", params)
        self.assertEqual(params["client_id"][0], TEST_DB_CONFIG["GOOGLE_CLIENT_ID"])
        self.assertIn("redirect_uri", params)
        self.assertEqual(params["redirect_uri"][0], TEST_DB_CONFIG["GOOGLE_REDIRECT_URI"])
        self.assertIn("response_type", params)
        self.assertEqual(params["response_type"][0], "code")
        self.assertIn("scope", params)
        self.assertEqual(params["scope"][0], "openid email profile")
        self.assertIn("state", params, "Phải có tham số state bảo vệ CSRF")
        self.assertIn("nonce", params, "Phải có tham số nonce bảo vệ OpenID Connect")
        self.assertTrue(len(params["state"][0]) >= 16)
        self.assertTrue(len(params["nonce"][0]) >= 16)

        # Cookie OAuth session riêng biệt
        cookie_header = res.headers.get("Set-Cookie", "")
        self.assertIn("foodie_oauth_session=", cookie_header)
        self.assertNotIn("foodie_customer_session=", cookie_header)
        self.assertNotIn("foodie_admin_session=", cookie_header)

    # 2. Callback hợp lệ tạo tài khoản khách và phiên đăng nhập
    def test_google_callback_valid_creates_customer_and_session(self):
        mock_userinfo = {
            "sub": "google-user-sub-123456",
            "email": "google_customer@example.com",
            "email_verified": True,
            "name": "Nguyễn Văn Google",
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
        }

        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {
            "access_token": "mock_access_token",
            "userinfo": mock_userinfo,
        }

        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            res = self.client.get("/api/auth/google/callback?code=mock_code&state=mock_state")
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers.get("Location"), "/")

            # Xác minh cookie foodie_customer_session được tạo
            cookie_header = res.headers.get("Set-Cookie", "")
            self.assertIn("foodie_customer_session=", cookie_header)
            self.assertNotIn("foodie_admin_session=", cookie_header)

        # Kiểm tra bản ghi trong MySQL phuc_foodie_test
        with self.engine.connect() as conn:
            user = conn.execute(text("SELECT * FROM users WHERE email = 'google_customer@example.com'")).fetchone()
            self.assertIsNotNone(user)
            self.assertEqual(user._mapping["full_name"], "Nguyễn Văn Google")
            self.assertEqual(user._mapping["role"], "customer")
            self.assertIsNone(user._mapping["phone"])
            self.assertIsNone(user._mapping["password_hash"])

            identity = conn.execute(
                text("SELECT * FROM user_identities WHERE provider = 'google' AND provider_id = 'google-user-sub-123456'")
            ).fetchone()
            self.assertIsNotNone(identity)
            self.assertEqual(identity._mapping["user_id"], user._mapping["id"])
            self.assertEqual(identity._mapping["email"], "google_customer@example.com")

        # Kiểm tra phiên hoạt động qua API /api/session
        sess_res = self.client.get("/api/session")
        self.assertEqual(sess_res.status_code, 200)
        user_data = sess_res.json["user"]
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["email"], "google_customer@example.com")
        self.assertEqual(user_data["role"], "customer")

    # 3. Đăng nhập lại cùng sub không tạo bản ghi trùng
    def test_google_callback_repeat_login_same_sub_no_duplicate(self):
        mock_userinfo = {
            "sub": "google-user-repeat-sub",
            "email": "repeat@example.com",
            "email_verified": True,
            "name": "Khách Đăng Nhập Lại",
        }

        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {
            "access_token": "mock_token",
            "userinfo": mock_userinfo,
        }

        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            # Lần 1
            res1 = self.client.get("/api/auth/google/callback?code=code1&state=state1")
            self.assertEqual(res1.status_code, 302)
            # Lần 2 (cùng sub)
            res2 = self.client.get("/api/auth/google/callback?code=code2&state=state2")
            self.assertEqual(res2.status_code, 302)

        with self.engine.connect() as conn:
            user_count = conn.execute(text("SELECT count(*) FROM users WHERE email = 'repeat@example.com'")).scalar()
            self.assertEqual(user_count, 1, "Không được tạo bản ghi user trùng lặp")

            identity_count = conn.execute(
                text("SELECT count(*) FROM user_identities WHERE provider = 'google' AND provider_id = 'google-user-repeat-sub'")
            ).scalar()
            self.assertEqual(identity_count, 1, "Không được tạo bản ghi user_identities trùng lặp")

    # 4. Email chưa xác minh, token sai, state sai, người dùng hủy đều thất bại an toàn
    def test_google_callback_unverified_email_fails_safely(self):
        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {
            "userinfo": {
                "sub": "sub-unverified",
                "email": "unverified@example.com",
                "email_verified": False,
                "name": "Chưa Xác Minh",
            }
        }
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            res = self.client.get("/api/auth/google/callback?code=code&state=state")
            self.assertEqual(res.status_code, 302)
            loc = unquote(res.headers.get("Location", ""))
            self.assertIn("auth_error=", loc)
            self.assertIn("chưa được xác minh", loc)

        # Không tạo phiên khách
        self.assertIsNone(self.client.get("/api/session").json["user"])

    def test_google_callback_user_cancelled_fails_safely(self):
        res = self.client.get("/api/auth/google/callback?error=access_denied")
        self.assertEqual(res.status_code, 302)
        loc = unquote(res.headers.get("Location", ""))
        self.assertIn("auth_error=", loc)
        self.assertIn("bị hủy bởi người dùng", loc)
        self.assertIsNone(self.client.get("/api/session").json["user"])

    def test_google_callback_state_mismatch_fails_safely(self):
        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.side_effect = MismatchingStateError()
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            res = self.client.get("/api/auth/google/callback?code=code&state=wrong_state")
            self.assertEqual(res.status_code, 302)
            loc = unquote(res.headers.get("Location", ""))
            self.assertIn("auth_error=", loc)
            self.assertIn("hết hạn hoặc trạng thái không hợp lệ", loc)
            self.assertNotIn("Traceback", loc)
            self.assertNotIn("client_secret", loc)

    def test_google_callback_oauth_error_fails_safely(self):
        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.side_effect = OAuthError(error="invalid_grant", description="Bad code")
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            res = self.client.get("/api/auth/google/callback?code=bad_code&state=state")
            self.assertEqual(res.status_code, 302)
            loc = unquote(res.headers.get("Location", ""))
            self.assertIn("auth_error=", loc)
            self.assertNotIn("Bad code", loc)
            self.assertNotIn("Traceback", loc)

    # 5. Trùng email tài khoản cũ không tự liên kết
    def test_existing_password_user_conflict_not_auto_linked(self):
        # Tạo người dùng đăng ký mật khẩu truyền thống từ trước
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                     "VALUES ('Khách Cũ', 'legacy_cust@example.com', '0911222333', :pw, 'customer')"),
                {"pw": generate_password_hash("MatKhauCu123")}
            )

        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {
            "userinfo": {
                "sub": "new-google-sub-legacy",
                "email": "legacy_cust@example.com",
                "email_verified": True,
                "name": "Google User With Same Email",
            }
        }
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            res = self.client.get("/api/auth/google/callback?code=code&state=state")
            self.assertEqual(res.status_code, 302)
            loc = unquote(res.headers.get("Location", ""))
            self.assertIn("auth_error=", loc)
            self.assertIn("đã được đăng ký bằng mật khẩu", loc)

        # Kiểm tra không tự liên kết vào bảng user_identities
        with self.engine.connect() as conn:
            identity = conn.execute(
                text("SELECT * FROM user_identities WHERE provider = 'google' AND provider_id = 'new-google-sub-legacy'")
            ).fetchone()
            self.assertIsNone(identity, "Tuyệt đối không tự động liên kết danh tính khi chưa xác nhận mật khẩu cũ!")

    # 6. Chặn xung đột email admin và không cấp quyền admin
    def test_admin_email_conflict_blocked(self):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                     "VALUES ('Quản Trị Viên', 'admin_boss@example.com', '0988777666', :pw, 'admin')"),
                {"pw": generate_password_hash("AdminPass123")}
            )

        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {
            "userinfo": {
                "sub": "fake-admin-google-sub",
                "email": "admin_boss@example.com",
                "email_verified": True,
                "name": "Hacker Trying Admin Email",
            }
        }
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            res = self.client.get("/api/auth/google/callback?code=code&state=state")
            self.assertEqual(res.status_code, 302)
            loc = unquote(res.headers.get("Location", ""))
            self.assertIn("auth_error=", loc)
            self.assertIn("quản trị viên", loc)

        # Kiểm tra không tạo phiên khách và không cấp phiên admin
        self.assertIsNone(self.client.get("/api/session").json["user"])
        self.assertIsNone(self.client.get("/api/admin/session").json["user"])

    # 7. Phiên khách và admin cùng tồn tại (song song trong cùng cookie jar)
    def test_customer_and_admin_sessions_coexist(self):
        # 1. Tạo tài khoản admin và đăng nhập admin
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                     "VALUES ('Admin System', 'system_admin@example.com', '0999888777', :pw, 'admin')"),
                {"pw": generate_password_hash("AdminSecret999")}
            )

        csrf_res = self.client.get("/api/admin/session")
        admin_csrf = csrf_res.json["csrfToken"]
        login_admin_res = self.client.post(
            "/api/admin/login",
            json={"identifier": "system_admin@example.com", "password": "AdminSecret999"},
            headers={"X-CSRF-Token": admin_csrf}
        )
        self.assertEqual(login_admin_res.status_code, 200)

        # 2. Đăng nhập khách qua Google callback trên cùng test_client
        mock_userinfo = {
            "sub": "customer-coexist-sub",
            "email": "coexist_customer@example.com",
            "email_verified": True,
            "name": "Khách Song Song",
        }
        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {
            "userinfo": mock_userinfo,
        }
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            cb_res = self.client.get("/api/auth/google/callback?code=code&state=state")
            self.assertEqual(cb_res.status_code, 302)

        # 3. Xác minh cả hai phiên cùng tồn tại độc lập
        cust_session = self.client.get("/api/session").json
        self.assertIsNotNone(cust_session["user"])
        self.assertEqual(cust_session["user"]["email"], "coexist_customer@example.com")
        self.assertEqual(cust_session["user"]["role"], "customer")

        admin_session = self.client.get("/api/admin/session").json
        self.assertIsNotNone(admin_session["user"])
        self.assertEqual(admin_session["user"]["email"], "system_admin@example.com")
        self.assertEqual(admin_session["user"]["role"], "admin")

    # 8. Đăng nhập mật khẩu và đăng xuất cũ vẫn hoạt động 100%
    def test_legacy_password_login_and_logout_still_work(self):
        csrf = self.client.get("/api/session").json["csrfToken"]
        # Đăng ký khách
        reg_res = self.client.post(
            "/api/register",
            json={
                "fullName": "Khách Mật Khẩu",
                "email": "pwd_user@example.com",
                "phone": "0987111222",
                "password": "Password123",
                "terms": True
            },
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(reg_res.status_code, 201)

        # Đăng nhập mật khẩu
        login_res = self.client.post(
            "/api/login",
            json={"identifier": "pwd_user@example.com", "password": "Password123"},
            headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json["user"]["email"], "pwd_user@example.com")

        # Đăng xuất
        logout_csrf = self.client.get("/api/session").json["csrfToken"]
        logout_res = self.client.post("/api/logout", headers={"X-CSRF-Token": logout_csrf})
        self.assertEqual(logout_res.status_code, 200)
        self.assertIsNone(self.client.get("/api/session").json["user"])

    # 9. Tài khoản Google không thể đăng nhập bằng mật khẩu hoặc reset mật khẩu bừa bãi
    def test_google_user_cannot_login_with_password(self):
        mock_userinfo = {
            "sub": "google-no-pw-sub",
            "email": "nopass@example.com",
            "email_verified": True,
            "name": "Không Có Mật Khẩu",
        }
        mock_oauth_client = MagicMock()
        mock_oauth_client.authorize_access_token.return_value = {"userinfo": mock_userinfo}
        with patch("phuc_foodie.modules.auth.routes.get_oauth_client", return_value=mock_oauth_client):
            self.client.get("/api/auth/google/callback?code=code&state=state")

        # Đăng xuất phiên Google
        logout_csrf = self.client.get("/api/session").json["csrfToken"]
        self.client.post("/api/logout", headers={"X-CSRF-Token": logout_csrf})

        # Thử đăng nhập bằng mật khẩu -> Phải từ chối 401 an toàn
        login_csrf = self.client.get("/api/session").json["csrfToken"]
        res = self.client.post(
            "/api/login",
            json={"identifier": "nopass@example.com", "password": "RandomPassword123"},
            headers={"X-CSRF-Token": login_csrf}
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json["error"], "Thông tin đăng nhập không đúng.")

        # Thử forgot password với tài khoản Google -> Thông báo rõ ràng
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.test", "SMTP_FROM": "bot@test"}):
            forgot_res = self.client.post(
                "/api/password/forgot",
                json={"email": "nopass@example.com"},
                headers={"X-CSRF-Token": login_csrf}
            )
            self.assertEqual(forgot_res.status_code, 400)
            self.assertIn("được đăng ký thông qua Google", forgot_res.json["error"])

    # 10. Thiếu cấu hình Google không làm hỏng ứng dụng
    def test_missing_google_config_does_not_crash_app(self):
        unconfigured_app = create_app({
            "TESTING": True,
            "MYSQL_DATABASE": "phuc_foodie_test",
            "SECRET_KEY": "test-key-no-google",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
        })
        test_c = unconfigured_app.test_client()

        sess = test_c.get("/api/session")
        self.assertEqual(sess.status_code, 200)
        self.assertFalse(sess.json["googleAuthEnabled"])

        # Endpoint /api/auth/google chuyển hướng an toàn thông báo lỗi thân thiện
        res = test_c.get("/api/auth/google")
        self.assertEqual(res.status_code, 302)
        loc = unquote(res.headers.get("Location", ""))
        self.assertIn("auth_error=", loc)
        self.assertIn("chưa được cấu hình", loc)

    # 11. create_app nhiều lần không dùng nhầm cấu hình OAuth
    def test_multiple_create_app_isolation(self):
        app1 = create_app({
            "TESTING": True,
            "MYSQL_DATABASE": "phuc_foodie_test",
            "SECRET_KEY": "sec1",
            "GOOGLE_CLIENT_ID": "id-app-1",
            "GOOGLE_CLIENT_SECRET": "secret-app-1",
        })
        app2 = create_app({
            "TESTING": True,
            "MYSQL_DATABASE": "phuc_foodie_test",
            "SECRET_KEY": "sec2",
            "GOOGLE_CLIENT_ID": "id-app-2",
            "GOOGLE_CLIENT_SECRET": "secret-app-2",
        })

        self.assertEqual(app1.config["GOOGLE_CLIENT_ID"], "id-app-1")
        self.assertEqual(app2.config["GOOGLE_CLIENT_ID"], "id-app-2")

        with app1.test_request_context():
            from phuc_foodie.extensions import get_oauth_client
            client1 = get_oauth_client("google")
            self.assertEqual(client1.client_id, "id-app-1")

        with app2.test_request_context():
            from phuc_foodie.extensions import get_oauth_client
            client2 = get_oauth_client("google")
            self.assertEqual(client2.client_id, "id-app-2")


if __name__ == "__main__":
    unittest.main()
