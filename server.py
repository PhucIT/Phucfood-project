"""PHUC-FOODIE: Entry point máy chủ và CLI quản trị.
Mã nguồn đã được tái cấu trúc thành Modular Monolith trong package phuc_foodie/.
File này giữ vai trò entry point tương thích ngược.
"""
import argparse
from phuc_foodie import create_app
from phuc_foodie.cli import create_admin_interactive
from phuc_foodie.common.errors import ApiError
from phuc_foodie.modules.store.schedule import check_store_open, DEFAULT_SCHEDULE, DAY_KEYS
from phuc_foodie.modules.orders.pricing import VOUCHERS
from phuc_foodie.modules.orders.service import STATES, TRANSITIONS

__all__ = [
    "create_app",
    "check_store_open",
    "DEFAULT_SCHEDULE",
    "DAY_KEYS",
    "VOUCHERS",
    "STATES",
    "TRANSITIONS",
    "ApiError",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-admin", action="store_true", help="Tạo tài khoản quản trị bằng lời nhắc")
    args = parser.parse_args()

    app = create_app()

    if args.create_admin:
        create_admin_interactive(app)
    else:
        print("PHUC-FOODIE: http://127.0.0.1:5000 | Quản trị: http://127.0.0.1:5000/admin")
        app.run(host="127.0.0.1", port=5000, debug=False)
