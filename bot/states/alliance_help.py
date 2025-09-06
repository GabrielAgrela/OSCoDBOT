from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, EndCycle


def build_alliance_help_state(cfg: AppConfig) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    steps = [
        GraphStep(
            name="ClickHelp",
            actions=[
                Screenshot(name="help_cap_1"),
                Wait(name="wait_after_screenshot", seconds=2.0),
                FindAndClick(
                    name="AllianceHelp",
                    templates=["AllianceHelp.png","AllianceHelpBig.png"],
                    region_pct=cfg.alliance_help_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="EndCycleStep",
            on_failure="EndCycleStep",
        ),
        GraphStep(
            name="EndCycleStep",
            actions=[
                EndCycle(name="end_cycle"),
            ],
            on_success="ClickHelp",
            on_failure="ClickHelp",
        ),
    ]
    state = GraphState(steps=steps, start="ClickHelp", loop_sleep_s=0.05)
    return state, ctx
