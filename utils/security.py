import hashlib

def hash_password(password: str) -> str:
    """
    使用 SHA-256 对密码进行哈希处理。
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
