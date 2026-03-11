import json
import os
import shutil
from datetime import datetime
from typing import Optional
from utils.paths import get_data_dir
from utils.logger import logger

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


DATA_DIR = get_data_dir("data")
SNAPSHOT_FILE = os.path.join(DATA_DIR, "snapshot.json")


def get_latest_total_assets() -> Optional[float]:
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        v = data.get("total_assets")
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None
    except Exception:
        return None


def backup_snapshot() -> None:
    try:
        if os.path.exists(SNAPSHOT_FILE):
            backups_dir = get_data_dir("backups")
            stamp = datetime.now().strftime("%Y%m%d")
            backup_file = os.path.join(backups_dir, f"snapshot_{stamp}.json")
            if not os.path.exists(backup_file):
                shutil.copy2(SNAPSHOT_FILE, backup_file)
    except Exception:
        pass
