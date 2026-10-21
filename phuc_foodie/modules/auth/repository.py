"""Truy xuất dữ liệu người dùng, phiên và token khôi phục mật khẩu."""
import time
from typing import Optional


class AuthRepository:
    @staticmethod
    def get_user_by_id(conn, user_id: int) -> Optional[dict]:
        return conn.execute("SELECT * FROM users WHERE id = :id", {"id": user_id}).fetchone()

    @staticmethod
    def get_user_by_email(conn, email: str) -> Optional[dict]:
        return conn.execute("SELECT * FROM users WHERE email = :email", {"email": email}).fetchone()

    @staticmethod
    def get_user_by_identifier(conn, identifier: str) -> Optional[dict]:
        return conn.execute(
            "SELECT * FROM users WHERE email = :id1 OR phone = :id2",
            {"id1": identifier, "id2": identifier}
        ).fetchone()

    @staticmethod
    def create_user(conn, full_name: str, email: str, phone: str, password_hash: str) -> int:
        cur = conn.execute(
            "INSERT INTO users (full_name, email, phone, password_hash) VALUES (:name, :email, :phone, :hash)",
            {"name": full_name, "email": email, "phone": phone, "hash": password_hash}
        )
        return cur.lastrowid

    @staticmethod
    def update_password(conn, email: str, password_hash: str):
        conn.execute(
            "UPDATE users SET password_hash = :hash WHERE email = :email",
            {"hash": password_hash, "email": email}
        )

    @staticmethod
    def delete_session_by_hash(conn, token_hash: str):
        conn.execute("DELETE FROM sessions WHERE token_hash = :hash", {"hash": token_hash})

    @staticmethod
    def delete_expired_sessions(conn):
        conn.execute("DELETE FROM sessions WHERE expires < :now", {"now": time.time()})

    @staticmethod
    def create_session(conn, token_hash: str, user_id: int, expires: float):
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires) VALUES (:hash, :uid, :exp)",
            {"hash": token_hash, "uid": user_id, "exp": expires}
        )

    @staticmethod
    def delete_user_sessions_by_email(conn, email: str):
        conn.execute("DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = :email)", {"email": email})

    @staticmethod
    def upsert_reset_token(conn, email: str, token_hash: str, expires: float):
        conn.execute(
            "INSERT INTO reset_tokens (email, token_hash, expires, attempts) VALUES (:email, :hash, :exp, 0) "
            "ON DUPLICATE KEY UPDATE token_hash = :hash, expires = :exp, attempts = 0",
            {"email": email, "hash": token_hash, "exp": expires}
        )

    @staticmethod
    def get_reset_token_for_update(conn, email: str) -> Optional[dict]:
        return conn.execute("SELECT * FROM reset_tokens WHERE email = :email FOR UPDATE", {"email": email}).fetchone()

    @staticmethod
    def increment_reset_attempts(conn, email: str):
        conn.execute("UPDATE reset_tokens SET attempts = attempts + 1 WHERE email = :email", {"email": email})

    @staticmethod
    def delete_reset_token(conn, email: str):
        conn.execute("DELETE FROM reset_tokens WHERE email = :email", {"email": email})

    @staticmethod
    def get_identity(conn, provider: str, provider_id: str) -> Optional[dict]:
        return conn.execute(
            "SELECT * FROM user_identities WHERE provider = :provider AND provider_id = :pid",
            {"provider": provider, "pid": provider_id}
        ).fetchone()

    @staticmethod
    def get_user_with_identity(conn, provider: str, provider_id: str) -> Optional[dict]:
        return conn.execute(
            "SELECT u.* FROM users u "
            "JOIN user_identities i ON i.user_id = u.id "
            "WHERE i.provider = :provider AND i.provider_id = :pid",
            {"provider": provider, "pid": provider_id}
        ).fetchone()

    @staticmethod
    def create_oauth_customer(conn, full_name: str, email: str, provider: str, provider_id: str) -> dict:
        cur = conn.execute(
            "INSERT INTO users (full_name, email, phone, password_hash, role) "
            "VALUES (:name, :email, NULL, NULL, 'customer')",
            {"name": full_name, "email": email}
        )
        user_id = cur.lastrowid
        import datetime
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO user_identities (user_id, provider, provider_id, email, created_at, updated_at) "
            "VALUES (:uid, :provider, :pid, :email, :created, :updated)",
            {"uid": user_id, "provider": provider, "pid": provider_id, "email": email, "created": now_str, "updated": now_str}
        )
        return conn.execute("SELECT * FROM users WHERE id = :id", {"id": user_id}).fetchone()
