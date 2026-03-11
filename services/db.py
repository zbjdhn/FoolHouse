import pymysql
import os
import certifi
from dotenv import load_dotenv
from dbutils.pooled_db import PooledDB

# 加载 .env 文件
load_dotenv()

# 全局数据库连接池
_POOL = None

def get_pool():
    """
    获取或初始化数据库连接池
    """
    global _POOL
    if _POOL is None:
        _POOL = PooledDB(
            creator=pymysql,
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 4000)),
            user=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
            cursorclass=pymysql.cursors.DictCursor,
            ssl={'ca': certifi.where()},
            # 快速启动：预热1个连接；高并发时按需创建，最多20个
            mincached=1,
            maxcached=20,
            maxconnections=30,
            blocking=True
        )
    return _POOL

def get_db_connection():
    """
    从池中获取 MySQL/TiDB 数据库连接
    """
    return get_pool().connection()

def init_db():
    """
    初始化数据库和表
    """
    # 1. 先不指定数据库连接，尝试创建数据库
    # 注意：连接池通常指定了具体数据库，这里手动创建一个临时连接来创建数据库
    try:
        temp_conn = pymysql.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 4000)),
            user=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            ssl={'ca': certifi.where()}
        )
        db_name = os.getenv("DB_DATABASE")
        with temp_conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        temp_conn.commit()
        temp_conn.close()
    except Exception as e:
        print(f"尝试创建数据库失败 (可能是权限不足，如果数据库已存在可忽略): {e}")

    # 2. 从池中获取连接并创建表
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 创建 trades 表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner VARCHAR(255),
                date VARCHAR(20),
                code VARCHAR(20),
                name VARCHAR(255),
                side VARCHAR(10),
                price DECIMAL(18, 4),
                quantity DECIMAL(18, 4),
                amount DECIMAL(18, 4),
                amount_auto VARCHAR(10) DEFAULT '0',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # 创建 users 表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
        conn.commit()
    finally:
        conn.close()
