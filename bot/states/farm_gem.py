from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import (
    Screenshot,
    FindAndClick,
    Wait,
    ClickPercent,
    EndCycle,
    CheckTemplatesCountAtLeast,
    CooldownGate,
    SetCooldownRandom,
    SpiralCameraMoveStep,
    ResetGemSpiral,
)


def build_farm_gem_state(cfg: AppConfig) -> tuple[State, Context]:
    """Farm Gems by scanning the map for Gem Mines and gathering.

    Logic:
      - Cooldown gate if max armies busy (units overview full)
      - Close actions menu if open
      - Try to find a Gem Mine on the map and click it
      - If not found, move the camera in a spiral: 1x left, 2x up, 3x right, 4x down, ...
      - When a Gem Mine is found, click Gather -> Create Legions -> March
      - Fallback: tap center and retry gather once
    """
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    full = (0.0, 0.0, 1.0, 1.0)

    steps = [
        # Skip running while in cooldown
        GraphStep(
            name="CooldownGate",
            actions=[CooldownGate(name="gems_cooldown_gate", key="gems")],
            on_success="CheckUnitsOverviewFull",
            on_failure="CooldownGate",
        ),
        # If all armies are busy, set cooldown and loop
        GraphStep(
            name="CheckUnitsOverviewFull",
            actions=[
                Wait(name="wait_before_units_check", seconds=1.0),
                Screenshot(name="gems_cap_units_overview"),
                CheckTemplatesCountAtLeast(
                    name="UnitsOverviewIcons",
                    templates=[
                        "MiningIcon.png",
                        "GoingIcon.png",
                        "ReturningIcon.png",
                        "BuildingIcon.png",
                        "StillIcon.png",
                    ],
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
                Screenshot(name="gems_cap_actions_close"),
                FindAndClick(
                    name="ActionsMenuClose",
                    templates=["ActionMenuClose.png"],
                    region_pct=cfg.action_menu_close_region_pct,
                    threshold=cfg.match_threshold,
                    verify_threshold=0.8,
                ),
                Wait(name="wait_after_actions_close", seconds=0.3),
            ],
            on_success="FindGemMine",
            on_failure="FindGemMine",
        ),
        GraphStep(
            name="FindGemMine",
            actions=[
                Screenshot(name="gems_cap_find_1"),
                FindAndClick(
                    name="GemMine",
                    templates=["GemMine.png"],
                    region_pct=full,
                    threshold=cfg.match_threshold,
                    verify_threshold=0.6,
                ),
            ],
            on_success="GatherButton",
            on_failure="CameraMoveStep",
        ),
        GraphStep(
            name="CameraMoveStep",
            actions=[
                SpiralCameraMoveStep(
                    name="SpiralMoveOne",
                    magnitude_x_pct=0.2,
                    magnitude_y_pct=0.15,
                    pause_after_drag_s=0.5,
                ),
                Wait(name="wait_after_spiral", seconds=0.1),
            ],
            on_success="FindGemMine",
            on_failure="FindGemMine",
        ),
        GraphStep(
            name="GatherButton",
            actions=[
                Wait(name="wait_after_gemmine_click", seconds=0.6),
                Screenshot(name="gems_cap_gather_1"),
                FindAndClick(
                    name="GatherButton",
                    templates=["GatherButton.png"],
                    region_pct=full,
                    threshold=cfg.match_threshold,
                    verify_threshold=0.95,
                ),
                Wait(name="wait_after_gather", seconds=1.0),
            ],
            on_success="CreateLegionsButton",
            on_failure="TapCenter",
        ),
        GraphStep(
            name="TapCenter",
            actions=[
                FindAndClick(
                    name="TapCenter",
                    templates=["GemMine.png"],
                    region_pct=full,
                    threshold=cfg.match_threshold,
                    verify_threshold=0.7,
                ),
                Wait(name="wait_after_tap_center", seconds=1.0),
            ],
            on_success="CameraMoveStep",
            on_failure="EndNoLegions",
        ),
        GraphStep(
            name="CreateLegionsButton",
            actions=[
                Screenshot(name="gems_cap_legions_1"),
                FindAndClick(
                    name="CreateLegionsButton",
                    templates=["CreateLegionsButton.png"],
                    region_pct=cfg.create_legions_button_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_legions", seconds=1.0),
            ],
            on_success="RemoveCommander",
            on_failure="EndNoLegions",
        ),

        GraphStep(
            name="RemoveCommander",
            actions=[
                Screenshot(name="gems_cap_remove_commander"),
                FindAndClick(
                    name="RemoveCommanderButton",
                    templates=["RemoveCommanderButton.png"],
                    region_pct=getattr(cfg, "remove_commander_button_region_pct", full),
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_remove_commander", seconds=getattr(cfg, "wait_after_remove_commander_s", 0.5)),
            ],
            on_success="March",
            on_failure="March",
        ),
        GraphStep(
            name="March",
            actions=[
                Screenshot(name="gems_cap_march_1"),
                FindAndClick(
                    name="March",
                    templates=["March.png"],
                    region_pct=cfg.march_button_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_march", seconds=1.0),
            ],
            on_success="End",
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
            name="CooldownAndEnd",
            actions=[
                ResetGemSpiral(name="reset_spiral"),
                SetCooldownRandom(
                    name="gems_set_cooldown",
                    key="gems",
                    min_seconds=getattr(cfg, 'farm_cooldown_min_s', 300),
                    max_seconds=getattr(cfg, 'farm_cooldown_max_s', 3600),
                ),
            ],
            on_success="CooldownGate",
            on_failure="CooldownGate",
        ),
        GraphStep(
            name="End",
            actions=[EndCycle(name="end_cycle")],
            on_failure="CooldownGate",
            on_success="CooldownGate",
        ),
    ]

    state = GraphState(steps=steps, start="CooldownGate", loop_sleep_s=0.05)
    return state, ctx
