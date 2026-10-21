"""Cấu hình toàn hệ thống PHUC-FOODIE. Quản lý đường dẫn và tham số môi trường theo từng app."""
import os
import secrets
from pathlib import Path
from dotenv import dotenv_values

# Thư mục gốc dự án (C:\WebDoAn)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Thư mục mặc định cấp dự án (dùng làm giá trị dự phòng nếu app không override)
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "uploads"
DEFAULT_IMAGES_DIR = PROJECT_ROOT / "images"
CATALOG_JSON_PATH = PROJECT_ROOT / "catalog.json"

# Biến tương thích ngược cho import trực tiếp
DATA_DIR = DEFAULT_DATA_DIR
UPLOAD_DIR = DEFAULT_UPLOAD_DIR
IMAGES_DIR = DEFAULT_IMAGES_DIR
SESSION_KEY_PATH = DEFAULT_DATA_DIR / "session.key"


def load_env_defaults() -> dict:
    """Đọc cấu hình mặc định từ .env.mysql và .env mà không ghi đè cấu hình hoặc os.environ."""
    env_dict = {}
    env_mysql_path = PROJECT_ROOT / ".env.mysql"
    if env_mysql_path.is_file():
        env_dict.update({k: v for k, v in dotenv_values(env_mysql_path).items() if v is not None})
    env_path = PROJECT_ROOT / ".env"
    if env_path.is_file():
        for k, v in dotenv_values(env_path).items():
            if v is not None and k not in env_dict:
                env_dict[k] = v
    return env_dict


def resolve_app_dirs(overrides=None):
    """
    Xác định thư mục data và upload theo thứ tự ưu tiên rõ ràng:
    1. config truyền vào factory (overrides)
    2. biến môi trường (PHUC_DATA_DIR, PHUC_UPLOAD_DIR)
    3. mặc định thư mục gốc dự án
    """
    overrides = overrides or {}

    upload_val = (
        overrides.get("UPLOAD_DIR")
        or overrides.get("UPLOAD_FOLDER")
        or overrides.get("PHUC_UPLOAD_DIR")
        or os.environ.get("PHUC_UPLOAD_DIR")
        or DEFAULT_UPLOAD_DIR
    )
    upload_dir = Path(upload_val).resolve()

    data_val = (
        overrides.get("DATA_DIR")
        or overrides.get("PHUC_DATA_DIR")
        or os.environ.get("PHUC_DATA_DIR")
        or DEFAULT_DATA_DIR
    )
    data_dir = Path(data_val).resolve()

    return data_dir, upload_dir


def get_secret_key(data_dir: Path, explicit_secret: str = None) -> str:
    """
    Lấy hoặc tạo khóa bí mật bền vững cho phiên làm việc.
    Nếu có explicit_secret (truyền vào config) hoặc biến môi trường SECRET_KEY,
    dùng trực tiếp và TUYỆT ĐỐI không tạo session.key trên đĩa.
    """
    if explicit_secret:
        return explicit_secret

    env_secret = os.environ.get("SECRET_KEY")
    if env_secret:
        return env_secret

    session_key_path = data_dir / "session.key"
    data_dir.mkdir(parents=True, exist_ok=True)
    if not session_key_path.exists():
        try:
            fd = os.open(session_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_hex(48))
        except FileExistsError:
            pass

    return session_key_path.read_text().strip()


def get_app_config(overrides=None) -> dict:
    """Trả về từ điển cấu hình ứng dụng Flask cho từng instance app."""
    overrides = overrides or {}
    env_defaults = load_env_defaults()
    data_dir, upload_dir = resolve_app_dirs(overrides)

    explicit_secret = overrides.get("SECRET_KEY")
    secret_key = get_secret_key(data_dir, explicit_secret=explicit_secret)

    # Chỉ tạo thư mục upload/data khi không có cờ tránh tạo thư mục hoặc khi chạy bình thường
    upload_dir.mkdir(parents=True, exist_ok=True)
    if not explicit_secret and not os.environ.get("SECRET_KEY"):
        data_dir.mkdir(parents=True, exist_ok=True)

    # Nạp cấu hình Google OAuth theo thứ tự ưu tiên: overrides -> os.environ -> .env.mysql
    google_client_id = (
        overrides.get("GOOGLE_CLIENT_ID")
        or os.environ.get("GOOGLE_CLIENT_ID")
        or env_defaults.get("GOOGLE_CLIENT_ID")
    )
    google_client_secret = (
        overrides.get("GOOGLE_CLIENT_SECRET")
        or os.environ.get("GOOGLE_CLIENT_SECRET")
        or env_defaults.get("GOOGLE_CLIENT_SECRET")
    )
    google_redirect_uri = (
        overrides.get("GOOGLE_REDIRECT_URI")
        or os.environ.get("GOOGLE_REDIRECT_URI")
        or env_defaults.get("GOOGLE_REDIRECT_URI")
    )

    config = {
        "SECRET_KEY": secret_key,
        "DATA_DIR": data_dir,
        "PHUC_DATA_DIR": str(data_dir),
        "UPLOAD_DIR": upload_dir,
        "UPLOAD_FOLDER": str(upload_dir),
        "PHUC_UPLOAD_DIR": str(upload_dir),
        "MAX_CONTENT_LENGTH": 6 * 1024 * 1024,
        "SESSION_COOKIE_NAME": "foodie_oauth_session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": os.environ.get("COOKIE_SECURE") == "1",
        "GOOGLE_CLIENT_ID": google_client_id,
        "GOOGLE_CLIENT_SECRET": google_client_secret,
        "GOOGLE_REDIRECT_URI": google_redirect_uri,
    }
    config.update(overrides)
    # Đảm bảo DATA_DIR và UPLOAD_DIR trong app.config luôn là Path object
    config["DATA_DIR"] = Path(config.get("DATA_DIR") or config.get("PHUC_DATA_DIR")).resolve()
    config["UPLOAD_DIR"] = Path(config.get("UPLOAD_DIR") or config.get("UPLOAD_FOLDER") or config.get("PHUC_UPLOAD_DIR")).resolve()
    return config
