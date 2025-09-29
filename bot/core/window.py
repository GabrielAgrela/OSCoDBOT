from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import ctypes
import random
import time
import sys

if sys.platform == "win32":
    import win32api
    import win32con
    import win32gui
    import win32process
else:  # pragma: no cover - platform-specific fallback
    class _Win32Unavailable:
        """Stub object used when Win32 bindings are unavailable."""

        def __getattr__(self, name: str):
            raise RuntimeError("Win32 APIs are unavailable on this platform")

    win32api = _Win32Unavailable()  # type: ignore[assignment]
    win32con = _Win32Unavailable()  # type: ignore[assignment]
    win32gui = _Win32Unavailable()  # type: ignore[assignment]
    win32process = _Win32Unavailable()  # type: ignore[assignment]

import bot.config as config


@dataclass
class WindowRect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def to_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


def find_window_by_title_substr(substr: str) -> Optional[int]:
    substr = substr.lower()
    match: Optional[int] = None

    def _enum_handler(hwnd, _):
        nonlocal match
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if substr in title.lower():
            match = hwnd

    win32gui.EnumWindows(_enum_handler, None)
    return match


def get_client_rect_screen(hwnd: int) -> WindowRect:
    # Client rect in client coords
    left_c, top_c, right_c, bottom_c = win32gui.GetClientRect(hwnd)
    # Convert to screen coords
    left_top = win32gui.ClientToScreen(hwnd, (left_c, top_c))
    right_bottom = win32gui.ClientToScreen(hwnd, (right_c, bottom_c))
    left = left_top[0]
    top = left_top[1]
    width = max(0, right_bottom[0] - left)
    height = max(0, right_bottom[1] - top)
    return WindowRect(left, top, width, height)


def bring_to_front(hwnd: int) -> None:
    """Best-effort to bring a window to the foreground and raise it in Z-order.

    Windows has foreground lock rules that can block SetForegroundWindow from
    stealing focus. This function uses several fallbacks:
    - Restore if minimized, ensure shown
    - Try SetForegroundWindow directly
    - Temporarily toggle TOPMOST to raise in Z-order
    - AttachThreadInput to the current foreground thread to allow activation
    - ALT key tap heuristic to satisfy foreground permission
    """
    try:
        # Restore if minimized and ensure visible
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                # Make sure it's shown (won't steal focus)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        except Exception:
            pass

        # Direct attempt
        try:
            if win32gui.GetForegroundWindow() != hwnd:
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

        # If still not foreground, use fallbacks
        try:
            if win32gui.GetForegroundWindow() != hwnd:
                # Raise in Z-order by toggling TOPMOST
                try:
                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_TOPMOST,
                        0,
                        0,
                        0,
                        0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                    )
                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_NOTOPMOST,
                        0,
                        0,
                        0,
                        0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                    )
                except Exception:
                    pass

                # ALT key tap heuristic
                try:
                    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                    win32api.keybd_event(
                        win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0
                    )
                except Exception:
                    pass

                # Attach to foreground thread and force activation
                try:
                    fg = win32gui.GetForegroundWindow()
                    if fg and fg != hwnd:
                        tid_fg, _ = win32process.GetWindowThreadProcessId(fg)
                        tid_hwnd, _ = win32process.GetWindowThreadProcessId(hwnd)
                        user32 = ctypes.windll.user32
                        user32.AttachThreadInput(tid_fg, tid_hwnd, True)
                        try:
                            win32gui.BringWindowToTop(hwnd)
                            user32.SetFocus(hwnd)
                            user32.SetActiveWindow(hwnd)
                            win32gui.SetForegroundWindow(hwnd)
                        finally:
                            try:
                                user32.AttachThreadInput(tid_fg, tid_hwnd, False)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        # Foreground rules may prevent focus; clicking still works with absolute coords
        pass






