from __future__ import annotations

from dataclasses import dataclass
import time

from bot.core.state_machine import Action, Context
from bot.core import logs


def _attr_name(key: str) -> str:
    return f"_cooldown_until_{key}"


@dataclass
class SetCooldown(Action):
    name: str
    key: str
    seconds: float

    def run(self, ctx: Context) -> None:
        try:
            seconds = max(0.0, float(self.seconds))
            until = time.time() + seconds
            setattr(ctx, _attr_name(self.key), until)
            try:
                logs.add(
                    f"[CooldownSet] key={self.key} seconds={seconds:.1f}",
                    level="info",
                )
            except Exception:
                pass
        except Exception:
            pass
        return None


@dataclass
class CooldownGate(Action):
    name: str
    key: str

    def run(self, ctx: Context) -> bool:
        try:
            until = float(getattr(ctx, _attr_name(self.key), 0.0))
        except Exception:
            until = 0.0
        now = time.time()
        if until > now:
            # Ask orchestrator to end this cycle early; other modes continue to run
            ctx.end_cycle = True
            return False  # indicate we are in cooldown
        return True  # proceed
