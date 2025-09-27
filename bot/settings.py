from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List
import sys


_SETTINGS_LOCK = threading.Lock()
_CACHE: Dict[str, Any] | None = None


def _bool_default(value: bool) -> bool:
    return bool(value)


SETTINGS_SCHEMA: List[Dict[str, Any]] = [
    {
        "key": "WINDOW_TITLE_SUBSTR",
        "label": "Window title substring",
        "type": "string",
        "category": "Window & Launch",
        "default": "Call of Dragons",
        "description": "Substring used to find the Call of Dragons client window.",
    },
    {
        "key": "MATCH_THRESHOLD",
        "label": "Match threshold",
        "type": "float",
        "category": "Capture & Matching",
        "default": 0.9,
        "description": "Minimum template matching ratio for detections (0-1).",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    {
        "key": "VERIFY_THRESHOLD",
        "label": "Verify threshold",
        "type": "float",
        "category": "Capture & Matching",
        "default": 0.85,
        "description": "Secondary verification threshold used by some matchers.",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    {
        "key": "CLICK_SNAP_BACK",
        "label": "Snap cursor after clicks",
        "type": "bool",
        "category": "Interaction",
        "default": _bool_default(True),
        "description": "Return the cursor to its previous location after each click.",
    },
    {
        "key": "SAVE_SHOTS",
        "label": "Save debug shots",
        "type": "bool",
        "category": "Debugging",
        "default": _bool_default(True),
        "description": "Store annotated screenshots for inspection.",
    },
    {
        "key": "SHOTS_DIR",
        "label": "Shots directory",
        "type": "string",
        "category": "Debugging",
        "default": r"C:\\Users\\netco\\codbot\\debug_captures",
        "description": "Folder for annotated match captures.",
    },
    {
        "key": "START_SHOTS_DIR",
        "label": "Start shots directory",
        "type": "string",
        "category": "Debugging",
        "default": "start_captures",
        "description": "Folder for initial launch screenshots (not pruned).",
    },
    {
        "key": "SHOTS_MAX_BYTES",
        "label": "Shots max bytes",
        "type": "int",
        "category": "Debugging",
        "default": 1_073_741_824,
        "description": "Maximum total size of debug captures before pruning (bytes).",
    },
    {
        "key": "FORCE_WINDOW_RESIZE",
        "label": "Force window resize",
        "type": "bool",
        "category": "Window & Launch",
        "default": _bool_default(True),
        "description": "Attempt to resize the game client window on startup.",
    },
    {
        "key": "FORCE_WINDOW_WIDTH",
        "label": "Target window width",
        "type": "int",
        "category": "Window & Launch",
        "default": 1765,
        "description": "Width of the client area when resizing (pixels).",
    },
    {
        "key": "FORCE_WINDOW_HEIGHT",
        "label": "Target window height",
        "type": "int",
        "category": "Window & Launch",
        "default": 993,
        "description": "Height of the client area when resizing (pixels).",
    },
    {
        "key": "GAME_SHORTCUT_PATH",
        "label": "Game shortcut path",
        "type": "string",
        "category": "Window & Launch",
        "default": r"C:\\Users\\netco\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Google Play Games\\Call of Dragons.lnk",
        "description": "Optional .lnk shortcut used to launch the game if no window is detected.",
    },
    {
        "key": "GAME_LAUNCH_WAIT",
        "label": "Game launch wait",
        "type": "float",
        "category": "Window & Launch",
        "default": 60.0,
        "description": "Seconds to wait after launching the game before searching for its window.",
        "min": 0.0,
        "step": 1.0,
    },
    {
        "key": "FARM_COOLDOWN_MIN",
        "label": "Farm cooldown (min)",
        "type": "duration",
        "category": "Cooldowns",
        "default": "1s",
        "description": "Minimum delay between farming loops (supports suffixes like s/m/h).",
    },
    {
        "key": "FARM_COOLDOWN_MAX",
        "label": "Farm cooldown (max)",
        "type": "duration",
        "category": "Cooldowns",
        "default": "10s",
        "description": "Maximum delay between farming loops (supports suffixes like s/m/h).",
    },
    {
        "key": "TRAIN_COOLDOWN_MIN",
        "label": "Train cooldown (min)",
        "type": "duration",
        "category": "Cooldowns",
        "default": "63s",
        "description": "Minimum delay before retrying troop training when queues are full.",
    },
    {
        "key": "TRAIN_COOLDOWN_MAX",
        "label": "Train cooldown (max)",
        "type": "duration",
        "category": "Cooldowns",
        "default": "94s",
        "description": "Maximum delay before retrying troop training when queues are full.",
    },
    {
        "key": "ALLIANCE_HELP_COOLDOWN_MIN",
        "label": "Alliance help cooldown (min)",
        "type": "duration",
        "category": "Cooldowns",
        "default": "0s",
        "description": "Minimum delay between alliance help attempts.",
    },
    {
        "key": "ALLIANCE_HELP_COOLDOWN_MAX",
        "label": "Alliance help cooldown (max)",
        "type": "duration",
        "category": "Cooldowns",
        "default": "0s",
        "description": "Maximum delay between alliance help attempts.",
    },
    {
        "key": "MAX_ARMIES",
        "label": "Max armies",
        "type": "int",
        "category": "Interaction",
        "default": 4,
        "description": "Number of legions available for gathering before idling.",
        "min": 1,
    },
    {
        "key": "LOG_TO_FILE",
        "label": "Log to file",
        "type": "bool",
        "category": "Logging",
        "default": _bool_default(True),
        "description": "Persist logs to a rotating file on disk.",
    },
    {
        "key": "LOG_FILE",
        "label": "Log file",
        "type": "string",
        "category": "Logging",
        "default": "bot.log",
        "description": "Path to the rotating log file.",
    },
    {
        "key": "LOG_MAX_BYTES",
        "label": "Log max bytes",
        "type": "int",
        "category": "Logging",
        "default": 1_048_576,
        "description": "Maximum size of the primary log file before rotating (bytes).",
    },
    {
        "key": "LOG_BACKUPS",
        "label": "Log backups",
        "type": "int",
        "category": "Logging",
        "default": 5,
        "description": "Number of rotated log files to retain.",
    },
    {
        "key": "WEB_BIND_HOST",
        "label": "Web bind host",
        "type": "string",
        "category": "Web UI",
        "default": "0.0.0.0",
        "description": "Interface the web control panel listens on.",
    },
    {
        "key": "WEB_PORT",
        "label": "Web port",
        "type": "int",
        "category": "Web UI",
        "default": 5000,
        "description": "Port used by the web control panel.",
        "min": 1,
        "max": 65535,
    },
    {
        "key": "WEB_DISPLAY_HOST",
        "label": "Web display host",
        "type": "string",
        "category": "Web UI",
        "default": "",
        "description": "Optional host used when opening the browser (defaults to bind host).",
    },
]


_SCHEMA_INDEX = {item["key"]: item for item in SETTINGS_SCHEMA}


def _settings_path_candidates() -> Iterable[Path]:
    cwd = Path.cwd()
    yield cwd / "settings.json"
    if getattr(sys, "frozen", False):
        try:
            exe_dir = Path(sys.executable).resolve().parent
            yield exe_dir / "settings.json"
        except Exception:
            pass
        try:
            bundle = Path(getattr(sys, "_MEIPASS", ""))
            if bundle:
                yield bundle / "settings.json"
        except Exception:
            pass


def _settings_write_path() -> Path:
    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).resolve().parent / "settings.json"
        except Exception:
            pass
    return Path.cwd() / "settings.json"


def _default_settings() -> Dict[str, Any]:
    return {item["key"]: item.get("default") for item in SETTINGS_SCHEMA}


def _coerce_value(key: str, value: Any) -> Any:
    meta = _SCHEMA_INDEX.get(key)
    if not meta:
        return value
    t = meta.get("type")
    if t == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            s = value.strip().lower()
            if s in {"1", "true", "yes", "on", "y"}:
                return True
            if s in {"0", "false", "no", "off", "n"}:
                return False
        return bool(meta.get("default"))
    if t == "int":
        try:
            return int(float(value))
        except Exception:
            return int(meta.get("default", 0))
    if t == "float":
        try:
            return float(value)
        except Exception:
            return float(meta.get("default", 0.0))
    if t == "duration":
        if isinstance(value, (int, float)):
            return f"{int(max(0, value))}s"
        if isinstance(value, str):
            return value.strip()
        return str(meta.get("default", "0s"))
    # Default: treat as string
    if value is None:
        return ""
    return str(value)


def _load_file(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            out: Dict[str, Any] = {}
            for key, value in data.items():
                out[key] = _coerce_value(key, value)
            return out
    except Exception:
        pass
    return {}


def _load_legacy_env() -> Dict[str, Any]:
    from pathlib import Path as _Path

    def _env_candidates() -> Iterable[_Path]:
        yield _Path(".env")
        if getattr(sys, "frozen", False):
            try:
                exe_dir = _Path(sys.executable).resolve().parent
                yield exe_dir / ".env"
            except Exception:
                pass
            try:
                bundle = _Path(getattr(sys, "_MEIPASS", ""))
                if bundle:
                    yield bundle / ".env"
            except Exception:
                pass

    result: Dict[str, Any] = {}
    for candidate in _env_candidates():
        try:
            if not candidate.exists():
                continue
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                result[key] = _coerce_value(key, val.strip())
            if result:
                break
        except Exception:
            continue
    return result


def _ensure_cached() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    data = _default_settings()
    path = None
    for candidate in _settings_path_candidates():
        if candidate.exists():
            path = candidate
            break
    if path is not None:
        loaded = _load_file(path)
        data.update({k: v for k, v in loaded.items() if k in data})
    else:
        legacy = _load_legacy_env()
        if legacy:
            for key, value in legacy.items():
                if key in data:
                    data[key] = value
        # Persist migrated defaults immediately
        _write_settings(data)
    _CACHE = data
    return _CACHE


def get_settings() -> Dict[str, Any]:
    with _SETTINGS_LOCK:
        data = _ensure_cached().copy()
    return data


def get_schema() -> List[Dict[str, Any]]:
    return SETTINGS_SCHEMA


def get_schema_with_values() -> List[Dict[str, Any]]:
    settings = get_settings()
    payload: List[Dict[str, Any]] = []
    for item in SETTINGS_SCHEMA:
        entry = dict(item)
        entry["value"] = settings.get(item["key"], item.get("default"))
        payload.append(entry)
    return payload


def update_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(updates, dict):
        raise ValueError("updates must be a mapping")
    with _SETTINGS_LOCK:
        current = _ensure_cached()
        for key, value in updates.items():
            if key in _SCHEMA_INDEX:
                current[key] = _coerce_value(key, value)
        _write_settings(current)
        return current.copy()


def _write_settings(data: Dict[str, Any]) -> None:
    path = _settings_write_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    ordered: Dict[str, Any] = {item["key"]: data.get(item["key"]) for item in SETTINGS_SCHEMA}
    try:
        path.write_text(json.dumps(ordered, indent=2, sort_keys=False), encoding="utf-8")
    except Exception:
        pass

