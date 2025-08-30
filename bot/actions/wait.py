from __future__ import annotations

import time
from dataclasses import dataclass

from bot.core.state_machine import Action, Context


@dataclass
class Wait(Action):
    name: str
    seconds: float

    def run(self, ctx: Context) -> None:
        end_by = time.time() + self.seconds
        print(f"[Wait] wait {self.seconds} seconds")
        while time.time() < end_by:
            if ctx.stop_event.is_set():
                break
            time.sleep(0.01)
