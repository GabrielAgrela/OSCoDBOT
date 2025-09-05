from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from .train_common import TrainSpec, build_train_state


def build_train_cavalry_state(cfg: AppConfig) -> tuple[State, Context]:
    spec = TrainSpec(
        key="cavalry",
        train_type_templates=[
            "TrainCavalaryButton.png",
        ],
    )
    return build_train_state(cfg, spec)

