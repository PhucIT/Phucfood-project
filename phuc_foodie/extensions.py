"""Khởi tạo và quản lý vòng đời tài nguyên cơ sở dữ liệu và OAuth trên request context."""
from flask import current_app, g
from authlib.integrations.flask_client import OAuth
from phuc_foodie.infrastructure.database import DatabaseConnection, create_database_engine
from phuc_foodie.infrastructure.schema import init_schema


def get_db() -> DatabaseConnection:
    """Lấy hoặc tạo kết nối cơ sở dữ liệu duy nhất cho request context hiện tại."""
    if "db" not in g:
        engine = current_app.extensions["db_engine"]
        raw_conn = engine.connect()
        g.db = DatabaseConnection(raw_conn)
    return g.db


def close_db(exception=None):
    """Đóng kết nối cơ sở dữ liệu khi request kết thúc, tự động rollback nếu gặp lỗi."""
    connection = g.pop("db", None)
    if connection is not None:
        if exception and connection.in_transaction():
            connection.rollback()
        connection.close()


def get_oauth_client(name="google"):
    """Lấy OAuth client từ ứng dụng hiện tại."""
    oauth = current_app.extensions.get("oauth")
    if not oauth:
        return None
    try:
        return oauth.create_client(name)
    except Exception:
        return None


def init_extensions(app, config=None):
    """Khởi tạo SQLAlchemy engine, kiểm tra schema, cấu hình OAuth và đăng ký teardown."""
    engine = create_database_engine(app.config)
    app.extensions = getattr(app, "extensions", {})
    app.extensions["db_engine"] = engine

    # Khởi tạo schema bảng trong MySQL nếu chưa có
    init_schema(engine, seed_products_if_empty=True)

    # Khởi tạo Authlib OAuth độc lập cho từng instance ứng dụng
    oauth = OAuth(app)
    client_id = app.config.get("GOOGLE_CLIENT_ID")
    client_secret = app.config.get("GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    app.extensions["oauth"] = oauth

    app.teardown_appcontext(close_db)
