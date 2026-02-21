import csv
import os
from typing import List, Tuple

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
DATA_FILE = os.path.join(DATA_DIR, "trades.csv")
CSV_HEADERS = ["owner", "date", "code", "name", "side", "price", "quantity", "amount", "amount_auto"]


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
                            "owner": row.get("owner", ""),
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


def clear_all_trades(owner: str | None = None) -> None:
    ensure_data_file()
    if owner is None:
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
    else:
        # Keep other users' records
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            dict_reader = csv.DictReader(f)
            rows = [r for r in dict_reader if (r.get("owner") or "") != owner]
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)


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
            and trade.get("name", "") == target_trade.get("name", "")
            and trade.get("side") == target_trade.get("side")
            and trade.get("price") == target_trade.get("price")
            and trade.get("quantity") == target_trade.get("quantity")
            and trade.get("amount") == target_trade.get("amount")
            and (trade.get("amount_auto", "") or "0") == (target_trade.get("amount_auto", "") or "0")
        ):
            return orig_index, trade
    return None, None
