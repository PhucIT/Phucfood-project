"""Compatibility facade cho database.py tại thư mục gốc.
Giữ nguyên giao diện để các migration scripts và test suite hoạt động không đổi.
"""
from phuc_foodie.infrastructure.database import (
    DatabaseConnection,
    QueryResult,
    build_connection_url,
    create_database_engine,
)
from phuc_foodie.infrastructure.schema import SCHEMA_STATEMENTS, init_schema

__all__ = [
    "DatabaseConnection",
    "QueryResult",
    "build_connection_url",
    "create_database_engine",
    "init_schema",
    "SCHEMA_STATEMENTS",
]
