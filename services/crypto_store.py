import csv
import os
import shutil
from datetime import datetime
from typing import List, Tuple
from services.paths import get_data_dir

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


DATA_DIR = get_data_dir("data")
DATA_FILE = os.path.join(DATA_DIR, "crypto_trades.csv")
CSV_HEADERS = ["owner", "date", "code", "platform", "side", "price", "quantity"]


def ensure_data_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    # 迁移旧路径文件
    old_file = os.path.join(ROOT_DIR, "data", "crypto_trades.csv")
    if not os.path.exists(DATA_FILE) and os.path.exists(old_file):
        try:
            shutil.copy2(old_file, DATA_FILE)
        except Exception:
            pass
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
    else:
        try:
            with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                first_row = next(reader, None)
            current_headers = first_row if first_row else []
            # 升级旧文件表头：补充/重排为新表头，去除 name/amount/amount_auto
            if current_headers and current_headers != CSV_HEADERS:
                with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
                    dr = csv.DictReader(f)
                    rows = list(dr)
                with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
                    dw = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                    dw.writeheader()
                    for r in rows:
                        out = {
                            "owner": r.get("owner", ""),
                            "date": r.get("date", ""),
                            "code": r.get("code", ""),
                            "platform": r.get("platform", ""),
                            "side": r.get("side", ""),
                            "price": r.get("price", ""),
                            "quantity": r.get("quantity", ""),
                        }
                        dw.writerow(out)
        except Exception:
            # 忽略升级异常，保持文件可读
            pass
    # 每日备份
    try:
        backups_dir = get_data_dir("backups")
        stamp = datetime.now().strftime("%Y%m%d")
        backup_file = os.path.join(backups_dir, f"crypto_trades_{stamp}.csv")
        if os.path.exists(DATA_FILE) and not os.path.exists(backup_file):
            shutil.copy2(DATA_FILE, backup_file)
    except Exception:
        pass


def append_trade(trade: dict) -> None:
    ensure_data_file()
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(trade)


def load_trades(owner: str | None = None) -> List[dict]:
    ensure_data_file()
    with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        trades = list(reader)
    if owner is not None:
        trades = [t for t in trades if (t.get("owner") or "") == owner]
    trades.sort(key=lambda t: t.get("date") or "", reverse=True)
    return trades


def load_all_trades_with_index() -> List[Tuple[int, dict]]:
    ensure_data_file()
    trades_with_index = []
    with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for index, trade in enumerate(reader):
            trades_with_index.append((index, trade))
    return trades_with_index


def update_trade_by_index(index: int, updated_trade: dict) -> bool:
    ensure_data_file()
    trades_with_index = load_all_trades_with_index()
    if index < 0 or index >= len(trades_with_index):
        return False
    trades_with_index[index] = (index, updated_trade)
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for _, trade in trades_with_index:
            writer.writerow(trade)
    return True


def delete_trade_by_index(index: int) -> bool:
    ensure_data_file()
    trades_with_index = load_all_trades_with_index()
    if index < 0 or index >= len(trades_with_index):
        return False
    trades_with_index.pop(index)
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for _, trade in trades_with_index:
            writer.writerow(trade)
    return True


def get_trade_by_display_index(display_index: int, owner: str | None = None) -> Tuple[int, dict] | tuple[None, None]:
    trades = load_trades(owner=owner)
    if display_index < 0 or display_index >= len(trades):
        return None, None
    target_trade = trades[display_index]
    trades_with_index = load_all_trades_with_index()
    for orig_index, trade in trades_with_index:
        if (
            ((trade.get("owner") or "") == (target_trade.get("owner") or "")) and
            trade.get("date") == target_trade.get("date")
            and trade.get("code") == target_trade.get("code")
            and (trade.get("platform", "") or "") == (target_trade.get("platform", "") or "")
            and trade.get("side") == target_trade.get("side")
            and trade.get("price") == target_trade.get("price")
            and trade.get("quantity") == target_trade.get("quantity")
        ):
            return orig_index, trade
    return None, None
