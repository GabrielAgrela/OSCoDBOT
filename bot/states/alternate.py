from __future__ import annotations

from typing import Callable, Tuple

from bot.config import AppConfig
from bot.core.state_machine import Context, State, GraphState


class AlternatingState(State):
    def __init__(self, first: State, second: State) -> None:
        self.name = "alternating_state"
        self._first = first
        self._second = second
        self._mode = 0  # 0 -> first, 1 -> second

    def _run_one_cycle(self, st: State, ctx: Context) -> None:
        # If it's a GraphState, consider a cycle completed when we loop back to the start step
        if isinstance(st, GraphState):
            start = getattr(st, "_current", None)
            progressed = False
            # Safety guard to avoid infinite loops
            for _ in range(128):
                if ctx.stop_event.is_set():
                    return
                prev = getattr(st, "_current", None)
                st.run_once(ctx)
                # Allow actions to request early end of the current cycle
                if getattr(ctx, "end_cycle", False):
                    ctx.end_cycle = False
                    break
                curr = getattr(st, "_current", None)
                if curr != start:
                    progressed = True
                if progressed and curr == start:
                    # Completed one full cycle
                    break
            return
        # For non-graph states (e.g., SequenceState), one run_once is one cycle
        st.run_once(ctx)
        if getattr(ctx, "end_cycle", False):
            ctx.end_cycle = False

    def run_once(self, ctx: Context) -> None:
        if self._mode == 0:
            self._run_one_cycle(self._first, ctx)
            self._mode = 1
        else:
            self._run_one_cycle(self._second, ctx)
            self._mode = 0


Builder = Callable[[AppConfig], Tuple[State, Context]]


def build_alternating_state(cfg: AppConfig, first_builder: Builder, second_builder: Builder) -> tuple[State, Context]:
    # Build underlying states (drop their contexts) and share a new context for both
    first_state, _ = first_builder(cfg)
    second_state, _ = second_builder(cfg)
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
    )
    return AlternatingState(first_state, second_state), ctx
