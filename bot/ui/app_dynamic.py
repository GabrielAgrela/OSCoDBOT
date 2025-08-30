from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from bot.config import DEFAULT_CONFIG, AppConfig
from bot.core.state_machine import Context, State, StateMachine
from bot.states import MODES as STATE_MODES, build_alternating_state


@dataclass
class Mode:
    key: str
    label: str
    builder: Callable[[AppConfig], Tuple[State, Context]]
    button: Optional[tk.Button] = None
    machine: Optional[StateMachine] = None
    ctx: Optional[Context] = None
    running: bool = False


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Call of the Dragons Bot")

        # Build modes from central registry
        self._modes: Dict[str, Mode] = {
            key: Mode(key, label, builder) for key, (label, builder) in STATE_MODES.items()
        }

        # Create buttons dynamically
        first = True
        for key, mode in self._modes.items():
            text = f"Start {mode.label}"
            btn = tk.Button(root, text=text, width=20, command=lambda k=key: self.on_toggle_mode(k))
            pady = (12, 6) if first else (0, 12)
            btn.pack(padx=12, pady=pady)
            first = False
            mode.button = btn

        self.status = tk.StringVar(value="Idle")
        self.lbl = tk.Label(root, textvariable=self.status)
        self.lbl.pack(padx=12, pady=(0, 12))

        # Active combo state (alternating two modes)
        self._combo_machine: Optional[StateMachine] = None
        self._combo_ctx: Optional[Context] = None
        self._combo_modes: Optional[Tuple[str, str]] = None  # (first, second)

        self._build_mode_machines()

    def _build_mode_machines(self) -> None:
        cfg = DEFAULT_CONFIG
        for mode in self._modes.values():
            state, ctx = mode.builder(cfg)
            mode.machine = StateMachine(state)
            mode.ctx = ctx

    # Generic mode toggling
    def on_toggle_mode(self, key: str) -> None:
        mode = self._modes[key]

        # If a combo is running
        if self._combo_modes is not None:
            if key in self._combo_modes:
                # Stop combo and switch to single of the pressed mode
                self._stop_combo()
                self._start_single(key)
                return
            else:
                # Stop combo and start single of the new mode
                self._stop_combo()
                self._start_single(key)
                return

        # If pressed mode is already running, stop it
        if mode.running:
            self._stop_single(key)
            self.status.set("Stopped")
            return

        # Check if another single mode is running; if yes, upgrade to combo
        other_running = [k for k, m in self._modes.items() if k != key and m.running]
        if other_running:
            other = other_running[0]
            self._stop_single(other)
            self._start_combo(other, key)
            return

        # Otherwise, start single mode
        self._start_single(key)

    # Helpers
    def _start_single(self, key: str) -> None:
        mode = self._modes[key]
        assert mode.machine and mode.ctx
        mode.machine.start(mode.ctx)
        mode.running = True
        if mode.button:
            mode.button.config(text=f"Stop {mode.label}")
        self.status.set(f"{mode.label} running...")

    def _stop_single(self, key: str) -> None:
        mode = self._modes[key]
        assert mode.machine and mode.ctx
        mode.machine.stop(mode.ctx)
        mode.running = False
        if mode.button:
            mode.button.config(text=f"Start {mode.label}")

    def _start_combo(self, first_key: str, second_key: str) -> None:
        first = self._modes[first_key]
        second = self._modes[second_key]
        cfg = DEFAULT_CONFIG
        combo_state, combo_ctx = build_alternating_state(cfg, first.builder, second.builder)
        self._combo_machine = StateMachine(combo_state)
        self._combo_ctx = combo_ctx
        self._combo_machine.start(self._combo_ctx)
        self._combo_modes = (first_key, second_key)
        # Update buttons
        if first.button:
            first.button.config(text=f"Stop {first.label}")
        if second.button:
            second.button.config(text=f"Stop {second.label}")
        self.status.set(f"Alternating: {first.label} -> {second.label}")

    def _stop_combo(self) -> None:
        if self._combo_machine and self._combo_ctx:
            self._combo_machine.stop(self._combo_ctx)
        if self._combo_modes:
            for key in self._combo_modes:
                mode = self._modes[key]
                if mode.button:
                    mode.button.config(text=f"Start {mode.label}")
        self._combo_machine = None
        self._combo_ctx = None
        self._combo_modes = None
        self.status.set("Stopped")


def run_app() -> None:
    root = tk.Tk()
    app = App(root)
    root.mainloop()

