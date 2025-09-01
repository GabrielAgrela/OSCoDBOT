from __future__ import annotations

from functools import lru_cache
from typing import Tuple, Optional
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def to_gray(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


@lru_cache(maxsize=64)
def load_template_bgr_mask(path: str) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Load a template as BGR plus an optional mask derived from alpha.

    - If the image has an alpha channel, trim fully-transparent borders and
      return both the cropped BGR image and a binary mask (uint8) of the
      visible area (alpha > 10).
    - If no alpha, return BGR and mask=None.
    """
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Template image not found: {path}")
    # BGRA
    if img.ndim == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
        # Threshold alpha to build a binary mask of visible pixels
        _, mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
        pts = cv2.findNonZero(mask)
        if pts is not None:
            x, y, w, h = cv2.boundingRect(pts)
            if w > 0 and h > 0:
                return bgr[y : y + h, x : x + w], mask[y : y + h, x : x + w]
        # Fallback: no visible pixels; return BGR without mask
        return bgr, None
    # Grayscale -> BGR
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), None
    # Already BGR
    return img, None


@lru_cache(maxsize=64)
def load_template_bgr(path: str) -> np.ndarray:
    """Backward-compatible helper returning only BGR template."""
    bgr, _ = load_template_bgr_mask(path)
    return bgr


def pct_region_to_pixels(win_wh: tuple[int, int], region_pct: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    w, h = win_wh
    x_pct, y_pct, w_pct, h_pct = region_pct
    x = int(max(0.0, min(1.0, x_pct)) * w)
    y = int(max(0.0, min(1.0, y_pct)) * h)
    rw = int(max(0.0, min(1.0 - x_pct, w_pct)) * w)
    rh = int(max(0.0, min(1.0 - y_pct, h_pct)) * h)
    return x, y, max(0, rw), max(0, rh)


def match_template(
    frame_bgr: np.ndarray,
    template_bgr: np.ndarray,
    threshold: float,
    roi_xywh: tuple[int, int, int, int],
    mask: Optional[np.ndarray] = None,
) -> tuple[bool, tuple[int, int], float]:
    rx, ry, rw, rh = roi_xywh
    if rw <= 0 or rh <= 0:
        return False, (0, 0), 0.0

    roi = frame_bgr[ry : ry + rh, rx : rx + rw]
    if roi.size == 0:
        return False, (0, 0), 0.0

    # Ensure template fits within ROI
    th, tw = template_bgr.shape[:2]
    if roi.shape[0] < th or roi.shape[1] < tw:
        return False, (0, 0), 0.0

    # If we have a mask (from alpha), use a method that supports masking
    if mask is not None:
        try:
            res = cv2.matchTemplate(roi, template_bgr, cv2.TM_CCORR_NORMED, mask=mask)
        except Exception:
            # Fallback to grayscale without mask if OpenCV lacks mask support
            roi_g = to_gray(roi)
            tpl_g = to_gray(template_bgr)
            res = cv2.matchTemplate(roi_g, tpl_g, cv2.TM_CCOEFF_NORMED)
    else:
        roi_g = to_gray(roi)
        tpl_g = to_gray(template_bgr)
        res = cv2.matchTemplate(roi_g, tpl_g, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    # Best match position in full-frame coords
    best_top_left = (rx + max_loc[0], ry + max_loc[1])
    if max_val >= threshold:
        return True, best_top_left, float(max_val)
    return False, best_top_left, float(max_val)


def save_debug_match(
    frame_bgr: np.ndarray,
    roi_xywh: tuple[int, int, int, int],
    template_bgr: np.ndarray,
    top_left_xy: tuple[int, int],
    score: float,
    out_dir: Path,
    tag: str,
) -> None:
    """Save annotated frame and template for a single match attempt.

    Files written (best effort):
      - <ts>_match_<tag>_<score>.png  (frame with ROI rectangle and match rectangle)
      - <ts>_tpl_<tag>.png            (template image)
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    # Annotate frame
    try:
        rx, ry, rw, rh = roi_xywh
        x0, y0 = max(0, rx), max(0, ry)
        x1, y1 = max(0, min(frame_bgr.shape[1] - 1, rx + rw)), max(0, min(frame_bgr.shape[0] - 1, ry + rh))
        vis = frame_bgr.copy()
        # Draw ROI rectangle in yellow
        cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 255), 2)
        # Draw best-match rectangle in green
        th, tw = template_bgr.shape[:2]
        mx, my = top_left_xy
        cv2.rectangle(vis, (mx, my), (mx + tw, my + th), (0, 255, 0), 2)
        # Put score text
        cv2.putText(vis, f"{score:.3f}", (mx, max(0, my - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        out_path = out_dir / f"{ts}_match_{tag}_{score:.3f}.png"
        try:
            cv2.imwrite(str(out_path), vis)
        except Exception:
            pass
    except Exception:
        pass
    # Save template
    try:
        out_tpl = out_dir / f"{ts}_tpl_{tag}.png"
        cv2.imwrite(str(out_tpl), template_bgr)
    except Exception:
        pass
    # Prune directory if over size budget (best-effort)
    try:
        # Read limit from config if available
        try:
            from bot.config import DEFAULT_CONFIG as _CFG  # type: ignore
            max_bytes = int(getattr(_CFG, "shots_max_bytes", 1_073_741_824))
        except Exception:
            max_bytes = 1_073_741_824
        _prune_dir_size(out_dir, max_bytes)
    except Exception:
        pass


def _prune_dir_size(folder: Path, max_bytes: int) -> None:
    try:
        if not folder.exists():
            return
        # Collect files (ignore subdirs)
        entries = []
        total = 0
        for p in folder.iterdir():
            try:
                if not p.is_file():
                    continue
                sz = p.stat().st_size
                total += sz
                entries.append((p, p.stat().st_mtime, sz))
            except Exception:
                continue
        if total <= max_bytes:
            return
        # Oldest first
        entries.sort(key=lambda t: t[1])
        for p, _mt, sz in entries:
            try:
                p.unlink(missing_ok=True)  # type: ignore[call-arg]
            except TypeError:
                # Python <3.8
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            except Exception:
                pass
            total -= sz
            if total <= max_bytes:
                break
    except Exception:
        pass
