from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import (
    Screenshot,
    FindAndClick,
    CheckTemplate,
    Wait,
    EndCycle,
    CooldownGate,
    SetCooldownRandom,
)


@dataclass(frozen=True)
class TrainSpec:
    key: str  # e.g., "infantry", "cavalry", "mage", "balista"
    # Templates for the specific unit type button inside the training panel
    train_type_templates: Sequence[str]
    # Optional small waits
    wait_after_open_menu_s: float = 0.6
    wait_after_minimize_s: float = 0.4
    wait_after_done_click_s: float = 2
    wait_after_type_btn_s: float = 0.6
    wait_after_train_s: float = 0.6


def build_train_state(cfg: AppConfig, spec: TrainSpec) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    full = (0.0, 0.0, 1.0, 1.0)

    steps = [
        # Gate to skip running this state while in cooldown
        GraphStep(
            name="CooldownGate",
            actions=[CooldownGate(name=f"{spec.key}_cooldown_gate", key="train")],
            on_success="CheckActionsMenu",
            on_failure="CooldownGate",
        ),
        # Ensure Actions menu is open: if the ActionsMenuButton is visible, it's closed -> click to open
        GraphStep(
            name="CheckActionsMenu",
            actions=[
                Wait(name="wait_before_screenshot", seconds=0.8),
                Screenshot(name=f"{spec.key}_cap_actions_menu_chk"),
                CheckTemplate(
                    name="ActionsMenuButtonCheck",
                    templates=["ActionsMenuButton.png"],
                    region_pct=cfg.magifier_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="OpenActionsMenu",
            on_failure="CheckSectionsMinimized",
        ),
        GraphStep(
            name="OpenActionsMenu",
            actions=[
                Screenshot(name=f"{spec.key}_cap_actions_menu_open"),
                FindAndClick(
                    name="ActionsMenuButtonClick",
                    templates=["ActionsMenuButton.png"],
                    region_pct=cfg.magifier_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_open_menu", seconds=spec.wait_after_open_menu_s),
            ],
            on_success="CheckSectionsMinimized",
            on_failure="CheckSectionsMinimized",
        ),
        # If sections are already minimized, proceed; otherwise, minimize first
        GraphStep(
            name="CheckSectionsMinimized",
            actions=[
                Screenshot(name=f"{spec.key}_cap_minimized_chk_1"),
                CheckTemplate(
                    name="SectionsMinimizedCheck1",
                    templates=["ActionSectionsMinimizedIndicator.png"],
                    region_pct=cfg.action_menu_first_half_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="ClickDoneNotification",
            on_failure="MinimizeFirst",
        ),
        # Minimize two sections by clicking the minimize arrow up to twice
        GraphStep(
            name="MinimizeFirst",
            actions=[
                Screenshot(name=f"{spec.key}_cap_minimize_1"),
                FindAndClick(
                    name="ActionMinimize1",
                    templates=["ActionMinimizeArrow.png"],
                    region_pct=cfg.action_menu_first_half_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_minimize_1", seconds=spec.wait_after_minimize_s),
            ],
            on_success="CheckSectionsMinimized2",
            on_failure="CheckSectionsMinimized2",
        ),
        GraphStep(
            name="CheckSectionsMinimized2",
            actions=[
                Screenshot(name=f"{spec.key}_cap_minimized_chk_2"),
                CheckTemplate(
                    name="SectionsMinimizedCheck2",
                    templates=["ActionSectionsMinimizedIndicator.png"],
                    region_pct=cfg.action_menu_first_half_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="ClickDoneNotification",
            on_failure="MinimizeSecond",
        ),
        GraphStep(
            name="MinimizeSecond",
            actions=[
                Screenshot(name=f"{spec.key}_cap_minimize_2"),
                FindAndClick(
                    name="ActionMinimize2",
                    templates=["ActionMinimizeArrow.png"],
                    region_pct=cfg.action_menu_first_half_region_pct,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_minimize_2", seconds=spec.wait_after_minimize_s),
            ],
            on_success="ClickDoneNotification",
            on_failure="ClickDoneNotification",
        ),
        GraphStep(
            name="ClickDoneNotification",
            actions=[
                Screenshot(name=f"{spec.key}_cap_done_notif"),
                FindAndClick(
                    name="ActionDone",
                    templates=["ActionDoneNotification.png", "ActionProgressComplete.png"],
                    region_pct=cfg.action_menu_training_region_pct,
                    threshold=cfg.match_threshold,
                    verify_threshold=0.95,
                ),
                Wait(name="wait_after_done", seconds=spec.wait_after_done_click_s),
            ],
            on_success="ClickTrainType",
            on_failure="CooldownAndEnd",
        ),
        GraphStep(
            name="ClickTrainType",
            actions=[
                Screenshot(name=f"{spec.key}_cap_type_btn"),
                FindAndClick(
                    name="TrainTypeButton",
                    templates=list(spec.train_type_templates),
                    region_pct=full,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_type_btn", seconds=spec.wait_after_type_btn_s),
            ],
            on_success="ClickTrain",
            on_failure="ClickTrain",
        ),
        GraphStep(
            name="ClickTrain",
            actions=[
                Screenshot(name=f"{spec.key}_cap_train_btn"),
                FindAndClick(
                    name="TrainButton",
                    templates=["TrainButton.png"],
                    region_pct=full,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_train", seconds=spec.wait_after_train_s),
            ],
            on_success="CheckActionsMenu",
            on_failure="End",
        ),
        GraphStep(
            name="CooldownAndEnd",
            actions=[
                SetCooldownRandom(
                    name=f"{spec.key}_set_cooldown",
                    key="train",
                    min_seconds=getattr(cfg, 'train_cooldown_min_s', 3600),
                    max_seconds=getattr(cfg, 'train_cooldown_max_s', 7200),
                ),
            ],
            on_success="End",
            on_failure="End",
        ),
        GraphStep(
            name="End",
            actions=[EndCycle(name="end_cycle")],
            on_success="CooldownGate",
            on_failure="CooldownGate",
        ),
    ]

    return GraphState(steps=steps, start="CooldownGate", loop_sleep_s=0.05), ctx
