"""Xác thực bảo vệ CSRF độc lập cho các endpoint khách và admin."""
import secrets
from flask import request
from phuc_foodie.common.errors import ApiError
from phuc_foodie.security.sessions import get_admin_session, get_customer_session


def csrf_before_request():
    """Kiểm tra CSRF Token cho các phương thức thay đổi trạng thái (POST, PATCH, DELETE)."""
    if request.path.startswith("/api/") and request.method in ("POST", "PATCH", "DELETE"):
        supplied = request.headers.get("X-CSRF-Token", "")
        if request.path.startswith("/api/admin/"):
            expected = get_admin_session().get("csrf", "")
        else:
            expected = get_customer_session().get("csrf", "")

        if not expected or not secrets.compare_digest(expected, supplied):
            raise ApiError("Phiên làm việc không hợp lệ. Hãy tải lại trang.", 403)
