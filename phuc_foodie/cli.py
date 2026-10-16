"""Giao diện dòng lệnh (CLI) cho PHUC-FOODIE: tạo tài khoản quản trị."""
import getpass
import re
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash


def create_admin_interactive(app):
    """Tạo tài khoản quản trị viên thông qua lời nhắc dòng lệnh."""
    name = input("Họ tên quản trị: ").strip()
    email = input("Email: ").strip().lower()
    phone = input("Số điện thoại (0 + 9 số): ").strip()
    pw = getpass.getpass("Mật khẩu (ít nhất 8 ký tự): ")
    if pw != getpass.getpass("Nhập lại mật khẩu: ") or not 8 <= len(pw) <= 128 or not name or not re.fullmatch(r"0\d{9}", phone) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise SystemExit("Thông tin không hợp lệ. Chưa tạo tài khoản.")

    with app.app_context():
        engine = app.extensions["db_engine"]
        with engine.begin() as conn:
            try:
                conn.execute(
                    text("INSERT INTO users (full_name, email, phone, password_hash, role) "
                         "VALUES (:name, :email, :phone, :hash, 'admin')"),
                    {"name": name, "email": email, "phone": phone, "hash": generate_password_hash(pw)}
                )
                print("Đã tạo quản trị. Đăng nhập tại /admin.")
            except IntegrityError:
                raise SystemExit("Email hoặc số điện thoại đã tồn tại. Không thay đổi quyền tài khoản cũ.")
