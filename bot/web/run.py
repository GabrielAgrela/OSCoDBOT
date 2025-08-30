from __future__ import annotations

import threading
import time
import webbrowser

try:
    import webview  # type: ignore
    HAS_WEBVIEW = True
except Exception:
    webview = None  # type: ignore
    HAS_WEBVIEW = False

from bot.core.window import (
    enable_dpi_awareness,
    find_window_by_title_substr,
    get_client_rect_screen,
    set_window_topmost,
    set_window_frameless,
)
from bot.config import DEFAULT_CONFIG
from .app import app


def _serve():
    # Run Flask app in background thread
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)


def _stick_left_loop(window) -> None:
    """Continuously pin the UI window to the left side of the game window.

    Margins are specified as a percentage of the game client size
    to keep placement consistent across resolutions and DPI.
    """
    margin_left_pct = DEFAULT_CONFIG.ui_margin_left_pct
    margin_top_pct = DEFAULT_CONFIG.ui_margin_top_pct
    title_substr = DEFAULT_CONFIG.window_title_substr
    while True:
        try:
            hwnd = find_window_by_title_substr(title_substr)
            if hwnd:
                rect = get_client_rect_screen(hwnd)
                x = rect.left + int(rect.width * margin_left_pct)
                y = rect.top + int(rect.height * margin_top_pct)
                try:
                    # Move the webview window to stick to the left inside the game window
                    window.move(x, y)
                except Exception:
                    # Ignore backend-specific issues and retry next tick
                    pass
        except Exception:
            pass
        time.sleep(0.5)


def _ensure_topmost_loop(title_substr: str) -> None:
    """Reassert our window as topmost periodically to stay visible over the game."""
    while True:
        try:
            hwnd = find_window_by_title_substr(title_substr)
            if hwnd:
                try:
                    set_window_topmost(hwnd, True)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(1.0)


def _frameless_loop(title_substr: str) -> None:
    """Try to remove title bar/borders from our UI window."""
    while True:
        try:
            hwnd = find_window_by_title_substr(title_substr)
            if hwnd:
                try:
                    set_window_frameless(hwnd, True)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(1.0)


def run_app() -> None:
    enable_dpi_awareness()
    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    # Give server a moment to start
    time.sleep(0.5)
    url = "http://127.0.0.1:5000"
    if HAS_WEBVIEW:
        # Smaller, compact window to fit inside the game client. Prefer frameless/on_top if supported.
        try:
            window = webview.create_window(
                "Call of the Dragons Bot",
                url,
                width=200,
                height=300,
                resizable=False,
                on_top=True,
                frameless=True,
                easy_drag=True,
            )
        except TypeError:
            # Older pywebview without these parameters
            try:
                window = webview.create_window(
                    "Call of the Dragons Bot",
                    url,
                    width=65,
                    height=365,
                    resizable=False,
                    on_top=True,
                )
            except TypeError:
                window = webview.create_window(
                    "Call of the Dragons Bot",
                    url,
                    width=30,
                    height=375,
                    resizable=False,
                )
        # Start a background thread to keep the window pinned to the left of the game window
        threading.Thread(target=_stick_left_loop, args=(window,), daemon=True).start()
        # Reassert topmost via Win32 as a fallback and to keep it above if the game grabs focus
        threading.Thread(target=_ensure_topmost_loop, args=("Call of the Dragons Bot",), daemon=True).start()
        # Try to enforce frameless via Win32 if backend doesn't support frameless
        threading.Thread(target=_frameless_loop, args=("Call of the Dragons Bot",), daemon=True).start()
        webview.start()
    else:
        print("pywebview not installed. Opening in your default browser instead.\nInstall with: pip install pywebview")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
