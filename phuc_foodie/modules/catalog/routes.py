"""Định tuyến API danh mục sản phẩm, tồn kho và upload ảnh."""
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request
from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import payload
from phuc_foodie.extensions import get_db
from phuc_foodie.modules.catalog.images import process_and_save_image
from phuc_foodie.modules.catalog.service import CatalogService
from phuc_foodie.security.permissions import auth

catalog_bp = Blueprint("catalog", __name__)


def _get_app_upload_dir() -> Path:
    """Lấy thư mục upload của instance app hiện tại từ current_app.config."""
    return Path(current_app.config.get("UPLOAD_DIR") or current_app.config.get("UPLOAD_FOLDER"))


@catalog_bp.get("/api/products")
def list_products():
    """Lấy danh sách toàn bộ món ăn công khai."""
    products = CatalogService.list_products(get_db())
    return jsonify(products=products)


@catalog_bp.post("/api/admin/products")
@auth(admin=True)
def add_product():
    """Admin thêm món ăn mới vào thực đơn."""
    p = payload()
    new_id = CatalogService.create_product(get_db(), p)
    return jsonify(id=new_id, message="Đã thêm món."), 201


@catalog_bp.patch("/api/admin/products/<product_id>")
@auth(admin=True)
def update_product(product_id):
    """Admin cập nhật thông tin, giá, danh mục, tồn kho hoặc bật/tắt bán món ăn."""
    try:
        pid = int(product_id)
    except (ValueError, TypeError):
        raise ApiError("Mã món ăn không hợp lệ.", 400)

    p = payload()
    upload_dir = _get_app_upload_dir()
    CatalogService.update_product(get_db(), pid, p, upload_dir)
    return jsonify(message="Đã lưu món.")


@catalog_bp.post("/api/admin/upload")
@auth(admin=True)
def admin_upload_image():
    """Admin tải ảnh món ăn từ máy tính lên máy chủ."""
    f = request.files.get("file") or request.files.get("image")
    if not f or not f.filename:
        raise ApiError("Vui lòng chọn tệp ảnh để tải lên.")
    upload_dir = _get_app_upload_dir()
    saved_path = process_and_save_image(f, upload_dir)
    return jsonify(image=saved_path), 201
