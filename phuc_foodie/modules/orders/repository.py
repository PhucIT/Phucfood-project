"""Truy xuất dữ liệu đơn hàng trong MySQL, không commit giữa chừng."""
from typing import List, Optional


class OrderRepository:
    @staticmethod
    def get_by_user(conn, user_id: int) -> List[dict]:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = :uid ORDER BY created_at DESC",
            {"uid": user_id}
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_all_admin(conn, limit: int = 1000) -> List[dict]:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT :limit",
            {"limit": limit}
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_user_and_request_key(conn, user_id: int, request_key: str, for_update: bool = False) -> Optional[dict]:
        sql = (
            "SELECT * FROM orders WHERE user_id = :uid AND request_key = :key FOR UPDATE"
            if for_update else
            "SELECT * FROM orders WHERE user_id = :uid AND request_key = :key"
        )
        return conn.execute(sql, {"uid": user_id, "key": request_key}).fetchone()

    @staticmethod
    def get_by_id(conn, order_id: str, user_id: Optional[int] = None, for_update: bool = False) -> Optional[dict]:
        if user_id is not None:
            sql = (
                "SELECT * FROM orders WHERE id = :id AND user_id = :uid FOR UPDATE"
                if for_update else
                "SELECT * FROM orders WHERE id = :id AND user_id = :uid"
            )
            return conn.execute(sql, {"id": order_id, "uid": user_id}).fetchone()
        else:
            sql = "SELECT * FROM orders WHERE id = :id FOR UPDATE" if for_update else "SELECT * FROM orders WHERE id = :id"
            return conn.execute(sql, {"id": order_id}).fetchone()

    @staticmethod
    def insert(conn, order_id: str, user_id: int, payload_json: str, created_at: str, request_key: str, zone_id: Optional[int]):
        conn.execute(
            "INSERT INTO orders (id, user_id, payload, created_at, request_key, state, stock_deducted, delivery_zone_id) "
            "VALUES (:id, :uid, :payload, :created_at, :key, 'pending', 1, :zone_id)",
            {
                "id": order_id,
                "uid": user_id,
                "payload": payload_json,
                "created_at": created_at,
                "key": request_key,
                "zone_id": zone_id,
            }
        )

    @staticmethod
    def cancel_order(conn, order_id: str):
        conn.execute(
            "UPDATE orders SET state = 'cancelled', stock_deducted = 0 WHERE id = :id",
            {"id": order_id}
        )

    @staticmethod
    def update_admin_state(conn, order_id: str, state: str, payload_json: str, stock_deducted: int):
        conn.execute(
            "UPDATE orders SET state = :state, payload = :payload, stock_deducted = :sd WHERE id = :id",
            {
                "state": state,
                "payload": payload_json,
                "sd": stock_deducted,
                "id": order_id,
            }
        )
