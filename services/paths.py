import os
import platform


def _expand(path: str) -> str:
    return os.path.expanduser(os.path.expandvars(path))


def _is_writable_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_data_root() -> str:
    env_path = os.environ.get("FOOLHOUSE_DATA_DIR")
    if env_path:
        p = _expand(env_path)
        if _is_writable_dir(p):
            return p
    system = platform.system().lower()
    home = os.path.expanduser("~")
    project_root = _project_root()
    if _is_writable_dir(project_root):
        return project_root
    if "darwin" in system or "mac" in system:
        base = os.path.join(home, "Library", "Application Support", "FoolHouse")
    elif "windows" in system or "cygwin" in system or "msys" in system:
        appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        base = os.path.join(appdata, "FoolHouse")
    else:
        base = os.path.join(home, ".local", "share", "FoolHouse")
    if _is_writable_dir(base):
        return base
    try:
        tmp_path = os.path.join("/tmp", "foolhouse")
        os.makedirs(tmp_path, exist_ok=True)
        return tmp_path
    except OSError:
        return project_root


def get_data_dir(subdir: str) -> str:
    root = get_data_root()
    p = os.path.join(root, subdir)
    os.makedirs(p, exist_ok=True)
    return p
