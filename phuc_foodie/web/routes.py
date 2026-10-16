"""Định tuyến giao diện người dùng và phục vụ tài nguyên tĩnh có kiểm soát."""
import re
from pathlib import Path
from flask import Blueprint, abort, current_app, send_from_directory
from phuc_foodie.config import PROJECT_ROOT

web_bp = Blueprint("web", __name__)

ALLOWED_STATIC_FILES = {
    "script.js",
    "api.js",
    "style.css",
    "app.css",
    "admin.js",
    "admin.css",
    "favicon.svg",
}


@web_bp.get("/")
def index():
    """Trang chủ dành cho khách hàng."""
    return send_from_directory(PROJECT_ROOT, "index.html")


@web_bp.get("/admin")
def admin_page():
    """Trang quản trị viên."""
    return send_from_directory(PROJECT_ROOT, "admin.html")


@web_bp.get("/<filename>")
def asset(filename):
    """Chỉ cho phép tải các file giao diện tĩnh được quy định."""
    if filename not in ALLOWED_STATIC_FILES:
        abort(404)
    return send_from_directory(PROJECT_ROOT, filename)


@web_bp.get("/images/<filename>")
def image(filename):
    """Phục vụ ảnh mẫu từ thư mục images/."""
    if not re.fullmatch(r"[\w-]+\.(jpg|png|webp)", filename):
        abort(404)
    return send_from_directory(PROJECT_ROOT / "images", filename)


@web_bp.get("/uploads/<filename>")
def uploaded_image(filename):
    """Phục vụ ảnh tải lên từ thư mục uploads/ của instance app hiện tại."""
    if not re.fullmatch(r"[\w-]+\.(jpg|jpeg|png|webp)", filename):
        abort(404)
    upload_dir = Path(current_app.config.get("UPLOAD_DIR") or current_app.config.get("UPLOAD_FOLDER"))
    return send_from_directory(upload_dir, filename)
