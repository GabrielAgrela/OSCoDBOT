from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Deque, Dict, List, Literal, Optional, IO
from pathlib import Path


Level = Literal["info", "ok", "err"]


@dataclass
class LogEntry:
    id: int
    ts: float
    level: Level
    text: str


_lock = threading.Lock()
_buf: Deque[LogEntry] = deque(maxlen=400)
_next_id = 1
_fh: Optional[IO[str]] = None
_log_path_base: Optional[Path] = None
_log_max_bytes: int = 1_048_576
_log_backups: int = 5
_file_lock = threading.Lock()

try:
    # Configure file logging from app config if available
    import bot.config as config

    cfg = config.DEFAULT_CONFIG
    if getattr(cfg, "log_to_file", False):
        p: Path = getattr(cfg, "log_file", Path("bot.log"))
        _log_path_base = p
        _log_max_bytes = int(getattr(cfg, "log_max_bytes", 1_048_576))
        _log_backups = int(getattr(cfg, "log_backups", 5))
        try:
            if p.parent and not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            _fh = open(p, "a", encoding="utf-8")
            # Small header on startup
            _fh.write("\n=== bot start ===\n")
            _fh.flush()
        except Exception:
            _fh = None
except Exception:
    # Logging should never break the app
    _fh = None


def _rotate_locked() -> None:
    global _fh
    if _fh is None or _log_path_base is None:
        return
    try:
        # Close current handle first
        try:
            _fh.close()
        except Exception:
            pass
        # Rotate existing files: base.(n-1)->base.n ... base.1->base.2, base->base.1
        base = _log_path_base
        for i in range(_log_backups - 1, 0, -1):
            src = base.with_name(base.name + f".{i}")
            dst = base.with_name(base.name + f".{i+1}")
            try:
                if src.exists():
                    if dst.exists():
                        dst.unlink()
                    src.rename(dst)
            except Exception:
                pass
        try:
            first = base.with_name(base.name + ".1")
            if first.exists():
                first.unlink()
            if base.exists():
                base.rename(first)
        except Exception:
            pass
        # Reopen base
        try:
            _fh = open(base, "a", encoding="utf-8")
            _fh.write("\n=== log rotate ===\n")
            _fh.flush()
        except Exception:
            _fh = None
    except Exception:
        pass


def add(text: str, level: Level = "info") -> None:
    global _next_id
    now = time.time()
    # First, update in-memory buffer under lock
    with _lock:
        entry = LogEntry(id=_next_id, ts=now, level=level, text=text)
        _buf.append(entry)
        _next_id += 1
    # Then, write to file outside the lock to avoid blocking other threads
    if _fh is not None:
        with _file_lock:
            try:
                # Timestamp: YYYY-MM-DD HH:MM:SS.mmm
                import datetime as _dt
                t = _dt.datetime.fromtimestamp(now)
                ts = t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                _fh.write(f"[{ts}] {level.upper()}: {text}\n")
                _fh.flush()
                # Rotate if file exceeds max bytes
                if _log_path_base is not None and _log_max_bytes > 0:
                    try:
                        size = _log_path_base.stat().st_size
                        if size >= _log_max_bytes:
                            _rotate_locked()
                    except Exception:
                        pass
            except Exception:
                pass


def get_since(since_id: Optional[int]) -> List[Dict]:
    with _lock:
        if not _buf:
            return []
        if since_id is None or since_id <= 0:
            # Return a snapshot of the tail
            return [asdict(e) for e in list(_buf)[-100:]]
        return [asdict(e) for e in _buf if e.id > since_id]
