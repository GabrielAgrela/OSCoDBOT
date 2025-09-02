from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, Sequence, Dict, List

import numpy as np
from .window import bring_to_front, find_window_by_title_substr
from . import logs


@dataclass
class MatchResult:
    score: float
    # center positions
    center_win_xy: tuple[int, int]
    center_screen_xy: tuple[int, int]
    # template size
    template_wh: tuple[int, int]
    # roi offset within window
    roi_win_offset_xy: tuple[int, int]


@dataclass
class Context:
    # Window and capture
    window_title_substr: str
    hwnd: Optional[int] = None
    window_rect: tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, width, height
    frame_bgr: Optional[np.ndarray] = None

    # Matching
    last_match: Optional[MatchResult] = None
    templates_dir: Path = Path("assets/templates")

    # Control
    stop_event: threading.Event = field(default_factory=threading.Event)
    # Pause control: when set, processing halts until cleared
    pause_event: threading.Event = field(default_factory=threading.Event)
    # Capture handle (reused per thread to avoid resource churn/leaks)
    _mss: Optional[object] = None
    # Debugging
    save_shots: bool = False
    shots_dir: Path = Path("debug_captures")
    # Signal to enclosing orchestrator (e.g., AlternatingState) to end the current cycle early
    end_cycle: bool = False
    # Telemetry
    cycle_count: int = 0
    last_action_name: str = ""
    last_action_duration_s: float = 0.0
    last_progress_ts: float = 0.0
    current_state_name: str = ""
    current_graph_step: str = ""


class Action(Protocol):
    name: str

    def run(self, ctx: Context) -> Optional[bool]:  # return True/False for success when relevant
        ...


class State(Protocol):
    name: str

    def run_once(self, ctx: Context) -> None:
        ...


class SequenceState:
    def __init__(self, name: str, actions: Sequence[Action], loop_sleep_s: float = 0.05) -> None:
        self.name = name
        self._actions = list(actions)
        self._loop_sleep_s = loop_sleep_s

    def run_once(self, ctx: Context) -> None:
        ctx.current_state_name = self.name
        # Honor pause at the start of a cycle
        try:
            while getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                if ctx.stop_event.is_set():
                    return
                time.sleep(0.05)
        except Exception:
            pass
        for action in self._actions:
            if ctx.stop_event.is_set():
                return
            # Honor pause between actions
            try:
                while getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                    if ctx.stop_event.is_set():
                        return
                    time.sleep(0.05)
            except Exception:
                pass
            try:
                # Bring target window to foreground before each action
                try:
                    hwnd = ctx.hwnd
                    if hwnd is None:
                        hwnd = find_window_by_title_substr(ctx.window_title_substr)
                        if hwnd is not None:
                            ctx.hwnd = hwnd
                    if hwnd is not None:
                        bring_to_front(hwnd)
                except Exception:
                    pass
                start = time.time()
                ctx.last_action_name = action.name
                _ = action.run(ctx)
                dur = time.time() - start
                ctx.last_action_duration_s = dur
                ctx.last_progress_ts = time.time()
                if dur > 2.0:
                    try:
                        logs.add(f"[ActionSlow] {action.name} took {dur:.2f}s in {self.name}", level="info")
                    except Exception:
                        pass
            except Exception as exc:
                # Keep loop resilient; log to console/UI and continue
                try:
                    print(f"[ActionError] {action.name}: {exc}")
                except Exception:
                    pass
                try:
                    logs.add(f"[ActionError] {action.name}: {exc}", level="err")
                except Exception:
                    pass
        # small pacing sleep between cycles to avoid CPU spin
        if self._loop_sleep_s > 0:
            end_by = time.time() + self._loop_sleep_s
            while time.time() < end_by:
                if ctx.stop_event.is_set():
                    return
                time.sleep(0.005)
        ctx.cycle_count += 1


