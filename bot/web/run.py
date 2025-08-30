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

from bot.core.window import enable_dpi_awareness
from .app import app


def _serve():
    # Run Flask app in background thread
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)


def run_app() -> None:
    enable_dpi_awareness()
    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    # Give server a moment to start
    time.sleep(0.5)
    url = "http://127.0.0.1:5000"
    if HAS_WEBVIEW:
        webview.create_window("Call of the Dragons Bot", url, width=560, height=720, resizable=False)
        webview.start()
    else:
        print("pywebview not installed. Opening in your default browser instead.\nInstall with: pip install pywebview")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
