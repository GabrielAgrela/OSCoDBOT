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
    # When True (default), add a small random extra delay to feel less robotic
    randomize: bool = True

    def run(self, ctx: Context) -> None:
        if bool(self.randomize):
            jitter = random.uniform(0.0, 2.0)
        else:
            jitter = 0.0
        total = max(0.0, float(self.seconds) + float(jitter))
        end_by = time.time() + total
        try:
            if jitter > 0.0:
                print(f"[Wait] wait {total:.2f}s (base {self.seconds:.2f}s + {jitter:.2f}s)")
            else:
                print(f"[Wait] wait {total:.2f}s (no jitter)")
        except Exception:
            pass
        try:
            logs.add(f"[Wait] {total:.2f}s", level="info")
        except Exception:
            pass
        while time.time() < end_by:
            if ctx.stop_event.is_set():
                break
            # Honor pause: idle while paused
            try:
                if getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                    time.sleep(0.05)
                    continue
            except Exception:
                pass
            time.sleep(0.01)
