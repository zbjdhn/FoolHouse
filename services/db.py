import pymysql
import os
import certifi
from dotenv import load_dotenv
from dbutils.pooled_db import PooledDB
from utils.logger import logger

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
        # Vercel 专用配置：由于 Serverless 函数频繁冷启动，maxconnections 不宜过大
        _POOL = PooledDB(
            creator=pymysql,
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 4000)),
            user=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
            cursorclass=pymysql.cursors.DictCursor,
            ssl={'ca': certifi.where()},
            # Vercel 环境下，预热连接设为 0 以加快冷启动
            mincached=0,
            maxcached=5,
            maxconnections=10,
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
    初始化数据库和表。
    在 Vercel 环境下，尽量避免在代码中创建数据库，而是在控制台手动创建。
    """
    db_name = os.getenv("DB_DATABASE")
    if db_name == "sys":
        logger.warning("正在尝试连接 'sys' 库。这在云数据库上通常会因为权限不足而失败。请在环境变量中更换数据库名。")

    # 1. 尝试直接连接目标库（如果库已存在，这是最安全的方式）
    try:
        conn = get_db_connection()
    except Exception as e:
        # 如果连接失败，尝试连接服务器并创建数据库
        logger.info(f"无法直接连接到库 '{db_name}'，尝试自动创建: {e}")
        try:
            temp_conn = pymysql.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT", 4000)),
                user=os.getenv("DB_USERNAME"),
                password=os.getenv("DB_PASSWORD"),
                ssl={'ca': certifi.where()}
            )
            with temp_conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            temp_conn.commit()
            temp_conn.close()
            # 创建完后再次尝试获取池连接
            conn = get_db_connection()
        except Exception as e_create:
            logger.error(f"严重错误: 无法创建数据库 '{db_name}'。权限不足或连接失败: {e_create}")
            logger.info("提示: 请在 TiDB Cloud 控制台手动创建数据库并更新环境变量。")
            return

    # 2. 从池中获取连接并创建表
    try:
        with conn.cursor() as cursor:
            # 创建 trades 表
            logger.info(f"正在检查或创建数据库表 'trades'...")
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
            logger.info(f"正在检查或创建数据库表 'users'...")
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
        logger.info("数据库初始化完成。")
    finally:
        conn.close()
