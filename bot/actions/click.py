from __future__ import annotations

import time
from dataclasses import dataclass

from bot.core.state_machine import Action, Context
from bot.core.window import bring_to_front, click_screen_xy


@dataclass
class ClickPercent(Action):
    name: str
    x_pct: float
    y_pct: float

    def run(self, ctx: Context) -> None:
        left, top, width, height = ctx.window_rect
        if width <= 0 or height <= 0:
            return
        x = left + int(max(0.0, min(1.0, self.x_pct)) * width)
        y = top + int(max(0.0, min(1.0, self.y_pct)) * height)
        if ctx.hwnd is not None:
            bring_to_front(ctx.hwnd)
            time.sleep(0.05)
        click_screen_xy(x, y)


@dataclass
class ClickBelowLastMatchPercent(Action):
    name: str
    down_pct: float  # fraction of window height (e.g., 0.05 for 5%)

    def run(self, ctx: Context) -> None:
        # Require a previous match to reference
        lm = getattr(ctx, "last_match", None)
        if lm is None:
            return None
        left, top, width, height = ctx.window_rect
        if width <= 0 or height <= 0:
            return None
        # Base on last match screen center; move downward by down_pct of window height
        sx, sy = lm.center_screen_xy
        dy = int(max(-1.0, min(1.0, float(self.down_pct))) * height)
        tx = max(left, min(left + width - 1, sx))
        ty = max(top, min(top + height - 1, sy + dy))
        if ctx.hwnd is not None:
            bring_to_front(ctx.hwnd)
            time.sleep(0.05)
        click_screen_xy(tx, ty)
