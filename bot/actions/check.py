from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from bot.core.state_machine import Action, Context
from bot.core.image import load_template_bgr_mask, match_template, pct_region_to_pixels
from bot.core import logs


@dataclass
class CheckTemplate(Action):
    name: str
    templates: Sequence[str]
    region_pct: tuple[float, float, float, float]
    threshold: float

    _tpl_cache: dict[str, tuple[np.ndarray, Optional[np.ndarray]]] = None  # type: ignore

    def _ensure_cache(self) -> None:
        if self._tpl_cache is None:
            self._tpl_cache = {}

    def _load(self, templates_dir, fname: str) -> Optional[tuple[np.ndarray, Optional[np.ndarray]]]:
        self._ensure_cache()
        if fname in self._tpl_cache:
            return self._tpl_cache[fname]
        path = (templates_dir / fname).as_posix()
        try:
            img, mask = load_template_bgr_mask(path)
        except FileNotFoundError:
            return None
        self._tpl_cache[fname] = (img, mask)
        return img, mask

    def run(self, ctx: Context) -> Optional[bool]:
        if ctx.frame_bgr is None:
            return False
        left, top, width, height = ctx.window_rect
        rx, ry, rw, rh = pct_region_to_pixels((width, height), self.region_pct)

        for fname in self.templates:
            tpl_pair = self._load(ctx.templates_dir, fname)
            if tpl_pair is None:
                continue
            tpl, mask = tpl_pair
            found, top_left_xy, score = match_template(ctx.frame_bgr, tpl, self.threshold, (rx, ry, rw, rh), mask=mask)
            try:
                logs.add(f"[CheckTemplate] tpl={fname} score={score:.3f} found={found}", level="ok" if found else "info")
            except Exception:
                pass
            if found:
                return True
        return False
