from __future__ import annotations

from dataclasses import dataclass

from bot.core.state_machine import Action, Context


@dataclass
class EndMachine(Action):
    name: str

    def run(self, ctx: Context) -> None:
        # Signal the current machine/context to stop
        ctx.stop_event.set()
        try:
            print("[EndMachine] signaled stop for current context")
        except Exception:
            pass


@dataclass
class EndCycle(Action):
    name: str

    def run(self, ctx: Context) -> None:
        # Ask the orchestrator to end the current cycle (e.g., switch to next mode in alternation)
        ctx.end_cycle = True
        try:
            print("[EndCycle] requested end of current cycle")
        except Exception:
            pass
