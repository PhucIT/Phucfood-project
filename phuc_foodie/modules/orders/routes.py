"""Định tuyến API đơn hàng khách và quản trị đơn hàng."""
from flask import Blueprint, g, jsonify
from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import payload
from phuc_foodie.extensions import get_db
from phuc_foodie.modules.orders.service import OrderService
from phuc_foodie.security.permissions import auth

orders_bp = Blueprint("orders", __name__)


@orders_bp.get("/api/orders")
@auth()
def orders():
    """Khách xem lịch sử đơn hàng của chính mình."""
    conn = get_db()
    items = OrderService.get_user_orders(conn, g.user["id"])
    return jsonify(orders=items)


@orders_bp.post("/api/orders")
@auth()
def place_order():
    """Khách tạo đơn hàng mới, khóa và trừ tồn kho trong transaction."""
    p = payload()
    conn = get_db()
    order_dict, status_code = OrderService.place_order(conn, g.user["id"], p)
    return jsonify(order=order_dict), status_code


@orders_bp.post("/api/orders/<order_id>/cancel")
@auth()
def cancel_order(order_id):
    """Khách hủy đơn hàng đang chờ xác nhận, tự động hoàn lại tồn kho."""
    conn = get_db()
    OrderService.cancel_order(conn, g.user["id"], order_id)
    return jsonify(message="Đã hủy đơn hàng.")


@orders_bp.get("/api/admin/orders")
@auth(admin=True)
def admin_orders():
    """Admin xem danh sách tối đa 1.000 đơn hàng gần nhất."""
    conn = get_db()
    items = OrderService.get_admin_orders(conn, limit=1000)
    return jsonify(orders=items)


@orders_bp.patch("/api/admin/orders/<order_id>")
@auth(admin=True)
def update_order(order_id):
    """Admin chuyển trạng thái đơn hàng (nếu hủy đơn sẽ tự động hoàn kho)."""
    target = payload().get("state")
    if not target:
        raise ApiError("Thiếu trạng thái mục tiêu.", 400)
    conn = get_db()
    OrderService.admin_update_order(conn, order_id, target)
    return jsonify(message="Đã cập nhật trạng thái.")
