from __future__ import annotations

from dataclasses import dataclass
import random
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
    CheckTemplatesCountAtLeast,
    CooldownGate,
    SetCooldown,
    SetCooldownRandom,
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

    full = (0.0, 0.0, 1.0, 1.0)

    steps = [
        # Gate to skip running this state while in cooldown
        GraphStep(
            name="CooldownGate",
            actions=[CooldownGate(name=f"{key}_cooldown_gate", key=key)],
            on_success="EnsureCityViewCheck",
            on_failure="CooldownGate",
        ),
        # Ensure we are in City view (MapButton appears only in city)
        GraphStep(
            name="EnsureCityViewCheck",
            actions=[
                Wait(name="wait_before_citycheck", seconds=1.0),
                Screenshot(name=f"{key}_cap_citycheck"),
                CheckTemplate(
                    name="MapButtonCheck",
                    templates=["MapButton.png", "MapIcon.png"],
                    region_pct=cfg.magifier_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="CheckUnitsOverviewFull",
            on_failure="ClickCityForCityView",
        ),
        GraphStep(
            name="ClickCityForCityView",
            actions=[
                Screenshot(name=f"{key}_cap_city_click"),
                FindAndClick(
                    name="CityButton",
                    templates=["CityButton.png", "CityIcon.png"],
                    region_pct=cfg.magifier_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_city", seconds=1.5),
            ],
            on_success="CheckUnitsOverviewFull",
            on_failure="CheckUnitsOverviewFull",
        ),
        GraphStep(
            name="CheckUnitsOverviewFull",
            actions=[
                Wait(name="wait_before_units_check", seconds=1.0),
                Screenshot(name=f"{key}_cap_units_overview"),
                CheckTemplatesCountAtLeast(
                    name="UnitsOverviewIcons",
                    templates=["MiningIcon.png", "GoingIcon.png", "ReturningIcon.png"],
                    region_pct=cfg.units_overview_region_pct,
                    threshold=cfg.match_threshold,
                    min_total=getattr(cfg, 'max_armies', 3),
                ),
            ],
            on_success="CooldownAndEnd",
            on_failure="CloseActionsMenu",
        ),
        GraphStep(
            name="CloseActionsMenu",
            actions=[
                Screenshot(name=f"{key}_cap_actions_close"),
                FindAndClick(
                    name="ActionsMenuClose",
                    templates=["ActionMenuClose.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_actions_close", seconds=0.3),
            ],
            on_success="OpenMagnifier",
            on_failure="OpenMagnifier",
        ),
        GraphStep(
            name="OpenMagnifier",
            actions=[
                Wait(name="wait_before_screenshot", seconds=2.0),
                Screenshot(name=f"{key}_cap_open_1"),
                FindAndClick(
                    name="Magnifier",
                    templates=["Magnifier.png"],
                    region_pct=cfg.magifier_region_pct,
                    threshold=cfg.match_threshold,
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
                    region_pct=cfg.magifier_region_pct,
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
                    region_pct=cfg.magifier_region_pct,
                    threshold=cfg.match_threshold,
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
                    region_pct=cfg.resource_search_selection_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name=f"wait_after_{key}", seconds=1.0),
            ],
            on_success="SearchFarmButton",
            on_failure="EndNoLegions",
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
                            region_pct=cfg.resource_search_button_region_pct,
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
                    region_pct=cfg.gather_button_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_gather", seconds=1.0),
            ],
            on_success="CreateLegionsButton",
            on_failure="TapCenterThenGather",
        ),
        GraphStep(
            name="CooldownAndEnd",
            actions=[
                SetCooldownRandom(
                    name=f"{key}_set_cooldown",
                    key=key,
                    min_seconds=getattr(cfg, 'farm_cooldown_min_s', 300),
                    max_seconds=getattr(cfg, 'farm_cooldown_max_s', 3600),
                ),
            ],
            on_success="CooldownGate",
            on_failure="CooldownGate",
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
                    region_pct=cfg.gather_button_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_gather_retry", seconds=spec.wait_after_gather_retry_s),
            ],
            on_success="CreateLegionsButton",
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name="CreateLegionsButton",
            actions=[
                Screenshot(name=f"{key}_cap_legions_1"),
                FindAndClick(
                    name="CreateLegionsButton",
                    templates=["CreateLegionsButton.png"],
                    region_pct=cfg.create_legions_button_region_pct,
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
                    region_pct=cfg.march_button_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_march", seconds=1.0),
            ],
            on_success="EnsureCityViewCheck",
            on_failure="EndNoLegions",
        ),
    ]

    state = GraphState(steps=steps, start="CooldownGate", loop_sleep_s=0.05)
    return state, ctx
