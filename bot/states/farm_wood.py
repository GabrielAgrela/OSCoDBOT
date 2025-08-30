from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, ClickPercent, EndCycle


def build_farm_wood_state(cfg: AppConfig) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    steps = [
        GraphStep(
            name="OpenMagnifier",
            actions=[
                Screenshot(name="farm_cap_open_1"),
                FindAndClick(
                    name="Magnifier",
                    templates=["Magnifier.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_magnifier", seconds=1.0),
            ],
            on_success="LoggingCampAny",
            on_failure="ClickMapIcon",
        ),
        GraphStep(
            name="ClickMapIcon",
            actions=[
                Screenshot(name="farm_cap_map_1"),
                FindAndClick(
                    name="MapIcon",
                    templates=["MapIcon.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_map", seconds=1.0),
            ],
            on_success="MagnifierAfterMap",
            on_failure="MagnifierAfterMap",
        ),
        GraphStep(
            name="MagnifierAfterMap",
            actions=[
                Screenshot(name="farm_cap_open_2"),
                FindAndClick(
                    name="MagnifierAgain",
                    templates=["Magnifier.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_magnifier2", seconds=1.0),
            ],
            on_success="LoggingCampAny",
            on_failure="OpenMagnifier",
        ),
        GraphStep(
            name="LoggingCampAny",
            actions=[
                Screenshot(name="farm_cap_log_1"),
                FindAndClick(
                    name="LoggingCampAny",
                    templates=["LoggingCamp.png", "LoggingCampEnabled.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_log", seconds=1.0),
            ],
            on_success="SearchFarmButton",
            on_failure="LoggingCampAny",
        ),
        GraphStep(
            name="SearchFarmButton",
            actions=[
                Screenshot(name="farm_cap_search_1"),
                FindAndClick(
                    name="SearchFarmButton",
                    templates=["SearchFarmButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_search", seconds=2.0),
            ],
            on_success="GatherButton",
            on_failure="SearchFarmButton",
        ),
        GraphStep(
            name="GatherButton",
            actions=[
                Screenshot(name="farm_cap_gather_1"),
                FindAndClick(
                    name="GatherButton",
                    templates=["GatherButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.95,
                ),
                Wait(name="wait_after_gather", seconds=1.0),
            ],
            on_success="CreateLegionsButton",
            on_failure="TapCenterThenGather",
        ),
        GraphStep(
            name="TapCenterThenGather",
            actions=[
                ClickPercent(name="tap_center", x_pct=0.5, y_pct=0.5),
                Screenshot(name="farm_cap_gather_retry"),
                FindAndClick(
                    name="GatherButtonRetry",
                    templates=["GatherButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.95,
                ),
                Wait(name="wait_after_gather_retry", seconds=1.0),
            ],
            on_success="CreateLegionsButton",
            on_failure="GatherButton",
        ),
        GraphStep(
            name="CreateLegionsButton",
            actions=[
                Screenshot(name="farm_cap_legions_1"),
                FindAndClick(
                    name="CreateLegionsButton",
                    templates=["CreateLegionsButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_legions", seconds=1.0),
            ],
            on_success="March",
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name="EndNoLegions",
            actions=[
                ClickPercent(name="tap_center_end", x_pct=0.5, y_pct=0.70),
                Wait(name="wait_after_end_click", seconds=1.0),
                EndCycle(name="end_cycle"),
            ],
            on_failure="OpenMagnifier",
            on_success="OpenMagnifier",
        ),
        GraphStep(
            name="March",
            actions=[
                Screenshot(name="farm_cap_march_1"),
                FindAndClick(
                    name="March",
                    templates=["March.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_march", seconds=1.0),
            ],
            on_success="OpenMagnifier",
            on_failure="March",
        ),
    ]
    state = GraphState(steps=steps, start="OpenMagnifier", loop_sleep_s=0.05)
    return state, ctx