def _wait_for_window_gone(hwnd: int, timeout_s: float) -> bool:
    deadline = time.time() + max(0.0, float(timeout_s))
    while True:
        try:
            if not win32gui.IsWindow(hwnd):
                return True
        except Exception:
            return True
        if time.time() >= deadline:
            break
        time.sleep(0.05)
    try:
        return not win32gui.IsWindow(hwnd)
    except Exception:
        return True


def close_window(hwnd: int, wait_s: float = 3.0, force_terminate: bool = True) -> Tuple[bool, bool]:
    """Attempt to close a window gracefully, optionally force-terminating its process."""
    if not hwnd:
        return False, False
    posted = False
    try:
        win32gui.PostMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_CLOSE, 0)
        posted = True
    except Exception:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            posted = True
        except Exception:
            posted = False
    if posted and _wait_for_window_gone(hwnd, wait_s):
        return True, False
    if not force_terminate:
        return False, False
    forced = terminate_window_process(hwnd, wait_s=max(wait_s, 2.0))
    if forced:
        return True, True
    return False, False


def terminate_window_process(hwnd: int, wait_s: float = 3.0) -> bool:
    """Force terminate the process that owns the given window."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        pid = 0
    if not pid:
        return False
    access = getattr(win32con, 'PROCESS_TERMINATE', 0x0001)
    sync_flag = getattr(win32con, 'SYNCHRONIZE', 0x00100000)
    access |= sync_flag
    try:
        handle = win32api.OpenProcess(access, False, int(pid))
    except Exception:
        handle = None
    if not handle:
        return False
    terminated = False
    try:
        try:
            win32api.TerminateProcess(handle, 0)
            terminated = True
        except Exception:
            try:
                ctypes.windll.kernel32.TerminateProcess(int(handle), 0)
                terminated = True
            except Exception:
                terminated = False
        if terminated and wait_s > 0:
            try:
                ctypes.windll.kernel32.WaitForSingleObject(int(handle), int(max(0.0, wait_s) * 1000))
            except Exception:
                end = time.time() + max(0.0, float(wait_s))
                while time.time() < end:
                    time.sleep(0.05)
    finally:
        try:
            win32api.CloseHandle(handle)
        except Exception:
            pass
    if not terminated:
        return False
    return _wait_for_window_gone(hwnd, max(1.5, float(wait_s)))

def click_screen_xy(x: int, y: int) -> None:
    # Remember current cursor position, click at (x, y) with slight jitter, then return
    try:
        prev_pos = win32api.GetCursorPos()
    except Exception:
        prev_pos = None
    try:
        try:
            dx = random.randint(-3, 3)
            dy = random.randint(-3, 3)
        except Exception:
            dx = 0
            dy = 0
        rx = x + dx
        ry = y + dy
        try:
            # Clamp to the entire virtual desktop (all monitors), not just primary
            # SM_XVIRTUALSCREEN(76), SM_YVIRTUALSCREEN(77), SM_CXVIRTUALSCREEN(78), SM_CYVIRTUALSCREEN(79)
            vx = win32api.GetSystemMetrics(76)
            vy = win32api.GetSystemMetrics(77)
            vw = win32api.GetSystemMetrics(78)
            vh = win32api.GetSystemMetrics(79)
            max_x = vx + max(0, vw - 1)
            max_y = vy + max(0, vh - 1)
            rx = max(vx, min(rx, max_x))
            ry = max(vy, min(ry, max_y))
        except Exception:
            pass
        win32api.SetCursorPos((rx, ry))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    finally:
        # Optionally restore the cursor to its previous position
        if config.DEFAULT_CONFIG.click_snap_back and prev_pos is not None:
            try:
                win32api.SetCursorPos(prev_pos)
            except Exception:
                pass


def enable_dpi_awareness() -> None:
    """Make process DPI aware so Win32 and pixel coords match on scaled displays."""
    try:
        shcore = ctypes.windll.shcore
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE
        shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_window_client_size(hwnd: int, client_width: int, client_height: int) -> None:
    """Resize a window so that its CLIENT area becomes the given size.

    - Restores the window if maximized/minimized
    - Computes outer size via AdjustWindowRectEx based on current styles
    - Keeps current position (no move)
    """
    try:
        # Ensure window is in a normal state to allow resizing
        try:
            if win32gui.IsIconic(hwnd) or win32gui.IsZoomed(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass
        # Query styles
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        # Prepare RECT for desired client size
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        rect = RECT(0, 0, int(client_width), int(client_height))
        user32 = ctypes.windll.user32
        # Best effort: assume no menu
        user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
        outer_w = max(0, rect.right - rect.left)
        outer_h = max(0, rect.bottom - rect.top)
        flags = win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        win32gui.SetWindowPos(hwnd, 0, 0, 0, int(outer_w), int(outer_h), flags)
    except Exception:
        # Ignore failures; some windows (e.g., UWP or restricted) may not resize
        pass


def set_window_topmost(hwnd: int, topmost: bool = True) -> None:
    """Set or clear the always-on-top flag for a window.

    On Windows this uses SetWindowPos with HWND_TOPMOST / HWND_NOTOPMOST.
    """
    try:
        insert_after = win32con.HWND_TOPMOST if topmost else win32con.HWND_NOTOPMOST
        flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
        win32gui.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)
    except Exception:
        pass


def set_window_frameless(hwnd: int, frameless: bool = True) -> None:
    """Toggle window frame (title bar and borders) on Windows.

    Removes WS_CAPTION/WS_THICKFRAME/WS_MINIMIZE/WS_MAXIMIZE/WS_SYSMENU for frameless.
    """
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if frameless:
            style &= ~(
                win32con.WS_CAPTION
                | win32con.WS_THICKFRAME
                | win32con.WS_MINIMIZEBOX
                | win32con.WS_MAXIMIZEBOX
                | win32con.WS_SYSMENU
            )
        else:
            # Restore a typical overlapped window style
            style |= (
                win32con.WS_CAPTION
                | win32con.WS_THICKFRAME
                | win32con.WS_MINIMIZEBOX
                | win32con.WS_MAXIMIZEBOX
                | win32con.WS_SYSMENU
            )
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        flags = (
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_FRAMECHANGED
        )
        win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except Exception:
        pass


def move_window_xy(hwnd: int, x: int, y: int) -> None:
    """Move a window to absolute screen coordinates using Win32.

    Uses SetWindowPos with SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE to avoid
    resizing, z-order changes or stealing focus. Safe to call from any thread.
    """
    try:
        flags = win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        win32gui.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0, flags)
    except Exception:
        pass


def get_monitor_rect_for_window(hwnd: int, work_area: bool = False) -> WindowRect:
    """Return the bounding rect of the monitor that contains (or is nearest to) the window.

    - When work_area is True, returns the work area (excluding taskbar).
    - Coordinates are in the virtual desktop space (can be negative on multi-monitor).
    """
    try:
        hmon = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(hmon)
        key = 'Work' if work_area else 'Monitor'
        left, top, right, bottom = info.get(key, info.get('Monitor'))
        return WindowRect(left=int(left), top=int(top), width=int(right - left), height=int(bottom - top))
    except Exception:
        # Fallback to primary monitor bounds
        try:
            # SM_XVIRTUALSCREEN etc. give the full virtual bounds; primary origin via SM_XVIRTUALSCREEN/SM_Y...
            vx = win32api.GetSystemMetrics(76)
            vy = win32api.GetSystemMetrics(77)
            vw = win32api.GetSystemMetrics(78)
            vh = win32api.GetSystemMetrics(79)
            return WindowRect(left=int(vx), top=int(vy), width=int(vw), height=int(vh))
        except Exception:
            return WindowRect(0, 0, 0, 0)
