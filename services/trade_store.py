import os
import pymysql
from typing import List, Tuple
from services.db import get_db_connection, init_db
from utils.logger import logger

# CSV 相关的常量保留，用于可能的迁移
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "trades.csv")
CSV_HEADERS = ["owner", "date", "code", "name", "side", "price", "quantity", "amount", "amount_auto"]

def ensure_data_file() -> None:
    """
    确保数据库表已创建
    """
    try:
        init_db()
    except Exception as e:
        logger.error(f"初始化数据库失败: {e}")

def append_trade(trade: dict) -> None:
    """
    将交易记录写入数据库
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO trades (owner, date, code, name, side, price, quantity, amount, amount_auto)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                trade.get("owner"),
                trade.get("date"),
                trade.get("code"),
                trade.get("name"),
                trade.get("side"),
                trade.get("price"),
                trade.get("quantity"),
                trade.get("amount"),
                trade.get("amount_auto", "0") or "0"
            ))
        conn.commit()
    finally:
        conn.close()

def load_trades(owner: str | None = None) -> List[dict]:
    """
    从数据库加载交易记录
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 优先使用 id 排序，如果不存在 id 则回退到 created_at
            order_by = "ORDER BY date DESC, id DESC"
            try:
                if owner:
                    cursor.execute(f"SELECT * FROM trades WHERE owner = %s {order_by}", (owner,))
                else:
                    cursor.execute(f"SELECT * FROM trades {order_by}")
            except Exception:
                # 兼容老旧表结构（没有 id 列）
                order_by = "ORDER BY date DESC, created_at DESC"
                if owner:
                    cursor.execute(f"SELECT * FROM trades WHERE owner = %s {order_by}", (owner,))
                else:
                    cursor.execute(f"SELECT * FROM trades {order_by}")
            
            trades = cursor.fetchall()
            
            # 转换为与之前 CSV 读取一致的格式（主要是数值转字符串）
            for t in trades:
                t['price'] = str(t['price'])
                t['quantity'] = str(t['quantity'])
                t['amount'] = str(t['amount'])
                # 保持 owner 为空字符串而不是 None，以兼容原有逻辑
                if t['owner'] is None:
                    t['owner'] = ""
            return trades
    finally:
        conn.close()

def load_all_trades_with_index() -> List[Tuple[int, dict]]:
    """
    获取所有交易记录及其数据库 ID
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM trades")
            trades = cursor.fetchall()
            result = []
            for t in trades:
                # 兼容缺少 id 列的情况
                db_id = t.pop('id', 0)
                t['price'] = str(t['price'])
                t['quantity'] = str(t['quantity'])
                t['amount'] = str(t['amount'])
                if t['owner'] is None:
                    t['owner'] = ""
                result.append((db_id, t))
            return result
    finally:
        conn.close()

def update_trade_by_index(db_id: int, updated_trade: dict) -> bool:
    """
    根据数据库 ID 更新交易记录
    """
    if not db_id:
        logger.error("无法更新交易：缺少有效的数据库 ID。")
        return False
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            UPDATE trades 
            SET date=%s, code=%s, name=%s, side=%s, price=%s, quantity=%s, amount=%s, amount_auto=%s
            WHERE id=%s
            """
            affected = cursor.execute(sql, (
                updated_trade.get("date"),
                updated_trade.get("code"),
                updated_trade.get("name"),
                updated_trade.get("side"),
                updated_trade.get("price"),
                updated_trade.get("quantity"),
                updated_trade.get("amount"),
                updated_trade.get("amount_auto", "0") or "0",
                db_id
            ))
        conn.commit()
        return affected > 0
    finally:
        conn.close()

def delete_trade_by_index(db_id: int) -> bool:
    """
    根据数据库 ID 删除交易记录
    """
    if not db_id:
        logger.error("无法删除交易：缺少有效的数据库 ID。")
        return False
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            affected = cursor.execute("DELETE FROM trades WHERE id=%s", (db_id,))
        conn.commit()
        return affected > 0
    finally:
        conn.close()

def clear_all_trades(owner: str | None = None) -> None:
    """
    清除所有或特定用户的交易记录
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if owner:
                cursor.execute("DELETE FROM trades WHERE owner=%s", (owner,))
            else:
                cursor.execute("DELETE FROM trades")
        conn.commit()
    finally:
        conn.close()

def get_trade_by_display_index(display_index: int, owner: str | None = None) -> Tuple[int, dict] | tuple[None, None]:
    """
    根据显示列表中的索引获取交易记录及其对应的数据库 ID
    """
    trades = load_trades(owner=owner)
    if display_index < 0 or display_index >= len(trades):
        return None, None
    target_trade = trades[display_index]
    
    # 因为 load_trades 已经返回了包含 id 的 dict，我们可以直接使用
    db_id = target_trade.get('id')
    return db_id, target_trade
