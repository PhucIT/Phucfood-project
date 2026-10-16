"""Nghiệp vụ đơn hàng: tạo đơn, trừ kho, hủy đơn, hoàn kho và chuyển trạng thái."""
import json
import re
import secrets
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError

from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import text
from phuc_foodie.modules.catalog.repository import CatalogRepository
from phuc_foodie.modules.orders.pricing import VOUCHERS, calculate_discount, calculate_shipping
from phuc_foodie.modules.orders.repository import OrderRepository
from phuc_foodie.modules.store.repository import StoreRepository
from phuc_foodie.modules.store.schedule import check_store_open

STATES = {
    "pending": "Chờ xác nhận",
    "confirmed": "Đã xác nhận",
    "preparing": "Đang chuẩn bị",
    "delivering": "Đang giao",
    "delivered": "Đã giao",
    "cancelled": "Đã hủy",
}

TRANSITIONS = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["preparing", "cancelled"],
    "preparing": ["delivering"],
    "delivering": ["delivered"],
    "delivered": [],
    "cancelled": [],
}


def serialize_order(row: dict) -> dict:
    p = json.loads(row["payload"])
    p.update(
        id=row["id"],
        orderStatus=row["state"],
        status=STATES.get(row["state"], row["state"]),
        createdAt=row["created_at"],
    )
    return p


