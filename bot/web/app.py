from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request

from bot.config import DEFAULT_CONFIG, AppConfig
from bot.core.state_machine import Context, State, StateMachine
from bot.states import MODES as STATE_MODES, build_alternating_state


@dataclass
class Running:
    kind: str  # 'single' or 'combo'
    modes: Tuple[str, ...]
    machine: Optional[StateMachine]
    ctx: Optional[Context]


app = Flask(__name__, template_folder="templates", static_folder="static")

_running: Optional[Running] = None


def _stop_running() -> None:
    global _running
    if _running and _running.machine and _running.ctx:
        _running.machine.stop(_running.ctx)
    _running = None


@app.get("/")
def index():
    modes = [{"key": k, "label": v[0]} for k, v in STATE_MODES.items()]
    return render_template("index.html", modes=modes)


@app.get("/api/modes")
def api_modes():
    return jsonify({k: {"label": v[0]} for k, v in STATE_MODES.items()})


@app.get("/api/status")
def api_status():
    if not _running:
        return jsonify({"running": False})
    return jsonify({
        "running": True,
        "kind": _running.kind,
        "modes": list(_running.modes),
    })


@app.post("/api/start")
def api_start():
    global _running
    data = request.get_json(silent=True) or {}
    selection: List[str] = list(data.get("selection") or [])
    selection = [s for s in selection if s in STATE_MODES]
    if not selection:
        return jsonify({"error": "No valid modes selected"}), 400
    _stop_running()
    cfg = DEFAULT_CONFIG
    if len(selection) == 1:
        key = selection[0]
        label, builder = STATE_MODES[key]
        state, ctx = builder(cfg)
        mach = StateMachine(state)
        mach.start(ctx)
        _running = Running(kind="single", modes=(key,), machine=mach, ctx=ctx)
        return jsonify({"ok": True, "kind": "single", "modes": selection})
    # Limit to two for now
    first, second = selection[:2]
    (_, b1) = STATE_MODES[first]
    (_, b2) = STATE_MODES[second]
    state, ctx = build_alternating_state(cfg, b1, b2)
    mach = StateMachine(state)
    mach.start(ctx)
    _running = Running(kind="combo", modes=(first, second), machine=mach, ctx=ctx)
    return jsonify({"ok": True, "kind": "combo", "modes": [first, second]})


@app.post("/api/stop")
def api_stop():
    _stop_running()
    return jsonify({"ok": True})


def run_web(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    app.run(host=host, port=port, debug=debug)

