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
    units_overview_region_pct: tuple[float, float, float, float] = (0.9, 0.15, 0.1, 0.6)  # right 20%

    # Assets directory
    assets_dir: Path = Path("assets")
    templates_dir: Path = Path("assets/templates")

    # Debugging
    save_shots: bool = False
    shots_dir: Path = Path("debug_captures")

    # Click behavior
    # When True, restore mouse cursor to its previous position after a click
    click_snap_back: bool = True

    # UI placement (percent margins relative to game client size)
    ui_margin_left_pct: float = 0.004  # ~0.4% of width
    ui_margin_top_pct: float = 0.56    # ~56% of height

    # UI behavior
    use_webview: bool = True          # If false, open in browser instead of embedding
    ui_pin_to_game: bool = True       # Keep UI window pinned near the game window
    ui_topmost: bool = True           # Keep UI always on top
    ui_frameless: bool = True         # Try to remove title bar/borders

    # Logging
    log_to_file: bool = True
    log_file: Path = Path("bot.log")
    log_max_bytes: int = 1_048_576  # 1 MB
    log_backups: int = 5            # number of rotated files to keep


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


def _env_bool(name: str, default: bool) -> bool:
    val: Optional[str] = os.getenv(name)
    if val is None:
        return default
    s = val.strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return default


def make_config() -> AppConfig:
    # Load .env if present
    _load_env_file()
    # Pull configurable values from env
    window_title = os.getenv("WINDOW_TITLE_SUBSTR", "Call of Dragons")
    left_pct = _env_float("UI_MARGIN_LEFT_PCT", 0.004)
    top_pct = _env_float("UI_MARGIN_TOP_PCT", 0.56)
    match_threshold = _env_float("MATCH_THRESHOLD", 0.9)
    click_snap_back = _env_bool("CLICK_SNAP_BACK", True)
    save_shots = _env_bool("SAVE_SHOTS", False)
    shots_dir_env = os.getenv("SHOTS_DIR", "").strip()
    shots_dir = Path(shots_dir_env) if shots_dir_env else Path("debug_captures")
    use_webview = _env_bool("USE_WEBVIEW", True)
    ui_pin_to_game = _env_bool("UI_PIN_TO_GAME", True)
    ui_topmost = _env_bool("UI_TOPMOST", True)
    ui_frameless = _env_bool("UI_FRAMELESS", True)
    log_to_file = _env_bool("LOG_TO_FILE", True)
    log_file_env = os.getenv("LOG_FILE", "").strip()
    log_file = Path(log_file_env) if log_file_env else Path("bot.log")
    # Parse size/backups (fallback to defaults on invalid values)
    try:
        log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "1048576").strip())
    except Exception:
        log_max_bytes = 1_048_576
    try:
        log_backups = int(os.getenv("LOG_BACKUPS", "5").strip())
    except Exception:
        log_backups = 5
    return AppConfig(
        window_title_substr=window_title,
        match_threshold=match_threshold,
        ui_margin_left_pct=left_pct,
        ui_margin_top_pct=top_pct,
        click_snap_back=click_snap_back,
        save_shots=save_shots,
        shots_dir=shots_dir,
        use_webview=use_webview,
        ui_pin_to_game=ui_pin_to_game,
        ui_topmost=ui_topmost,
        ui_frameless=ui_frameless,
        log_to_file=log_to_file,
        log_file=log_file,
        log_max_bytes=log_max_bytes,
        log_backups=log_backups,
    )


DEFAULT_CONFIG = make_config()
