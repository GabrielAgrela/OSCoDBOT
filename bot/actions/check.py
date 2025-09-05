from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import cv2

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


@dataclass
class CheckTemplatesCountAtLeast(Action):
    name: str
    templates: Sequence[str]
    region_pct: tuple[float, float, float, float]
    threshold: float
    min_total: int
    verify_threshold: float = 0.85

    _tpl_cache: dict[str, tuple[np.ndarray, Optional[np.ndarray]] ] = None  # type: ignore

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

    def _match_all(self, frame_bgr: np.ndarray, roi_xywh: tuple[int, int, int, int], tpl: np.ndarray, mask: Optional[np.ndarray]) -> list[tuple[int, int, float]]:
        rx, ry, rw, rh = roi_xywh
        if rw <= 0 or rh <= 0:
            return []
        roi = frame_bgr[ry : ry + rh, rx : rx + rw]
        th, tw = tpl.shape[:2]
        if roi.shape[0] < th or roi.shape[1] < tw:
            return []
        # Compute response map similar to match_template
        try:
            if mask is not None:
                roi_g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                tpl_g = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
                res = cv2.matchTemplate(roi_g, tpl_g, cv2.TM_CCORR_NORMED, mask=mask)
            else:
                roi_g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                tpl_g = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
                res = cv2.matchTemplate(roi_g, tpl_g, cv2.TM_CCOEFF_NORMED)
        except Exception:
            try:
                res = cv2.matchTemplate(roi, tpl, cv2.TM_CCORR_NORMED, mask=mask if mask is not None else None)
            except Exception:
                return []
        matches: list[tuple[int, int, float]] = []
        # Non-maximum suppression by zeroing a neighborhood around each found peak
        h_res, w_res = res.shape[:2]
        # Suppress window size roughly equal to template size
        nms_w = max(1, int(tw * 0.8))
        nms_h = max(1, int(th * 0.8))
        # Iterate until no strong peaks remain or a safety cap reached
        safety = 50
        while safety > 0:
            safety -= 1
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if float(max_val) < float(self.threshold):
                break
            top_left = (rx + max_loc[0], ry + max_loc[1])
            matches.append((top_left[0], top_left[1], float(max_val)))
            # Zero out neighborhood around this peak in response map
            x0 = max(0, int(max_loc[0] - nms_w // 2))
            y0 = max(0, int(max_loc[1] - nms_h // 2))
            x1 = min(w_res, int(max_loc[0] + nms_w // 2))
            y1 = min(h_res, int(max_loc[1] + nms_h // 2))
            res[y0:y1, x0:x1] = 0.0
        return matches

    def run(self, ctx: Context) -> Optional[bool]:
        if ctx.frame_bgr is None:
            return False
        left, top, width, height = ctx.window_rect
        rx, ry, rw, rh = pct_region_to_pixels((width, height), self.region_pct)

        total = 0
        debug_msgs = []
        # Collect per-template debug data
        per_tpl_verified: dict[str, list[tuple[int, int, float, float]]] = {}
        for fname in self.templates:
            tpl_pair = self._load(ctx.templates_dir, fname)
            if tpl_pair is None:
                continue
            tpl, mask = tpl_pair
            # Find multiple matches per template within ROI
            peaks = self._match_all(ctx.frame_bgr, (rx, ry, rw, rh), tpl, mask)
            # Verify each peak with masked ZNCC as in other actions
            verified = 0
            verified_list: list[tuple[int, int, float, float]] = []
            for (mx, my, score) in peaks:
                vscore = 0.0
                try:
                    th, tw = tpl.shape[:2]
                    patch = ctx.frame_bgr[my : my + th, mx : mx + tw]
                    if patch.shape[:2] == (th, tw):
                        vscore = masked_zncc(patch, tpl, mask)
                except Exception:
                    vscore = 0.0
                VERIFY_MIN = max(0.90, min(0.98, self.threshold)) if self.threshold >= 0.9 else 0.90
                if vscore >= VERIFY_MIN:
                    verified += 1
                    verified_list.append((mx, my, float(score), float(vscore)))
            total += verified
            per_tpl_verified[fname] = verified_list
            debug_msgs.append(f"{fname} count={verified}")
        try:
            logs.add(f"[CheckTemplatesCount] total={total} need>={self.min_total} details={' '.join(debug_msgs)}", level="info")
        except Exception:
            pass
        # Save annotated matches when debug is enabled
        try:
            if getattr(ctx, "save_shots", False):
                from pathlib import Path as _Path
                # For each template, save up to 3 verified matches; if none verified, save a negative best match
                for fname in self.templates:
                    tpl_pair = self._load(ctx.templates_dir, fname)
                    if tpl_pair is None:
                        continue
                    tpl, mask = tpl_pair
                    verified_list = per_tpl_verified.get(fname, [])
                    if verified_list:
                        for i, (mx, my, score, vscore) in enumerate(verified_list[:3]):
                            tag = f"{self.name}_{_Path(fname).stem}_{i+1}"
                            save_debug_match(
                                ctx.frame_bgr,
                                (rx, ry, rw, rh),
                                tpl,
                                (mx, my),
                                score,
                                getattr(ctx, "shots_dir", _Path("debug_captures")),
                                tag,
                                vscore=vscore,
                                threshold=self.threshold,
                                found=True,
                            )
                    else:
                        # Negative example: record the best location even if below threshold
                        from bot.core.image import match_template as _single_match
                        found, top_left_xy, score = _single_match(ctx.frame_bgr, tpl, self.threshold, (rx, ry, rw, rh), mask=mask)
                        tag = f"{self.name}_{_Path(fname).stem}_none"
                        save_debug_match(
                            ctx.frame_bgr,
                            (rx, ry, rw, rh),
                            tpl,
                            top_left_xy,
                            score,
                            getattr(ctx, "shots_dir", _Path("debug_captures")),
                            tag,
                            vscore=None,
                            threshold=self.threshold,
                            found=False,
                        )
        except Exception:
            pass
        return bool(total >= int(self.min_total))
