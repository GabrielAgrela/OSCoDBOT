from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_file
import time as _time
import logging
import os
import threading as _threading

from bot.config import DEFAULT_CONFIG, AppConfig, make_config
from bot.core.state_machine import Context, State, StateMachine
from bot.states import MODES as STATE_MODES, build_alternating_state, build_round_robin_state, build_with_checkstuck_state
from bot.core import logs
from bot.core import counters as _counters
from bot.core.window import find_window_by_title_substr, get_client_rect_screen, bring_to_front
import numpy as _np  # type: ignore
import mss as _mss   # type: ignore
from datetime import datetime
from pathlib import Path as _Path


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


def _restart_with_current_selection() -> bool:
    """Rebuild and restart the running machine using the latest DEFAULT_CONFIG.

    Returns True if a machine was restarted, False if nothing was running.
    """
    global _running
    if not _running:
        return False
    # Capture current selection and paused state
    try:
        was_paused = bool(_running.machine and _running.ctx and _running.machine.is_paused(_running.ctx))
    except Exception:
        was_paused = False
    selection = list(_running.modes)
    kind = _running.kind
    # Stop existing
    _stop_running()
    # Recreate with latest DEFAULT_CONFIG
    cfg = DEFAULT_CONFIG
    try:
        if len(selection) == 1:
            key = selection[0]
            label, builder = STATE_MODES[key]
            state, ctx = build_with_checkstuck_state(cfg, builder, label=label)
            mach = StateMachine(state)
            mach.start(ctx)
            if was_paused:
                try:
                    mach.pause(ctx)
                except Exception:
                    pass
            _running = Running(kind="single", modes=(key,), machine=mach, ctx=ctx)
        else:
            builders = [(STATE_MODES[k][0], STATE_MODES[k][1]) for k in selection]
            state, ctx = build_round_robin_state(cfg, builders)
            mach = StateMachine(state)
            mach.start(ctx)
            if was_paused:
                try:
                    mach.pause(ctx)
                except Exception:
                    pass
            _running = Running(kind="multi", modes=tuple(selection), machine=mach, ctx=ctx)
        return True
    except Exception:
        _running = None
        return False


