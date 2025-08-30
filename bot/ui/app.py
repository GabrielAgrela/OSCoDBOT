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
    build_farm_gold_state,
    build_alternating_state,
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

        self.btn_gold = tk.Button(root, text="Start Farm Gold", width=20, command=self.on_toggle_farm_gold)
        self.btn_gold.pack(padx=12, pady=(0, 12))

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

        self._gold_machine: StateMachine | None = None
        self._gold_ctx: Context | None = None
        self._gold_running = False

        self._combo_machine: StateMachine | None = None
        self._combo_ctx: Context | None = None
        self._combo_running = False
        self._combo_modes: tuple[str, str] | None = None  # order: (first, second)

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

        # combo built on demand when user starts a second mode

        gold_state, gold_ctx = build_farm_gold_state(cfg)
        self._gold_machine = StateMachine(gold_state)
        self._gold_ctx = gold_ctx

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
            # If Ore is running, upgrade to combo (Ore -> Scouts)
            if self._ore_running and self._ore_machine and self._ore_ctx:
                self._ore_machine.stop(self._ore_ctx)
                self._ore_running = False
                self.btn_ore.config(text="Start Farm Ore")
                self._start_combo(("farm_ore", build_farm_ore_state), ("scouts", build_scouts_state))
                return
            # If Gold is running, upgrade to combo (Gold -> Scouts)
            if self._gold_running and self._gold_machine and self._gold_ctx:
                self._gold_machine.stop(self._gold_ctx)
                self._gold_running = False
                self.btn_gold.config(text="Start Farm Gold")
                self._start_combo(("farm_gold", build_farm_gold_state), ("scouts", build_scouts_state))
                return
            # If Farm Wood is running, upgrade to combo (Wood -> Scouts)
            if self._farm_running and self._farm_machine and self._farm_ctx:
                self._farm_machine.stop(self._farm_ctx)
                self._farm_running = False
                self.btn_farm.config(text="Start Farm Wood")
                # Start combo: farm_wood then scouts
                self._start_combo(("farm_wood", build_farm_wood_state), ("scouts", build_scouts_state))
                return
            # If a different combo is running, stop it and start single scouts
            if self._combo_running:
                self._stop_combo()
                self._start_single_scouts()
                return
            # Otherwise start single scouts
            self._start_single_scouts()


    def on_toggle_farm(self) -> None:
        if not self._farm_machine or not self._farm_ctx:
            messagebox.showerror("Error", "Farm machine not initialized")
            return
        # If Scouts is running, upgrade to combo (Scouts -> Farm Wood)
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
            self._start_combo(("scouts", build_scouts_state), ("farm_wood", build_farm_wood_state))
            return
        # If Ore is running, upgrade to combo (Ore -> Farm Wood)
        if self._ore_running and self._ore_machine and self._ore_ctx:
            self._ore_machine.stop(self._ore_ctx)
            self._ore_running = False
            self.btn_ore.config(text="Start Farm Ore")
            self._start_combo(("farm_ore", build_farm_ore_state), ("farm_wood", build_farm_wood_state))
            return
        # If Gold is running, upgrade to combo (Gold -> Farm Wood)
        if self._gold_running and self._gold_machine and self._gold_ctx:
            self._gold_machine.stop(self._gold_ctx)
            self._gold_running = False
            self.btn_gold.config(text="Start Farm Gold")
            self._start_combo(("farm_gold", build_farm_gold_state), ("farm_wood", build_farm_wood_state))
            return
        # If a combo is running
        if self._combo_running:
            if self._combo_modes and "farm_wood" in self._combo_modes:
                self._stop_combo()
            else:
                self._stop_combo()
                self._farm_machine.start(self._farm_ctx)
                self._farm_running = True
                self.btn_farm.config(text="Stop Farm Wood")
                self.status.set("Farm wood running...")
            return
        # Toggle single Farm Wood
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

    def _stop_combo(self) -> None:
        if self._combo_running and self._combo_machine and self._combo_ctx:
            self._combo_machine.stop(self._combo_ctx)
        self._combo_running = False
        self._combo_modes = None
        # Reset button texts
        self.btn.config(text="Start Scouts")
        self.btn_farm.config(text="Start Farm Wood")
        self.btn_ore.config(text="Start Farm Ore")
        self.btn_gold.config(text="Start Farm Gold")
        self.status.set("Stopped")

    def _start_single_scouts(self) -> None:
        self._machine.start(self._ctx)
        self._running = True
        self.btn.config(text="Stop Scouts")
        self.status.set("Scouts running...")

    def _start_single_ore(self) -> None:
        self._ore_machine.start(self._ore_ctx)
        self._ore_running = True
        self.btn_ore.config(text="Stop Farm Ore")
        self.status.set("Farm ore running...")

    def _start_single_gold(self) -> None:
        self._gold_machine.start(self._gold_ctx)
        self._gold_running = True
        self.btn_gold.config(text="Stop Farm Gold")
        self.status.set("Farm gold running...")

    def _start_combo(self, first: tuple[str, callable], second: tuple[str, callable]) -> None:
        # Build and start a fresh alternating state machine using the two builders
        cfg = DEFAULT_CONFIG
        combo_state, combo_ctx = build_alternating_state(cfg, first[1], second[1])
        self._combo_machine = StateMachine(combo_state)
        self._combo_ctx = combo_ctx
        self._combo_machine.start(self._combo_ctx)
        self._combo_running = True
        self._combo_modes = (first[0], second[0])
        # Update button labels for the two modes involved
        if "scouts" in self._combo_modes:
            self.btn.config(text="Stop Scouts")
        if "farm_wood" in self._combo_modes:
            self.btn_farm.config(text="Stop Farm Wood")
        if "farm_ore" in self._combo_modes:
            self.btn_ore.config(text="Stop Farm Ore")
        if "farm_gold" in self._combo_modes:
            self.btn_gold.config(text="Stop Farm Gold")
        self.status.set(f"Alternating: {self._combo_modes[0]} -> {self._combo_modes[1]}")

    def on_toggle_farm_ore(self) -> None:
        if not self._ore_machine or not self._ore_ctx:
            messagebox.showerror("Error", "Farm ore machine not initialized")
            return
        # If Scouts is running, upgrade to combo (Scouts -> Ore)
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
            self._start_combo(("scouts", build_scouts_state), ("farm_ore", build_farm_ore_state))
            return
        # If Farm Wood is running, upgrade to combo (Wood -> Ore)
        if self._farm_running and self._farm_machine and self._farm_ctx:
            self._farm_machine.stop(self._farm_ctx)
            self._farm_running = False
            self.btn_farm.config(text="Start Farm Wood")
            self._start_combo(("farm_wood", build_farm_wood_state), ("farm_ore", build_farm_ore_state))
            return
        # If a combo is running
        if self._combo_running:
            if self._combo_modes and "farm_ore" in self._combo_modes:
                self._stop_combo()
            else:
                self._stop_combo()
                self._start_single_ore()
            return
        # Toggle single Ore
        if self._ore_running:
            self._ore_machine.stop(self._ore_ctx)
            self._ore_running = False
            self.btn_ore.config(text="Start Farm Ore")
            self.status.set("Stopped")
        else:
            self._start_single_ore()

    def on_toggle_farm_gold(self) -> None:
        if not self._gold_machine or not self._gold_ctx:
            messagebox.showerror("Error", "Farm gold machine not initialized")
            return
        # If Scouts is running, upgrade to combo (Scouts -> Gold)
        if self._running and self._machine and self._ctx:
            self._machine.stop(self._ctx)
            self._running = False
            self.btn.config(text="Start Scouts")
            self._start_combo(("scouts", build_scouts_state), ("farm_gold", build_farm_gold_state))
            return
        # If Farm Wood is running, upgrade to combo (Wood -> Gold)
        if self._farm_running and self._farm_machine and self._farm_ctx:
            self._farm_machine.stop(self._farm_ctx)
            self._farm_running = False
            self.btn_farm.config(text="Start Farm Wood")
            self._start_combo(("farm_wood", build_farm_wood_state), ("farm_gold", build_farm_gold_state))
            return
        # If Ore is running, upgrade to combo (Ore -> Gold)
        if self._ore_running and self._ore_machine and self._ore_ctx:
            self._ore_machine.stop(self._ore_ctx)
            self._ore_running = False
            self.btn_ore.config(text="Start Farm Ore")
            self._start_combo(("farm_ore", build_farm_ore_state), ("farm_gold", build_farm_gold_state))
            return
        # If a combo is running
        if self._combo_running:
            if self._combo_modes and "farm_gold" in self._combo_modes:
                self._stop_combo()
            else:
                self._stop_combo()
                self._start_single_gold()
            return
        # Toggle single Gold
        if self._gold_running:
            self._gold_machine.stop(self._gold_ctx)
            self._gold_running = False
            self.btn_gold.config(text="Start Farm Gold")
            self.status.set("Stopped")
        else:
            self._start_single_gold()

def run_app() -> None:
    root = tk.Tk()
    app = App(root)
    root.mainloop()



