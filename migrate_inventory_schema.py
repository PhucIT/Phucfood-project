"""Script sao lưu dữ liệu và migration bổ sung cột tồn kho cho MySQL.

Bảo toàn 100% dữ liệu hiện có trong MySQL Docker.
Chạy:
  .\\.venv\\Scripts\\python.exe migrate_inventory_schema.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import create_database_engine, build_connection_url

def backup_and_migrate(target_db=None):
    print(f"\n=== MIGRATION TỒN KHO & SAO LƯU CHO DATABASE: {target_db or 'Mặc định'} ===")
    config = {}
    if target_db:
        config["MYSQL_DATABASE"] = target_db
    engine = create_database_engine(config)

    backup_dir = ROOT / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y%m%d_%H%M%S")

    # 1. Sao lưu dữ liệu bảng products và orders hiện có ra file JSON có timestamp
    with engine.connect() as conn:
        current_db = conn.execute(text("SELECT DATABASE()")).scalar()
        print(f"[1/3] Đang kết nối database: {current_db}")

        products_data = [dict(r) for r in conn.execute(text("SELECT * FROM products ORDER BY id")).mappings().fetchall()]
        orders_data = [dict(r) for r in conn.execute(text("SELECT * FROM orders ORDER BY id")).mappings().fetchall()]

        backup_file = backup_dir / f"backup_{current_db}_{now_str}.json"
        backup_content = {
            "database": current_db,
            "timestamp": now_str,
            "products_count": len(products_data),
            "orders_count": len(orders_data),
            "products": products_data,
            "orders": orders_data
        }
        backup_file.write_text(json.dumps(backup_content, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Đã sao lưu {len(products_data)} món ăn và {len(orders_data)} đơn hàng vào: data/backups/{backup_file.name}")

        # 2. Kiểm tra và bổ sung cột stock_quantity vào bảng products
        existing_product_cols = [r[0] for r in conn.execute(text("SHOW COLUMNS FROM products")).fetchall()]
        if "stock_quantity" not in existing_product_cols:
            print("[2/3] Bổ sung cột stock_quantity vào bảng products...")
            with engine.begin() as tx_conn:
                tx_conn.execute(text(
                    "ALTER TABLE products ADD COLUMN stock_quantity INT NULL DEFAULT NULL"
                ))
            print("[OK] Đã thêm cột stock_quantity (mặc định NULL cho các món cũ, không đặt số giả).")
        else:
            print("[2/3] Cột stock_quantity đã tồn tại trong products (bỏ qua).")

        # 3. Kiểm tra và bổ sung cột stock_deducted vào bảng orders
        existing_order_cols = [r[0] for r in conn.execute(text("SHOW COLUMNS FROM orders")).fetchall()]
        if "stock_deducted" not in existing_order_cols:
            print("[3/3] Bổ sung cột stock_deducted vào bảng orders...")
            with engine.begin() as tx_conn:
                tx_conn.execute(text(
                    "ALTER TABLE orders ADD COLUMN stock_deducted TINYINT(1) NOT NULL DEFAULT 0"
                ))
            print("[OK] Đã thêm cột stock_deducted (mặc định 0 cho các đơn cũ, không tự hoàn kho khi hủy).")
        else:
            print("[3/3] Cột stock_deducted đã tồn tại trong orders (bỏ qua).")

    print(f"[HOÀN TẤT] Migration thành công cho database: {current_db}\n")

if __name__ == "__main__":
    # Chạy cho database chính phuc_foodie
    backup_and_migrate()
    # Chạy cho database test phuc_foodie_test
    try:
        backup_and_migrate("phuc_foodie_test")
    except Exception as e:
        print(f"[Lưu ý] Database test phuc_foodie_test: {e}")
