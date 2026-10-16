"""Nghiệp vụ xác thực người dùng khách và admin, cấp/hủy phiên, quên mật khẩu."""
import hashlib
import logging
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from phuc_foodie.common.errors import ApiError
from phuc_foodie.common.validation import password, text
from phuc_foodie.modules.auth.repository import AuthRepository
from phuc_foodie.security.sessions import (
    clear_admin_session,
    clear_customer_session,
    get_admin_session,
    get_customer_session,
    public_user,
    set_admin_session,
    set_customer_session,
)


class AuthService:
    @staticmethod
    def register(conn, p: dict):
        name = text(p.get("fullName"), "Họ tên", 100)
        email = text(p.get("email"), "Email", 254).lower()
        phone = text(p.get("phone"), "Số điện thoại", 10)
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not re.fullmatch(r"0\d{9}", phone):
            raise ApiError("Email hoặc số điện thoại không hợp lệ.")
        if p.get("terms") is not True:
            raise ApiError("Vui lòng đồng ý điều khoản sử dụng.")
        pw = password(p.get("password"))
        try:
            AuthRepository.create_user(conn, name, email, phone, generate_password_hash(pw))
            conn.commit()
        except IntegrityError:
            conn.rollback()
            raise ApiError("Email hoặc số điện thoại đã được đăng ký.", 409)

    @staticmethod
    def login_customer(conn, p: dict) -> dict:
        identifier = text(p.get("identifier"), "Email/Số điện thoại", 254).lower()
        pw = p.get("password")
        if not isinstance(pw, str) or not 1 <= len(pw) <= 128:
            raise ApiError("Vui lòng nhập mật khẩu hợp lệ.")
        u = AuthRepository.get_user_by_identifier(conn, identifier)
        if not u or not check_password_hash(u["password_hash"], pw):
            raise ApiError("Thông tin đăng nhập không đúng.", 401)

        old_sid = get_customer_session().get("sid", "")
        if old_sid:
            AuthRepository.delete_session_by_hash(conn, hashlib.sha256(old_sid.encode()).hexdigest())

        sid = secrets.token_urlsafe(48)
        AuthRepository.delete_expired_sessions(conn)
        AuthRepository.create_session(
            conn,
            token_hash=hashlib.sha256(sid.encode()).hexdigest(),
            user_id=u["id"],
            expires=time.time() + 8 * 3600,
        )
        conn.commit()

        set_customer_session(sid, csrf=secrets.token_hex(32))
        return public_user(u)

    @staticmethod
    def logout_customer(conn):
        sid = get_customer_session().get("sid", "")
        if sid:
            AuthRepository.delete_session_by_hash(conn, hashlib.sha256(sid.encode()).hexdigest())
            conn.commit()
        clear_customer_session()

    @staticmethod
    def login_admin(conn, p: dict) -> dict:
        identifier = text(p.get("identifier"), "Email/Số điện thoại", 254).lower()
        pw = p.get("password")
        if not isinstance(pw, str) or not 1 <= len(pw) <= 128:
            raise ApiError("Vui lòng nhập mật khẩu hợp lệ.")
        u = AuthRepository.get_user_by_identifier(conn, identifier)
        if not u or not check_password_hash(u["password_hash"], pw):
            raise ApiError("Thông tin đăng nhập không đúng.", 401)
        if u["role"] != "admin":
            raise ApiError("Tài khoản này không có quyền quản trị.", 403)

        old_sid = get_admin_session().get("sid", "")
        if old_sid:
            AuthRepository.delete_session_by_hash(conn, hashlib.sha256(old_sid.encode()).hexdigest())

        sid = secrets.token_urlsafe(48)
        AuthRepository.delete_expired_sessions(conn)
        AuthRepository.create_session(
            conn,
            token_hash=hashlib.sha256(sid.encode()).hexdigest(),
            user_id=u["id"],
            expires=time.time() + 8 * 3600,
        )
        conn.commit()

        set_admin_session(sid, csrf=secrets.token_hex(32))
        return public_user(u)

    @staticmethod
    def logout_admin(conn):
        sid = get_admin_session().get("sid", "")
        if sid:
            AuthRepository.delete_session_by_hash(conn, hashlib.sha256(sid.encode()).hexdigest())
            conn.commit()
        clear_admin_session()

    @staticmethod
    def forgot_password(conn, p: dict):
        email = text(p.get("email"), "Email", 254).lower()
        if not os.environ.get("SMTP_HOST") or not os.environ.get("SMTP_FROM"):
            raise ApiError("Chưa cấu hình email. Vui lòng liên hệ quản trị để hỗ trợ tài khoản.", 503)
        u = AuthRepository.get_user_by_email(conn, email)
        if u:
            code = str(secrets.randbelow(900000) + 100000)
            token_hash = hashlib.sha256((email + code).encode()).hexdigest()
            AuthRepository.upsert_reset_token(conn, email, token_hash, time.time() + 600)
            conn.commit()
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = "PHUC-FOODIE — Đặt lại mật khẩu", os.environ["SMTP_FROM"], email
            msg.set_content(f"Mã xác nhận: {code}\nCó hiệu lực 10 phút. Không chia sẻ mã này với người khác.")
            try:
                port = int(os.environ.get("SMTP_PORT", "587"))
                if port == 465:
                    smtp = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=15, context=ssl.create_default_context())
                else:
                    smtp = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=15)
                    smtp.starttls(context=ssl.create_default_context())
                with smtp:
                    if os.environ.get("SMTP_USER"):
                        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                    smtp.send_message(msg)
            except Exception:
                logging.exception("Không gửi được email đặt lại mật khẩu")
                AuthRepository.delete_reset_token(conn, email)
                conn.commit()
                raise ApiError("Chưa gửi được email. Vui lòng thử lại sau.", 503)

    @staticmethod
    def reset_password(conn, p: dict):
        email = text(p.get("email"), "Email", 254).lower()
        code = text(p.get("code"), "Mã xác nhận", 6, 6)
        pw = password(p.get("password"))

        row = AuthRepository.get_reset_token_for_update(conn, email)
        if not row or row["expires"] < time.time() or row["attempts"] >= 5:
            conn.rollback()
            raise ApiError("Mã không hợp lệ hoặc đã hết hạn.")
        if not secrets.compare_digest(row["token_hash"], hashlib.sha256((email + code).encode()).hexdigest()):
            AuthRepository.increment_reset_attempts(conn, email)
            conn.commit()
            raise ApiError("Mã xác nhận không chính xác.")

        AuthRepository.update_password(conn, email, generate_password_hash(pw))
        AuthRepository.delete_user_sessions_by_email(conn, email)
        AuthRepository.delete_reset_token(conn, email)
        conn.commit()
        clear_customer_session()
