from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from bot.config import DEFAULT_CONFIG
from bot.core.state_machine import Context, StateMachine
from bot.states import build_scouts_state, build_farm_wood_state


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Call of the Dragons Bot")

        self.btn = tk.Button(root, text="Start Scouts", width=20, command=self.on_toggle_scouts)
        self.btn.pack(padx=12, pady=(12, 6))

        self.btn_farm = tk.Button(root, text="Start Farm Wood", width=20, command=self.on_toggle_farm)
        self.btn_farm.pack(padx=12, pady=(0, 12))

        self.status = tk.StringVar(value="Idle")
        self.lbl = tk.Label(root, textvariable=self.status)
        self.lbl.pack(padx=12, pady=(0, 12))

        self._machine: StateMachine | None = None
        self._ctx: Context | None = None
        self._running = False

        self._farm_machine: StateMachine | None = None
        self._farm_ctx: Context | None = None
        self._farm_running = False

        self._build_machines()

    def _build_machines(self) -> None:
        cfg = DEFAULT_CONFIG
        scout_state, scout_ctx = build_scouts_state(cfg)
        self._machine = StateMachine(scout_state)
        self._ctx = scout_ctx

        farm_state, farm_ctx = build_farm_wood_state(cfg)
        self._farm_machine = StateMachine(farm_state)
        self._farm_ctx = farm_ctx

    def on_toggle_scouts(self) -> None:
        if not self._machine or not self._ctx:
            messagebox.showerror("Error", "State machine not initialized")
            return
        if self._running:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
            self.status.set("Stopped")
        else:

            self._machine.start(self._ctx)
            self._running = True
            self.btn.config(text="Stop Scouts")
            self.status.set("Scouts running...")


    def on_toggle_farm(self) -> None:
        if not self._farm_machine or not self._farm_ctx:
            messagebox.showerror("Error", "Farm machine not initialized")
            return
        # Stop scouts if running
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
        if self._farm_running:
            self._farm_machine.stop(self._farm_ctx)
            self._farm_running = False
            self.btn_farm.config(text="Start Farm Wood")
            self.status.set("Stopped")
        else:
            self._farm_machine.start(self._farm_ctx)
            self._farm_running = True
            self.btn_farm.config(text="Stop Farm Wood")
            self.status.set("Farm wood running...")

def run_app() -> None:
    root = tk.Tk()
    app = App(root)
    root.mainloop()

