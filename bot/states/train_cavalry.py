from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from .train_common import TrainSpec, build_train_state


def build_train_cavalry_state(cfg: AppConfig) -> tuple[State, Context]:
    spec = TrainSpec(
        key="cavalry",
        finished_templates=[
            # Placeholder(s) if specific finished markers are added later
            # e.g., "CavalryT2FinishTraining.png",
            "CavalaryT2FinishTraining.png",  # fallback generic if UI is similar
        ],
        train_type_templates=[
            "TrainCavalaryButton.png",
        ],
    )
    return build_train_state(cfg, spec)

