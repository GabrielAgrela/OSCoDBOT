from __future__ import annotations

import time
from dataclasses import dataclass
import random

from bot.core.state_machine import Action, Context
from bot.core.window import bring_to_front, click_screen_xy
from bot.config import DEFAULT_CONFIG

try:
    import win32api  # type: ignore
    import win32con  # type: ignore
except Exception:  # pragma: no cover - environment specific
    win32api = None  # type: ignore
    win32con = None  # type: ignore


@dataclass
class ClickPercent(Action):
    name: str
    x_pct: float
    y_pct: float

    def run(self, ctx: Context) -> None:
        left, top, width, height = ctx.window_rect
        if width <= 0 or height <= 0:
            return
        x = left + int(max(0.0, min(1.0, self.x_pct)) * width)
        y = top + int(max(0.0, min(1.0, self.y_pct)) * height)
        if ctx.hwnd is not None:
            bring_to_front(ctx.hwnd)
            time.sleep(0.05)
        click_screen_xy(x, y)


@dataclass
class ClickBelowLastMatchPercent(Action):
    name: str
    down_pct: float  # fraction of window height (e.g., 0.05 for 5%)

    def run(self, ctx: Context) -> None:
        # Require a previous match to reference
        lm = getattr(ctx, "last_match", None)
        if lm is None:
            return None
        left, top, width, height = ctx.window_rect
        if width <= 0 or height <= 0:
            return None
        # Base on last match screen center; move downward by down_pct of window height
        sx, sy = lm.center_screen_xy
        dy = int(max(-1.0, min(1.0, float(self.down_pct))) * height)
        tx = max(left, min(left + width - 1, sx))
        ty = max(top, min(top + height - 1, sy + dy))
        if ctx.hwnd is not None:
            bring_to_front(ctx.hwnd)
            time.sleep(0.05)
        click_screen_xy(tx, ty)


@dataclass
class DragPercent(Action):
    name: str
    from_x_pct: float
    from_y_pct: float
    to_x_pct: float
    to_y_pct: float
    duration_s: float = 0.15  # total drag duration
    steps: int = 8            # intermediate move steps

    def run(self, ctx: Context) -> None:
        # Require Win32 API for dragging
        if win32api is None or win32con is None:
            return None
        left, top, width, height = ctx.window_rect
        if width <= 0 or height <= 0:
            return None
        sx = left + int(max(0.0, min(1.0, self.from_x_pct)) * width)
        sy = top + int(max(0.0, min(1.0, self.from_y_pct)) * height)
        ex = left + int(max(0.0, min(1.0, self.to_x_pct)) * width)
        ey = top + int(max(0.0, min(1.0, self.to_y_pct)) * height)
        if ctx.hwnd is not None:
            bring_to_front(ctx.hwnd)
            time.sleep(0.05)
        # Remember cursor and clamp to virtual desktop
        try:
            prev_pos = win32api.GetCursorPos()
        except Exception:
            prev_pos = None
        try:
            # Clamp helpers
            try:
                vx = win32api.GetSystemMetrics(76)
                vy = win32api.GetSystemMetrics(77)
                vw = win32api.GetSystemMetrics(78)
                vh = win32api.GetSystemMetrics(79)
                max_x = vx + max(0, vw - 1)
                max_y = vy + max(0, vh - 1)
            except Exception:
                vx = 0
                vy = 0
                max_x = 65535
                max_y = 65535
            sx = max(vx, min(sx, max_x))
            sy = max(vy, min(sy, max_y))
            ex = max(vx, min(ex, max_x))
            ey = max(vy, min(ey, max_y))
            # Go to start, press, interpolate moves, release
            win32api.SetCursorPos((sx, sy))
            time.sleep(0.01)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            n = max(1, int(self.steps))
            delay = max(0.0, float(self.duration_s)) / float(n)
            dx = (ex - sx) / float(n)
            dy = (ey - sy) / float(n)
            cx = float(sx)
            cy = float(sy)
            for _ in range(n):
                cx += dx
                cy += dy
                win32api.SetCursorPos((int(cx), int(cy)))
                time.sleep(delay)
            win32api.SetCursorPos((ex, ey))
            time.sleep(0.01)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        finally:
            # Optionally restore the cursor to its previous position
            if getattr(DEFAULT_CONFIG, 'click_snap_back', True) and prev_pos is not None:
                try:
                    win32api.SetCursorPos(prev_pos)
                except Exception:
                    pass


