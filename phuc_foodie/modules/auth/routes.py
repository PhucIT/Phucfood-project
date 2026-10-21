"""Định tuyến API phiên làm việc, đăng ký, đăng nhập và khôi phục mật khẩu."""
import os
from urllib.parse import quote
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import payload
from phuc_foodie.extensions import get_db, get_oauth_client
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
    """Lấy trạng thái phiên khách hàng, CSRF token và trạng thái cấu hình Google OAuth."""
    sess = get_customer_session()
    u = customer_user()
    has_google = bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )
    return jsonify(
        user=public_user(u) if u else None,
        csrfToken=sess["csrf"],
        emailResetEnabled=bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM")),
        googleAuthEnabled=has_google,
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


@auth_bp.get("/api/auth/google")
def google_login():
    """Khởi tạo luồng xác thực Google OpenID Connect và chuyển hướng trình duyệt."""
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
    oauth_client = get_oauth_client("google")

    if not client_id or not client_secret or not oauth_client:
        return redirect("/?auth_error=" + quote("Đăng nhập Google hiện chưa được cấu hình. Vui lòng liên hệ quản trị."))

    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI")
    if not redirect_uri:
        redirect_uri = url_for("auth.google_callback", _external=True)

    return oauth_client.authorize_redirect(redirect_uri)


@auth_bp.get("/api/auth/google/callback")
def google_callback():
    """Nhận authorization code từ Google, xác minh ID Token và tạo phiên khách hàng."""
    error = request.args.get("error")
    if error:
        if error == "access_denied":
            msg = "Đăng nhập bị hủy bởi người dùng."
        else:
            msg = "Đăng nhập qua Google không thành công. Vui lòng thử lại."
        session.clear()
        return redirect("/?auth_error=" + quote(msg))

    oauth_client = get_oauth_client("google")
    if not oauth_client:
        session.clear()
        return redirect("/?auth_error=" + quote("Đăng nhập Google hiện chưa được cấu hình."))

    try:
        token = oauth_client.authorize_access_token()
    except MismatchingStateError:
        session.clear()
        return redirect("/?auth_error=" + quote("Phiên đăng nhập đã hết hạn hoặc trạng thái không hợp lệ. Vui lòng thử lại."))
    except OAuthError as e:
        current_app.logger.warning("Lỗi Google OAuth: %s", str(e))
        session.clear()
        return redirect("/?auth_error=" + quote("Không thể xác thực thông tin với Google. Vui lòng thử lại."))
    except Exception as e:
        current_app.logger.warning("Lỗi callback Google: %s", type(e).__name__)
        session.clear()
        return redirect("/?auth_error=" + quote("Đã xảy ra lỗi trong quá trình xác thực. Vui lòng thử lại."))

    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = oauth_client.parse_id_token(token)
        except Exception:
            userinfo = None

    if not userinfo:
        session.clear()
        return redirect("/?auth_error=" + quote("Không trích xuất được thông tin xác thực từ Google."))

    conn = get_db()
    try:
        AuthService.handle_google_callback(conn, userinfo)
    except ApiError as e:
        session.clear()
        return redirect("/?auth_error=" + quote(e.message))

    # Xóa dữ liệu tạm trong Flask OAuth session sau khi đăng nhập thành công
    session.clear()
    return redirect("/")
