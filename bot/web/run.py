from __future__ import annotations

import socket
import threading
import time
import webbrowser

from bot.core.window import enable_dpi_awareness
from .app import app


def _serve() -> None:
    """Run the Flask app in a background thread."""
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)


def _wait_for_server(host: str, port: int, timeout_s: float = 5.0) -> None:
    """Best-effort wait until the development server is accepting connections."""
    deadline = time.time() + max(0.0, timeout_s)
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    # Give up after timeout; browser open will still try to connect later.


def run_app() -> None:
    enable_dpi_awareness()
    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    host, port = "127.0.0.1", 5000
    _wait_for_server(host, port)
    url = f"http://{host}:{port}"
    print(f"Opening control panel at {url}")
    try:
        webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        pass
    try:
        while thread.is_alive():
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
