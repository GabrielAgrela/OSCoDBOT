from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

from bot.core.image import load_template_bgr, match_template, pct_region_to_pixels
from bot.core.state_machine import Action, Context, MatchResult
from bot.core.window import bring_to_front, click_screen_xy
from bot.core import logs

# ANSI colors for Windows 10+ terminals; ignored if unsupported
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


@dataclass
class FindAndClick(Action):
    name: str
    templates: Sequence[str]
    region_pct: tuple[float, float, float, float]
    threshold: float

    _tpl_cache: dict[str, np.ndarray] = None  # type: ignore

    def _ensure_cache(self) -> None:
        if self._tpl_cache is None:
            self._tpl_cache = {}

    def _load(self, templates_dir: Path, fname: str) -> Optional[np.ndarray]:
        self._ensure_cache()
        if fname in self._tpl_cache:
            return self._tpl_cache[fname]
        path = (templates_dir / fname).as_posix()
        try:
            img = load_template_bgr(path)
        except FileNotFoundError:
            return None
        self._tpl_cache[fname] = img
        return img

    def run(self, ctx: Context) -> Optional[bool]:
        if ctx.frame_bgr is None:
            return False
        left, top, width, height = ctx.window_rect
        roi_xywh = pct_region_to_pixels((width, height), self.region_pct)

        for fname in self.templates:
            tpl = self._load(ctx.templates_dir, fname)
            if tpl is None:
                continue
            found, top_left_xy, score = match_template(ctx.frame_bgr, tpl, self.threshold, roi_xywh)
            msg = f"[FindAndClick] tpl={fname} score={score:.3f} found={found}"
            # Console color (best-effort) and UI log
            try:
                color = GREEN if found else RED
                print(f"{color}{msg}{RESET}")
            except Exception:
                pass
            try:
                logs.add(msg, level="ok" if found else "err")
            except Exception:
                pass
            if not found:
                continue

            tpl_h, tpl_w = tpl.shape[:2]
            cx = top_left_xy[0] + tpl_w // 2
            cy = top_left_xy[1] + tpl_h // 2
            screen_x = left + cx
            screen_y = top + cy

            ctx.last_match = MatchResult(
                score=score,
                center_win_xy=(cx, cy),
                center_screen_xy=(screen_x, screen_y),
                template_wh=(tpl_w, tpl_h),
                roi_win_offset_xy=(roi_xywh[0], roi_xywh[1]),
            )
            if ctx.hwnd is not None:
                bring_to_front(ctx.hwnd)
                time.sleep(0.05)
            click_screen_xy(screen_x, screen_y)
            return True
        return False
