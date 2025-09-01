from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import (
    Screenshot,
    FindAndClick,
    Wait,
    ClickPercent,
    EndCycle,
    CheckTemplate,
    CooldownGate,
    SetCooldown,
    Retry,
)


@dataclass(frozen=True)
class FarmSpec:
    # Used for naming steps/screenshots (e.g., "wood", "ore", "gold")
    key: str
    # Human/resource label used in step names (e.g., "LoggingCampAny", "OreAny", "GoldAny")
    resource_step_label: str
    # Template filenames that identify the resource icon/button in the map/search dialog
    resource_templates: Sequence[str]
    # Optional overrides for certain waits (seconds)
    wait_after_gather_retry_s: float = 1.0
    wait_after_legions_s: float = 1.0


def build_farm_state(cfg: AppConfig, spec: FarmSpec) -> tuple[State, Context]:
    """Generic farm flow builder shared by wood/ore/gold.

    Flow:
      - Open magnifier -> pick resource -> search -> gather -> create legions -> march
      - Fallbacks: tap center and retry gather; end cycle if creation fails
    """
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    key = spec.key
    res_label = spec.resource_step_label
    res_templates = list(spec.resource_templates)

    steps = [
        # Gate to skip running this state while in cooldown
        GraphStep(
            name="CooldownGate",
            actions=[CooldownGate(name=f"{key}_cooldown_gate", key=key)],
            on_success="OpenMagnifier",
            on_failure="CooldownGate",
        ),
        GraphStep(
            name="OpenMagnifier",
            actions=[
                Wait(name="wait_before_screenshot", seconds=2.0),
                Screenshot(name=f"{key}_cap_open_1"),
                FindAndClick(
                    name="Magnifier",
                    templates=["Magnifier.png"],
                    region_pct=(0.0, 0.7, 0.1, 0.75),
                    threshold=0.75,
                ),
                Wait(name="wait_after_magnifier", seconds=1.0),
            ],
            on_success=res_label,
            on_failure="ClickMapIcon",
        ),
        GraphStep(
            name="ClickMapIcon",
            actions=[
                Screenshot(name=f"{key}_cap_map_1"),
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
                Screenshot(name=f"{key}_cap_open_2"),
                FindAndClick(
                    name="MagnifierAgain",
                    templates=["Magnifier.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.75,
                ),
                Wait(name="wait_after_magnifier2", seconds=1.0),
            ],
            on_success=res_label,
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name=res_label,
            actions=[
                Screenshot(name=f"{key}_cap_res_1"),
                FindAndClick(
                    name=res_label,
                    templates=res_templates,
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name=f"wait_after_{key}", seconds=1.0),
            ],
            on_success="SearchFarmButton",
            on_failure=res_label,
        ),
        GraphStep(
            name="SearchFarmButton",
            actions=[
                Retry(
                    name="SearchFarmButtonRetry",
                    attempts=3,
                    actions=[
                        Screenshot(name=f"{key}_cap_search_1"),
                        FindAndClick(
                            name="SearchFarmButton",
                            templates=["SearchFarmButton.png"],
                            region_pct=(0.0, 0.0, 1.0, 1.0),
                            threshold=cfg.match_threshold,
                        ),
                        Wait(name="wait_after_search", seconds=2.0),
                    ],
                )
            ],
            on_success="GatherButton",
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name="GatherButton",
            actions=[
                Screenshot(name=f"{key}_cap_gather_1"),
                FindAndClick(
                    name="GatherButton",
                    templates=["GatherButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.95,
                ),
                Wait(name="wait_after_gather", seconds=1.0),
            ],
            on_success="CheckMarchFull",
            on_failure="TapCenterThenGather",
        ),
        GraphStep(
            name="CheckMarchFull",
            actions=[
                Screenshot(name=f"{key}_cap_marchfull_chk"),
                CheckTemplate(
                    name="MarchFullCheck",
                    templates=["MarchFullButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.98,
                ),
            ],
            on_success="CooldownAndEnd",
            on_failure="CreateLegionsButton",
        ),
        GraphStep(
            name="CooldownAndEnd",
            actions=[
                SetCooldown(name=f"{key}_set_cooldown", key=key, seconds=60*30),
            ],
            on_success="EndNoLegions",
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name="TapCenterThenGather",
            actions=[
                ClickPercent(name="tap_center", x_pct=0.5, y_pct=0.5),
                Wait(name="wait_after_tap_center", seconds=1.0),
                Screenshot(name=f"{key}_cap_gather_retry"),
                FindAndClick(
                    name="GatherButtonRetry",
                    templates=["GatherButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=0.95,
                ),
                Wait(name="wait_after_gather_retry", seconds=spec.wait_after_gather_retry_s),
            ],
            on_success="CheckMarchFull",
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name="CreateLegionsButton",
            actions=[
                Screenshot(name=f"{key}_cap_legions_1"),
                FindAndClick(
                    name="CreateLegionsButton",
                    templates=["CreateLegionsButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_legions", seconds=spec.wait_after_legions_s),
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
            on_failure="CooldownGate",
            on_success="CooldownGate",
        ),
        GraphStep(
            name="March",
            actions=[
                Screenshot(name=f"{key}_cap_march_1"),
                FindAndClick(
                    name="March",
                    templates=["March.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_march", seconds=1.0),
            ],
            on_success="CooldownGate",
            on_failure="EndNoLegions",
        ),
    ]

    state = GraphState(steps=steps, start="CooldownGate", loop_sleep_s=0.05)
    return state, ctx
