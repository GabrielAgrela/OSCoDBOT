from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import ctypes

import win32api
import win32con
import win32gui


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
    try:
        # Only restore if minimized; keep maximized state intact
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Set foreground if different
        if win32gui.GetForegroundWindow() != hwnd:
            win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # Foreground rules may prevent focus; clicking still works with absolute coords
        pass


def click_screen_xy(x: int, y: int) -> None:
    # Remember current cursor position, click at (x, y), then return immediately
    try:
        prev_pos = win32api.GetCursorPos()
    except Exception:
        prev_pos = None
    try:
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    finally:
        if prev_pos is not None:
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
