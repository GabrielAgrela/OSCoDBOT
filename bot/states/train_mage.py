from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from .train_common import TrainSpec, build_train_state


def build_train_mage_state(cfg: AppConfig) -> tuple[State, Context]:
    spec = TrainSpec(
        key="mage",
        finished_templates=[
            # Placeholder; update when a specific template is available
            "MageT2FinishTraining.png",
        ],
        train_type_templates=[
            "TrainMageButton.png",
        ],
    )
    return build_train_state(cfg, spec)

