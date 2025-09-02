from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request
import time as _time
import logging

from bot.config import DEFAULT_CONFIG, AppConfig
from bot.core.state_machine import Context, State, StateMachine
from bot.states import MODES as STATE_MODES, build_alternating_state, build_round_robin_state
from bot.core import logs


@dataclass
class Running:
    kind: str  # 'single' or 'combo'
    modes: Tuple[str, ...]
    machine: Optional[StateMachine]
    ctx: Optional[Context]


app = Flask(__name__, template_folder="templates", static_folder="static")
# Suppress Flask/Werkzeug request logs in console
logging.getLogger("werkzeug").setLevel(logging.ERROR)
app.logger.disabled = True

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
    paused = False
    try:
        if _running.machine and _running.ctx:
            paused = bool(_running.machine.is_paused(_running.ctx))
    except Exception:
        paused = False
    return jsonify({
        "running": True,
        "kind": _running.kind,
        "modes": list(_running.modes),
        "paused": paused,
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
    # 2+ selections: run round-robin in selection order
    builders = [STATE_MODES[k][1] for k in selection]
    state, ctx = build_round_robin_state(cfg, builders)
    mach = StateMachine(state)
    mach.start(ctx)
    _running = Running(kind="multi", modes=tuple(selection), machine=mach, ctx=ctx)
    return jsonify({"ok": True, "kind": "multi", "modes": selection})


@app.post("/api/stop")
def api_stop():
    _stop_running()
    return jsonify({"ok": True})


@app.post("/api/pause")
def api_pause():
    if not _running or not _running.machine or not _running.ctx:
        return jsonify({"error": "Not running"}), 400
    try:
        _running.machine.pause(_running.ctx)
    except Exception:
        return jsonify({"error": "Failed to pause"}), 500
    return jsonify({"ok": True})


@app.post("/api/resume")
def api_resume():
    if not _running or not _running.machine or not _running.ctx:
        return jsonify({"error": "Not running"}), 400
    try:
        _running.machine.resume(_running.ctx)
    except Exception:
        return jsonify({"error": "Failed to resume"}), 500
    return jsonify({"ok": True})


@app.get("/api/logs")
def api_logs():
    try:
        since_raw = request.args.get("since")
        since = int(since_raw) if since_raw is not None else 0
    except Exception:
        since = 0
    entries = logs.get_since(since)
    return jsonify({"logs": entries})


@app.get("/api/metrics")
def api_metrics():
    if not _running or not _running.ctx:
        return jsonify({"running": False})
    ctx = _running.ctx
    now = _time.time()
    try:
        since = max(0.0, now - float(getattr(ctx, "last_progress_ts", 0.0)))
    except Exception:
        since = 0.0
    # Perf metrics (best-effort)
    try:
        from bot.core import perf as _perf
        m = _perf.get_process_metrics()
        rss_mb = float(m.get('rss_bytes', 0)) / (1024 * 1024)
        priv_mb = float(m.get('private_bytes', 0)) / (1024 * 1024)
        page_mb = float(m.get('pagefile_bytes', 0)) / (1024 * 1024)
        handles = int(m.get('handle_count', 0))
        gdi = int(m.get('gdi_count', 0))
        user = int(m.get('user_count', 0))
    except Exception:
        rss_mb = priv_mb = page_mb = 0.0
        handles = gdi = user = 0
    # Window rect (left, top, width, height)
    try:
        wr = getattr(ctx, "window_rect", (0, 0, 0, 0))
        w_left, w_top, w_width, w_height = int(wr[0]), int(wr[1]), int(wr[2]), int(wr[3])
    except Exception:
        w_left = w_top = w_width = w_height = 0
    data = {
        "running": True,
        "kind": _running.kind,
        "modes": list(_running.modes),
        "thread_alive": bool(_running.machine and _running.machine._thread and _running.machine._thread.is_alive()),
        "metrics": {
            "current_state": getattr(ctx, "current_state_name", ""),
            "current_step": getattr(ctx, "current_graph_step", ""),
            "last_action": getattr(ctx, "last_action_name", ""),
            "last_action_duration_s": float(getattr(ctx, "last_action_duration_s", 0.0)),
            "cycle_count": int(getattr(ctx, "cycle_count", 0)),
            "since_last_progress_s": since,
            "rss_mb": rss_mb,
            "private_mb": priv_mb,
            "pagefile_mb": page_mb,
            "handles": handles,
            "gdi_objects": gdi,
            "user_objects": user,
            "capture_ok": bool(getattr(ctx, '_mss', None) is not None),
            "capture_grabs": int(getattr(ctx, '_mss_grab_count', 0)),
            "window": {
                "left": w_left,
                "top": w_top,
                "width": w_width,
                "height": w_height,
                "title_substr": getattr(ctx, "window_title_substr", "") or "",
            },
        }
    }
    return jsonify(data)


def run_web(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    app.run(host=host, port=port, debug=debug)
