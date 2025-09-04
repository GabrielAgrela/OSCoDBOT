from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from bot.core.state_machine import Action, Context
from bot.core.image import (
    load_template_bgr_mask,
    match_template,
    pct_region_to_pixels,
    save_debug_match,
    masked_zncc,
)
from bot.core import logs


@dataclass
class CheckTemplate(Action):
    name: str
    templates: Sequence[str]
    region_pct: tuple[float, float, float, float]
    threshold: float
    verify_threshold: float = 0.85

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
            roi = (rx, ry, rw, rh)
            found, top_left_xy, score = match_template(ctx.frame_bgr, tpl, self.threshold, roi, mask=mask)
            vscore = 0.0
            if found:
                try:
                    mx, my = top_left_xy
                    th, tw = tpl.shape[:2]
                    patch = ctx.frame_bgr[my : my + th, mx : mx + tw]
                    if patch.shape[:2] == (th, tw):
                        vscore = masked_zncc(patch, tpl, mask)
                except Exception:
                    vscore = 0.0
                VERIFY_MIN = max(0.90, min(0.98, self.threshold)) if self.threshold >= 0.9 else 0.90
                if vscore < VERIFY_MIN:
                    found = False
            try:
                extra = f" v={vscore:.3f}" if vscore > 0 else ""
                logs.add(f"[CheckTemplate] tpl={fname} score={score:.3f}{extra} found={found}", level="ok" if found else "info")
            except Exception:
                pass
            if found:
                if getattr(ctx, "save_shots", False):
                    try:
                        from pathlib import Path as _Path
                        out_dir = getattr(ctx, "shots_dir", _Path("debug_captures"))
                        tag = f"{self.name}_{_Path(fname).stem}"
                        save_debug_match(
                            ctx.frame_bgr,
                            roi,
                            tpl,
                            top_left_xy,
                            score,
                            out_dir,
                            tag,
                            vscore=(vscore if vscore > 0 else None),
                            threshold=self.threshold,
                            found=True,
                        )
                    except Exception:
                        pass
                return True
            else:
                if getattr(ctx, "save_shots", False):
                    try:
                        from pathlib import Path as _Path
                        out_dir = getattr(ctx, "shots_dir", _Path("debug_captures"))
                        tag = f"{self.name}_{_Path(fname).stem}"
                        save_debug_match(
                            ctx.frame_bgr,
                            roi,
                            tpl,
                            top_left_xy,
                            score,
                            out_dir,
                            tag,
                            vscore=(vscore if vscore > 0 else None),
                            threshold=self.threshold,
                            found=False,
                        )
                    except Exception:
                        pass
        return False
