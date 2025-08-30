from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, EndCycle


def build_scouts_state(cfg: AppConfig) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    steps = [
        GraphStep(
            name="ScoutIdle",
            actions=[
                Screenshot(name="scout_cap_1"),
                FindAndClick(
                    name="ScoutIdle",
                    templates=["ScoutIdle.png"],
                    region_pct=cfg.side_region_pct,
                    threshold=0.95,
                ),
            ],
            on_success="ScoutSelectExplore",
            on_failure="EndNoIdle",
        ),
        GraphStep(
            name="ScoutSelectExplore",
            actions=[
                Wait(name="wait_after_idle", seconds=0.8),
                Screenshot(name="scout_cap_2"),
                FindAndClick(
                    name="ScoutSelectExplore",
                    templates=["ScoutSelectExplore.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="ScoutExplore",
            on_failure="EndNoIdle",
        ),
        GraphStep(
            name="ScoutExplore",
            actions=[
                Wait(name="wait_after_select", seconds=2),
                Screenshot(name="scout_cap_3"),
                FindAndClick(
                    name="ScoutExplore",
                    templates=["ScoutExplore.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_explore", seconds=0.8),
            ],
            on_success="ScoutIdle",
            on_failure="EndNoIdle",
        ),
        GraphStep(
            name="EndNoIdle",
            actions=[
                EndCycle(name="end_cycle"),
            ],
            on_success="ScoutIdle",
            on_failure="ScoutIdle",
        ),
    ]
    state = GraphState(steps=steps, start="ScoutIdle", loop_sleep_s=0.05)
    return state, ctx
