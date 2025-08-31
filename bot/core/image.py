from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np


def to_gray(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


@lru_cache(maxsize=64)
def load_template_bgr(path: str) -> np.ndarray:
    """Load a template image as BGR, trimming transparent borders if present.

    If the image has an alpha channel (e.g., PNG with transparency), we detect
    non-transparent pixels (alpha > 10) and crop to the minimal bounding box.
    This improves match quality for icons with transparent backgrounds
    without changing matching logic elsewhere.
    """
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Template image not found: {path}")

    # If 4-channel (BGRA), trim transparent margins and return BGR
    if img.ndim == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
        # Threshold alpha to build a binary mask of visible pixels
        # Using a small threshold to ignore semi-transparent edge noise
        _, mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
        pts = cv2.findNonZero(mask)
        if pts is not None:
            x, y, w, h = cv2.boundingRect(pts)
            # Guard against degenerate boxes
            if w > 0 and h > 0:
                return bgr[y : y + h, x : x + w]
        # Fallback: no visible pixels found; return BGR without alpha
        return bgr

    # Already BGR or grayscale; ensure BGR
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


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
) -> tuple[bool, tuple[int, int], float]:
    rx, ry, rw, rh = roi_xywh
    if rw <= 0 or rh <= 0:
        return False, (0, 0), 0.0

    roi = frame_bgr[ry : ry + rh, rx : rx + rw]
    if roi.size == 0:
        return False, (0, 0), 0.0

    roi_g = to_gray(roi)
    tpl_g = to_gray(template_bgr)

    if roi_g.shape[0] < tpl_g.shape[0] or roi_g.shape[1] < tpl_g.shape[1]:
        return False, (0, 0), 0.0

    res = cv2.matchTemplate(roi_g, tpl_g, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        # Location within ROI (top-left)
        return True, (rx + max_loc[0], ry + max_loc[1]), float(max_val)
    return False, (0, 0), float(max_val)
