"""Truy xuất dữ liệu cấu hình cửa hàng và khu vực giao hàng trong cơ sở dữ liệu."""
import json
from typing import List, Optional
from phuc_foodie.modules.store.schedule import DEFAULT_SCHEDULE


class StoreRepository:
    @staticmethod
    def get_settings(conn) -> dict:
        row = conn.execute("SELECT * FROM store_settings WHERE id = 1").fetchone()
        if not row:
            return {
                "store_name": "PHUC-FOODIE",
                "address": "",
                "phone": "",
                "is_paused": False,
                "pause_reason": "",
                "schedule": DEFAULT_SCHEDULE,
                "delivery_time_min": None,
                "delivery_time_max": None,
                "free_shipping_enabled": True,
                "free_shipping_threshold": 100000,
                "default_shipping_fee": 15000,
                "updated_at": "",
            }
        sched = json.loads(row["schedule"]) if row["schedule"] else DEFAULT_SCHEDULE
        return {
            "store_name": row["store_name"],
            "address": row["address"],
            "phone": row["phone"],
            "is_paused": bool(row["is_paused"]),
            "pause_reason": row["pause_reason"] or "",
            "schedule": sched,
            "delivery_time_min": row["delivery_time_min"],
            "delivery_time_max": row["delivery_time_max"],
            "free_shipping_enabled": bool(row["free_shipping_enabled"]),
            "free_shipping_threshold": row["free_shipping_threshold"],
            "default_shipping_fee": row["default_shipping_fee"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def update_settings(conn, store_name: str, address: str, phone: str, is_paused: int,
                        pause_reason: str, schedule: dict, delivery_time_min: Optional[int],
                        delivery_time_max: Optional[int], free_shipping_enabled: int,
                        free_shipping_threshold: int, now_str: str):
        conn.execute(
            "UPDATE store_settings SET "
            "store_name = :name, address = :addr, phone = :phone, is_paused = :paused, pause_reason = :reason, "
            "schedule = :sched, delivery_time_min = :d_min, delivery_time_max = :d_max, "
            "free_shipping_enabled = :free_ship, free_shipping_threshold = :thresh, updated_at = :now "
            "WHERE id = 1",
            {
                "name": store_name,
                "addr": address,
                "phone": phone,
                "paused": is_paused,
                "reason": pause_reason,
                "sched": json.dumps(schedule, ensure_ascii=False),
                "d_min": delivery_time_min,
                "d_max": delivery_time_max,
                "free_ship": free_shipping_enabled,
                "thresh": free_shipping_threshold,
                "now": now_str,
            }
        )

    @staticmethod
    def get_all_zones(conn) -> List[dict]:
        return conn.execute("SELECT * FROM delivery_zones ORDER BY id ASC").fetchall()

    @staticmethod
    def get_active_zones(conn) -> List[dict]:
        return conn.execute("SELECT * FROM delivery_zones WHERE is_active = 1 ORDER BY fee ASC, name ASC").fetchall()

    @staticmethod
    def get_zone_by_id(conn, zone_id: int) -> Optional[dict]:
        return conn.execute("SELECT * FROM delivery_zones WHERE id = :id", {"id": zone_id}).fetchone()

    @staticmethod
    def insert_zone(conn, name: str, fee: int, is_active: int, created_at: str, updated_at: str) -> int:
        res = conn.execute(
            "INSERT INTO delivery_zones (name, fee, is_active, created_at, updated_at) "
            "VALUES (:name, :fee, :active, :created, :updated)",
            {"name": name, "fee": fee, "active": is_active, "created": created_at, "updated": updated_at}
        )
        return res.lastrowid

    @staticmethod
    def update_zone(conn, zone_id: int, name: str, fee: int, is_active: int, updated_at: str):
        conn.execute(
            "UPDATE delivery_zones SET name = :name, fee = :fee, is_active = :active, updated_at = :now WHERE id = :id",
            {"name": name, "fee": fee, "active": is_active, "now": updated_at, "id": zone_id}
        )

    @staticmethod
    def count_zone_orders(conn, zone_id: int) -> int:
        row = conn.execute("SELECT count(*) as cnt FROM orders WHERE delivery_zone_id = :id", {"id": zone_id}).fetchone()
        return row["cnt"] if row else 0

    @staticmethod
    def get_zone_order_counts(conn) -> dict:
        order_rows = conn.execute("SELECT payload, delivery_zone_id FROM orders").fetchall()
        zone_counts = {}
        for r in order_rows:
            zid = r["delivery_zone_id"]
            if zid is None:
                try:
                    op = json.loads(r["payload"])
                    zid = op.get("deliveryZoneId")
                except Exception:
                    pass
            if zid is not None:
                zone_counts[zid] = zone_counts.get(zid, 0) + 1
        return zone_counts

    @staticmethod
    def delete_zone(conn, zone_id: int):
        conn.execute("DELETE FROM delivery_zones WHERE id = :id", {"id": zone_id})
