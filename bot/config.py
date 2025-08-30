from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    # Window identification
    window_title_substr: str = "Call of Dragons"

    # Capture and matching
    screenshot_period_s: float = 0.7
    match_threshold: float = 0.85

    # Default side region where the first image is searched (x, y, w, h in 0..1)
    side_region_pct: tuple[float, float, float, float] = (0.6, 0.0, 0.4, 1.0)  # right 40%

    # Assets directory
    assets_dir: Path = Path("assets")
    templates_dir: Path = Path("assets/templates")

    # Debugging
    save_shots: bool = False
    shots_dir: Path = Path("debug_captures")


DEFAULT_CONFIG = AppConfig()
