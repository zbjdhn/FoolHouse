import csv
import os
import pymysql
from services.db import get_db_connection, init_db
from services.trade_store import DATA_FILE, CSV_HEADERS

def migrate_data():
    """
    从 CSV 迁移数据到 MySQL (使用 PyMySQL)
    """
    if not os.path.exists(DATA_FILE):
        print(f"CSV 文件 {DATA_FILE} 不存在，跳过迁移。")
        return

    init_db()  # 确保表已创建
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查表是否已经有数据
            cursor.execute("SELECT COUNT(*) as count FROM trades")
            count = cursor.fetchone()['count']
            if count > 0:
                print("数据库表 'trades' 已有数据，跳过自动迁移。")
                return

            print(f"正在从 {DATA_FILE} 迁移数据到数据库...")
            
            with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                trades = list(reader)
            
            if not trades:
                print("CSV 文件为空，跳过迁移。")
                return

            sql = """
            INSERT INTO trades (owner, date, code, name, side, price, quantity, amount, amount_auto)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = []
            for trade in trades:
                values.append((
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
            
            cursor.executemany(sql, values)
            conn.commit()
            print(f"成功迁移 {len(values)} 条记录。")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        migrate_data()
    except Exception as e:
        print(f"发生错误: {e}")
