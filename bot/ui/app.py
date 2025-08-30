from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from bot.config import DEFAULT_CONFIG
from bot.core.state_machine import Context, StateMachine
from bot.states import (
    build_scouts_state,
    build_farm_wood_state,
    build_farm_ore_state,
    build_farm_ore_and_scout_state,
)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Call of the Dragons Bot")

        self.btn = tk.Button(root, text="Start Scouts", width=20, command=self.on_toggle_scouts)
        self.btn.pack(padx=12, pady=(12, 6))

        self.btn_farm = tk.Button(root, text="Start Farm Wood", width=20, command=self.on_toggle_farm)
        self.btn_farm.pack(padx=12, pady=(0, 12))

        self.btn_ore = tk.Button(root, text="Start Farm Ore", width=20, command=self.on_toggle_farm_ore)
        self.btn_ore.pack(padx=12, pady=(0, 12))

        self.btn_combo = tk.Button(root, text="Start Farm Ore and Scout", width=22, command=self.on_toggle_combo)
        self.btn_combo.pack(padx=12, pady=(0, 12))

        self.status = tk.StringVar(value="Idle")
        self.lbl = tk.Label(root, textvariable=self.status)
        self.lbl.pack(padx=12, pady=(0, 12))

        self._machine: StateMachine | None = None
        self._ctx: Context | None = None
        self._running = False

        self._farm_machine: StateMachine | None = None
        self._farm_ctx: Context | None = None
        self._farm_running = False

        self._ore_machine: StateMachine | None = None
        self._ore_ctx: Context | None = None
        self._ore_running = False

        self._combo_machine: StateMachine | None = None
        self._combo_ctx: Context | None = None
        self._combo_running = False

        self._build_machines()

    def _build_machines(self) -> None:
        cfg = DEFAULT_CONFIG
        scout_state, scout_ctx = build_scouts_state(cfg)
        self._machine = StateMachine(scout_state)
        self._ctx = scout_ctx

        farm_state, farm_ctx = build_farm_wood_state(cfg)
        self._farm_machine = StateMachine(farm_state)
        self._farm_ctx = farm_ctx

        ore_state, ore_ctx = build_farm_ore_state(cfg)
        self._ore_machine = StateMachine(ore_state)
        self._ore_ctx = ore_ctx

        combo_state, combo_ctx = build_farm_ore_and_scout_state(cfg)
        self._combo_machine = StateMachine(combo_state)
        self._combo_ctx = combo_ctx

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
            # Stop other modes if running
            if self._farm_running and self._farm_machine and self._farm_ctx:
                self._farm_machine.stop(self._farm_ctx)
                self._farm_running = False
                self.btn_farm.config(text="Start Farm Wood")
            if self._ore_running and self._ore_machine and self._ore_ctx:
                self._ore_machine.stop(self._ore_ctx)
                self._ore_running = False
                self.btn_ore.config(text="Start Farm Ore")
            if self._combo_running and self._combo_machine and self._combo_ctx:
                self._combo_machine.stop(self._combo_ctx)
                self._combo_running = False
                self.btn_combo.config(text="Start Farm Ore and Scout")

            self._machine.start(self._ctx)
            self._running = True
            self.btn.config(text="Stop Scouts")
            self.status.set("Scouts running...")


    def on_toggle_farm(self) -> None:
        if not self._farm_machine or not self._farm_ctx:
            messagebox.showerror("Error", "Farm machine not initialized")
            return
        # Stop other modes if running
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
        if self._ore_running and self._ore_machine and self._ore_ctx:
            self._ore_machine.stop(self._ore_ctx)
            self._ore_running = False
            self.btn_ore.config(text="Start Farm Ore")
        if self._combo_running and self._combo_machine and self._combo_ctx:
            self._combo_machine.stop(self._combo_ctx)
            self._combo_running = False
            self.btn_combo.config(text="Start Farm Ore and Scout")
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

    def on_toggle_combo(self) -> None:
        if not self._combo_machine or not self._combo_ctx:
            messagebox.showerror("Error", "Combo machine not initialized")
            return
        # Stop other modes if running
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
        if self._farm_running and self._farm_machine and self._farm_ctx:
            self._farm_machine.stop(self._farm_ctx)
            self._farm_running = False
            self.btn_farm.config(text="Start Farm Wood")
        if self._ore_running and self._ore_machine and self._ore_ctx:
            self._ore_machine.stop(self._ore_ctx)
            self._ore_running = False
            self.btn_ore.config(text="Start Farm Ore")
        if self._combo_running:
            self._combo_machine.stop(self._combo_ctx)
            self._combo_running = False
            self.btn_combo.config(text="Start Farm Ore and Scout")
            self.status.set("Stopped")
        else:
            self._combo_machine.start(self._combo_ctx)
            self._combo_running = True
            self.btn_combo.config(text="Stop Farm Ore and Scout")
            self.status.set("Farm ore and scouts running...")

    def on_toggle_farm_ore(self) -> None:
        if not self._ore_machine or not self._ore_ctx:
            messagebox.showerror("Error", "Farm ore machine not initialized")
            return
        # Stop other modes if running
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
        if self._farm_running and self._farm_machine and self._farm_ctx:
            self._farm_machine.stop(self._farm_ctx)
            self._farm_running = False
            self.btn_farm.config(text="Start Farm Wood")
        if self._ore_running:
            self._ore_machine.stop(self._ore_ctx)
            self._ore_running = False
            self.btn_ore.config(text="Start Farm Ore")
            self.status.set("Stopped")
        else:
            self._ore_machine.start(self._ore_ctx)
            self._ore_running = True
            self.btn_ore.config(text="Stop Farm Ore")
            self.status.set("Farm ore running...")

def run_app() -> None:
    root = tk.Tk()
    app = App(root)
    root.mainloop()

