import os
import platform


def _expand(path: str) -> str:
    return os.path.expanduser(os.path.expandvars(path))


def get_data_root() -> str:
    env_path = os.environ.get("FOOLHOUSE_DATA_DIR")
    if env_path:
        p = _expand(env_path)
        os.makedirs(p, exist_ok=True)
        return p
    system = platform.system().lower()
    home = os.path.expanduser("~")
    if "darwin" in system or "mac" in system:
        base = os.path.join(home, "Library", "Application Support", "FoolHouse")
    elif "windows" in system or "cygwin" in system or "msys" in system:
        appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        base = os.path.join(appdata, "FoolHouse")
    else:
        base = os.path.join(home, ".local", "share", "FoolHouse")
    try:
        os.makedirs(base, exist_ok=True)
        return base
    except OSError:
        tmp_path = os.path.join("/tmp", "foolhouse")
        os.makedirs(tmp_path, exist_ok=True)
        return tmp_path


def get_data_dir(subdir: str) -> str:
    root = get_data_root()
    p = os.path.join(root, subdir)
    os.makedirs(p, exist_ok=True)
    return p
