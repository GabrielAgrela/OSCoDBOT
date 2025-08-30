from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, ClickPercent, EndCycle


def build_farm_gold_state(cfg: AppConfig) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
    )

    steps = [
        GraphStep(
            name="OpenMagnifier",
            actions=[
                Screenshot(name="gold_cap_open_1"),
                FindAndClick(
                    name="Magnifier",
                    templates=["Magnifier.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_magnifier", seconds=1.0),
            ],
            on_success="GoldAny",
            on_failure="ClickMapIcon",
        ),
        GraphStep(
            name="ClickMapIcon",
            actions=[
                Screenshot(name="gold_cap_map_1"),
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
                Screenshot(name="gold_cap_open_2"),
                FindAndClick(
                    name="MagnifierAgain",
                    templates=["Magnifier.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_magnifier2", seconds=1.0),
            ],
            on_success="GoldAny",
            on_failure="OpenMagnifier",
        ),
        GraphStep(
            name="GoldAny",
            actions=[
                Screenshot(name="gold_cap_gold_1"),
                FindAndClick(
                    name="GoldAny",
                    # Provide any of these templates; the first that matches is used.
                    templates=[
                        "GoldMine.png",
                        "GoldMineEnabled.png",
                        "GoldDeposit.png",
                        "GoldDepositEnabled.png",
                    ],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_gold", seconds=1.0),
            ],
            on_success="SearchFarmButton",
            on_failure="GoldAny",
        ),
        GraphStep(
            name="SearchFarmButton",
            actions=[
                Screenshot(name="gold_cap_search_1"),
                FindAndClick(
                    name="SearchFarmButton",
                    templates=["SearchFarmButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_search", seconds=1.0),
            ],
            on_success="GatherButton",
            on_failure="SearchFarmButton",
        ),
        GraphStep(
            name="GatherButton",
            actions=[
                Screenshot(name="gold_cap_gather_1"),
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
                Screenshot(name="gold_cap_gather_retry"),
                FindAndClick(
                    name="GatherButtonRetry",
                    templates=["GatherButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.95,
                ),
                Wait(name="wait_after_gather_retry", seconds=2.0),
            ],
            on_success="CreateLegionsButton",
            on_failure="GatherButton",
        ),
        GraphStep(
            name="CreateLegionsButton",
            actions=[
                Screenshot(name="gold_cap_legions_1"),
                FindAndClick(
                    name="CreateLegionsButton",
                    templates=["CreateLegionsButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_legions", seconds=2.0),
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
                Screenshot(name="gold_cap_march_1"),
                FindAndClick(
                    name="March",
                    templates=["March.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_march", seconds=1.0),
            ],
            on_success="OpenMagnifier",
            on_failure="EndNoLegions",
        ),
    ]
    state = GraphState(steps=steps, start="OpenMagnifier", loop_sleep_s=0.05)
    return state, ctx
