from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
        # Use a short-lived mss instance bound to current thread
        with mss.mss() as sct:
            raw = np.array(sct.grab(monitor))  # BGRA
        frame_bgr = raw[:, :, :3]
        ctx.frame_bgr = frame_bgr
        ctx.window_rect = rect.to_tuple()
