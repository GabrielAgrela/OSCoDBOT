from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sys

from . import settings as settings_store


@dataclass(frozen=True)
class AppConfig:
    # Window identification
    window_title_substr: str = "Call of Dragons"

    # Capture and matching
    screenshot_period_s: float = 0.7
    match_threshold: float = 0.85
    verify_threshold: float = 0.85

    # Default side region where the first image is searched (x, y, w, h in 0..1)
    units_overview_region_pct: tuple[float, float, float, float] = (0.9, 0.15, 0.1, 0.6)  # right 20%

    #magifier region
    magifier_region_pct: tuple[float, float, float, float] = (0.0, 0.65, 0.1, 0.35)

    #alliance health region
    alliance_help_region_pct: tuple[float, float, float, float] = (0.65, 0.7, 0.3, 0.3)

    #resource search selection region
    resource_search_selection_region_pct: tuple[float, float, float, float] = (0.1, 0.8, 0.8, 0.2)

    #resoure search button region
    resource_search_button_region_pct: tuple[float, float, float, float] = (0.1, 0.6, 0.85, 0.2)

    #gather button region
    gather_button_region_pct: tuple[float, float, float, float] = (0.55, 0.6, 0.35, 0.3)

    #create legions button region
    create_legions_button_region_pct: tuple[float, float, float, float] = (0.5, 0.1, 0.4, 0.8)

    #march button region
    march_button_region_pct: tuple[float, float, float, float] = (0.6, 0.8, 0.4, 0.2)
    
    #back arrow region
    back_arrow_region_pct: tuple[float, float, float, float] = (0.0, 0.0, 0.1, 0.1)

    #action menu first half region
    action_menu_first_half_region_pct: tuple[float, float, float, float] = (0.075, 0.1, 0.2, 0.4)

    #action menu training region
    action_menu_training_region_pct: tuple[float, float, float, float] = (0, 0.3, 0.25, 0.51)

    #action menu close region
    action_menu_close_region_pct: tuple[float, float, float, float] = (0.2, 0.25, 0.1, 0.5)

    #resource buy window close button region
    resource_buy_window_close_button_region_pct: tuple[float, float, float, float] = (0.8, 0.05, 0.1, 0.2)

    #train troop selection region
    train_troop_selection_region_pct: tuple[float, float, float, float] = (0.1, 0.7, 0.4, 0.2)


    # Assets directory
    assets_dir: Path = Path("assets")
    templates_dir: Path = Path("assets/templates")

    # Debugging
    save_shots: bool = False
    shots_dir: Path = Path("debug_captures")
    # Dedicated folder for one-off start screenshots (not pruned)
    start_shots_dir: Path = Path("start_captures")
    # Max total bytes to keep in shots_dir before pruning oldest files
    shots_max_bytes: int = 1_073_741_824  # 1 GiB

    # Click behavior
    # When True, restore mouse cursor to its previous position after a click
    click_snap_back: bool = True

    # UI placement (percent margins relative to game client size)
    # Game launching
    game_shortcut_path: Optional[Path] = None
    game_launch_wait_s: float = 60.0

    # Game window sizing (client area)
    # When >0, attempt to resize the target window's CLIENT area to this size
    force_window_resize: bool = True
    force_window_width: int = 1765
    force_window_height: int = 993

    # Logging
    log_to_file: bool = True
    log_file: Path = Path("bot.log")
    log_max_bytes: int = 1_048_576  # 1 MB
    log_backups: int = 5            # number of rotated files to keep

    # Farm cooldown window (seconds) for random delay between farm cycles
    farm_cooldown_min_s: int = 300    # 5 minutes
    farm_cooldown_max_s: int = 3600   # 1 hour

    # Alliance help cooldown window (seconds)
    alliance_help_cooldown_min_s: int = 300   # 5 minutes
    alliance_help_cooldown_max_s: int = 900   # 15 minutes

    # Max concurrent armies/legions available for gathering
    max_armies: int = 3

    # Training cooldown window (seconds) for random delay when no troops to train
    train_cooldown_min_s: int = 3600   # 1 hour
    train_cooldown_max_s: int = 7200   # 2 hours


def _duration_seconds(value: Optional[object], default: int) -> int:
    """Parse duration like '300', '5m', '1h' into seconds (int)."""
    if value is None:
        return int(default)
    if isinstance(value, (int, float)):
        try:
            return max(0, int(float(value)))
        except Exception:
            return int(default)
    if isinstance(value, str):
        s = value.strip().lower()
        try:
            if s.endswith('ms'):
                return max(0, int(float(s[:-2].strip()) / 1000.0))
            if s.endswith('s'):
                return max(0, int(float(s[:-1].strip())))
            if s.endswith('m'):
                return max(0, int(float(s[:-1].strip()) * 60))
            if s.endswith('h'):
                return max(0, int(float(s[:-1].strip()) * 3600))
            if s.endswith('d'):
                return max(0, int(float(s[:-1].strip()) * 86400))
            return max(0, int(float(s)))
        except Exception:
            return int(default)
    return int(default)


