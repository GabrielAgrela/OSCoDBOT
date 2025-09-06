from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_file
import time as _time
import logging
import os
import threading as _threading

from bot.config import DEFAULT_CONFIG, AppConfig
from bot.core.state_machine import Context, State, StateMachine
from bot.states import MODES as STATE_MODES, build_alternating_state, build_round_robin_state, build_with_checkstuck_state
from bot.core import logs
from bot.core import counters as _counters


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
    # Report cooldowns (remaining seconds) for active modes
    cooldowns = {}
    try:
        if _running.ctx and _running.modes:
            now = _time.time()
            # Map UI mode keys to cooldown keys used by states
            alias = {
                "farm_wood": "farm",
                "farm_ore": "ore",
                "farm_gold": "gold",
                "farm_mana": "mana",
                "train": "train",
            }
            for mode_key in _running.modes:
                cd_key = alias.get(mode_key, mode_key)
                try:
                    until = float(getattr(_running.ctx, f"_cooldown_until_{cd_key}", 0.0))
                except Exception:
                    until = 0.0
                remain = max(0, int(until - now))
                if remain > 0:
                    cooldowns[mode_key] = remain
    except Exception:
        cooldowns = {}
    return jsonify({
        "running": True,
        "kind": _running.kind,
        "modes": list(_running.modes),
        "paused": paused,
        "cooldowns": cooldowns,
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
        # Wrap with checkstuck so it runs after each cycle; pass label for pink switch logs
        state, ctx = build_with_checkstuck_state(cfg, builder, label=label)
        mach = StateMachine(state)
        mach.start(ctx)
        _running = Running(kind="single", modes=(key,), machine=mach, ctx=ctx)
        return jsonify({"ok": True, "kind": "single", "modes": selection})
    # 2+ selections: run round-robin in selection order
    builders = [(STATE_MODES[k][0], STATE_MODES[k][1]) for k in selection]
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
    # Global counters snapshot
    try:
        counters = _counters.get_all()
    except Exception:
        counters = {}
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
            "counters": {
                "troops_trained": int(counters.get("troops_trained", 0)),
                "nodes_farmed": int(counters.get("nodes_farmed", 0)),
                "alliance_helps": int(counters.get("alliance_helps", 0)),
            },
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


@app.get("/shots/latest")
def shots_latest():
    """Return the most recent annotated match screenshot as an image response.

    Looks for files like "*_match_*.png" inside the configured shots directory.
    Sends the file bytes with Cache-Control disabled so the UI can poll safely.
    """
    try:
        shots_dir = DEFAULT_CONFIG.shots_dir
    except Exception:
        from pathlib import Path as _Path
        shots_dir = _Path("debug_captures")
    try:
        import os as _os
        from pathlib import Path as _Path
        folder = _Path(shots_dir)
        if not folder.exists() or not folder.is_dir():
            return ("No shots", 404)
        # Find latest "match" png
        latest_path = None
        latest_mtime = -1.0
        candidates = []
        for p in folder.iterdir():
            try:
                if not p.is_file():
                    continue
                name = p.name.lower()
                if not name.endswith('.png'):
                    continue
                if "_match_" not in name:
                    # collect for fallback if no annotated matches exist
                    candidates.append(p)
                    continue
                mt = p.stat().st_mtime
                if mt > latest_mtime:
                    latest_mtime = mt
                    latest_path = p
            except Exception:
                continue
        # Fallback: use latest any PNG if no annotated match was found
        if not latest_path:
            for p in candidates:
                try:
                    mt = p.stat().st_mtime
                    if mt > latest_mtime:
                        latest_mtime = mt
                        latest_path = p
                except Exception:
                    continue
        if not latest_path:
            return ("No shots", 404)
        # Send file with no caching
        resp = send_file(str(latest_path))
        try:
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        except Exception:
            pass
        return resp
    except Exception:
        return ("No shots", 404)


def run_web(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    app.run(host=host, port=port, debug=debug)


@app.post("/api/quit")
def api_quit():
    """Stop any running state and terminate the process shortly after responding."""
    try:
        _stop_running()
    except Exception:
        pass
    # Delay exit slightly so the HTTP response can be delivered cleanly
    def _later_exit():
        try:
            _time.sleep(0.2)
        except Exception:
            pass
        try:
            os._exit(0)
        except Exception:
            raise SystemExit(0)
    try:
        _threading.Thread(target=_later_exit, daemon=True).start()
    except Exception:
        pass
    return jsonify({"ok": True})
