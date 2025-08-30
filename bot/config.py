from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    # Window identification
    window_title_substr: str = "Call of Dragons"

    # Capture and matching
    screenshot_period_s: float = 0.7
    match_threshold: float = 0.9

    # Default side region where the first image is searched (x, y, w, h in 0..1)
    side_region_pct: tuple[float, float, float, float] = (0.6, 0.0, 0.4, 1.0)  # right 40%

    # Assets directory
    assets_dir: Path = Path("assets")
    templates_dir: Path = Path("assets/templates")

    # Debugging
    save_shots: bool = False
    shots_dir: Path = Path("debug_captures")

    # UI placement (percent margins relative to game client size)
    ui_margin_left_pct: float = 0.004  # ~0.4% of width
    ui_margin_top_pct: float = 0.56    # ~56% of height


def _load_env_file() -> None:
    """Lightweight .env loader without external dependency.

    Parses KEY=VALUE lines, ignoring comments and blanks.
    Does not overwrite existing environment variables.
    """
    path = Path(".env")
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and (key not in os.environ):
                os.environ[key] = val
    except Exception:
        # Ignore parsing errors; environment vars can still be set externally
        pass


def _env_float(name: str, default: float) -> float:
    val: Optional[str] = os.getenv(name)
    if not val:
        return default
    try:
        s = val.strip()
        if s.endswith("%"):
            return float(s[:-1]) / 100.0
        return float(s)
    except Exception:
        return default


def make_config() -> AppConfig:
    # Load .env if present
    _load_env_file()
    # Only margins and title are pulled from env to keep behavior minimal
    window_title = os.getenv("WINDOW_TITLE_SUBSTR", "Call of Dragons")
    left_pct = _env_float("UI_MARGIN_LEFT_PCT", 0.004)
    top_pct = _env_float("UI_MARGIN_TOP_PCT", 0.56)
    return AppConfig(
        window_title_substr=window_title,
        ui_margin_left_pct=left_pct,
        ui_margin_top_pct=top_pct,
    )


DEFAULT_CONFIG = make_config()
