"""Các hàm tiện ích xác thực dữ liệu đầu vào chuẩn hóa."""
from flask import request
from phuc_foodie.common.errors import ApiError


def payload() -> dict:
    """Trích xuất và xác thực dữ liệu JSON từ yêu cầu HTTP."""
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ApiError("Dữ liệu phải là JSON hợp lệ.")
    return value


def text(value, label: str, limit: int, minimum: int = 1) -> str:
    """Xác thực chuỗi văn bản theo độ dài tối thiểu và tối đa."""
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= limit:
        raise ApiError(f"{label}: cần từ {minimum} đến {limit} ký tự.")
    return value.strip()


def password(value) -> str:
    """Xác thực độ dài mật khẩu (8 đến 128 ký tự)."""
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        raise ApiError("Mật khẩu phải có từ 8 đến 128 ký tự.")
    return value
