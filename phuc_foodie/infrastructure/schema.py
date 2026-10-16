"""Định nghĩa và khởi tạo schema bảng MySQL cho PHUC-FOODIE."""
import json
from sqlalchemy import text
from phuc_foodie.config import CATALOG_JSON_PATH

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      full_name VARCHAR(100) NOT NULL,
      email VARCHAR(254) NOT NULL UNIQUE,
      phone VARCHAR(20) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      role ENUM('customer', 'admin') NOT NULL DEFAULT 'customer'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      price INT NOT NULL,
      category VARCHAR(50) NOT NULL,
      image VARCHAR(150) NOT NULL,
      description TEXT NOT NULL,
      available TINYINT(1) NOT NULL DEFAULT 1,
      stock_quantity INT NULL DEFAULT NULL,
      CONSTRAINT chk_price CHECK (price > 0),
      CONSTRAINT chk_stock_quantity CHECK (stock_quantity IS NULL OR stock_quantity >= 0)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash VARCHAR(64) PRIMARY KEY,
      user_id INT NOT NULL,
      expires DOUBLE NOT NULL,
      CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      INDEX idx_sessions_expires (expires)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
      id VARCHAR(50) PRIMARY KEY,
      user_id INT NOT NULL,
      payload LONGTEXT NOT NULL,
      state VARCHAR(20) NOT NULL DEFAULT 'pending',
      created_at VARCHAR(50) NOT NULL,
      request_key VARCHAR(100) NOT NULL,
      stock_deducted TINYINT(1) NOT NULL DEFAULT 0,
      delivery_zone_id INT NULL DEFAULT NULL,
      CONSTRAINT uq_orders_user_request UNIQUE (user_id, request_key),
      CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id),
      INDEX idx_orders_user_created (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS reset_tokens (
      email VARCHAR(254) PRIMARY KEY,
      token_hash VARCHAR(64) NOT NULL,
      expires DOUBLE NOT NULL,
      attempts INT NOT NULL DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS rate_limits (
      `key` VARCHAR(191) PRIMARY KEY,
      `count` INT NOT NULL,
      `started` DOUBLE NOT NULL,
      INDEX idx_rate_started (`started`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS store_settings (
      id INT PRIMARY KEY,
      store_name VARCHAR(150) NOT NULL DEFAULT 'PHUC-FOODIE',
      address VARCHAR(255) NOT NULL DEFAULT '',
      phone VARCHAR(20) NOT NULL DEFAULT '',
      is_paused TINYINT(1) NOT NULL DEFAULT 0,
      pause_reason VARCHAR(255) NOT NULL DEFAULT '',
      schedule LONGTEXT NOT NULL,
      delivery_time_min INT NULL DEFAULT NULL,
      delivery_time_max INT NULL DEFAULT NULL,
      free_shipping_enabled TINYINT(1) NOT NULL DEFAULT 1,
      free_shipping_threshold INT NOT NULL DEFAULT 100000,
      default_shipping_fee INT NOT NULL DEFAULT 15000,
      updated_at VARCHAR(50) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS delivery_zones (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      fee INT NOT NULL DEFAULT 15000,
      is_active TINYINT(1) NOT NULL DEFAULT 1,
      created_at VARCHAR(50) NOT NULL,
      updated_at VARCHAR(50) NOT NULL,
      CONSTRAINT chk_zone_fee CHECK (fee >= 0)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
]


def init_schema(engine, seed_products_if_empty: bool = True):
    """Khởi tạo schema bảng MySQL và bổ sung các cột mới an toàn."""
    with engine.begin() as conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(text(stmt))

        # Kiểm tra và thêm cột nếu chưa có (migration an toàn)
        product_cols = [r[0] for r in conn.execute(text("SHOW COLUMNS FROM products")).fetchall()]
        if "stock_quantity" not in product_cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN stock_quantity INT NULL DEFAULT NULL"))

        order_cols = [r[0] for r in conn.execute(text("SHOW COLUMNS FROM orders")).fetchall()]
        if "stock_deducted" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN stock_deducted TINYINT(1) NOT NULL DEFAULT 0"))
        if "delivery_zone_id" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_zone_id INT NULL DEFAULT NULL"))

        has_settings = conn.execute(text("SELECT 1 FROM store_settings WHERE id = 1")).fetchone()
        if not has_settings:
            default_schedule = {
                str(i): {
                    "is_closed": False,
                    "ranges": [{"open": "00:00", "close": "23:59"}]
                }
                for i in range(7)
            }
            conn.execute(
                text("INSERT INTO store_settings ("
                     "id, store_name, address, phone, is_paused, pause_reason, schedule, "
                     "delivery_time_min, delivery_time_max, free_shipping_enabled, free_shipping_threshold, "
                     "default_shipping_fee, updated_at) "
                     "VALUES (1, 'PHUC-FOODIE', '', '', 0, '', :schedule, NULL, NULL, 1, 100000, 15000, :now)"),
                {"schedule": json.dumps(default_schedule, ensure_ascii=False), "now": "2026-10-16T00:00:00"}
            )

    if seed_products_if_empty:
        with engine.connect() as conn:
            has_products = conn.execute(text("SELECT 1 FROM products LIMIT 1")).fetchone()
        if not has_products and CATALOG_JSON_PATH.is_file():
            items = json.loads(CATALOG_JSON_PATH.read_text(encoding="utf-8"))
            with engine.begin() as conn:
                for p in items:
                    conn.execute(
                        text("INSERT INTO products (id, name, price, category, image, description, available) "
                             "VALUES (:id, :name, :price, :category, :image, :description, 1)"),
                        p
                    )
                max_id = max([p["id"] for p in items], default=0)
                if max_id > 0:
                    conn.execute(text(f"ALTER TABLE products AUTO_INCREMENT = {max_id + 1}"))
