"""Nghiệp vụ quản lý danh mục món ăn, tồn kho và ảnh sản phẩm."""
import re
from pathlib import Path
from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import text
from phuc_foodie.modules.catalog.images import cleanup_unused_image
from phuc_foodie.modules.catalog.repository import CatalogRepository


def product_fields(p: dict, is_update: bool = False, old_product: dict = None):
    """Xác thực và chuẩn hóa các trường thông tin của món ăn."""
    if not is_update or "name" in p:
        name = text(p.get("name"), "Tên món", 100)
    else:
        name = old_product["name"]

    if not is_update or "price" in p:
        price = p.get("price")
        if type(price) is not int or not 1000 <= price <= 10000000:
            raise ApiError("Giá phải là số nguyên từ 1.000 đến 10.000.000đ.")
    else:
        price = old_product["price"]

    if not is_update or "category" in p:
        category = p.get("category")
        if category not in ("Đồ ăn", "Nước uống", "Combo"):
            raise ApiError("Danh mục không hợp lệ.")
    else:
        category = old_product["category"]

    if not is_update or "image" in p:
        img_val = p.get("image")
        if not is_update and not img_val:
            raise ApiError("Vui lòng chọn ảnh cho món ăn.")
        if img_val:
            image_path = text(img_val, "Đường dẫn ảnh", 150)
            if not re.fullmatch(r"(images/[\w-]+\.(jpg|png|webp)|uploads/[\w-]+\.(jpg|jpeg|png|webp))", image_path):
                raise ApiError("Đường dẫn ảnh không hợp lệ.")
        else:
            image_path = old_product["image"] if old_product else ""
    else:
        image_path = old_product["image"]

    if not is_update or "description" in p:
        desc = text(p.get("description", ""), "Mô tả", 1000, 0)
    else:
        desc = old_product["description"]

    if not is_update or "available" in p:
        available = p.get("available")
        if type(available) is not bool:
            raise ApiError("Trạng thái còn hàng không hợp lệ.")
        available_val = int(available)
    else:
        available_val = old_product["available"]

    if "stock_quantity" in p:
        stock_qty = p.get("stock_quantity")
        if stock_qty is not None:
            if type(stock_qty) is not int or stock_qty < 0:
                raise ApiError("Số lượng tồn kho phải là số nguyên không âm (>= 0).")
    elif not is_update:
        stock_qty = p.get("stock_quantity")
        if stock_qty is not None and (type(stock_qty) is not int or stock_qty < 0):
            raise ApiError("Số lượng tồn kho phải là số nguyên không âm (>= 0).")
    else:
        stock_qty = old_product["stock_quantity"]

    return name, price, category, image_path, desc, available_val, stock_qty


class CatalogService:
    @staticmethod
    def list_products(conn):
        return CatalogRepository.get_all(conn)

    @staticmethod
    def create_product(conn, data: dict) -> int:
        name, price, category, image_path, desc, available, stock_qty = product_fields(data, is_update=False)
        new_id = CatalogRepository.insert(conn, name, price, category, image_path, desc, available, stock_qty)
        conn.commit()
        return new_id

    @staticmethod
    def update_product(conn, product_id: int, data: dict, upload_dir: Path):
        old = CatalogRepository.get_by_id(conn, product_id, for_update=True)
        if not old:
            conn.rollback()
            raise ApiError("Không tìm thấy món ăn.", 404)

        name, price, category, image_path, desc, available, stock_qty = product_fields(data, is_update=True, old_product=old)
        old_image = old["image"]
        CatalogRepository.update(conn, product_id, name, price, category, image_path, desc, available, stock_qty)
        conn.commit()

        # Dọn dẹp ảnh cũ nếu đã đổi sang ảnh mới
        if old_image != image_path:
            cleanup_unused_image(old_image, upload_dir, conn, current_product_id=product_id)