def _env_current_values() -> Dict[str, str]:
    """Return current config values mapped to .env keys as strings."""
    import os as _os
    cfg = DEFAULT_CONFIG
    # Helper to fetch env override or derive from cfg
    def get(k: str, default: str) -> str:
        v = _os.getenv(k)
        if v is not None:
            return v
        return default
    # Percent helpers
    def pct(v: float) -> str:
        try:
            return f"{max(0.0, min(100.0, float(v)*100.0)):.1f}%"
        except Exception:
            return "0.0%"
    # Bool helper
    def b(v: bool) -> str:
        return "true" if bool(v) else "false"
    out: Dict[str, str] = {
        "WINDOW_TITLE_SUBSTR": get("WINDOW_TITLE_SUBSTR", cfg.window_title_substr),
        "MATCH_THRESHOLD": get("MATCH_THRESHOLD", f"{cfg.match_threshold:.2f}"),
        "VERIFY_THRESHOLD": get("VERIFY_THRESHOLD", "0.85"),
        "UI_MARGIN_LEFT_PCT": get("UI_MARGIN_LEFT_PCT", pct(cfg.ui_margin_left_pct)),
        "UI_MARGIN_TOP_PCT": get("UI_MARGIN_TOP_PCT", pct(cfg.ui_margin_top_pct)),
        "CLICK_SNAP_BACK": get("CLICK_SNAP_BACK", b(cfg.click_snap_back)),
        "SAVE_SHOTS": get("SAVE_SHOTS", b(cfg.save_shots)),
        "SHOTS_DIR": get("SHOTS_DIR", str(getattr(cfg, 'shots_dir', 'debug_captures'))),
        "SHOTS_MAX_BYTES": get("SHOTS_MAX_BYTES", str(getattr(cfg, 'shots_max_bytes', 1073741824))),
        "USE_WEBVIEW": get("USE_WEBVIEW", b(cfg.use_webview)),
        "UI_PIN_TO_GAME": get("UI_PIN_TO_GAME", b(cfg.ui_pin_to_game)),
        "UI_TOPMOST": get("UI_TOPMOST", b(cfg.ui_topmost)),
        "UI_FRAMELESS": get("UI_FRAMELESS", b(cfg.ui_frameless)),
        "FORCE_WINDOW_RESIZE": get("FORCE_WINDOW_RESIZE", b(cfg.force_window_resize)),
        "FORCE_WINDOW_WIDTH": get("FORCE_WINDOW_WIDTH", str(cfg.force_window_width)),
        "FORCE_WINDOW_HEIGHT": get("FORCE_WINDOW_HEIGHT", str(cfg.force_window_height)),
        "FARM_COOLDOWN_MIN": get("FARM_COOLDOWN_MIN", f"{cfg.farm_cooldown_min_s}s"),
        "FARM_COOLDOWN_MAX": get("FARM_COOLDOWN_MAX", f"{cfg.farm_cooldown_max_s}s"),
        "TRAIN_COOLDOWN_MIN": get("TRAIN_COOLDOWN_MIN", f"{cfg.train_cooldown_min_s}s"),
        "TRAIN_COOLDOWN_MAX": get("TRAIN_COOLDOWN_MAX", f"{cfg.train_cooldown_max_s}s"),
        "ALLIANCE_HELP_COOLDOWN_MIN": get("ALLIANCE_HELP_COOLDOWN_MIN", f"{cfg.alliance_help_cooldown_min_s}s"),
        "ALLIANCE_HELP_COOLDOWN_MAX": get("ALLIANCE_HELP_COOLDOWN_MAX", f"{cfg.alliance_help_cooldown_max_s}s"),
        "TRAIN_COOLDOWN_MIN": get("TRAIN_COOLDOWN_MIN", f"{cfg.train_cooldown_min_s}s"),
        "TRAIN_COOLDOWN_MAX": get("TRAIN_COOLDOWN_MAX", f"{cfg.train_cooldown_max_s}s"),
        "MAX_ARMIES": get("MAX_ARMIES", str(cfg.max_armies)),
        "LOG_TO_FILE": get("LOG_TO_FILE", b(getattr(cfg, 'log_to_file', True))),
        "LOG_FILE": get("LOG_FILE", str(getattr(cfg, 'log_file', 'bot.log'))),
        "LOG_MAX_BYTES": get("LOG_MAX_BYTES", str(getattr(cfg, 'log_max_bytes', 1048576))),
        "LOG_BACKUPS": get("LOG_BACKUPS", str(getattr(cfg, 'log_backups', 5))),
        # Hotkey (if present in environment; default to F12)
        "STOP_HOTKEY": get("STOP_HOTKEY", "F12"),
    }
    return out


def _write_env_updates(updates: Dict[str, str]) -> bool:
    """Merge updates into .env in the current working directory.

    - Preserves comments and unrelated keys
    - Adds new keys at the end
    """
    from pathlib import Path as _Path
    import os as _os
    import sys as _sys
    # Prefer writing next to the executable when frozen; else CWD
    if getattr(_sys, "frozen", False):
        try:
            base = _Path(_sys.executable).resolve().parent
        except Exception:
            base = _Path.cwd()
    else:
        base = _Path.cwd()
    path = base / ".env"
    existing: Dict[str, str] = {}
    lines: list[str] = []
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8").splitlines()
            lines = raw[:]
            for ln in raw:
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" not in s:
                    continue
                k, v = s.split("=", 1)
                existing[k.strip()] = v
        except Exception:
            lines = []
            existing = {}
    # Apply updates to lines
    updated_keys = set()
    new_lines: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            new_lines.append(ln)
            continue
        k, _v = s.split("=", 1)
        key = k.strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(ln)
    # Append any remaining keys
    for k, v in updates.items():
        if k not in updated_keys and k:
            new_lines.append(f"{k}={v}")
    try:
        txt = "\n".join(new_lines) + "\n"
        path.write_text(txt, encoding="utf-8")
        return True
    except Exception:
        return False


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
                "farm_wood": "wood",
                "farm_ore": "ore",
                "farm_gold": "gold",
                "farm_mana": "mana",
                "farm_gem": "gems",
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


