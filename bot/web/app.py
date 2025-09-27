from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_file
import time as _time
import logging
import os
import threading as _threading

import bot.config as config
from bot import settings as settings_store
from bot.core.state_machine import Context, State, StateMachine
from bot.states import MODES as STATE_MODES, build_alternating_state, build_round_robin_state, build_with_checkstuck_state
from bot.core import logs
from bot.core import counters as _counters
from bot.core.window import find_window_by_title_substr, get_client_rect_screen, bring_to_front, close_window
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


MODE_META = {
    "farm_alliance_resource_center": {
        "category": "Alliance & Events",
        "badge": "Alliance",
        "description": "Navigates the alliance territory panel to queue Alliance Resource Center runs with fallback gather steps.",
        "tags": ["alliance", "resource", "center", "event"],
    },
    "scouts": {
        "category": "Support & Utilities",
        "badge": "Support",
        "description": "Keeps scouts exploring by clicking idle icons and reissuing explore orders automatically.",
        "tags": ["scout", "explore", "support"],
    },
    "farm_wood": {
        "category": "Primary Farming",
        "badge": "Loop",
        "description": "Searches for wood nodes, manages legion dispatch, and respects cooldown gates when armies are full.",
        "tags": ["farm", "wood", "gather"],
    },
    "farm_ore": {
        "category": "Primary Farming",
        "badge": "Loop",
        "description": "Targets ore deposits, downgrades search level when needed, and handles gather and march flows.",
        "tags": ["farm", "ore", "gather"],
    },
    "farm_gold": {
        "category": "Primary Farming",
        "badge": "Loop",
        "description": "Finds gold sources and sends available legions through gather, create, and march steps with retries.",
        "tags": ["farm", "gold", "gather"],
    },
    "farm_mana": {
        "category": "Primary Farming",
        "badge": "Loop",
        "description": "Automates mana crystal farming using the standard magnifier -> search -> gather flow.",
        "tags": ["farm", "mana", "resource"],
    },
    "farm_gem": {
        "category": "Primary Farming",
        "badge": "Loop",
        "description": "Sweeps the map with spiral camera drags to locate gem mines before dispatching legions.",
        "tags": ["farm", "gems", "camera"],
    },
    "train": {
        "category": "Support & Utilities",
        "badge": "Support",
        "description": "Keeps troop training queues full by cycling the action menu and respecting configurable cooldowns.",
        "tags": ["train", "troops", "barracks"],
    },
    "alliance_help": {
        "category": "Support & Utilities",
        "badge": "Support",
        "description": "Clicks the alliance help button whenever it is available and idles until the next cooldown.",
        "tags": ["alliance", "help", "support"],
    },
}

CATEGORY_ORDER = [
    "Primary Farming",
    "Support & Utilities",
    "Alliance & Events",
]


def _build_mode_payload() -> List[Dict[str, object]]:
    payload: List[Dict[str, object]] = []
    for key, (label, _builder) in STATE_MODES.items():
        meta = MODE_META.get(key, {})
        tags = list(meta.get("tags", []))
        if not tags:
            tags = key.replace('_', ' ').split()
        payload.append(
            {
                "key": key,
                "label": label,
                "description": meta.get("description", "Automation flow."),
                "category": meta.get("category", "Other"),
                "badge": meta.get("badge", ""),
                "tags": tags,
            }
        )
    return payload