@dataclass
class SpiralCameraMoveBlock(Action):
    name: str
    magnitude_x_pct: float = 0.25  # how far to drag horizontally (fraction of width)
    magnitude_y_pct: float = 0.25  # how far to drag vertically (fraction of height)
    pause_between_drags_s: float = 0.25

    def run(self, ctx: Context) -> bool:
        # Initialize spiral counters on context
        block_len = int(getattr(ctx, "_gem_spiral_block_len", 1))
        dir_idx = int(getattr(ctx, "_gem_spiral_dir_idx", 0))

        # Directions order: left, up, right, down -> 0,1,2,3
        dirs = [
            (-abs(self.magnitude_x_pct), 0.0),
            (0.0, -abs(self.magnitude_y_pct)),
            (abs(self.magnitude_x_pct), 0.0),
            (0.0, abs(self.magnitude_y_pct)),
        ]
        dx_pct, dy_pct = dirs[dir_idx % 4]

        # Occasionally do one more or one less drag than the nominal block length (~25% chance)
        eff_block_len = block_len
        try:
            if random.random() < 0.25:
                eff_block_len = max(1, block_len + (1 if random.random() < 0.5 else -1))
        except Exception:
            pass

        # Perform drags in the current direction. Start from center each time.
        start_x = 0.50
        start_y = 0.50
        # Randomize how far to drag for this block (80%..120% per axis)
        try:
            sx_scale = 1.0 + random.uniform(-0.2, 0.2)
            sy_scale = 1.0 + random.uniform(-0.2, 0.2)
        except Exception:
            sx_scale = sy_scale = 1.0
        end_x = max(0.0, min(1.0, start_x + dx_pct * sx_scale))
        end_y = max(0.0, min(1.0, start_y + dy_pct * sy_scale))
        for _ in range(max(1, eff_block_len)):
            # Randomize drag speed and path density
            try:
                dur = max(0.08, 0.18 * random.uniform(0.7, 1.4))
            except Exception:
                dur = 0.18
            try:
                steps = int(max(5, min(16, random.randint(7, 12))))
            except Exception:
                steps = 10
            DragPercent(
                name="drag",
                from_x_pct=start_x,
                from_y_pct=start_y,
                to_x_pct=end_x,
                to_y_pct=end_y,
                duration_s=dur,
                steps=steps,
            ).run(ctx)
            # Randomize inter-drag pause slightly
            try:
                pause = max(0.05, float(self.pause_between_drags_s) * random.uniform(0.7, 1.4))
            except Exception:
                pause = self.pause_between_drags_s
            time.sleep(pause)

        # Advance spiral: next direction and increase block length by 1 every move
        try:
            setattr(ctx, "_gem_spiral_dir_idx", (dir_idx + 1) % 4)
        except Exception:
            pass
        try:
            setattr(ctx, "_gem_spiral_block_len", block_len + 1)
        except Exception:
            pass
        return True


