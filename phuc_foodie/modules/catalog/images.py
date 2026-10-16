"""Xử lý tải lên, kiểm tra định dạng và dọn dẹp ảnh món ăn an toàn bằng Pillow."""
import os
import secrets
from pathlib import Path
from PIL import Image
from phuc_foodie.common.errors import ApiError


def process_and_save_image(file_storage, upload_dir: Path) -> str:
    """Xác thực định dạng thật bằng Pillow, chuẩn hóa kích thước và lưu ảnh an toàn."""
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > 5 * 1024 * 1024:
        raise ApiError("Dung lượng ảnh tối đa là 5 MB.")
    if size == 0:
        raise ApiError("Tệp ảnh rỗng.")

    try:
        img = Image.open(file_storage.stream)
        img_format = (img.format or "").upper()
        if img_format not in ("JPEG", "PNG", "WEBP"):
            raise ApiError("Chỉ chấp nhận định dạng ảnh JPEG, PNG hoặc WebP.")

        width, height = img.size
        if width > 4000 or height > 4000 or (width * height) > 16_000_000:
            raise ApiError("Kích thước ảnh sau giải mã quá lớn (tối đa 4000x4000 pixels).")

        # Chuẩn hóa ảnh: thu nhỏ nếu vượt quá 1200x1200 giữ tỷ lệ
        img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            save_format = "WEBP"
            ext = "webp"
        else:
            img = img.convert("RGB")
            save_format = "JPEG"
            ext = "jpg"

        filename = f"{secrets.token_hex(16)}.{ext}"
        target_path = upload_dir / filename
        img.save(target_path, format=save_format, quality=85, optimize=True)
        return f"uploads/{filename}"
    except ApiError:
        raise
    except Exception as e:
        raise ApiError(f"Tệp không phải là ảnh hợp lệ hoặc bị lỗi: {e}")


def cleanup_unused_image(image_path: str, upload_dir: Path, db_conn, current_product_id: int = None):
    """Xóa ảnh cũ trong uploads/ nếu không còn sản phẩm nào sử dụng."""
    if not image_path or not image_path.startswith("uploads/"):
        return
    filename = Path(image_path).name
    query = "SELECT COUNT(*) AS cnt FROM products WHERE image = :img"
    params = {"img": image_path}
    if current_product_id:
        query += " AND id != :pid"
        params["pid"] = current_product_id
    res = db_conn.execute(query, params).fetchone()
    count = res["cnt"] if res else 0
    if count == 0:
        file_to_del = upload_dir / filename
        if file_to_del.is_file():
            try:
                file_to_del.unlink()
            except OSError:
                pass
