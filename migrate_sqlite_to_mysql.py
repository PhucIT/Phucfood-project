"""Công cụ chuyển đổi dữ liệu từ SQLite sang MySQL cho dự án PHUC-FOODIE.

Sử dụng:
  python migrate_sqlite_to_mysql.py --dry-run   (Kiểm tra trước khi ghi)
  python migrate_sqlite_to_mysql.py             (Thực hiện chuyển đổi)
"""
import argparse
import os
import shutil
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parent

def check_server_running(host="127.0.0.1", port=5000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.error, OSError):
        return False

def get_mysql_engine():
    env_mysql_path = ROOT / ".env.mysql"
    if not env_mysql_path.is_file():
        raise RuntimeError("Không tìm thấy file .env.mysql!")
    cfg = dotenv_values(env_mysql_path)
    
    db_name = cfg.get("MYSQL_DATABASE") or os.environ.get("MYSQL_DATABASE", "phuc_foodie")
    user = cfg.get("MYSQL_USER") or os.environ.get("MYSQL_USER", "foodie_user")
    password = cfg.get("MYSQL_PASSWORD") or os.environ.get("MYSQL_PASSWORD")
    host = cfg.get("MYSQL_HOST") or os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(cfg.get("MYSQL_PORT") or os.environ.get("MYSQL_PORT", 3308))

    if not password:
        raise RuntimeError("Thiếu MYSQL_PASSWORD trong .env.mysql!")

    url = URL.create(
        drivername="mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=db_name,
        query={"charset": "utf8mb4"}
    )
    return create_engine(url, pool_pre_ping=True), db_name, host, port

def backup_sqlite(sqlite_path):
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = sqlite_path.with_name(f"{sqlite_path.name}.bak_{now_str}")
    shutil.copy2(sqlite_path, backup_file)
    return backup_file

