from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from datetime import datetime

import mss
import numpy as np

from bot.core.state_machine import Action, Context
from bot.core.window import find_window_by_title_substr, get_client_rect_screen


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

        rect = get_client_rect_screen(hwnd)
        if rect.width <= 0 or rect.height <= 0:
            return

        monitor = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        }
        # Reuse a per-thread mss instance stored in context to avoid GDI leaks
        sct = getattr(ctx, "_mss", None)
        if sct is None:
            try:
                sct = mss.mss()
                setattr(ctx, "_mss", sct)
            except Exception:
                return
        try:
            raw = np.array(sct.grab(monitor))  # BGRA
        except Exception:
            # On grab failure, try to recreate the mss handle once
            try:
                sct = mss.mss()
                setattr(ctx, "_mss", sct)
                raw = np.array(sct.grab(monitor))
            except Exception:
                return
        frame_bgr = raw[:, :, :3]
        ctx.frame_bgr = frame_bgr
        ctx.window_rect = rect.to_tuple()
        # Save debug shot if enabled in context
        if getattr(ctx, "save_shots", False):
            try:
                out_dir = getattr(ctx, "shots_dir", Path("debug_captures"))
                out_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                out_path = out_dir / f"{ts}.png"
                try:
                    import cv2  # type: ignore
                    cv2.imwrite(str(out_path), frame_bgr)
                except Exception:
                    try:
                        from PIL import Image  # type: ignore
                        Image.fromarray(frame_bgr[:, :, ::-1]).save(str(out_path))
                    except Exception:
                        pass
            except Exception:
                pass
