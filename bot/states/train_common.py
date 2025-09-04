from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import (
    Screenshot,
    FindAndClick,
    CheckTemplate,
    ClickBelowLastMatchPercent,
    Wait,
    EndCycle,
)


@dataclass(frozen=True)
class TrainSpec:
    key: str  # e.g., "infantry", "cavalry", "mage", "balista"
    # Templates that indicate the finished training bubble/icon to focus the building
    finished_templates: Sequence[str]
    # Templates for the specific unit type button inside the training panel
    train_type_templates: Sequence[str]
    # Optional small waits
    wait_after_city_s: float = 1.5
    wait_after_finished_s: float = 0.6
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
        GraphStep(
            name="CheckMapButton",
            actions=[
                Wait(name="wait_before_screenshot", seconds=1.0),
                Screenshot(name=f"{spec.key}_cap_citycheck"),
                CheckTemplate(
                    name="MapButtonCheck",
                    templates=["MapButton.png", "MapIcon.png"],
                    region_pct=full,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="FindFinished",
            on_failure="ClickCity",
        ),
        GraphStep(
            name="ClickCity",
            actions=[
                Screenshot(name=f"{spec.key}_cap_city_click"),
                FindAndClick(
                    name="CityButton",
                    templates=["CityButton.png", "CityIcon.png"],
                    region_pct=full,
                    threshold=cfg.match_threshold,
                ),
                Wait(name="wait_after_city", seconds=spec.wait_after_city_s),
            ],
            on_success="FindFinished",
            on_failure="End",
        ),
        GraphStep(
            name="FindFinished",
            actions=[
                Screenshot(name=f"{spec.key}_cap_finished"),
                FindAndClick(
                    name="FinishedTraining",
                    templates=list(spec.finished_templates),
                    region_pct=full,
                    threshold=cfg.match_threshold,
                    verify_threshold=0.65,
                ),
                Wait(name="wait_after_finished", seconds=spec.wait_after_finished_s),
            ],
            on_success="TapBelow",
            on_failure="End",
        ),
        GraphStep(
            name="TapBelow",
            actions=[
                ClickBelowLastMatchPercent(name="tap_below_5pct", down_pct=0.05),
                Wait(name="wait_after_tap_below", seconds=0.3),
            ],
            on_success="ClickTrainType",
            on_failure="ClickTrainType",
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
            on_failure="End",
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
            on_success="End",
            on_failure="End",
        ),
        GraphStep(
            name="End",
            actions=[EndCycle(name="end_cycle")],
            on_success="CheckMapButton",
            on_failure="CheckMapButton",
        ),
    ]

    return GraphState(steps=steps, start="CheckMapButton", loop_sleep_s=0.05), ctx
