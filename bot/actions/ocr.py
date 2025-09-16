from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
import difflib

import cv2
try:
    import easyocr  # type: ignore
    HAS_EASYOCR = True
except Exception:  # pragma: no cover
    easyocr = None  # type: ignore
    HAS_EASYOCR = False

from bot.core.state_machine import Action, Context
from bot.core.image import pct_region_to_pixels
from bot.core import logs


@dataclass
class ReadText(Action):
    name: str
    region_pct: tuple[float, float, float, float]
    expected: Optional[str] = None
    min_ratio: float = 0.85
    ocr_config: Optional[str] = None
    preprocess: Sequence[str] = ("gray", "thresh")
    langs: Sequence[str] = ("en",)

    def run(self, ctx: Context) -> Optional[bool]:
        if not HAS_EASYOCR or easyocr is None:
            logs.add(f"[OCR] easyocr not available for {self.name}", level="err")
            return False if self.expected else None
        if ctx.frame_bgr is None:
            logs.add(f"[OCR] frame missing for {self.name}", level="err")
            return False if self.expected else None
        left, top, width, height = ctx.window_rect
        if width <= 0 or height <= 0:
            logs.add(f"[OCR] invalid window rect for {self.name}", level="err")
            return False if self.expected else None
        rx, ry, rw, rh = pct_region_to_pixels((width, height), self.region_pct)
        if rw <= 0 or rh <= 0:
            logs.add(f"[OCR] empty region for {self.name}", level="err")
            return False if self.expected else None
        frame = ctx.frame_bgr
        if ry + rh > frame.shape[0] or rx + rw > frame.shape[1]:
            logs.add(f"[OCR] region outside frame for {self.name}", level="err")
            return False if self.expected else None
        roi = frame[ry:ry + rh, rx:rx + rw]
        img = roi.copy()
        for step in self.preprocess:
            if step == "gray":
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            elif step == "thresh":
                img = cv2.fastNlMeansDenoising(img) if img.ndim == 2 else img
                _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            elif step == "invert":
                img = cv2.bitwise_not(img)
        if img.ndim == 2:
            proc = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        else:
            proc = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        reader = getattr(self, "_reader", None)
        if reader is None:
            try:
                langs = list(self.langs) if hasattr(self, "langs") else ["en"]
                reader = easyocr.Reader(langs, gpu=False)
                self._reader = reader
            except Exception as exc:
                logs.add(f"[OCR] easyocr init failed for {self.name}: {exc}", level="err")
                return False if self.expected else None
        try:
            results = reader.readtext(proc)
        except Exception as exc:
            logs.add(f"[OCR] easyocr error in {self.name}: {exc}", level="err")
            return False if self.expected else None
        text = " ".join([res[1] for res in results]).strip()
        try:
            setattr(ctx, "last_ocr_text", text)
        except Exception:
            pass
        logs.add(f"[OCR] {self.name} -> '{text}'", level="info")
        if self.expected is None:
            return None
        expected_norm = self.expected.strip().lower()
        actual_norm = text.lower()
        ratio = difflib.SequenceMatcher(None, actual_norm, expected_norm).ratio()
        ok = ratio >= self.min_ratio
        logs.add(f"[OCR] compare '{actual_norm}' vs '{expected_norm}' ratio={ratio:.2f}", level="ok" if ok else "err")
        return ok
