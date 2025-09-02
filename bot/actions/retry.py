from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Optional
import time

from bot.core.state_machine import Action, Context
from bot.core.window import bring_to_front, find_window_by_title_substr
from bot.core import logs


@dataclass
class Retry(Action):
    name: str
    actions: Sequence[Action]
    attempts: int = 3

    def run(self, ctx: Context) -> Optional[bool]:
        tries = max(1, int(self.attempts))
        for i in range(1, tries + 1):
            if ctx.stop_event.is_set():
                return False
            try:
                logs.add(f"[Retry] {self.name} attempt {i}/{tries}")
            except Exception:
                pass
            last_result: Optional[bool] = None
            for act in self.actions:
                if ctx.stop_event.is_set():
                    return False
                # Time the inner action (update telemetry like GraphState)
                start = time.time()
                ctx.last_action_name = act.name
                try:
                    res = act.run(ctx)
                except Exception as exc:
                    try:
                        logs.add(f"[ActionError] {act.name} in Retry:{self.name}: {exc}", level="err")
                    except Exception:
                        pass
                    res = None
                dur = time.time() - start
                ctx.last_action_duration_s = dur
                ctx.last_progress_ts = time.time()
                if res is not None:
                    last_result = res
            # Success if any inner action signaled success (commonly the matcher)
            if bool(last_result):
                try:
                    logs.add(f"[Retry] {self.name} success on attempt {i}/{tries}", level="ok")
                except Exception:
                    pass
                return True
        try:
            logs.add(f"[RetryFail] {self.name} failed after {tries} attempts", level="err")
        except Exception:
            pass
        return False
