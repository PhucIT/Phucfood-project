"""Xử lý và thẩm định lịch mở cửa, ca hoạt động theo tuần theo múi giờ Asia/Ho_Chi_Minh."""
import re
from datetime import datetime
from phuc_foodie.common.errors import ApiError

DEFAULT_SCHEDULE = {
    str(i): {
        "is_closed": False,
        "ranges": [{"open": "00:00", "close": "23:59"}]
    }
    for i in range(7)
}

DAY_KEYS = [
    ("0", "mon", "Thứ Hai"),
    ("1", "tue", "Thứ Ba"),
    ("2", "wed", "Thứ Tư"),
    ("3", "thu", "Thứ Năm"),
    ("4", "fri", "Thứ Sáu"),
    ("5", "sat", "Thứ Bảy"),
    ("6", "sun", "Chủ Nhật"),
]


def check_store_open(schedule, now_dt: datetime):
    """
    Kiểm tra cửa hàng có đang mở cửa tại thời điểm now_dt (Asia/Ho_Chi_Minh).
    - Hỗ trợ ngày nghỉ (is_closed).
    - Hỗ trợ nhiều khoảng giờ trong ngày.
    - Hỗ trợ khoảng giờ qua nửa đêm (ví dụ: 18:00 - 02:00 sáng hôm sau).
    - Ranh giới: mở lúc open_str, đóng lúc close_str (open <= current < close).
    """
    if not schedule:
        return True, "Mở cả ngày"

    weekday = now_dt.weekday()  # 0 = Monday ... 6 = Sunday
    yesterday = (weekday - 1) % 7
    curr_hm = now_dt.strftime("%H:%M")

    # 1. Kiểm tra ca tối hôm qua có kéo dài qua nửa đêm sang hôm nay không
    yesterday_cfg = schedule.get(str(yesterday)) or schedule.get(yesterday) or {}
    if not yesterday_cfg.get("is_closed", False):
        for r in yesterday_cfg.get("ranges", []):
            o = (r.get("open") or "").strip()
            c = (r.get("close") or "").strip()
            if o and c and o > c:  # Qua nửa đêm (ví dụ 18:00 -> 02:00)
                if curr_hm < c:  # Trước giờ đóng ca đêm
                    return True, f"Đang mở cửa (ca đêm {o} - {c})"

    # 2. Kiểm tra các khoảng giờ trong ngày hôm nay
    today_cfg = schedule.get(str(weekday)) or schedule.get(weekday) or {}
    if today_cfg.get("is_closed", False):
        return False, "Hôm nay cửa hàng nghỉ"

    ranges = today_cfg.get("ranges", [])
    if not ranges:
        return False, "Chưa thiết lập giờ mở cửa hôm nay"

    for r in ranges:
        o = (r.get("open") or "").strip()
        c = (r.get("close") or "").strip()
        if not o or not c:
            continue
        if o <= c:
            if o <= curr_hm < c:
                return True, f"Đang mở cửa ({o} - {c})"
        else:
            if curr_hm >= o:
                return True, f"Đang mở cửa (ca tối {o} - {c})"

    return False, "Ngoài giờ hoạt động"


def validate_schedule(sched: dict) -> dict:
    """Xác thực định dạng cấu hình lịch mở cửa tuần."""
    if not isinstance(sched, dict):
        raise ApiError("Dữ liệu lịch hoạt động phải là đối tượng.")
    cleaned = {}
    time_regex = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    for d_num, d_str, d_label in DAY_KEYS:
        cfg = sched.get(d_num) or sched.get(int(d_num)) or sched.get(d_str) or {}
        if not isinstance(cfg, dict):
            raise ApiError(f"Cấu hình ngày {d_label} không hợp lệ.")
        if "is_closed" in cfg:
            is_closed = bool(cfg["is_closed"])
        elif "isOpen" in cfg:
            is_closed = not bool(cfg["isOpen"])
        else:
            is_closed = False
        cleaned_ranges = []
        if not is_closed:
            ranges = cfg.get("ranges", [])
            if not isinstance(ranges, list):
                raise ApiError(f"Danh sách khoảng giờ ngày {d_label} không hợp lệ.")
            for r in ranges:
                if not isinstance(r, dict):
                    raise ApiError(f"Khoảng giờ ngày {d_label} phải là đối tượng có open và close.")
                o = (r.get("open") or "").strip()
                c = (r.get("close") or "").strip()
                if not time_regex.match(o) or not time_regex.match(c):
                    raise ApiError(f"Giờ mở ({o}) hoặc giờ đóng ({c}) không đúng định dạng HH:MM (00:00 - 23:59).")
                cleaned_ranges.append({"open": o, "close": c})
        day_dict = {
            "is_closed": is_closed,
            "isOpen": not is_closed,
            "ranges": cleaned_ranges
        }
        cleaned[d_num] = day_dict
        cleaned[d_str] = day_dict
    return cleaned


def get_today_schedule_text(schedule, now_dt: datetime) -> str:
    """Tạo chuỗi tóm tắt lịch hoạt động hôm nay để hiển thị."""
    if not schedule:
        return "Mở cả ngày"
    weekday = now_dt.weekday()
    cfg = schedule.get(str(weekday)) or schedule.get(weekday) or {}
    if cfg.get("is_closed", False):
        return "Nghỉ hôm nay"
    ranges = cfg.get("ranges", [])
    if not ranges:
        return "Chưa cập nhật giờ"
    return ", ".join(f"{r['open']} - {r['close']}" for r in ranges)
