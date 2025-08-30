from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, SequenceState, State
from bot.actions import Screenshot, FindAndClick, Wait


def build_scouts_state(cfg: AppConfig) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )
    actions = [
        Screenshot(name="capture_1"),
        Wait(name="wait_1", seconds=2.0),
        FindAndClick(
            name="ScoutIdle",
            templates=["ScoutIdle.png"],
            region_pct=cfg.side_region_pct,
            threshold=0.95,
        ),
        Wait(name="wait_1", seconds=1.0),
        Screenshot(name="capture_2"),
        FindAndClick(
            name="ScoutSelectExplore",
            templates=["ScoutSelectExplore.png"],
            region_pct=(0.0, 0.0, 1.0, 1.0),
            threshold=cfg.match_threshold,
        ),
        Wait(name="wait_2", seconds=1.0),
        Screenshot(name="capture_3"),
        FindAndClick(
            name="ScoutExplore",
            templates=["ScoutExplore.png"],
            region_pct=(0.0, 0.0, 1.0, 1.0),
            threshold=cfg.match_threshold,
        ),
        Wait(name="wait_3", seconds=1.0),
    ]
    state = SequenceState(name="scout_loop", actions=actions, loop_sleep_s=0.05)
    return state, ctx
