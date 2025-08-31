from __future__ import annotations

import time
from dataclasses import dataclass
import random

from bot.core.state_machine import Action, Context
from bot.core import logs


@dataclass
class Wait(Action):
    name: str
    seconds: float

    def run(self, ctx: Context) -> None:
        jitter = random.uniform(0.0, 2.0)
        total = self.seconds + jitter
        end_by = time.time() + total
        try:
            print(f"[Wait] wait {total:.2f}s (base {self.seconds:.2f}s + {jitter:.2f}s)")
        except Exception:
            pass
        try:
            logs.add(f"[Wait] {total:.2f}s", level="info")
        except Exception:
            pass
        while time.time() < end_by:
            if ctx.stop_event.is_set():
                break
            time.sleep(0.01)
