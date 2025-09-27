from __future__ import annotations

import socket
import threading
import time
import webbrowser

from bot.core.window import enable_dpi_awareness
from .app import app
from bot import settings as settings_store


def _serve(host: str, port: int) -> None:
    """Run the Flask app in a background thread."""
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


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
    cfg = settings_store.get_settings()
    bind_host = str(cfg.get("WEB_BIND_HOST", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1"
    port_raw = str(cfg.get("WEB_PORT", 5000))
    try:
        port = int(port_raw)
        if not (0 < port < 65536):
            raise ValueError
    except ValueError:
        port = 5000
    display_host = str(cfg.get("WEB_DISPLAY_HOST", "") or "").strip()
    if not display_host:
        display_host = "127.0.0.1" if bind_host in ("0.0.0.0", "::", "") else bind_host
    wait_host = "127.0.0.1" if bind_host in ("0.0.0.0", "::", "") else bind_host

    enable_dpi_awareness()
    thread = threading.Thread(target=_serve, args=(bind_host, port), daemon=True)
    thread.start()
    _wait_for_server(wait_host, port)
    url = f"http://{display_host}:{port}"
    print(f"Opening control panel at {url} (listening on {bind_host}:{port})")
    try:
        webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        pass
    try:
        while thread.is_alive():
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


