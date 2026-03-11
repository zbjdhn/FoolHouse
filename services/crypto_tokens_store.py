import json
import os
from datetime import datetime
from typing import List, Dict
from utils.paths import get_data_dir
from utils.logger import logger

DATA_DIR = get_data_dir("data")
TOKENS_FILE = os.path.join(DATA_DIR, "crypto_tokens.json")
REQUESTS_FILE = os.path.join(DATA_DIR, "crypto_token_requests.json")

DEFAULT_TOKENS = ["BTC", "ETH", "SUI"]


def _read_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_tokens_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(TOKENS_FILE):
        _write_json(TOKENS_FILE, {"tokens": DEFAULT_TOKENS})
    if not os.path.exists(REQUESTS_FILE):
        _write_json(REQUESTS_FILE, {"requests": []})


def list_tokens() -> List[str]:
    ensure_tokens_file()
    data = _read_json(TOKENS_FILE, {"tokens": DEFAULT_TOKENS})
    tokens = data.get("tokens") or []
    # 去重并标准化大写
    out = []
    seen = set()
    for t in tokens:
        u = str(t or "").upper()
        if u and u not in seen:
            out.append(u)
            seen.add(u)
    return out


def add_token(code: str) -> bool:
    if not code:
        return False
    ensure_tokens_file()
    tokens = list_tokens()
    u = code.upper()
    if u in tokens:
        return False
    tokens.append(u)
    _write_json(TOKENS_FILE, {"tokens": tokens})
    # 清除已存在的同名请求
    reqs = list_requests()
    reqs = [r for r in reqs if (r.get("code") or "").upper() != u]
    _write_json(REQUESTS_FILE, {"requests": reqs})
    return True


def remove_token(code: str) -> bool:
    if not code:
        return False
    ensure_tokens_file()
    tokens = list_tokens()
    u = code.upper()
    if u not in tokens:
        return False
    tokens = [t for t in tokens if t != u]
    if not tokens:
        # 至少保留一个，避免空列表
        tokens = DEFAULT_TOKENS.copy()
    _write_json(TOKENS_FILE, {"tokens": tokens})
    return True


def list_requests() -> List[Dict]:
    ensure_tokens_file()
    data = _read_json(REQUESTS_FILE, {"requests": []})
    reqs = data.get("requests") or []
    # 规范化 code 大写
    for r in reqs:
        if "code" in r and r["code"]:
            r["code"] = str(r["code"]).upper()
    return reqs


def submit_request(username: str, code: str, name: str = "", reason: str = "") -> bool:
    if not username or not code:
        return False
    ensure_tokens_file()
    u = code.upper()
    # 已在允许列表中则不记录
    if u in list_tokens():
        return False
    reqs = list_requests()
    # 去重：同用户同代码不重复记录
    if any((r.get("user") == username and (r.get("code") or "").upper() == u) for r in reqs):
        return False
    reqs.append(
        {
            "user": username,
            "code": u,
            "name": name.strip(),
            "reason": reason.strip(),
            "ts": datetime.utcnow().isoformat() + "Z",
        }
    )
    _write_json(REQUESTS_FILE, {"requests": reqs})
    return True


def approve_request(code: str) -> bool:
    u = code.upper()
    if not u:
        return False
    ok = add_token(u)
    return ok
