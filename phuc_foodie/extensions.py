"""Khởi tạo và quản lý vòng đời tài nguyên cơ sở dữ liệu trên request context."""
from flask import current_app, g
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


def init_extensions(app, config=None):
    """Khởi tạo SQLAlchemy engine, kiểm tra schema và đăng ký teardown."""
    engine = create_database_engine(app.config)
    app.extensions = getattr(app, "extensions", {})
    app.extensions["db_engine"] = engine

    # Khởi tạo schema bảng trong MySQL nếu chưa có
    init_schema(engine, seed_products_if_empty=True)

    app.teardown_appcontext(close_db)
