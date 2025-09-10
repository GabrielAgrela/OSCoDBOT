from __future__ import annotations

from typing import Callable, Tuple, List, Sequence
import random

from bot.config import AppConfig
from bot.core.state_machine import Context, State, GraphState
from bot.core import logs
from .checkstuck import build_checkstuck_state


class AlternatingState(State):
    def __init__(self, first: State, second: State) -> None:
        self.name = "alternating_state"
        self._first = first
        self._second = second
        # First pick is deterministic (use 'first'); subsequent iterations are random
        self._mode = 0  # 0 -> first, 1 -> second
        self._first_pick_done = False
        self._last_label: str | None = None

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
        # First iteration: deterministic order (first). Afterwards: random each iteration
        if not getattr(self, "_first_pick_done", False):
            st = self._first
            self._first_pick_done = True
        else:
            self._mode = 0 if random.random() < 0.5 else 1
            st = self._first if self._mode == 0 else self._second
        # Log state switches in pink when label changes
        try:
            label = getattr(st, "_label", getattr(st, "name", "state"))
            if label != self._last_label:
                logs.add(f"[Switch] {label}", level="pink")  # styled in UI
                self._last_label = label
        except Exception:
            pass
        self._run_one_cycle(st, ctx)


class RoundRobinState(State):
    def __init__(self, states: Sequence[State]) -> None:
        self.name = "round_robin_state"
        self._states: List[State] = list(states)
        if not self._states:
            raise ValueError("RoundRobinState requires at least one state")
        # First round uses the original order; subsequent rounds reshuffle
        self._order: List[int] = list(range(len(self._states)))
        self._pos: int = 0  # position within current order
        self._first_round_done: bool = False
        self._last_label: str | None = None

    def _run_one_cycle(self, st: State, ctx: Context) -> None:
        # Mirror AlternatingState semantics for cycle completion and end_cycle support
        if isinstance(st, GraphState):
            start = getattr(st, "_current", None)
            progressed = False
            for _ in range(256):
                if ctx.stop_event.is_set():
                    return
                st.run_once(ctx)
                if getattr(ctx, "end_cycle", False):
                    ctx.end_cycle = False
                    break
                curr = getattr(st, "_current", None)
                if curr != start:
                    progressed = True
                if progressed and curr == start:
                    break
            return
        st.run_once(ctx)
        if getattr(ctx, "end_cycle", False):
            ctx.end_cycle = False

    def run_once(self, ctx: Context) -> None:
        # When completing a full round, keep first round deterministic, then reshuffle per round
        if self._pos >= len(self._order):
            self._pos = 0
            if not self._first_round_done:
                self._first_round_done = True
            # For every round after the first, reshuffle order
            if self._first_round_done:
                self._order = list(range(len(self._states)))
                random.shuffle(self._order)
        st = self._states[self._order[self._pos]]
        # Log state switches
        try:
            label = getattr(st, "_label", getattr(st, "name", "state"))
            if label != self._last_label:
                logs.add(f"[Switch] {label}", level="pink")
                self._last_label = label
        except Exception:
            pass
        self._run_one_cycle(st, ctx)
        # Remove one-shot states after their first cycle so they don't run again
        try:
            if bool(getattr(st, "_one_shot", False)):
                # Index in the underlying states list that we just executed
                ridx = int(self._order[self._pos])
                # Remove the state
                try:
                    del self._states[ridx]
                except Exception:
                    pass
                # Rebuild order mapping (drop removed index; shift higher indices down)
                new_order: List[int] = []
                for idx in self._order:
                    if idx == ridx:
                        continue
                    new_order.append(idx - 1 if idx > ridx else idx)
                self._order = new_order
                # Keep position pointing at the next item now occupying this slot
                # Do not increment _pos here.
            else:
                self._pos += 1
        except Exception:
            # On any error, advance position normally
            self._pos += 1

    def _choose_next_mode(self) -> int:
        # Helper for AlternatingState-style random choice where applicable
        return 0 if random.random() < 0.5 else 1


Builder = Callable[[AppConfig], Tuple[State, Context]]


def build_alternating_state(
    cfg: AppConfig,
    first_builder: Builder,
    second_builder: Builder,
    first_label: str | None = None,
    second_label: str | None = None,
) -> tuple[State, Context]:
    # Build underlying states and wrap each with its own check-stuck
    first_state, _ = first_builder(cfg)
    second_state, _ = second_builder(cfg)
    chk1, _ = build_checkstuck_state(cfg)
    chk2, _ = build_checkstuck_state(cfg)
    wrapped_first = WithCheckStuckState(first_state, chk1, label=first_label)
    wrapped_second = WithCheckStuckState(second_state, chk2, label=second_label)
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )
    return AlternatingState(wrapped_first, wrapped_second), ctx


def build_round_robin_state(cfg: AppConfig, builders: Sequence[Builder] | Sequence[tuple[str, Builder]]) -> tuple[State, Context]:
    if not builders:
        raise ValueError("builders must be a non-empty sequence")
    states: List[State] = []
    for item in builders:
        if isinstance(item, tuple):
            label, builder = item  # type: ignore[misc]
        else:
            builder = item  # type: ignore[assignment]
            label = None
        st, _ = builder(cfg)
        chk, _ = build_checkstuck_state(cfg)
        states.append(WithCheckStuckState(st, chk, label=label))
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )
    return RoundRobinState(states), ctx


class WithCheckStuckState(State):
    """Runs a primary state for one cycle, then runs check-stuck for one cycle.

    Carries a human-friendly label for logging when orchestrators switch states.
    """
    def __init__(self, primary: State, check: State, label: str | None = None) -> None:
        self.name = "with_checkstuck_state"
        self._primary = primary
        self._check = check
        self._label = label or getattr(primary, "name", "state")

    def _run_one_cycle(self, st: State, ctx: Context) -> None:
        # Mirror GraphState cycle completion semantics
        if isinstance(st, GraphState):
            start = getattr(st, "_current", None)
            progressed = False
            for _ in range(256):
                if ctx.stop_event.is_set():
                    return
                st.run_once(ctx)
                if getattr(ctx, "end_cycle", False):
                    ctx.end_cycle = False
                    break
                curr = getattr(st, "_current", None)
                if curr != start:
                    progressed = True
                if progressed and curr == start:
                    break
            return
        st.run_once(ctx)
        if getattr(ctx, "end_cycle", False):
            ctx.end_cycle = False

    def run_once(self, ctx: Context) -> None:
        # Run primary state for one cycle
        self._run_one_cycle(self._primary, ctx)
        # Log transition to check-stuck phase in pink for visibility
        try:
            logs.add("[Switch] Check Stuck", level="pink")
        except Exception:
            pass
        # Run the checker for one cycle
        self._run_one_cycle(self._check, ctx)


def build_with_checkstuck_state(cfg: AppConfig, builder: Builder, label: str | None = None) -> tuple[State, Context]:
    primary, _ = builder(cfg)
    checker, _ = build_checkstuck_state(cfg)
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )
    # Wrap primary with a dedicated checker instance
    wrapped = WithCheckStuckState(primary, checker, label=label)
    return wrapped, ctx
