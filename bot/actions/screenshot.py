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
    _sct: Optional[mss.mss] = None

    def _ensure_sct(self) -> mss.mss:
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

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

        sct = self._ensure_sct()
        monitor = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        }
        raw = np.array(sct.grab(monitor))  # BGRA
        frame_bgr = raw[:, :, :3]
        ctx.frame_bgr = frame_bgr
        ctx.window_rect = rect.to_tuple()
        try:
            print(f"[Screenshot] hwnd={hwnd} rect={ctx.window_rect} frame={frame_bgr.shape[1]}x{frame_bgr.shape[0]}")
        except Exception:
            pass