def make_config() -> AppConfig:
    settings = settings_store.get_settings()

    def _str(key: str, default: str) -> str:
        val = settings.get(key, default)
        if val is None:
            return default
        return str(val)

    def _bool(key: str, default: bool) -> bool:
        val = settings.get(key)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            s = val.strip().lower()
            if s in {"1", "true", "yes", "on", "y"}:
                return True
            if s in {"0", "false", "no", "off", "n"}:
                return False
        return default

    def _float(key: str, default: float) -> float:
        val = settings.get(key)
        try:
            if isinstance(val, str):
                s = val.strip()
                if s.endswith("%"):
                    return float(s[:-1]) / 100.0
                return float(s)
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            return default
        return default

    def _int(key: str, default: int) -> int:
        val = settings.get(key)
        try:
            if isinstance(val, str):
                return int(float(val.strip()))
            if isinstance(val, (int, float)):
                return int(val)
        except Exception:
            return default
        return default

    window_title = _str("WINDOW_TITLE_SUBSTR", "Call of Dragons")
    match_threshold = _float("MATCH_THRESHOLD", 0.85)
    verify_threshold = _float("VERIFY_THRESHOLD", 0.85)
    click_snap_back = _bool("CLICK_SNAP_BACK", True)
    save_shots = _bool("SAVE_SHOTS", False)
    shots_dir_env = _str("SHOTS_DIR", "debug_captures").strip()
    shots_dir = Path(shots_dir_env) if shots_dir_env else Path("debug_captures")
    start_shots_dir_env = _str("START_SHOTS_DIR", "start_captures").strip()
    start_shots_dir = Path(start_shots_dir_env) if start_shots_dir_env else Path("start_captures")
    # Make shots_dir absolute to avoid CWD differences between UI/server threads
    try:
        if not shots_dir.is_absolute():
            shots_dir = Path.cwd() / shots_dir
        if not start_shots_dir.is_absolute():
            start_shots_dir = Path.cwd() / start_shots_dir
    except Exception:
        # Fallback: leave as-is if cwd is unavailable
        pass
    shots_max_bytes = _int("SHOTS_MAX_BYTES", 1_073_741_824)

    # Resolve assets/templates paths for both dev and PyInstaller onefile/onedir
    assets_dir = Path("assets")
    templates_dir = Path("assets/templates")
    try:
        base_candidates = []
        # Prefer bundled resources when frozen
        if getattr(sys, "frozen", False):
            base_candidates.append(Path(getattr(sys, "_MEIPASS", "")))
        # Also consider the current working directory (next to the exe)
        base_candidates.append(Path.cwd())
        for base in base_candidates:
            a = base / "assets"
            t = a / "templates"
            if a.exists() and t.exists():
                assets_dir = a
                templates_dir = t
                break
    except Exception:
        pass
    force_window_resize = _bool("FORCE_WINDOW_RESIZE", True)
    force_window_width = _int("FORCE_WINDOW_WIDTH", 1765)
    force_window_height = _int("FORCE_WINDOW_HEIGHT", 993)
    game_shortcut_env = _str("GAME_SHORTCUT_PATH", "").strip()
    game_shortcut_path: Optional[Path]
    if game_shortcut_env:
        candidate = Path(game_shortcut_env)
        try:
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
        except Exception:
            pass
        game_shortcut_path = candidate
    else:
        game_shortcut_path = None
    game_launch_wait_s = _float("GAME_LAUNCH_WAIT", 60.0)
    if game_launch_wait_s < 0:
        game_launch_wait_s = 0.0

    log_to_file = _bool("LOG_TO_FILE", True)
    log_file_env = _str("LOG_FILE", "bot.log").strip()
    log_file = Path(log_file_env) if log_file_env else Path("bot.log")
    log_max_bytes = _int("LOG_MAX_BYTES", 1_048_576)
    log_backups = _int("LOG_BACKUPS", 5)
    # Farm cooldown min/max
    cd_min = _duration_seconds(settings.get("FARM_COOLDOWN_MIN"), 300)
    cd_max = _duration_seconds(settings.get("FARM_COOLDOWN_MAX"), 3600)
    if cd_max < cd_min:
        cd_min, cd_max = cd_max, cd_min
    # Training cooldown min/max
    tcd_min = _duration_seconds(settings.get("TRAIN_COOLDOWN_MIN"), 3600)
    tcd_max = _duration_seconds(settings.get("TRAIN_COOLDOWN_MAX"), 7200)
    if tcd_max < tcd_min:
        tcd_min, tcd_max = tcd_max, tcd_min
    # Alliance help cooldown min/max
    ah_min = _duration_seconds(settings.get("ALLIANCE_HELP_COOLDOWN_MIN"), 300)
    ah_max = _duration_seconds(settings.get("ALLIANCE_HELP_COOLDOWN_MAX"), 900)
    if ah_max < ah_min:
        ah_min, ah_max = ah_max, ah_min
    # Max armies from env
    max_armies = max(1, _int("MAX_ARMIES", 3))
    return AppConfig(
        window_title_substr=window_title,
        match_threshold=match_threshold,
        verify_threshold=verify_threshold,
        click_snap_back=click_snap_back,
        save_shots=save_shots,
        shots_dir=shots_dir,
        start_shots_dir=start_shots_dir,
        shots_max_bytes=shots_max_bytes,
        assets_dir=assets_dir,
        templates_dir=templates_dir,
        game_shortcut_path=game_shortcut_path,
        game_launch_wait_s=game_launch_wait_s,
        force_window_resize=force_window_resize,
        force_window_width=force_window_width,
        force_window_height=force_window_height,
        farm_cooldown_min_s=cd_min,
        farm_cooldown_max_s=cd_max,
        alliance_help_cooldown_min_s=ah_min,
        alliance_help_cooldown_max_s=ah_max,
        max_armies=max_armies,
        train_cooldown_min_s=tcd_min,
        train_cooldown_max_s=tcd_max,
        log_to_file=log_to_file,
        log_file=log_file,
        log_max_bytes=log_max_bytes,
        log_backups=log_backups,
    )


DEFAULT_CONFIG = make_config()