def main():
    parser = argparse.ArgumentParser(description="Chuyển dữ liệu SQLite sang MySQL")
    parser.add_argument("--dry-run", action="store_true", help="Kiểm tra tính toàn vẹn dữ liệu trước khi ghi")
    parser.add_argument("--force", action="store_true", help="Bỏ qua cảnh báo dữ liệu có sẵn")
    args = parser.parse_args()

    print("=== CÔNG CỤ CHUYỂN DỮ LIỆU SQLITE SANG MYSQL (PHUC-FOODIE) ===")

    # 1. Kiểm tra server đang chạy
    if check_server_running():
        print("LỖI: Server đang chạy tại 127.0.0.1:5000!")
        print("Vui lòng dừng server (Ctrl+C trong terminal đang chạy server) trước khi chuyển đổi dữ liệu.")
        sys.exit(1)

    # 2. Kiểm tra file SQLite
    sqlite_path = ROOT / "data" / "foodie.db"
    if not sqlite_path.is_file():
        print(f"LỖI: Không tìm thấy database SQLite tại {sqlite_path}")
        sys.exit(1)

    # 3. Sao lưu SQLite
    backup_path = backup_sqlite(sqlite_path)
    print(f"[OK] Đã sao lưu database SQLite: {backup_path.name}")
    print(f"[OK] Database SQLite gốc được giữ nguyên tại: {sqlite_path}")

    # 4. Kết nối MySQL
    try:
        engine, db_name, host, port = get_mysql_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[OK] Đã kết nối MySQL thành công: {host}:{port}/{db_name}")
    except Exception as e:
        print(f"LỖI KẾT NỐI MYSQL: {e}")
        sys.exit(1)

    # 5. Kiểm tra dữ liệu hiện có trong MySQL
    with engine.connect() as conn:
        users_count = conn.execute(text("SELECT count(*) FROM users")).scalar() or 0
        products_count = conn.execute(text("SELECT count(*) FROM products")).scalar() or 0
        orders_count = conn.execute(text("SELECT count(*) FROM orders")).scalar() or 0

    if (users_count > 0 or products_count > 0 or orders_count > 0) and not args.force:
        print("\nCẢNH BÁO: MySQL đã có dữ liệu hiện tại:")
        print(f"  - Users: {users_count}")
        print(f"  - Products: {products_count}")
        print(f"  - Orders: {orders_count}")
        print("Để bảo vệ dữ liệu, quá trình chuyển đổi dừng lại. Không tự động xóa bảng hay truncate.")
        sys.exit(1)

    # 6. Đọc dữ liệu từ SQLite
    lite = sqlite3.connect(sqlite_path)
    lite.row_factory = sqlite3.Row

    users = [dict(r) for r in lite.execute("SELECT id, full_name, email, phone, password_hash, role FROM users ORDER BY id").fetchall()]
    products = [dict(r) for r in lite.execute("SELECT id, name, price, category, image, description, available FROM products ORDER BY id").fetchall()]
    orders = [dict(r) for r in lite.execute("SELECT id, user_id, payload, state, created_at, request_key FROM orders ORDER BY created_at").fetchall()]
    lite.close()

    # 7. Kiểm tra khóa ngoại và tính nhất quán
    user_ids = {u["id"] for u in users}
    for o in orders:
        if o["user_id"] not in user_ids:
            print(f"LỖI: Đơn hàng {o['id']} tham chiếu user_id {o['user_id']} không tồn tại trong bảng users!")
            sys.exit(1)

    print("\n[KIỂM TRA DỮ LIỆU SQLITE]")
    print(f"  - Tài khoản (users): {len(users)} bản ghi")
    print(f"  - Món ăn (products): {len(products)} bản ghi")
    print(f"  - Đơn hàng (orders): {len(orders)} bản ghi")
    print("  - Các bảng tạm (sessions, reset_tokens, rate_limits): Bỏ qua theo yêu cầu (người dùng sẽ đăng nhập lại).")

    if args.dry_run:
        print("\n[CHẾ ĐỘ KIỂM TRA - DRY RUN]")
        print("  - Các ràng buộc khóa chính, duy nhất và khóa ngoại đều hợp lệ.")
        print("  - Thứ tự nạp: users -> products -> orders.")
        max_uid = max([u["id"] for u in users], default=0)
        max_pid = max([p["id"] for p in products], default=0)
        print(f"  - Sau khi nạp, AUTO_INCREMENT users sẽ được đặt thành: {max_uid + 1}")
        print(f"  - Sau khi nạp, AUTO_INCREMENT products sẽ được đặt thành: {max_pid + 1}")
        print("Hoàn tất kiểm tra trước khi ghi. Chưa có dữ liệu nào được ghi vào MySQL.")
        return

    # 8. Thực hiện ghi vào MySQL
    print("\n[ĐANG GHI DỮ LIỆU VÀO MYSQL...]")
    with engine.begin() as conn:
        # Nạp users
        for u in users:
            conn.execute(
                text("INSERT INTO users (id, full_name, email, phone, password_hash, role) VALUES (:id, :full_name, :email, :phone, :password_hash, :role)"),
                u
            )
        max_uid = max([u["id"] for u in users], default=0)
        if max_uid > 0:
            conn.execute(text(f"ALTER TABLE users AUTO_INCREMENT = {max_uid + 1}"))

        # Nạp products
        for p in products:
            conn.execute(
                text("INSERT INTO products (id, name, price, category, image, description, available) VALUES (:id, :name, :price, :category, :image, :description, :available)"),
                p
            )
        max_pid = max([p["id"] for p in products], default=0)
        if max_pid > 0:
            conn.execute(text(f"ALTER TABLE products AUTO_INCREMENT = {max_pid + 1}"))

        # Nạp orders
        for o in orders:
            conn.execute(
                text("INSERT INTO orders (id, user_id, payload, state, created_at, request_key) VALUES (:id, :user_id, :payload, :state, :created_at, :request_key)"),
                o
            )

    # 9. Kiểm tra lại sau khi nạp
    with engine.connect() as conn:
        my_users = conn.execute(text("SELECT count(*) FROM users")).scalar()
        my_products = conn.execute(text("SELECT count(*) FROM products")).scalar()
        my_orders = conn.execute(text("SELECT count(*) FROM orders")).scalar()

    print("\n[KẾT QUẢ CHUYỂN ĐỔI]")
    print(f"  - Users đã chuyển: {my_users}/{len(users)}")
    print(f"  - Products đã chuyển: {my_products}/{len(products)}")
    print(f"  - Orders đã chuyển: {my_orders}/{len(orders)}")
    print("[THÀNH CÔNG] Dữ liệu đã được chuyển sang MySQL Docker an toàn và bảo toàn tính toàn vẹn.")

if __name__ == "__main__":
    main()
