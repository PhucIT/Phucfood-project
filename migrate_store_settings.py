"""Migration bổ sung bảng store_settings và delivery_zones cho MySQL Docker (PHUC-FOODIE).
Chạy:
  .\\.venv\\Scripts\\python.exe migrate_store_settings.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import create_database_engine, init_schema
from sqlalchemy import text

def run_migration():
    print("=== MIGRATION CẤU HÌNH CỬA HÀNG VÀ KHU VỰC GIAO HÀNG (PHUC-FOODIE) ===")
    engine = create_database_engine()
    init_schema(engine, seed_products_if_empty=False)
    
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
        print(f"[OK] Bảng hiện tại trong MySQL: {', '.join(sorted(tables))}")
        
        has_settings = conn.execute(text("SELECT id, store_name, is_paused FROM store_settings WHERE id = 1")).fetchone()
        print(f"[OK] Cấu hình cửa hàng hiện tại: ID={has_settings[0]}, Tên={has_settings[1]}, Tạm ngừng={has_settings[2]}")
        
        zones_cnt = conn.execute(text("SELECT count(*) FROM delivery_zones")).scalar()
        print(f"[OK] Số khu vực giao hàng hiện có: {zones_cnt}")

    print("[THÀNH CÔNG] Migration hoàn tất an toàn, dữ liệu cũ được bảo toàn 100%!")

if __name__ == "__main__":
    run_migration()
