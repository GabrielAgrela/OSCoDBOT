from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, ClickPercent
from bot.actions.end import EndCycle


def build_farm_alliance_resource_center_state(cfg: AppConfig) -> tuple[State, Context]:
    """Farm Alliance Resource Center: one-shot navigation to create legions and march.

    Flow: AllianceIcon -> TerritoryIcon -> Hide x5 -> AllianceResourceCenters -> Plus -> CreateLegions -> March.
    Includes fallback when CreateLegions is not found.
    """
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    FULL = (0.0, 0.0, 1.0, 1.0)
    thr = cfg.match_threshold

    steps = [
        # 1) Click Alliance icon; on failure, stop
        GraphStep(
            name="OpenAlliance",
            actions=[
                Screenshot(name="cap_alliance_1"),
                FindAndClick(
                    name="AllianceIcon",
                    templates=["AllianceIcon.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait1", seconds=0.5),
            ],
            on_success="OpenTerritory",
            on_failure="Stop",
        ),
        # 2) Click Territory icon; on failure, stop
        GraphStep(
            name="OpenTerritory",
            actions=[
                Screenshot(name="cap_territory_1"),
                FindAndClick(
                    name="TerritoryIcon",
                    templates=["TerritoryIcon.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait2", seconds=0.5),
            ],
            on_success="Hide1",
            on_failure="Stop",
        ),
        # 3) Try to click Hide up to 5 times; continue regardless after loop ends
        GraphStep(
            name="Hide1",
            actions=[
                Screenshot(name="cap_hide_1"),
                FindAndClick(
                    name="AllianceTerritoryHideButton",
                    templates=["AllianceTerritoryHideButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait3", seconds=0.5),
            ],
            on_success="Hide2",
            on_failure="AfterHide",
        ),
        GraphStep(
            name="Hide2",
            actions=[
                Screenshot(name="cap_hide_2"),
                FindAndClick(
                    name="AllianceTerritoryHideButton",
                    templates=["AllianceTerritoryHideButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait4", seconds=0.5),
            ],
            on_success="Hide3",
            on_failure="AfterHide",
        ),
        GraphStep(
            name="Hide3",
            actions=[
                Screenshot(name="cap_hide_3"),
                FindAndClick(
                    name="AllianceTerritoryHideButton",
                    templates=["AllianceTerritoryHideButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait5", seconds=0.5),
            ],
            on_success="Hide4",
            on_failure="AfterHide",
        ),
        GraphStep(
            name="Hide4",
            actions=[
                Screenshot(name="cap_hide_4"),
                FindAndClick(
                    name="AllianceTerritoryHideButton",
                    templates=["AllianceTerritoryHideButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait6", seconds=0.5),
            ],
            on_success="Hide5",
            on_failure="AfterHide",
        ),
        GraphStep(
            name="Hide5",
            actions=[
                Screenshot(name="cap_hide_5"),
                FindAndClick(
                    name="AllianceTerritoryHideButton",
                    templates=["AllianceTerritoryHideButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait7", seconds=0.5),
            ],
            on_success="AfterHide",
            on_failure="AfterHide",
        ),
        # 4) Open Alliance Resource Centers; on failure, stop
        GraphStep(
            name="AfterHide",
            actions=[
                Screenshot(name="cap_arc_1"),
                FindAndClick(
                    name="AllianceResourceCentersButton",
                    templates=["AllianceResourceCentersButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait8", seconds=0.5),
            ],  
            on_success="ClickPlus",
            on_failure="Stop",
        ),
        # 5) Click the plus button; on failure, stop
        GraphStep(
            name="ClickPlus",
            actions=[
                Screenshot(name="cap_plus_1"),
                FindAndClick(
                    name="AllianceResouceCenterPlusButton",
                    templates=["AllianceResouceCenterPlusButton.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="Wait9", seconds=0.5),
            ],
            on_success="CreateLegions",
            on_failure="Stop",
        ),
        # 6) Click Create Legions; on failure, run fallback path
        GraphStep(
            name="CreateLegions",
            actions=[
                Screenshot(name="cap_create_legions_1"),
                FindAndClick(
                    name="CreateLegionsButton",
                    templates=["CreateLegionsButton.png"],
                    region_pct=getattr(cfg, "create_legions_button_region_pct", FULL),
                    threshold=thr,
                ),
                Wait(name="Wait10", seconds=0.5),
            ],
            on_success="March",
            on_failure="FallbackCenter",
        ),
        # Fallback: center click -> Gather -> open Create Legion icon -> retry CreateLegions
        GraphStep(
            name="FallbackCenter",
            actions=[
                Screenshot(name="cap_fb_center"),
                ClickPercent(name="ClickCenter", x_pct=0.5, y_pct=0.5),
                Wait(name="WaitFB1", seconds=0.5),
            ],
            on_success="FallbackGather",
            on_failure="FallbackGather",
        ),
        GraphStep(
            name="FallbackGather",
            actions=[
                Screenshot(name="cap_fb_gather"),
                FindAndClick(
                    name="GatherButton",
                    templates=["GatherButton.png"],
                    region_pct=getattr(cfg, "gather_button_region_pct", FULL),
                    threshold=thr,
                ),
                Wait(name="WaitFB2", seconds=0.5),
            ],
            on_success="FallbackOpenIcon",
            on_failure="Stop",
        ),
        GraphStep(
            name="FallbackOpenIcon",
            actions=[
                Screenshot(name="cap_fb_icon"),
                FindAndClick(
                    name="AllianceResourceCenterCreateLegionIcon",
                    templates=["AllianceResourceCenterCreateLegionIcon.png"],
                    region_pct=FULL,
                    threshold=thr,
                ),
                Wait(name="WaitFB3", seconds=0.5),
            ],
            on_success="CreateLegions",
            on_failure="Stop",
        ),
        # 7) Click March; always end afterwards
        GraphStep(
            name="March",
            actions=[
                Screenshot(name="cap_march_1"),
                FindAndClick(
                    name="March",
                    templates=["March.png"],
                    region_pct=getattr(cfg, "march_button_region_pct", FULL),
                    threshold=thr,
                ),
                Wait(name="Wait11", seconds=0.5),
            ],
            on_success="Stop",
            on_failure="Stop",
        ),
        # Terminal step: end current cycle (do not stop machine)
        GraphStep(
            name="Stop",
            actions=[EndCycle(name="end_cycle")],
            on_success=None,
            on_failure=None,
        ),
    ]

    state = GraphState(steps=steps, start="OpenAlliance", loop_sleep_s=0.05)
    # Give a friendly label for orchestrator logs
    try:
        setattr(state, "_label", "Farm Alliance Resource Center")
        # Hint to orchestrators that this state should run once then be removed
        setattr(state, "_one_shot", True)
    except Exception:
        pass
    return state, ctx
