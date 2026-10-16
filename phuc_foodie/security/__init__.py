"""Gói bảo mật: phiên độc lập, CSRF, phân quyền và rate limit."""
from phuc_foodie.security.sessions import (
    CUSTOMER_COOKIE_NAME,
    ADMIN_COOKIE_NAME,
    get_customer_session,
    set_customer_session,
    clear_customer_session,
    get_admin_session,
    set_admin_session,
    clear_admin_session,
    customer_user,
    admin_user,
    public_user,
    save_session_cookies,
)
from phuc_foodie.security.csrf import csrf_before_request
from phuc_foodie.security.permissions import auth
from phuc_foodie.security.rate_limits import rate_limit

__all__ = [
    "CUSTOMER_COOKIE_NAME",
    "ADMIN_COOKIE_NAME",
    "get_customer_session",
    "set_customer_session",
    "clear_customer_session",
    "get_admin_session",
    "set_admin_session",
    "clear_admin_session",
    "customer_user",
    "admin_user",
    "public_user",
    "save_session_cookies",
    "csrf_before_request",
    "auth",
    "rate_limit",
]
