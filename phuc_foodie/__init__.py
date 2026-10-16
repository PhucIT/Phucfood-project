"""PHUC-FOODIE: Khởi tạo ứng dụng Flask theo mô hình Modular Monolith."""
import os
from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from phuc_foodie.common.errors import ApiError, register_error_handlers
from phuc_foodie.config import get_app_config
from phuc_foodie.extensions import init_extensions
from phuc_foodie.security.csrf import csrf_before_request
from phuc_foodie.security.sessions import save_session_cookies

# Modules
from phuc_foodie.modules.auth.routes import auth_bp
from phuc_foodie.modules.catalog.routes import catalog_bp
from phuc_foodie.modules.orders.routes import orders_bp
from phuc_foodie.modules.store.routes import store_bp
from phuc_foodie.web.routes import web_bp


def create_app(config=None):
    """Application factory khởi tạo Flask app, extensions, blueprints và middleware."""
    app = Flask(__name__, static_folder=None)

    # Nạp cấu hình ứng dụng
    app_cfg = get_app_config(config)
    app.config.update(app_cfg)

    if os.environ.get("BEHIND_PROXY") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # Khởi tạo kết nối cơ sở dữ liệu và schema
    init_extensions(app, config)

    # Đăng ký middleware kiểm tra CSRF
    app.before_request(csrf_before_request)

    # Đăng ký middleware gắn security headers và lưu cookie session
    @app.after_request
    def set_security_headers_and_cookies(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return save_session_cookies(response)

    # Đăng ký xử lý lỗi chuẩn
    register_error_handlers(app)

    # Đăng ký các Blueprint nghiệp vụ và giao diện
    app.register_blueprint(web_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(store_bp)

    return app


__all__ = ["create_app"]