class StateMachine:
    def __init__(self, state: State) -> None:
        self._state = state
        self._thread: Optional[threading.Thread] = None
        self._watchdog: Optional[threading.Thread] = None
        self._watchdog_stop: threading.Event = threading.Event()

    def start(self, ctx: Context) -> None:
        if self._thread and self._thread.is_alive():
            return
        ctx.stop_event.clear()
        # Ensure we are not paused when starting
        try:
            ctx.pause_event.clear()
        except Exception:
            pass
        try:
            ctx.last_progress_ts = time.time()
        except Exception:
            pass
        self._thread = threading.Thread(target=self._run_loop, args=(ctx,), daemon=True)
        self._thread.start()
        # Start watchdog thread for telemetry logging
        try:
            self._watchdog_stop.clear()
            self._watchdog = threading.Thread(target=self._watchdog_loop, args=(ctx,), daemon=True)
            self._watchdog.start()
        except Exception:
            pass

    def stop(self, ctx: Context) -> None:
        ctx.stop_event.set()
        # Clear pause so any waits unblock
        try:
            ctx.pause_event.clear()
        except Exception:
            pass
        try:
            self._watchdog_stop.set()
            if self._watchdog and self._watchdog.is_alive():
                self._watchdog.join(timeout=1.0)
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        # Dispose capture handle if present
        try:
            sct = getattr(ctx, "_mss", None)
            if sct is not None:
                try:
                    # mss() instances expose close()
                    sct.close()
                except Exception:
                    pass
                try:
                    setattr(ctx, "_mss", None)
                except Exception:
                    pass
        except Exception:
            pass

    def _run_loop(self, ctx: Context) -> None:
        while not ctx.stop_event.is_set():
            # If paused, idle here but remain responsive to stop
            try:
                if getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                    time.sleep(0.05)
                    continue
            except Exception:
                pass
            self._state.run_once(ctx)

    def _watchdog_loop(self, ctx: Context) -> None:
        last_log = 0.0
        last_perf = 0.0
        prev_cpu_proc_time = time.process_time()
        prev_cpu_wall = time.time()
        while not self._watchdog_stop.is_set() and not ctx.stop_event.is_set():
            now = time.time()
            try:
                # If paused, suppress stall recovery and mark as paused in logs periodically
                try:
                    if getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                        if now - last_log >= 15.0:
                            logs.add("[Watchdog] paused", level="info")
                            last_log = now
                        time.sleep(0.5)
                        continue
                except Exception:
                    pass
                since = max(0.0, now - float(getattr(ctx, "last_progress_ts", 0.0)))
                if now - last_log >= 15.0:
                    step = getattr(ctx, "current_graph_step", "") or getattr(ctx, "current_state_name", "?")
                    act = getattr(ctx, "last_action_name", "")
                    dur = float(getattr(ctx, "last_action_duration_s", 0.0))
                    cyc = int(getattr(ctx, "cycle_count", 0))
                    logs.add(f"[Watchdog] step={step} action={act} last_dur={dur:.2f}s since_progress={since:.1f}s cycles={cyc}")
                    last_log = now
                # Periodic perf telemetry
                if now - last_perf >= 30.0:
                    try:
                        from . import perf as _perf
                        m = _perf.get_process_metrics()
                    except Exception:
                        m = {}
                    # CPU percent based on process_time delta and wall time
                    try:
                        curr_proc = time.process_time()
                        curr_wall = now
                        used = max(0.0, curr_proc - prev_cpu_proc_time)
                        wall = max(0.001, curr_wall - prev_cpu_wall)
                        cores = max(1, int(getattr(__import__('os'), 'cpu_count')() or 1))
                        cpu_pct = max(0.0, min(100.0, (used / wall) * 100.0 / cores))
                        prev_cpu_proc_time = curr_proc
                        prev_cpu_wall = curr_wall
                    except Exception:
                        cpu_pct = 0.0
                    try:
                        import threading as _th
                        thr = len(list(_th.enumerate()))
                    except Exception:
                        thr = 0
                    try:
                        rss_mb = float(m.get('rss_bytes', 0)) / (1024 * 1024)
                        priv_mb = float(m.get('private_bytes', 0)) / (1024 * 1024)
                        page_mb = float(m.get('pagefile_bytes', 0)) / (1024 * 1024)
                        handles = int(m.get('handle_count', 0))
                        gdi = int(m.get('gdi_count', 0))
                        user = int(m.get('user_count', 0))
                        cap_ok = bool(getattr(ctx, '_mss', None) is not None)
                        grab_count = int(getattr(ctx, '_mss_grab_count', 0))
                        wr = getattr(ctx, 'window_rect', (0,0,0,0))
                        logs.add(
                            (
                                f"[Perf] rss={rss_mb:.1f}MB priv={priv_mb:.1f}MB page={page_mb:.1f}MB "
                                f"handles={handles} gdi={gdi} user={user} thr={thr} cpu={cpu_pct:.1f}% "
                                f"cap={'1' if cap_ok else '0'} grabs={grab_count} win={wr}"
                            ),
                            level="info",
                        )
                    except Exception:
                        pass
                    last_perf = now
                if since > 45.0:
                    # Proactively try to recover capture/window handles
                    try:
                        sct = getattr(ctx, "_mss", None)
                        if sct is not None:
                            try:
                                sct.close()
                            except Exception:
                                pass
                            try:
                                setattr(ctx, "_mss", None)
                            except Exception:
                                pass
                        logs.add("[WatchdogRecover] Reset capture handle after 45s stall", level="info")
                    except Exception:
                        pass
                if since > 60.0:
                    logs.add(f"[WatchdogStall] No progress for {since:.1f}s at step={step} action={act}", level="err")
                    # Nudge the graph to end the current cycle so orchestrators can switch modes
                    try:
                        ctx.end_cycle = True
                        # Force window re-discovery next cycle
                        ctx.hwnd = None
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(2.0)

    # Pause/resume controls
    def pause(self, ctx: Context) -> None:
        try:
            ctx.pause_event.set()
        except Exception:
            pass

    def resume(self, ctx: Context) -> None:
        try:
            ctx.pause_event.clear()
            # Consider progress updated to avoid immediate stall heuristics
            ctx.last_progress_ts = time.time()
        except Exception:
            pass

    def is_paused(self, ctx: Context) -> bool:
        try:
            return bool(getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set())
        except Exception:
            return False


