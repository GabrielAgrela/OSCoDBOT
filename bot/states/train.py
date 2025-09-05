from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from .train_common import TrainSpec, build_train_state as build_train_graph


def build_train_state(cfg: AppConfig) -> tuple[State, Context]:
    # Generic train: supports all unit types; pick whichever Train* button is available
    spec = TrainSpec(
        key="train",
        train_type_templates=[
            "TrainCavalaryButton.png",
            "TrainMageButton.png",
            "TrainBalistaButton.png",
            "TrainInfantaryButton.png",
            "TrainInfantryButton.png",
        ],
    )
    return build_train_graph(cfg, spec)

