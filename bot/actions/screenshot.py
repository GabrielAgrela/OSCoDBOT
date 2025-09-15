from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from datetime import datetime

import mss
import numpy as np

from bot.core.state_machine import Action, Context
from bot.core.window import (
    find_window_by_title_substr,
    get_client_rect_screen,
    set_window_client_size,
    move_window_xy,
    get_monitor_rect_for_window,
)
from bot.config import DEFAULT_CONFIG
try:
    import win32gui  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    win32gui = None  # type: ignore


@dataclass
class Screenshot(Action):
    name: str
    # Do not cache mss instance across threads; mss uses thread-local state internally.
    # Caching and reusing across start/stop (new threads) can cause attribute errors like
    # "'_thread._local' object has no attribute 'srcdc'". Use a fresh instance per call.

    def run(self, ctx: Context) -> None:
        hwnd = ctx.hwnd
        if hwnd is None:
            hwnd = find_window_by_title_substr(ctx.window_title_substr)
            if hwnd is None:
                return  # window not found yet
            ctx.hwnd = hwnd

        # Try to enforce desired client size once per grab if configured
        try:
            target_w = int(getattr(DEFAULT_CONFIG, 'force_window_width', 0))
            target_h = int(getattr(DEFAULT_CONFIG, 'force_window_height', 0))
        except Exception:
            target_w = target_h = 0
        try:
            do_resize = bool(getattr(DEFAULT_CONFIG, 'force_window_resize', True))
        except Exception:
            do_resize = True
        if do_resize and target_w > 0 and target_h > 0:
            try:
                rect_now = get_client_rect_screen(hwnd)
                # Determine desired adjustments
                needs_resize = (rect_now.width != target_w or rect_now.height != target_h)
                try:
                    is_zoomed = bool(win32gui and win32gui.IsZoomed(hwnd))  # maximized
                except Exception:
                    is_zoomed = False
                # If size mismatch OR window is maximized, enforce target client size (also restores)
                if needs_resize or is_zoomed:
                    set_window_client_size(hwnd, target_w, target_h)
                    rect_now = get_client_rect_screen(hwnd)
                # Independently ensure position is top-left of its monitor, or if it was maximized
                try:
                    mon = get_monitor_rect_for_window(hwnd, work_area=False)
                    needs_move = (rect_now.left != mon.left or rect_now.top != mon.top)
                except Exception:
                    mon = None
                    needs_move = False
                if (needs_move or is_zoomed) and mon is not None:
                    try:
                        move_window_xy(hwnd, mon.left, mon.top)
                        rect_now = get_client_rect_screen(hwnd)
                    except Exception:
                        pass
                rect = rect_now
            except Exception:
                rect = get_client_rect_screen(hwnd)
        else:
            rect = get_client_rect_screen(hwnd)
            # If resizing is disabled, log current resolution once for visibility
            if not do_resize:
                try:
                    from bot.core import logs as _logs
                    if not getattr(ctx, "_res_logged", False):
                        _logs.add(f"[Resolution] Client area {rect.width}x{rect.height}", level="info")
                        setattr(ctx, "_res_logged", True)
                except Exception:
                    pass
        if rect.width <= 0 or rect.height <= 0:
            return

        monitor = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        }
        # Reuse a per-thread mss instance stored in context to avoid GDI leaks
        # Periodically refresh the handle to prevent long‑running resource buildup on Windows.
        sct = getattr(ctx, "_mss", None)
        grab_count = int(getattr(ctx, "_mss_grab_count", 0))
        # Refresh every N grabs as a stability guard (tunable; conservative default)
        REFRESH_EVERY = 1200  # ~ every 20–30 minutes depending on loop cadence
        need_refresh = (sct is not None) and (grab_count >= REFRESH_EVERY)
        if sct is None or need_refresh:
            # Dispose old handle if refreshing
            if need_refresh:
                try:
                    sct.close()
                except Exception:
                    pass
                try:
                    setattr(ctx, "_mss", None)
                except Exception:
                    pass
                try:
                    from bot.core import logs as _logs
                    _logs.add("[Screenshot] Refreshed capture handle after periodic threshold", level="info")
                except Exception:
                    pass
                grab_count = 0
            try:
                sct = mss.mss()
                setattr(ctx, "_mss", sct)
            except Exception:
                return
        try:
            raw = np.array(sct.grab(monitor))  # BGRA
            # Bump grab counter
            grab_count += 1
            try:
                setattr(ctx, "_mss_grab_count", grab_count)
            except Exception:
                pass
        except Exception as exc:
            try:
                from bot.core import logs
                logs.add(f"[ScreenshotError] grab failed: {exc}", level="err")
            except Exception:
                pass
            # On grab failure, try to recreate the mss handle once
            try:
                # Dispose existing first (best effort)
                try:
                    sct.close()
                except Exception:
                    pass
                try:
                    setattr(ctx, "_mss", None)
                except Exception:
                    pass
                sct = mss.mss()
                setattr(ctx, "_mss", sct)
                raw = np.array(sct.grab(monitor))
                grab_count = 1
                try:
                    setattr(ctx, "_mss_grab_count", grab_count)
                except Exception:
                    pass
            except Exception as exc2:
                try:
                    from bot.core import logs
                    logs.add(f"[ScreenshotError] recreate failed: {exc2}", level="err")
                except Exception:
                    pass
                return
        frame_bgr = raw[:, :, :3]
        ctx.frame_bgr = frame_bgr
        ctx.window_rect = rect.to_tuple()
        # Intentionally do not save raw screenshots here to avoid disk spam.
        # Use debug saves in matcher actions when an object is actually found.
