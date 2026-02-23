import json
import os
from typing import Optional

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

