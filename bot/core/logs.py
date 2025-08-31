from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Deque, Dict, List, Literal, Optional


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


def add(text: str, level: Level = "info") -> None:
    global _next_id
    now = time.time()
    with _lock:
        entry = LogEntry(id=_next_id, ts=now, level=level, text=text)
        _buf.append(entry)
        _next_id += 1


def get_since(since_id: Optional[int]) -> List[Dict]:
    with _lock:
        if not _buf:
            return []
        if since_id is None or since_id <= 0:
            # Return a snapshot of the tail
            return [asdict(e) for e in list(_buf)[-100:]]
        return [asdict(e) for e in _buf if e.id > since_id]

