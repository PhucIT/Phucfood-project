"""Định tuyến API thông tin cửa hàng, lịch hoạt động và cấu hình giao hàng."""
from flask import Blueprint, jsonify
from phuc_foodie.common.validation import payload
from phuc_foodie.extensions import get_db
from phuc_foodie.modules.store.service import StoreService
from phuc_foodie.security.permissions import auth

store_bp = Blueprint("store", __name__)


@store_bp.get("/api/store-info")
def get_store_info():
    """Lấy thông tin công khai của cửa hàng, trạng thái mở cửa và khu vực giao hàng."""
    conn = get_db()
    info = StoreService.get_public_store_info(conn)
    return jsonify(**info)


@store_bp.get("/api/admin/store/settings")
@auth(admin=True)
def admin_get_store_settings():
    """Admin lấy toàn bộ cấu hình cửa hàng, lịch hoạt động và danh sách khu vực."""
    conn = get_db()
    res = StoreService.get_admin_store_settings(conn)
    return jsonify(**res)


@store_bp.patch("/api/admin/store/settings")
@auth(admin=True)
def admin_update_store_settings():
    """Admin cập nhật cấu hình cửa hàng, trạng thái tạm ngưng, lịch mở cửa và phí ship."""
    p = payload()
    conn = get_db()
    settings = StoreService.update_store_settings(conn, p)
    return jsonify(message="Đã lưu cấu hình cửa hàng.", settings=settings)


@store_bp.post("/api/admin/delivery-zones")
@auth(admin=True)
def admin_create_delivery_zone():
    """Admin tạo khu vực giao hàng mới."""
    p = payload()
    conn = get_db()
    zid = StoreService.create_delivery_zone(conn, p)
    return jsonify(id=zid, message="Đã thêm khu vực giao hàng."), 201


@store_bp.patch("/api/admin/delivery-zones/<int:zone_id>")
@auth(admin=True)
def admin_update_delivery_zone(zone_id: int):
    """Admin cập nhật khu vực giao hàng hoặc bật/tắt hoạt động."""
    p = payload()
    conn = get_db()
    StoreService.update_delivery_zone(conn, zone_id, p)
    return jsonify(message="Đã cập nhật khu vực giao hàng.")


@store_bp.delete("/api/admin/delivery-zones/<int:zone_id>")
@auth(admin=True)
def admin_delete_delivery_zone(zone_id: int):
    """Admin xóa khu vực giao hàng nếu chưa từng được sử dụng trong đơn hàng."""
    conn = get_db()
    StoreService.delete_delivery_zone(conn, zone_id)
    return jsonify(message="Đã xóa khu vực giao hàng.")
