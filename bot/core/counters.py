from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Dict


_lock = threading.Lock()
_path: Path

try:
    # Allow configuring counters file path via app config if available
    from bot.config import DEFAULT_CONFIG  # type: ignore
    p = getattr(DEFAULT_CONFIG, "counters_file", None)
    if isinstance(p, (str, Path)) and str(p):
        _path = Path(p)
    else:
        _path = Path("bot.counters.json")
except Exception:
    _path = Path("bot.counters.json")

# Ensure absolute path to avoid surprises with CWD differences
try:
    if not _path.is_absolute():
        _path = Path.cwd() / _path
except Exception:
    pass

_counters: Dict[str, int] = {
    # Public keys expected by UI/backend
    "troops_trained": 0,
    "nodes_farmed": 0,
    "alliance_helps": 0,
}


def _load_locked() -> None:
    try:
        if not _path.exists():
            return
        data = json.loads(_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    _counters[k] = int(v)
                except Exception:
                    continue
        # Ensure default keys exist
        for k in ("troops_trained", "nodes_farmed", "alliance_helps"):
            _counters.setdefault(k, 0)
    except Exception:
        # Ignore load errors to avoid breaking the app
        pass


def _save_locked() -> None:
    try:
        # Ensure parent dir exists
        parent = _path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        tmp = _path.with_suffix(_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_counters, fh, ensure_ascii=False, separators=(",", ":"))
            try:
                fh.flush()
                os.fsync(fh.fileno())
            except Exception:
                pass
        try:
            os.replace(tmp, _path)
        except Exception:
            # Best effort fallback
            try:
                if _path.exists():
                    _path.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            try:
                tmp.replace(_path)
            except Exception:
                pass
    except Exception:
        pass


def inc(key: str, by: int = 1) -> None:
    """Atomically increment a counter by key and persist to disk.

    Unknown keys are created on first use.
    """
    if not key:
        return
    try:
        b = int(by)
    except Exception:
        b = 1
    with _lock:
        _counters[key] = int(_counters.get(key, 0)) + b
        _save_locked()


def get_all() -> Dict[str, int]:
    """Return a snapshot of counters as a plain dict."""
    with _lock:
        return dict(_counters)


def reset(keys: list[str] | None = None, persist: bool = True) -> None:
    """Reset specified counters (or all known counters if keys is None)."""
    with _lock:
        if keys is None:
            for k in list(_counters.keys()):
                _counters[k] = 0
        else:
            for k in keys:
                _counters[k] = 0
        if persist:
            _save_locked()


# Load persisted counters on import
with _lock:
    _load_locked()
    # Persist file creation if it didn't exist
    try:
        if not _path.exists():
            _save_locked()
    except Exception:
        pass