@dataclass
class SpiralCameraMoveStep(Action):
    name: str
    magnitude_x_pct: float = 0.25  # base horizontal drag distance (0..1 of width)
    magnitude_y_pct: float = 0.25  # base vertical drag distance (0..1 of height)
    pause_after_drag_s: float = 0.25
    # Random starting point jitter from center (fraction of width/height)
    start_jitter_pct: float = 0.02

    def run(self, ctx: Context) -> bool:
        # Counters for spiral progression stored on context
        block_len = int(getattr(ctx, "_gem_spiral_block_len", 1))
        dir_idx = int(getattr(ctx, "_gem_spiral_dir_idx", 0))
        done_in_block = int(getattr(ctx, "_gem_spiral_done_in_block", 0))
        # On new block, decide an effective target length with small randomness and store it
        if done_in_block <= 0:
            target = block_len
            try:
                if random.random() < 0.25:
                    target = max(1, block_len + (1 if random.random() < 0.5 else -1))
            except Exception:
                target = block_len
            try:
                setattr(ctx, "_gem_spiral_block_target", int(target))
            except Exception:
                pass
        else:
            try:
                target = int(getattr(ctx, "_gem_spiral_block_target", block_len))
            except Exception:
                target = block_len

        # Direction selection: left, up, right, down (0..3)
        dirs = [
            (-abs(self.magnitude_x_pct), 0.0),
            (0.0, -abs(self.magnitude_y_pct)),
            (abs(self.magnitude_x_pct), 0.0),
            (0.0, abs(self.magnitude_y_pct)),
        ]
        dx_pct, dy_pct = dirs[dir_idx % 4]

        # Randomize distance per axis (80%..120%)
        try:
            sx_scale = 1.0 + random.uniform(-0.2, 0.2)
            sy_scale = 1.0 + random.uniform(-0.2, 0.2)
        except Exception:
            sx_scale = sy_scale = 1.0
        # Start near center with small random jitter
        try:
            jx = random.uniform(-abs(self.start_jitter_pct), abs(self.start_jitter_pct))
            jy = random.uniform(-abs(self.start_jitter_pct), abs(self.start_jitter_pct))
        except Exception:
            jx = jy = 0.0
        start_x = max(0.0, min(1.0, 0.50 + jx))
        start_y = max(0.0, min(1.0, 0.50 + jy))
        end_x = max(0.0, min(1.0, start_x + dx_pct * sx_scale))
        end_y = max(0.0, min(1.0, start_y + dy_pct * sy_scale))

        # Randomize drag dynamics
        try:
            dur = max(0.08, 0.18 * random.uniform(0.7, 1.4))
        except Exception:
            dur = 0.18
        try:
            steps = int(max(5, min(16, random.randint(7, 12))))
        except Exception:
            steps = 10
        DragPercent(
            name="drag",
            from_x_pct=start_x,
            from_y_pct=start_y,
            to_x_pct=end_x,
            to_y_pct=end_y,
            duration_s=dur,
            steps=steps,
        ).run(ctx)

        # Pause slightly after drag with jitter
        try:
            pause = max(0.05, float(self.pause_after_drag_s) * random.uniform(0.7, 1.4))
        except Exception:
            pause = self.pause_after_drag_s
        time.sleep(pause)

        # Update progression counters: increment done; if reaching target, advance direction and block size
        done_in_block += 1
        try:
            setattr(ctx, "_gem_spiral_done_in_block", int(done_in_block))
        except Exception:
            pass
        if done_in_block >= max(1, int(target)):
            try:
                setattr(ctx, "_gem_spiral_done_in_block", 0)
            except Exception:
                pass
            try:
                setattr(ctx, "_gem_spiral_dir_idx", (dir_idx + 1) % 4)
            except Exception:
                pass
            try:
                setattr(ctx, "_gem_spiral_block_len", block_len + 1)
            except Exception:
                pass
        return True


@dataclass
class ResetGemSpiral(Action):
    name: str

    def run(self, ctx: Context) -> bool:
        try:
            setattr(ctx, "_gem_spiral_block_len", 1)
        except Exception:
            pass
        try:
            setattr(ctx, "_gem_spiral_dir_idx", 0)
        except Exception:
            pass
        try:
            setattr(ctx, "_gem_spiral_done_in_block", 0)
        except Exception:
            pass
        try:
            setattr(ctx, "_gem_spiral_block_target", 1)
        except Exception:
            pass
        return True