def _group_modes(modes: List[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for item in modes:
        cat = str(item.get("category") or "Other")
        grouped.setdefault(cat, []).append(item)
    def _sort_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
        return sorted(items, key=lambda m: str(m.get("label", "")).lower())
    ordered: List[Dict[str, object]] = []
    for cat in CATEGORY_ORDER:
        if cat in grouped:
            ordered.append({"name": cat, "modes": _sort_items(grouped.pop(cat))})
    for cat in sorted(grouped.keys()):
        ordered.append({"name": cat, "modes": _sort_items(grouped[cat])})
    return ordered


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
    """Rebuild and restart the running machine using the latest configuration values.

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
    # Recreate with latest configuration
    cfg = config.DEFAULT_CONFIG
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


def _settings_with_values() -> List[Dict[str, object]]:
    """Return schema entries including current values."""
    return settings_store.get_schema_with_values()


@app.get("/")
def index():
    modes = _build_mode_payload()
    grouped = _group_modes(modes)
    return render_template("index.html", modes=modes, grouped=grouped)


@app.get("/api/modes")
def api_modes():
    payload: Dict[str, Dict[str, object]] = {}
    for item in _build_mode_payload():
        payload[item["key"]] = {
            "label": item["label"],
            "description": item["description"],
            "category": item["category"],
            "badge": item["badge"],
            "tags": item["tags"],
        }
    return jsonify(payload)


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


@app.get("/api/settings")
@app.get("/api/env")
def api_settings_get():
    return jsonify({"settings": _settings_with_values()})


@app.post("/api/settings")
@app.post("/api/env")
def api_settings_post():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload"}), 400
    allowed = {item["key"] for item in settings_store.get_schema()}
    updates: Dict[str, object] = {}
    for key, value in data.items():
        if key in allowed:
            updates[key] = value
    if not updates:
        return jsonify({"ok": False, "error": "No valid keys"}), 400
    try:
        settings_store.update_settings(updates)
        config.DEFAULT_CONFIG = config.make_config()
    except Exception:
        return jsonify({"ok": False, "error": "Failed to save"}), 500
    reloaded = False
    try:
        reloaded = _restart_with_current_selection()
    except Exception:
        reloaded = False
    return jsonify({"ok": True, "reloaded": bool(reloaded)})


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
    cfg = config.DEFAULT_CONFIG
    target_title = getattr(cfg, "window_title_substr", "")
    launch_wait_s = float(getattr(cfg, "game_launch_wait_s", 0.0) or 0.0)
    initial_hwnd: Optional[int] = None

    def _find_hwnd() -> Optional[int]:
        try:
            return find_window_by_title_substr(target_title)
        except Exception:
            return None

    current_hwnd = _find_hwnd()
    launched_game = False
    if not current_hwnd:
        shortcut = getattr(cfg, "game_shortcut_path", None)
        if shortcut:
            shortcut_path = str(shortcut)
            shortcut_exists = False
            try:
                shortcut_exists = _Path(shortcut_path).exists()
            except Exception:
                pass
            if not shortcut_exists:
                return jsonify({"error": f"Game shortcut not found at {shortcut_path}"}), 400
            try:
                try:
                    logs.add(f"[GameLaunch] Opening shortcut {shortcut_path}", level='info')
                except Exception:
                    pass
                os.startfile(shortcut_path)  # type: ignore[attr-defined]
                launched_game = True
            except Exception as exc:
                try:
                    logs.add(f"[GameLaunch] Failed to open shortcut: {exc}", level='err')
                except Exception:
                    pass
                return jsonify({"error": "Failed to launch game from shortcut"}), 500
        else:
            return jsonify({"error": "Game window not found and GAME_SHORTCUT_PATH is not set"}), 400
    if launched_game:
        if launch_wait_s > 0:
            try:
                logs.add(f"[GameLaunch] Waiting {launch_wait_s:.0f}s for game to load", level='info')
            except Exception:
                pass
            end_time = _time.time() + launch_wait_s
            while True:
                remaining = end_time - _time.time()
                if remaining <= 0:
                    break
                _time.sleep(min(1.0, remaining))
        current_hwnd = _find_hwnd()
        if not current_hwnd:
            try:
                logs.add("[GameLaunch] Game window not detected after launch wait", level='err')
            except Exception:
                pass
            return jsonify({"error": "Game window not detected after launch wait"}), 500
    initial_hwnd = current_hwnd

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
                out_dir = getattr(config.DEFAULT_CONFIG, 'start_shots_dir', _Path('start_captures'))
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
        if initial_hwnd:
            try:
                ctx.hwnd = initial_hwnd
            except Exception:
                pass
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
    if initial_hwnd:
        try:
            ctx.hwnd = initial_hwnd
        except Exception:
            pass
    try:
        _save_start_shot(ctx)
    except Exception:
        pass
    mach.start(ctx)
    _running = Running(kind="multi", modes=tuple(selection), machine=mach, ctx=ctx)
    return jsonify({"ok": True, "kind": "multi", "modes": selection})


@app.post("/api/close-game")
def api_close_game():
    """Stop the state machine and request the game window to close."""
    _stop_running()
    cfg = config.DEFAULT_CONFIG
    window_substr = str(getattr(cfg, "window_title_substr", "") or "").strip()
    if not window_substr:
        return jsonify({"ok": False, "error": "WINDOW_TITLE_SUBSTR is not configured"}), 400
    try:
        logs.add("[Web] Close game requested", level='info')
    except Exception:
        pass
    try:
        hwnd = find_window_by_title_substr(window_substr)
    except Exception:
        hwnd = None
    if not hwnd:
        try:
            logs.add("[Web] Close game skipped (window not found)", level='info')
        except Exception:
            pass
        return jsonify({"ok": True, "missing": True})
    try:
        closed, forced = close_window(hwnd, wait_s=5.0)
    except Exception:
        closed, forced = (False, False)
    if not closed:
        return jsonify({"ok": False, "error": "Failed to close game window"}), 500
    if forced:
        try:
            logs.add("[Web] Force-terminated Call of Dragons process", level='warn')
        except Exception:
            pass
    return jsonify({"ok": True, "forced": bool(forced)})



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
        shots_dir = config.DEFAULT_CONFIG.shots_dir
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



