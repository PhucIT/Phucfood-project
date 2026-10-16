"""Kiểm soát tần suất gửi yêu cầu (Rate Limiting) để chống tấn công brute-force."""
import time
from flask import request
from phuc_foodie.common.errors import ApiError
from phuc_foodie.extensions import get_db


def rate_limit(action: str, maximum: int = 10, period: int = 900):
    """Giới hạn số lần thao tác của một địa chỉ IP trong khoảng thời gian nhất định."""
    key = action + ":" + (request.remote_addr or "local")
    now = time.time()
    c = get_db()
    row = c.execute("SELECT * FROM rate_limits WHERE `key` = :key FOR UPDATE", {"key": key}).fetchone()
    if row and now - row["started"] < period:
        if row["count"] >= maximum:
            c.rollback()
            raise ApiError("Bạn thao tác quá nhiều. Vui lòng thử lại sau.", 429)
        c.execute("UPDATE rate_limits SET `count` = `count` + 1 WHERE `key` = :key", {"key": key})
    else:
        c.execute(
            "INSERT INTO rate_limits (`key`, `count`, `started`) VALUES (:key, 1, :started) "
            "ON DUPLICATE KEY UPDATE `count` = 1, `started` = :started",
            {"key": key, "started": now}
        )
    c.execute("DELETE FROM rate_limits WHERE `started` < :cutoff", {"cutoff": now - 86400})
    c.commit()
