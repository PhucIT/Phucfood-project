"""Kiểm tra xác thực kết nối và tính toàn vẹn của Backend MySQL Docker.

File kiểm thử được đặt trong thư mục tests/ của dự án PHUC-FOODIE.
Chạy:
  .\\.venv\\Scripts\\python.exe tests/verify_e2e_mysql.py
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Thêm thư mục gốc dự án vào sys.path để import các module nội bộ server và database
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import build_connection_url, create_database_engine
from server import create_app

def verify_mysql_backend():
    print("=== XÁC THỰC KẾT NỐI VÀ TÍNH TOÀN VẸN BACKEND MYSQL (PHUC-FOODIE) ===")

    # 1. Kiểm tra cấu hình kết nối từ .env.mysql
    url, db_name, host, port = build_connection_url()
    print(f"[OK] Cấu hình MySQL hợp lệ: {host}:{port}/{db_name}")

    # 2. Kiểm tra kết nối trực tiếp tới MySQL Docker
    engine = create_database_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT DATABASE(), CURRENT_USER(), VERSION()")).fetchone()
        print(f"[OK] Kết nối MySQL thành công: DB={res[0]}, User={res[1]}, Version={res[2]}")

        # Kiểm tra sự tồn tại của đầy đủ 9 bảng
        tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
        expected_tables = {"users", "products", "orders", "sessions", "reset_tokens", "rate_limits", "store_settings", "delivery_zones", "user_identities"}
        missing = expected_tables - set(tables)
        if missing:
            raise RuntimeError(f"Thiếu bảng trong MySQL: {missing}")
        print(f"[OK] Đầy đủ 9 bảng: {', '.join(sorted(tables))}")

        # Kiểm tra số lượng bản ghi hiện có
        users_cnt = conn.execute(text("SELECT count(*) FROM users")).scalar()
        products_cnt = conn.execute(text("SELECT count(*) FROM products")).scalar()
        orders_cnt = conn.execute(text("SELECT count(*) FROM orders")).scalar()
        print(f"[OK] Dữ liệu hiện tại: {users_cnt} tài khoản, {products_cnt} món ăn, {orders_cnt} đơn hàng")

    # 3. Kiểm tra khởi tạo ứng dụng Flask với backend MySQL
    app = create_app()
    client = app.test_client()

    # Kiểm tra API /api/session
    session_res = client.get("/api/session")
    assert session_res.status_code == 200, f"Lỗi /api/session: {session_res.status_code}"
    assert "csrfToken" in session_res.json, "Không nhận được CSRF token"
    print("[OK] API /api/session (khách) hoạt động bình thường")

    # Kiểm tra API /api/admin/session
    admin_session_res = client.get("/api/admin/session")
    assert admin_session_res.status_code == 200, f"Lỗi /api/admin/session: {admin_session_res.status_code}"
    assert "csrfToken" in admin_session_res.json, "Không nhận được Admin CSRF token"
    print("[OK] API /api/admin/session (quản trị) hoạt động bình thường")

    # Kiểm tra API /api/products
    products_res = client.get("/api/products")
    assert products_res.status_code == 200, f"Lỗi /api/products: {products_res.status_code}"
    products = products_res.json.get("products", [])
    assert len(products) > 0, "Không có sản phẩm nào được trả về từ MySQL"
    print(f"[OK] API /api/products trả về {len(products)} món ăn từ MySQL")

    print("\n[THÀNH CÔNG] Backend MySQL Docker hoạt động chính xác và toàn vẹn!")

if __name__ == "__main__":
    verify_mysql_backend()
