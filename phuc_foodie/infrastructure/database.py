"""Cấu hình và kết nối cơ sở dữ liệu MySQL (SQLAlchemy Core + PyMySQL)."""
import os
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from phuc_foodie.config import PROJECT_ROOT


class QueryResult:
    """Wrapper cho kết quả truy vấn SQLAlchemy với giao diện mappings()."""
    def __init__(self, sa_result):
        self._res = sa_result

    @property
    def rowcount(self):
        return self._res.rowcount

    @property
    def lastrowid(self):
        return self._res.lastrowid

    def fetchone(self):
        return self._res.mappings().fetchone()

    def fetchall(self):
        return self._res.mappings().fetchall()

    def __iter__(self):
        return iter(self._res.mappings())


class DatabaseConnection:
    """Wrapper cho kết nối cơ sở dữ liệu SQLAlchemy."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, statement, parameters=None):
        stmt = text(statement) if isinstance(statement, str) else statement
        params = parameters or {}
        return QueryResult(self._conn.execute(stmt, params))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def in_transaction(self):
        return self._conn.in_transaction()

    def close(self):
        self._conn.close()


def build_connection_url(config=None):
    """Xây dựng SQLAlchemy URL an toàn, đọc cấu hình từ .env.mysql, .env và config."""
    cfg = {}
    env_mysql_path = PROJECT_ROOT / ".env.mysql"
    if env_mysql_path.is_file():
        cfg.update(dotenv_values(env_mysql_path))

    env_path = PROJECT_ROOT / ".env"
    if env_path.is_file():
        for k, v in dotenv_values(env_path).items():
            if k.startswith("MYSQL_"):
                cfg[k] = v

    for k in ("MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_HOST", "MYSQL_PORT"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]

    if config:
        cfg.update(config)

    db_name = cfg.get("MYSQL_DATABASE")
    user = cfg.get("MYSQL_USER")
    password = cfg.get("MYSQL_PASSWORD")
    host = cfg.get("MYSQL_HOST", "127.0.0.1")
    port = int(cfg.get("MYSQL_PORT", 3308))

    if not db_name or not user or not password:
        raise RuntimeError(
            "Cấu hình MySQL không đầy đủ! Vui lòng kiểm tra MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD trong .env.mysql."
        )

    return URL.create(
        drivername="mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=db_name,
        query={"charset": "utf8mb4"}
    ), db_name, host, port


def create_database_engine(config=None):
    """Tạo SQLAlchemy engine và kiểm tra kết nối tới MySQL."""
    if config and config.get("DATABASE_URI"):
        uri = config["DATABASE_URI"]
        return create_engine(uri, pool_pre_ping=True)

    url, db_name, host, port = build_connection_url(config)
    try:
        engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        raise RuntimeError(
            f"Không thể kết nối tới MySQL Docker tại {host}:{port}/{db_name}. Lỗi: {e}"
        ) from e
