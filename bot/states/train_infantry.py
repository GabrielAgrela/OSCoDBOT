from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from .train_common import TrainSpec, build_train_state


def build_train_infantry_state(cfg: AppConfig) -> tuple[State, Context]:
    spec = TrainSpec(
        key="infantry",
        finished_templates=[
            "InfantaryT2FinishTraining.png",
            "InfantryT2FinishTraining.png",
        ],
        train_type_templates=[
            "TrainInfantaryButton.png",
            "TrainInfantryButton.png",
        ],
    )
    return build_train_state(cfg, spec)

