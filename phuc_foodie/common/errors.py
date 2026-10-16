"""Xử lý lỗi tập trung và ngoại lệ nghiệp vụ cho PHUC-FOODIE."""
from flask import jsonify


class ApiError(Exception):
    """Ngoại lệ chuẩn cho các lỗi nghiệp vụ và xác thực dữ liệu API."""
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app):
    """Đăng ký các hàm xử lý lỗi HTTP và ApiError vào Flask app."""
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(413)
    def handle_too_large(_):
        return jsonify(error="Dữ liệu gửi lên quá lớn."), 413

    @app.errorhandler(500)
    def handle_server_error(_):
        return jsonify(error="Server gặp lỗi. Vui lòng thử lại."), 500
