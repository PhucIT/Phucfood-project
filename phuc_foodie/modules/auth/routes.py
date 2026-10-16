"""Định tuyến API phiên làm việc, đăng ký, đăng nhập và khôi phục mật khẩu."""
import os
from flask import Blueprint, jsonify
from phuc_foodie.common.validation import payload
from phuc_foodie.extensions import get_db
from phuc_foodie.modules.auth.service import AuthService
from phuc_foodie.security.rate_limits import rate_limit
from phuc_foodie.security.sessions import (
    admin_user,
    customer_user,
    get_admin_session,
    get_customer_session,
    public_user,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/api/session")
def get_session():
    """Lấy trạng thái phiên khách hàng và CSRF token."""
    sess = get_customer_session()
    u = customer_user()
    return jsonify(
        user=public_user(u) if u else None,
        csrfToken=sess["csrf"],
        emailResetEnabled=bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM")),
    )


@auth_bp.get("/api/admin/session")
def get_admin_session_route():
    """Lấy trạng thái phiên quản trị viên và CSRF token riêng."""
    sess = get_admin_session()
    u = admin_user()
    return jsonify(
        user=public_user(u) if u else None,
        csrfToken=sess["csrf"],
    )


@auth_bp.post("/api/register")
def register():
    """Đăng ký tài khoản khách hàng mới."""
    rate_limit("register", 10)
    p = payload()
    conn = get_db()
    AuthService.register(conn, p)
    return jsonify(message="Đăng ký thành công. Vui lòng đăng nhập."), 201


@auth_bp.post("/api/login")
def login():
    """Đăng nhập khách hàng bằng email hoặc số điện thoại."""
    rate_limit("login", 15)
    p = payload()
    conn = get_db()
    user_info = AuthService.login_customer(conn, p)
    return jsonify(user=user_info, csrfToken=get_customer_session()["csrf"])


@auth_bp.post("/api/logout")
def logout():
    """Đăng xuất khách hàng và hủy token phiên trong cơ sở dữ liệu."""
    conn = get_db()
    AuthService.logout_customer(conn)
    return jsonify(csrfToken=get_customer_session()["csrf"])


@auth_bp.post("/api/admin/login")
def admin_login():
    """Đăng nhập trang quản trị viên."""
    rate_limit("admin_login", 15)
    p = payload()
    conn = get_db()
    user_info = AuthService.login_admin(conn, p)
    return jsonify(user=user_info, csrfToken=get_admin_session()["csrf"])


@auth_bp.post("/api/admin/logout")
def admin_logout():
    """Đăng xuất quản trị viên và hủy token phiên trong cơ sở dữ liệu."""
    conn = get_db()
    AuthService.logout_admin(conn)
    return jsonify(csrfToken=get_admin_session()["csrf"])


@auth_bp.post("/api/password/forgot")
def forgot():
    """Yêu cầu gửi mã đặt lại mật khẩu qua email."""
    rate_limit("forgot", 5)
    p = payload()
    conn = get_db()
    AuthService.forgot_password(conn, p)
    return jsonify(message="Nếu email đã được đăng ký, mã xác nhận sẽ được gửi đến hộp thư của bạn.")


@auth_bp.post("/api/password/reset")
def reset():
    """Đặt lại mật khẩu mới bằng mã xác nhận 6 số."""
    rate_limit("reset", 15)
    p = payload()
    conn = get_db()
    AuthService.reset_password(conn, p)
    return jsonify(message="Đã đổi mật khẩu. Vui lòng đăng nhập lại.")
