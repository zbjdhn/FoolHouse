import hashlib
import pymysql
import threading
import os
from typing import List, Dict, Optional
from services.db import get_db_connection, init_db
from utils.security import hash_password
from utils.logger import logger

# 用户信息内存缓存
_USER_CACHE = {}
_CACHE_LOCK = threading.RLock()

def ensure_users_file() -> None:
    """
    确保数据库表已创建，并进行初始用户数据迁移，同时预加载缓存。
    优先从环境变量读取管理员密码。
    """
    init_db()
    # 检查是否需要迁移
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 检查 admin 是否已存在
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            admin_exists = cursor.fetchone()
            
            if not admin_exists:
                # 初始管理员密码：优先读取环境变量 ADMIN_PASSWORD，否则使用默认值
                admin_pwd = os.getenv("ADMIN_PASSWORD", "001123")
                ada_pwd = os.getenv("ADA_PASSWORD", "001123")
                
                users = [
                    ("admin", hash_password(admin_pwd), True),
                    ("ada", hash_password(ada_pwd), False),
                ]
                cursor.executemany(
                    "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
                    users
                )
                conn.commit()
                logger.info(f"数据库初始化成功，已创建默认用户（管理员密码{'源自环境变量' if os.getenv('ADMIN_PASSWORD') else '使用默认值'}）。")
            
            # 2. 预加载所有用户信息到缓存
            cursor.execute("SELECT * FROM users")
            all_users = cursor.fetchall()
            with _CACHE_LOCK:
                _USER_CACHE.clear()
                for u in all_users:
                    _USER_CACHE[u['username']] = u
    finally:
        conn.close()

def get_user(username: str) -> Optional[Dict]:
    """
    优先从内存缓存中获取用户信息，实现极速响应
    """
    with _CACHE_LOCK:
        if username in _USER_CACHE:
            return _USER_CACHE[username]
    
    # 缓存未命中（虽然 ensure_users_file 会预加载，但为了健壮性保留 DB 查询）
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if user:
                with _CACHE_LOCK:
                    _USER_CACHE[username] = user
            return user
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    极速验证：完全基于内存缓存进行匹配，无需数据库连接
    """
    u = get_user(username)
    if u and u.get("password_hash") == hash_password(password):
        return u
    return None

def verify_password(username: str, password: str) -> bool:
    u = get_user(username)
    if not u:
        return False
    return u.get("password_hash") == hash_password(password)

def is_admin(username: str) -> bool:
    u = get_user(username)
    return bool(u and u.get("is_admin"))

def create_user(username: str, password: str, is_admin_flag: bool = False) -> tuple[bool, str]:
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return False, "用户名和密码不能为空"
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查用户是否存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "用户已存在"
            
            cursor.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
                (username, hash_password(password), is_admin_flag)
            )
            conn.commit()
            
            # 更新缓存
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            new_user = cursor.fetchone()
            if new_user:
                with _CACHE_LOCK:
                    _USER_CACHE[username] = new_user
            
            return True, "用户创建成功"
    except Exception as e:
        return False, f"用户创建失败：{str(e)}"
    finally:
        conn.close()

def list_users() -> List[Dict]:
    """
    优先返回缓存中的用户列表
    """
    with _CACHE_LOCK:
        if _USER_CACHE:
            return list(_USER_CACHE.values())
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
            # 顺便更新缓存
            with _CACHE_LOCK:
                _USER_CACHE.clear()
                for u in users:
                    _USER_CACHE[u['username']] = u
            return users
    finally:
        conn.close()

def delete_user(username: str) -> tuple[bool, str]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT is_admin FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                return False, "用户不存在"
            
            if user['is_admin']:
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = TRUE")
                admin_count = cursor.fetchone()['count']
                if admin_count <= 1:
                    return False, "至少保留一个管理员"
            
            cursor.execute("DELETE FROM users WHERE username = %s", (username,))
            conn.commit()
            
            # 清理缓存
            with _CACHE_LOCK:
                _USER_CACHE.pop(username, None)
                
            return True, "用户已删除"
    finally:
        conn.close()

def update_password(username: str, new_password: str) -> tuple[bool, str]:
    if not new_password:
        return False, "密码不能为空"
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if not cursor.fetchone():
                return False, "用户不存在"
            
            new_hash = hash_password(new_password)
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s",
                (new_hash, username)
            )
            conn.commit()
            
            # 更新缓存中的密码哈希
            with _CACHE_LOCK:
                if username in _USER_CACHE:
                    _USER_CACHE[username]['password_hash'] = new_hash
            
            return True, "密码已更新"
    finally:
        conn.close()
