from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State, GraphState
from .scouts import build_scouts_state
from .farm_ore import build_farm_ore_state


class AlternatingState(State):
    def __init__(self, scouts: State, ore: GraphState) -> None:
        self.name = "farm_ore_and_scout"
        self._scouts = scouts
        self._ore = ore
        self._mode: str = "scout"  # start with scouts
        self._prev_ore_step: str | None = None

    def run_once(self, ctx: Context) -> None:
        if self._mode == "scout":
            # One full scouts cycle per run_once
            self._scouts.run_once(ctx)
            # Switch to ore for next cycle
            self._mode = "ore"
            return

        # Ore mode: run one graph step at a time and detect wrap-around
        # Access current step name; GraphState keeps it in a private attr
        prev = getattr(self._ore, "_current", None)
        self._ore.run_once(ctx)
        curr = getattr(self._ore, "_current", None)
        # If we just transitioned from the last step back to the start, switch to scouts
        if prev == "March" and curr == "OpenMagnifier":
            self._mode = "scout"


def build_farm_ore_and_scout_state(cfg: AppConfig) -> tuple[State, Context]:
    # Build underlying states using their own builders
    scouts_state, _ = build_scouts_state(cfg)
    ore_state, _ = build_farm_ore_state(cfg)

    # Shared context for both flows
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
    )

    combined = AlternatingState(scouts=scouts_state, ore=ore_state)  # type: ignore[arg-type]
    return combined, ctx

