"""Decorator phân quyền và xác thực người dùng."""
import functools
from flask import g
from phuc_foodie.common.errors import ApiError
from phuc_foodie.security.sessions import admin_user, customer_user


def auth(admin: bool = False):
    """Decorator yêu cầu đăng nhập khách hàng hoặc quyền quản trị viên."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapped(*a, **kw):
            if admin:
                g.user = admin_user()
                if not g.user:
                    if customer_user():
                        raise ApiError("Bạn không có quyền quản trị.", 403)
                    raise ApiError("Vui lòng đăng nhập quản trị để tiếp tục.", 401)
            else:
                g.user = customer_user()
                if not g.user:
                    raise ApiError("Vui lòng đăng nhập để tiếp tục.", 401)
            return fn(*a, **kw)
        return wrapped
    return decorator
