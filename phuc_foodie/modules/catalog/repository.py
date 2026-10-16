"""Truy xuất dữ liệu sản phẩm và kho hàng trong cơ sở dữ liệu."""
from typing import List, Optional


class CatalogRepository:
    """Truy vấn bảng products bằng SQL trực tiếp, không commit giữa chừng."""

    @staticmethod
    def get_all(conn) -> List[dict]:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(conn, product_id: int, for_update: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM products WHERE id = :id FOR UPDATE" if for_update else "SELECT * FROM products WHERE id = :id"
        return conn.execute(sql, {"id": product_id}).fetchone()

    @staticmethod
    def insert(conn, name: str, price: int, category: str, image: str, description: str, available: int, stock_quantity: Optional[int]) -> int:
        res = conn.execute(
            "INSERT INTO products (name, price, category, image, description, available, stock_quantity) "
            "VALUES (:name, :price, :category, :image, :description, :available, :stock)",
            {
                "name": name,
                "price": price,
                "category": category,
                "image": image,
                "description": description,
                "available": available,
                "stock": stock_quantity,
            }
        )
        return res.lastrowid

    @staticmethod
    def update(conn, product_id: int, name: str, price: int, category: str, image: str, description: str, available: int, stock_quantity: Optional[int]):
        conn.execute(
            "UPDATE products SET name = :name, price = :price, category = :category, "
            "image = :image, description = :description, available = :available, stock_quantity = :stock WHERE id = :id",
            {
                "name": name,
                "price": price,
                "category": category,
                "image": image,
                "description": description,
                "available": available,
                "stock": stock_quantity,
                "id": product_id,
            }
        )

    @staticmethod
    def deduct_stock(conn, product_id: int, quantity: int):
        conn.execute(
            "UPDATE products SET stock_quantity = stock_quantity - :qty WHERE id = :id",
            {"qty": quantity, "id": product_id}
        )

    @staticmethod
    def restore_stock(conn, product_id: int, quantity: int):
        conn.execute(
            "UPDATE products SET stock_quantity = stock_quantity + :qty WHERE id = :id",
            {"qty": quantity, "id": product_id}
        )
