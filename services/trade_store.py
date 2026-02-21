import csv
import os
from typing import List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "trades.csv")
CSV_HEADERS = ["date", "code", "name", "side", "price", "quantity", "amount", "amount_auto"]


def ensure_data_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
    else:
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
        else:
            header = rows[0]
            if header != CSV_HEADERS:
                with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
                    dict_reader = csv.DictReader(f)
                    existing = list(dict_reader)
                with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                    writer.writeheader()
                    for row in existing:
                        new_row = {
                            "date": row.get("date", ""),
                            "code": row.get("code", ""),
                            "name": row.get("name", ""),
                            "side": row.get("side", ""),
                            "price": row.get("price", ""),
                            "quantity": row.get("quantity", ""),
                            "amount": row.get("amount", ""),
                            "amount_auto": row.get("amount_auto", "") or "0",
                        }
                        writer.writerow(new_row)


def append_trade(trade: dict) -> None:
    ensure_data_file()
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(trade)


def load_trades() -> List[dict]:
    ensure_data_file()
    with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        trades = list(reader)
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


def clear_all_trades() -> None:
    ensure_data_file()
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)


def get_trade_by_display_index(display_index: int) -> Tuple[int, dict] | tuple[None, None]:
    trades = load_trades()
    if display_index < 0 or display_index >= len(trades):
        return None, None
    target_trade = trades[display_index]
    trades_with_index = load_all_trades_with_index()
    for orig_index, trade in trades_with_index:
        if (
            trade.get("date") == target_trade.get("date")
            and trade.get("code") == target_trade.get("code")
            and trade.get("name", "") == target_trade.get("name", "")
            and trade.get("side") == target_trade.get("side")
            and trade.get("price") == target_trade.get("price")
            and trade.get("quantity") == target_trade.get("quantity")
            and trade.get("amount") == target_trade.get("amount")
            and (trade.get("amount_auto", "") or "0") == (target_trade.get("amount_auto", "") or "0")
        ):
            return orig_index, trade
    return None, None
