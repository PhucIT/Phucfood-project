"""Nghiệp vụ cấu hình cửa hàng, thời gian giao hàng và phân vùng giao."""
from datetime import datetime
from zoneinfo import ZoneInfo
from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import text
from phuc_foodie.modules.store.repository import StoreRepository
from phuc_foodie.modules.store.schedule import check_store_open, get_today_schedule_text, validate_schedule


class StoreService:
    @staticmethod
    def get_public_store_info(conn, now_dt: datetime = None) -> dict:
        if now_dt is None:
            now_dt = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

        settings = StoreRepository.get_settings(conn)
        is_paused = settings["is_paused"]
        is_open, open_reason = check_store_open(settings["schedule"], now_dt)

        if is_paused:
            status = "paused"
            status_text = "Tạm ngừng nhận đơn"
            status_reason = settings["pause_reason"] or "Cửa hàng đang tạm ngừng nhận đơn."
        elif not is_open:
            status = "closed"
            status_text = "Ngoài giờ hoạt động"
            status_reason = open_reason
        else:
            status = "open"
            status_text = "Đang nhận đơn"
            status_reason = open_reason

        all_zones = StoreRepository.get_all_zones(conn)
        has_delivery_zones = len(all_zones) > 0
        active_zones = [
            {"id": z["id"], "name": z["name"], "fee": z["fee"]}
            for z in all_zones if z["is_active"]
        ]
        all_zones_inactive = has_delivery_zones and len(active_zones) == 0

        min_m = settings["delivery_time_min"]
        max_m = settings["delivery_time_max"]
        if min_m is not None and max_m is not None:
            est_text = f"{min_m} - {max_m} phút (ước tính)"
        elif min_m is not None:
            est_text = f"Khoảng {min_m} phút (ước tính)"
        else:
            est_text = None

        return {
            "storeName": settings["store_name"],
            "address": settings["address"],
            "phone": settings["phone"],
            "isPaused": is_paused,
            "pauseReason": settings["pause_reason"],
            "isOpen": (status == "open"),
            "status": status,
            "statusText": status_text,
            "statusReason": status_reason,
            "schedule": settings["schedule"],
            "todaySchedule": get_today_schedule_text(settings["schedule"], now_dt),
            "deliveryTimeMin": min_m,
            "deliveryTimeMax": max_m,
            "deliveryTimeText": est_text,
            "freeShippingEnabled": settings["free_shipping_enabled"],
            "freeShippingThreshold": settings["free_shipping_threshold"],
            "defaultShippingFee": settings["default_shipping_fee"],
            "hasDeliveryZones": has_delivery_zones,
            "allZonesInactive": all_zones_inactive,
            "deliveryZones": active_zones,
        }

    @staticmethod
    def get_admin_store_settings(conn) -> dict:
        settings = StoreRepository.get_settings(conn)
        zones = StoreRepository.get_all_zones(conn)
        zone_counts = StoreRepository.get_zone_order_counts(conn)

        formatted_zones = [
            {
                "id": z["id"],
                "name": z["name"],
                "fee": z["fee"],
                "isActive": bool(z["is_active"]),
                "usedInOrders": zone_counts.get(z["id"], 0),
            }
            for z in zones
        ]
        return {
            "settings": settings,
            "zones": formatted_zones,
        }

    @staticmethod
    def update_store_settings(conn, p: dict) -> dict:
        current = StoreRepository.get_settings(conn)

        raw_name = p.get("storeName") if "storeName" in p else p.get("store_name", current["store_name"])
        store_name = text(raw_name, "Tên cửa hàng", 150)
        address = text(p.get("address", current["address"]), "Địa chỉ", 255, 0)
        phone = text(p.get("phone", current["phone"]), "Số điện thoại", 20, 0)
        raw_paused = p.get("isPaused") if "isPaused" in p else p.get("is_paused", current["is_paused"])
        is_paused = bool(raw_paused)
        raw_reason = p.get("pauseReason") if "pauseReason" in p else p.get("pause_reason", current["pause_reason"])
        pause_reason = text(raw_reason, "Lý do tạm ngừng", 255, 0)

        if "schedule" in p:
            cleaned_sched = validate_schedule(p["schedule"])
        else:
            cleaned_sched = current["schedule"]

        min_m = p.get("deliveryTimeMin") if "deliveryTimeMin" in p else p.get("delivery_time_min", current["delivery_time_min"])
        max_m = p.get("deliveryTimeMax") if "deliveryTimeMax" in p else p.get("delivery_time_max", current["delivery_time_max"])
        if min_m is not None:
            if type(min_m) is not int or min_m < 0 or min_m > 300:
                raise ApiError("Thời gian giao tối thiểu phải là số nguyên từ 0 đến 300 phút.")
        if max_m is not None:
            if type(max_m) is not int or max_m < 0 or max_m > 300:
                raise ApiError("Thời gian giao tối đa phải là số nguyên từ 0 đến 300 phút.")
        if min_m is not None and max_m is not None and min_m > max_m:
            raise ApiError("Thời gian giao tối thiểu không được lớn hơn thời gian giao tối đa.")

        raw_free = p.get("freeShippingEnabled") if "freeShippingEnabled" in p else p.get("free_shipping_enabled", current["free_shipping_enabled"])
        free_ship = bool(raw_free)
        raw_thresh = p.get("freeShippingThreshold") if "freeShippingThreshold" in p else p.get("free_shipping_threshold", current["free_shipping_threshold"])
        if type(raw_thresh) is not int or raw_thresh <= 0 or raw_thresh > 100_000_000:
            raise ApiError("Ngưỡng miễn phí giao hàng phải là số nguyên lớn hơn 0.")
        threshold = raw_thresh

        now_str = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat()
        StoreRepository.update_settings(
            conn, store_name, address, phone, int(is_paused), pause_reason,
            cleaned_sched, min_m, max_m, int(free_ship), threshold, now_str
        )
        conn.commit()
        return StoreRepository.get_settings(conn)

    @staticmethod
    def create_delivery_zone(conn, p: dict) -> int:
        name = text(p.get("name"), "Tên khu vực", 100)
        fee = p.get("fee")
        if type(fee) is not int or fee < 0 or fee > 10_000_000:
            raise ApiError("Phí giao hàng phải là số nguyên không âm.")
        is_active = p.get("isActive") if "isActive" in p else p.get("is_active", True)
        if type(is_active) is not bool:
            raise ApiError("Trạng thái khu vực không hợp lệ.")

        now_str = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat()
        zone_id = StoreRepository.insert_zone(conn, name, fee, int(is_active), now_str, now_str)
        conn.commit()
        return zone_id

    @staticmethod
    def update_delivery_zone(conn, zone_id: int, p: dict):
        zone = StoreRepository.get_zone_by_id(conn, zone_id)
        if not zone:
            raise ApiError("Khu vực giao hàng không tồn tại.", 404)

        name = text(p.get("name", zone["name"]), "Tên khu vực", 100) if "name" in p else zone["name"]
        fee = zone["fee"]
        if "fee" in p:
            raw_fee = p.get("fee")
            if type(raw_fee) is not int or raw_fee < 0 or raw_fee > 10_000_000:
                raise ApiError("Phí giao hàng phải là số nguyên không âm.")
            fee = raw_fee

        is_active = zone["is_active"]
        if "isActive" in p or "is_active" in p:
            raw_act = p.get("isActive") if "isActive" in p else p.get("is_active")
            if type(raw_act) is not bool:
                raise ApiError("Trạng thái khu vực không hợp lệ.")
            is_active = int(raw_act)

        now_str = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat()
        StoreRepository.update_zone(conn, zone_id, name, fee, is_active, now_str)
        conn.commit()

    @staticmethod
    def delete_delivery_zone(conn, zone_id: int):
        zone = StoreRepository.get_zone_by_id(conn, zone_id)
        if not zone:
            raise ApiError("Khu vực giao hàng không tồn tại.", 404)

        used_count = StoreRepository.count_zone_orders(conn, zone_id)
        if used_count > 0:
            raise ApiError("Khu vực này đã có đơn hàng trong lịch sử, hãy tắt nhận giao thay vì xóa.", 400)

        StoreRepository.delete_zone(conn, zone_id)
        conn.commit()