@app.get("/api/env")
def api_env_get():
    return jsonify(_env_current_values())


@app.post("/api/env")
def api_env_post():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload"}), 400
    # Whitelist keys we manage
    allowed = set(_env_current_values().keys())
    updates: Dict[str, str] = {}
    for k, v in data.items():
        if k in allowed and isinstance(v, str):
            updates[k] = v.strip()
    if not updates:
        return jsonify({"ok": False, "error": "No valid keys"}), 400
    ok = _write_env_updates(updates)
    # Rebuild default config and hot-restart running machine to apply changes live
    try:
        import bot.config as _cfg
        _cfg.DEFAULT_CONFIG = _cfg.make_config()
    except Exception:
        pass
    reloaded = False
    try:
        reloaded = _restart_with_current_selection()
    except Exception:
        reloaded = False
    return jsonify({"ok": bool(ok), "reloaded": bool(reloaded)})


@app.post("/api/reload")
def api_reload():
    """Hot-restart the running machine using current selection and config."""
    try:
        reloaded = _restart_with_current_selection()
        return jsonify({"ok": True, "reloaded": bool(reloaded)})
    except Exception:
        return jsonify({"ok": False}), 500


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
    def _save_start_shot(ctx: Context) -> None:
        try:
            hwnd = ctx.hwnd
            if hwnd is None:
                hwnd = find_window_by_title_substr(ctx.window_title_substr)
                if hwnd is None:
                    return
                ctx.hwnd = hwnd
            try:
                bring_to_front(hwnd)
            except Exception:
                pass
            rect = get_client_rect_screen(hwnd)
            if rect.width <= 0 or rect.height <= 0:
                return
            mon = {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
            with _mss.mss() as sct:
                raw = _np.array(sct.grab(mon))
            img_bgr = raw[:, :, :3]
            try:
                out_dir = getattr(DEFAULT_CONFIG, 'start_shots_dir', _Path('start_captures'))
            except Exception:
                out_dir = _Path('start_captures')
            folder = _Path(out_dir)
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_path = folder / f"start_{ts}.png"
            try:
                import cv2 as _cv2  # type: ignore
                _cv2.imwrite(str(out_path), img_bgr)
            except Exception:
                try:
                    from PIL import Image as _Image  # type: ignore
                    _Image.fromarray(img_bgr[:, :, ::-1]).save(str(out_path))
                except Exception:
                    return
            try:
                logs.add(f"[StartShot] Saved {out_path}", level='info')
            except Exception:
                pass
        except Exception:
            return
    if len(selection) == 1:
        key = selection[0]
        label, builder = STATE_MODES[key]
        # Wrap with checkstuck so it runs after each cycle; pass label for pink switch logs
        state, ctx = build_with_checkstuck_state(cfg, builder, label=label)
        mach = StateMachine(state)
        try:
            _save_start_shot(ctx)
        except Exception:
            pass
        mach.start(ctx)
        _running = Running(kind="single", modes=(key,), machine=mach, ctx=ctx)
        return jsonify({"ok": True, "kind": "single", "modes": selection})
    # 2+ selections: run round-robin in selection order
    builders = [(STATE_MODES[k][0], STATE_MODES[k][1]) for k in selection]
    state, ctx = build_round_robin_state(cfg, builders)
    mach = StateMachine(state)
    try:
        _save_start_shot(ctx)
    except Exception:
        pass
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