class OrderService:
    @staticmethod
    def get_user_orders(conn, user_id: int) -> List[dict]:
        rows = OrderRepository.get_by_user(conn, user_id)
        return [serialize_order(r) for r in rows]

    @staticmethod
    def get_admin_orders(conn, limit: int = 1000) -> List[dict]:
        rows = OrderRepository.get_all_admin(conn, limit=limit)
        return [serialize_order(r) for r in rows]

    @staticmethod
    def place_order(conn, user_id: int, p: dict) -> dict:
        key = text(p.get("requestKey"), "Mã yêu cầu", 100, 16)
        customer = p.get("customer", {})
        if not isinstance(customer, dict):
            raise ApiError("Thông tin khách hàng không hợp lệ.")
        name = text(customer.get("name"), "Họ tên", 100)
        phone = text(customer.get("phone"), "Số điện thoại", 10)
        address = text(customer.get("address"), "Địa chỉ", 500)
        note = text(customer.get("note", ""), "Ghi chú", 1000, 0)
        if not re.fullmatch(r"0\d{9}", phone):
            raise ApiError("Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.")

        method = p.get("paymentMethod")
        if method not in ("cod", "bank_transfer", "qr_demo"):
            raise ApiError("Vui lòng chọn phương thức thanh toán.")
        if method != "cod" and p.get("demoConfirmed") is not True:
            raise ApiError("Vui lòng xác nhận đây là thanh toán DEMO.")

        old = OrderRepository.get_by_user_and_request_key(conn, user_id, key, for_update=True)
        if old:
            conn.rollback()
            return serialize_order(old), 200

        settings = StoreRepository.get_settings(conn)
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

        if settings["is_paused"]:
            conn.rollback()
            raise ApiError(settings["pause_reason"] or "Cửa hàng hiện đang tạm ngừng nhận đơn. Vui lòng quay lại sau.", 409)

        is_open, open_reason = check_store_open(settings["schedule"], now)
        if not is_open:
            conn.rollback()
            raise ApiError(f"Cửa hàng hiện đang ngoài giờ hoạt động ({open_reason}). Vui lòng quay lại vào giờ mở cửa.", 409)

        zones = StoreRepository.get_all_zones(conn)
        has_zones = len(zones) > 0
        active_zones = [z for z in zones if z["is_active"]]

        zone_id = None
        zone_name = None
        if has_zones:
            if len(active_zones) == 0:
                conn.rollback()
                raise ApiError("Cửa hàng hiện đang tạm dừng nhận giao hàng cho tất cả các khu vực.", 409)
            raw_zid = p.get("deliveryZoneId") or p.get("delivery_zone_id") or p.get("zoneId")
            if type(raw_zid) is not int:
                conn.rollback()
                raise ApiError("Vui lòng chọn khu vực giao hàng.", 400)
            selected_zone = next((z for z in active_zones if z["id"] == raw_zid), None)
            if not selected_zone:
                conn.rollback()
                raise ApiError("Khu vực giao hàng đã chọn không hợp lệ hoặc đang tạm ngừng nhận giao.", 400)
            base_shipping = selected_zone["fee"]
            zone_id = selected_zone["id"]
            zone_name = selected_zone["name"]
        else:
            base_shipping = settings["default_shipping_fee"]

        raw_items = p.get("items")
        if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 100:
            raise ApiError("Giỏ hàng không hợp lệ.")
        items, seen = [], set()

        sorted_raw_items = sorted(
            raw_items,
            key=lambda x: x.get("id") if isinstance(x, dict) and type(x.get("id")) is int else 0,
        )
        for item in sorted_raw_items:
            if not isinstance(item, dict) or type(item.get("id")) is not int or type(item.get("quantity")) is not int or not 1 <= item["quantity"] <= 99:
                conn.rollback()
                raise ApiError("Số lượng mỗi món phải từ 1 đến 99.")
            if item["id"] in seen:
                conn.rollback()
                raise ApiError("Món trong giỏ hàng bị trùng.")
            seen.add(item["id"])
            product = CatalogRepository.get_by_id(conn, item["id"], for_update=True)
            if not product:
                conn.rollback()
                raise ApiError(f"Món (mã {item['id']}) không tồn tại.", 404)
            if not product["available"]:
                conn.rollback()
                raise ApiError(f"Món '{product['name']}' hiện đang tạm ngừng bán. Vui lòng tải lại danh sách món.", 409)
            if product["stock_quantity"] is None:
                conn.rollback()
                raise ApiError(f"Món '{product['name']}' chưa sẵn sàng phục vụ. Vui lòng chọn món khác.", 409)
            if product["stock_quantity"] < item["quantity"]:
                conn.rollback()
                if product["stock_quantity"] == 0:
                    raise ApiError(f"Món '{product['name']}' đã hết hàng.", 409)
                else:
                    raise ApiError(f"Món '{product['name']}' chỉ còn {product['stock_quantity']} phần (bạn yêu cầu {item['quantity']} phần). Vui lòng điều chỉnh số lượng.", 409)

            CatalogRepository.deduct_stock(conn, product["id"], item["quantity"])

            items.append({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "image": product["image"],
                "quantity": item["quantity"],
                "subtotal": product["price"] * item["quantity"],
            })

        subtotal = sum(i["subtotal"] for i in items)
        voucher = p.get("voucherCode") or ""
        if not isinstance(voucher, str):
            conn.rollback()
            raise ApiError("Mã giảm giá không hợp lệ.")
        try:
            discount = calculate_discount(voucher, subtotal)
        except ApiError:
            conn.rollback()
            raise

        shipping = calculate_shipping(
            subtotal,
            base_shipping,
            settings["free_shipping_enabled"],
            settings["free_shipping_threshold"],
        )
        total = subtotal + shipping - discount

        if type(p.get("expectedTotal")) is not int or p["expectedTotal"] != total:
            conn.rollback()
            raise ApiError("Phí giao hàng hoặc tổng tiền đã thay đổi. Hãy tải lại trang và kiểm tra tổng tiền trước khi đặt.", 409)

        min_m = settings["delivery_time_min"]
        max_m = settings["delivery_time_max"]
        if min_m is not None and max_m is not None:
            est_time_str = f"{min_m} - {max_m} phút (ước tính)"
        elif min_m is not None:
            est_time_str = f"Khoảng {min_m} phút (ước tính)"
        else:
            est_time_str = None

        order_id = "PF-" + now.strftime("%Y%m%d") + "-" + secrets.token_hex(5).upper()
        order_dict = dict(
            customerName=name, customerPhone=phone, customerAddress=address, customerNote=note,
            deliveryZoneId=zone_id, deliveryZoneName=zone_name, estimatedDeliveryTime=est_time_str,
            items=items, subtotalPrice=subtotal, voucherCode=voucher.upper().strip() or None, discountAmount=discount,
            shippingFee=shipping, totalPrice=total, orderTime=now.strftime("%d/%m/%Y %H:%M"),
            paymentMethod=method, paymentStatus="pending" if method == "cod" else "demo_confirmed",
        )

        try:
            OrderRepository.insert(
                conn,
                order_id=order_id,
                user_id=user_id,
                payload_json=json.dumps(order_dict, ensure_ascii=False),
                created_at=now.isoformat(),
                request_key=key,
                zone_id=zone_id,
            )
            conn.commit()
        except IntegrityError:
            conn.rollback()
            existing = OrderRepository.get_by_user_and_request_key(conn, user_id, key)
            if existing:
                return serialize_order(existing), 200
            raise

        row = OrderRepository.get_by_id(conn, order_id)
        return serialize_order(row), 201

    @staticmethod
    def cancel_order(conn, user_id: int, order_id: str) -> None:
        order = OrderRepository.get_by_id(conn, order_id, user_id=user_id, for_update=True)
        if not order or order["state"] != "pending":
            conn.rollback()
            raise ApiError("Chỉ có thể hủy đơn của bạn khi đơn đang chờ xác nhận.", 409)

        if order["stock_deducted"] == 1:
            payload_data = json.loads(order["payload"])
            order_items = payload_data.get("items", [])
            sorted_order_items = sorted(order_items, key=lambda x: x["id"])
            for it in sorted_order_items:
                CatalogRepository.get_by_id(conn, it["id"], for_update=True)
                CatalogRepository.restore_stock(conn, it["id"], it["quantity"])

        OrderRepository.cancel_order(conn, order_id)
        conn.commit()

    @staticmethod
    def admin_update_order(conn, order_id: str, target: str) -> None:
        row = OrderRepository.get_by_id(conn, order_id, for_update=True)
        if not row:
            conn.rollback()
            raise ApiError("Không tìm thấy đơn hàng.", 404)
        if target not in TRANSITIONS[row["state"]]:
            conn.rollback()
            raise ApiError("Không thể chuyển sang trạng thái này.", 409)

        order = json.loads(row["payload"])
        if target == "delivered" and order.get("paymentMethod") == "cod":
            order["paymentStatus"] = "paid"

        if target == "cancelled" and row["stock_deducted"] == 1:
            order_items = order.get("items", [])
            sorted_order_items = sorted(order_items, key=lambda x: x["id"])
            for it in sorted_order_items:
                CatalogRepository.get_by_id(conn, it["id"], for_update=True)
                CatalogRepository.restore_stock(conn, it["id"], it["quantity"])
            stock_deducted_val = 0
        else:
            stock_deducted_val = row["stock_deducted"]

        OrderRepository.update_admin_state(
            conn,
            order_id=order_id,
            state=target,
            payload_json=json.dumps(order, ensure_ascii=False),
            stock_deducted=stock_deducted_val,
        )
        conn.commit()
