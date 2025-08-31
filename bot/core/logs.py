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

try:
    # Configure file logging from app config if available
    from bot.config import DEFAULT_CONFIG

    if getattr(DEFAULT_CONFIG, "log_to_file", False):
        p: Path = getattr(DEFAULT_CONFIG, "log_file", Path("bot.log"))
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
        try:
            # Timestamp: YYYY-MM-DD HH:MM:SS.mmm
            import datetime as _dt
            t = _dt.datetime.fromtimestamp(now)
            ts = t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            _fh.write(f"[{ts}] {level.upper()}: {text}\n")
            _fh.flush()
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
