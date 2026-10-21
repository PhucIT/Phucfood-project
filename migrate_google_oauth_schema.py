"""Migration bổ sung bảng user_identities và cập nhật users cho Google OAuth (PHUC-FOODIE).
Thực hiện an toàn, bổ sung (additive), không làm mất dữ liệu cũ và có thể chạy lại an toàn.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phuc_foodie.infrastructure.database import create_database_engine
from sqlalchemy import text


CREATE_USER_IDENTITIES_SQL = """
CREATE TABLE IF NOT EXISTS user_identities (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  provider VARCHAR(50) NOT NULL,
  provider_id VARCHAR(191) NOT NULL,
  email VARCHAR(254) NOT NULL,
  created_at VARCHAR(50) NOT NULL,
  updated_at VARCHAR(50) NOT NULL,
  CONSTRAINT fk_user_identities_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT uq_provider_provider_id UNIQUE (provider, provider_id),
  INDEX idx_user_identities_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def migrate_database(db_name: str = None):
    """Thực hiện migration an toàn trên database được chỉ định."""
    cfg = {"MYSQL_DATABASE": db_name} if db_name else {}
    engine = create_database_engine(cfg)

    with engine.begin() as conn:
        active_db = conn.execute(text("SELECT DATABASE()")).scalar()
        print(f"=== Đang thực hiện migration trên database: {active_db} ===")

        # 1. Tạo bảng user_identities nếu chưa có
        conn.execute(text(CREATE_USER_IDENTITIES_SQL))
        print("[OK] Bảng user_identities đã sẵn sàng với UNIQUE(provider, provider_id).")

        # 2. Kiểm tra và cập nhật cột password_hash thành nullable
        cols = {r[0]: r for r in conn.execute(text("SHOW COLUMNS FROM users")).fetchall()}
        if "password_hash" in cols and cols["password_hash"][2] == "NO":
            conn.execute(text("ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) NULL DEFAULT NULL"))
            print("[OK] Đã chuyển password_hash sang NULLABLE để hỗ trợ tài khoản Google.")
        else:
            print("[OK] Cột password_hash đã ở trạng thái NULLABLE hợp lệ.")

        # 3. Kiểm tra và cập nhật cột phone thành nullable
        if "phone" in cols and cols["phone"][2] == "NO":
            conn.execute(text("ALTER TABLE users MODIFY COLUMN phone VARCHAR(20) NULL DEFAULT NULL"))
            print("[OK] Đã chuyển phone sang NULLABLE để hỗ trợ tài khoản Google.")
        else:
            print("[OK] Cột phone đã ở trạng thái NULLABLE hợp lệ.")

    # Xác minh lại cấu trúc sau migration
    with engine.connect() as conn:
        active_db = conn.execute(text("SELECT DATABASE()")).scalar()
        tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
        print(f"[OK] Danh sách bảng trên {active_db}: {', '.join(sorted(tables))}")
        user_schema = [r for r in conn.execute(text("DESCRIBE users")).fetchall() if r[0] in ("phone", "password_hash")]
        for col in user_schema:
            print(f"[OK] Cột users.{col[0]}: Null={col[2]}, Default={col[4]}")

    print(f"[THÀNH CÔNG] Migration hoàn tất trên {active_db}!\n")


def run_all():
    # 1. Thử nghiệm trên phuc_foodie_test trước
    print("--- BƯỚC 1: Thử nghiệm migration trên database test (phuc_foodie_test) ---")
    migrate_database("phuc_foodie_test")

    # 2. Áp dụng trên phuc_foodie chính
    print("--- BƯỚC 2: Áp dụng migration trên database chính (phuc_foodie) ---")
    migrate_database("phuc_foodie")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        migrate_database(target)
    else:
        run_all()