# Branching graph-based state machine

class GraphStep:
    def __init__(
        self,
        name: str,
        actions: Sequence[Action],
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
    ) -> None:
        self.name = name
        self.actions = list(actions)
        self.on_success = on_success
        self.on_failure = on_failure


class GraphState:
    def __init__(self, steps: Sequence[GraphStep], start: str, loop_sleep_s: float = 0.05) -> None:
        self.name = "graph_state"
        self._steps: Dict[str, GraphStep] = {s.name: s for s in steps}
        if start not in self._steps:
            raise ValueError(f"Start step '{start}' not in steps")
        self._current: str = start
        self._loop_sleep_s = loop_sleep_s

    def run_once(self, ctx: Context) -> None:
        step = self._steps.get(self._current)
        if not step:
            time.sleep(self._loop_sleep_s)
            return
        last_result: Optional[bool] = None
        ctx.current_state_name = self.name
        ctx.current_graph_step = step.name
        # Honor pause at the start of a step
        try:
            while getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                if ctx.stop_event.is_set():
                    return
                time.sleep(0.05)
        except Exception:
            pass
        for action in step.actions:
            if ctx.stop_event.is_set():
                return
            # Honor pause between actions
            try:
                while getattr(ctx, "pause_event", None) is not None and ctx.pause_event.is_set():
                    if ctx.stop_event.is_set():
                        return
                    time.sleep(0.05)
            except Exception:
                pass
            try:
                # Bring target window to foreground before each action
                try:
                    hwnd = ctx.hwnd
                    if hwnd is None:
                        hwnd = find_window_by_title_substr(ctx.window_title_substr)
                        if hwnd is not None:
                            ctx.hwnd = hwnd
                    if hwnd is not None:
                        bring_to_front(hwnd)
                except Exception:
                    pass
                start = time.time()
                ctx.last_action_name = action.name
                res = action.run(ctx)
                dur = time.time() - start
                ctx.last_action_duration_s = dur
                ctx.last_progress_ts = time.time()
                if dur > 2.0:
                    try:
                        logs.add(f"[ActionSlow] {action.name} took {dur:.2f}s in {self.name}:{step.name}", level="info")
                    except Exception:
                        pass
                if res is not None:
                    last_result = res
            except Exception as exc:
                try:
                    print(f"[ActionError] {action.name} in step {step.name}: {exc}")
                except Exception:
                    pass
                try:
                    logs.add(f"[ActionError] {action.name} in step {step.name}: {exc}", level="err")
                except Exception:
                    pass
        # Transition
        success = bool(last_result)
        next_name: Optional[str] = step.on_success if success else step.on_failure
        if next_name and next_name in self._steps:
            self._current = next_name
        ctx.cycle_count += 1
        # Pace
        if self._loop_sleep_s > 0:
            end_by = time.time() + self._loop_sleep_s
            while time.time() < end_by:
                if ctx.stop_event.is_set():
                    return
                time.sleep(0.005)
