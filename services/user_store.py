import json
import os
import hashlib
from typing import List, Dict, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _choose_data_dir() -> str:
    env_path = os.environ.get("FOOLHOUSE_DATA_DIR")
    if env_path:
        try:
            os.makedirs(env_path, exist_ok=True)
            return env_path
        except OSError:
            pass
    default_path = os.path.join(ROOT_DIR, "data")
    try:
        os.makedirs(default_path, exist_ok=True)
        return default_path
    except OSError:
        tmp_path = os.path.join("/tmp", "foolhouse", "data")
        os.makedirs(tmp_path, exist_ok=True)
        return tmp_path

DATA_DIR = _choose_data_dir()
USERS_FILE = os.path.join(DATA_DIR, "users.json")


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_users_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        users = [
            {"username": "admin", "password_hash": _hash("001123"), "is_admin": True},
            {"username": "ada", "password_hash": _hash("001123"), "is_admin": False},
        ]
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)


def _load_users() -> List[Dict]:
    ensure_users_file()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: List[Dict]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def get_user(username: str) -> Optional[Dict]:
    for u in _load_users():
        if u.get("username") == username:
            return u
    return None


def verify_password(username: str, password: str) -> bool:
    u = get_user(username)
    if not u:
        return False
    return u.get("password_hash") == _hash(password)


def is_admin(username: str) -> bool:
    u = get_user(username)
    return bool(u and u.get("is_admin"))


def create_user(username: str, password: str, is_admin_flag: bool = False) -> bool:
    if not username or not password:
        return False
    users = _load_users()
    for u in users:
        if u.get("username") == username:
            return False
    users.append({"username": username, "password_hash": _hash(password), "is_admin": is_admin_flag})
    _save_users(users)
    return True


def list_users() -> List[Dict]:
    return _load_users()
