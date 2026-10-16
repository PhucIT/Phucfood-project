"""Quản lý phiên khách hàng và quản trị viên độc lập trong cùng một trình duyệt."""
import hashlib
import secrets
import time
from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from phuc_foodie.extensions import get_db

CUSTOMER_COOKIE_NAME = "foodie_customer_session"
ADMIN_COOKIE_NAME = "foodie_admin_session"


def get_customer_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="phuc-foodie-customer-session")


def get_admin_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="phuc-foodie-admin-session")


def get_customer_session() -> dict:
    if "customer_session" not in g:
        secret = current_app.config["SECRET_KEY"]
        serializer = get_customer_serializer(secret)
        cookie_val = request.cookies.get(CUSTOMER_COOKIE_NAME) or request.cookies.get("session")
        data = None
        if cookie_val:
            try:
                data = serializer.loads(cookie_val, max_age=8 * 3600)
            except (BadSignature, SignatureExpired):
                data = None
        if not isinstance(data, dict):
            data = {"sid": None, "csrf": secrets.token_hex(32)}
            g.customer_session_modified = True
        elif not data.get("csrf"):
            data["csrf"] = secrets.token_hex(32)
            g.customer_session_modified = True
        g.customer_session = data
    return g.customer_session


def set_customer_session(sid: str, csrf: str = None):
    sess = get_customer_session()
    sess["sid"] = sid
    if csrf:
        sess["csrf"] = csrf
    g.customer_session_modified = True


def clear_customer_session():
    sess = get_customer_session()
    sess["sid"] = None
    g.customer_session_modified = True


def get_admin_session() -> dict:
    if "admin_session" not in g:
        secret = current_app.config["SECRET_KEY"]
        serializer = get_admin_serializer(secret)
        cookie_val = request.cookies.get(ADMIN_COOKIE_NAME)
        data = None
        if cookie_val:
            try:
                data = serializer.loads(cookie_val, max_age=8 * 3600)
            except (BadSignature, SignatureExpired):
                data = None
        if not isinstance(data, dict):
            data = {"sid": None, "csrf": secrets.token_hex(32)}
            g.admin_session_modified = True
        elif not data.get("csrf"):
            data["csrf"] = secrets.token_hex(32)
            g.admin_session_modified = True
        g.admin_session = data
    return g.admin_session


def set_admin_session(sid: str, csrf: str = None):
    sess = get_admin_session()
    sess["sid"] = sid
    if csrf:
        sess["csrf"] = csrf
    g.admin_session_modified = True


def clear_admin_session():
    sess = get_admin_session()
    sess["sid"] = None
    g.admin_session_modified = True


def customer_user():
    """Lấy thông tin người dùng khách hàng đang đăng nhập từ session hiện tại."""
    sid = get_customer_session().get("sid")
    if not sid:
        return None
    return get_db().execute(
        "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id "
        "WHERE s.token_hash = :hash AND s.expires > :now",
        {"hash": hashlib.sha256(sid.encode()).hexdigest(), "now": time.time()}
    ).fetchone()


def admin_user():
    """Lấy thông tin quản trị viên đang đăng nhập từ session admin hiện tại."""
    sid = get_admin_session().get("sid")
    if not sid:
        return None
    u = get_db().execute(
        "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id "
        "WHERE s.token_hash = :hash AND s.expires > :now",
        {"hash": hashlib.sha256(sid.encode()).hexdigest(), "now": time.time()}
    ).fetchone()
    if u and u["role"] == "admin":
        return u
    return None


def public_user(u) -> dict:
    """Định dạng dữ liệu người dùng an toàn trả về cho client."""
    if not u:
        return None
    return {
        "id": u["id"],
        "fullName": u["full_name"],
        "email": u["email"],
        "phone": u["phone"],
        "role": u["role"]
    }


def save_session_cookies(response):
    """Gắn cookie phiên khách và admin vào response nếu có thay đổi."""
    secret = current_app.config["SECRET_KEY"]
    secure = current_app.config.get("SESSION_COOKIE_SECURE", False)
    samesite = current_app.config.get("SESSION_COOKIE_SAMESITE", "Lax")
    httponly = True

    if getattr(g, "customer_session_modified", False) and "customer_session" in g:
        customer_serializer = get_customer_serializer(secret)
        cookie_data = customer_serializer.dumps(g.customer_session)
        response.set_cookie(
            CUSTOMER_COOKIE_NAME,
            cookie_data,
            max_age=8 * 3600,
            httponly=httponly,
            samesite=samesite,
            secure=secure,
            path="/"
        )
    if getattr(g, "admin_session_modified", False) and "admin_session" in g:
        admin_serializer = get_admin_serializer(secret)
        cookie_data = admin_serializer.dumps(g.admin_session)
        response.set_cookie(
            ADMIN_COOKIE_NAME,
            cookie_data,
            max_age=8 * 3600,
            httponly=httponly,
            samesite=samesite,
            secure=secure,
            path="/"
        )
    return response
