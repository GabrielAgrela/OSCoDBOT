from __future__ import annotations

from bot.states.farm_common import FarmSpec, build_farm_state
from bot.config import AppConfig


def build_farm_mana_state(cfg: AppConfig):
    spec = FarmSpec(
        key="mana",
        resource_step_label="ManaPoolAny",
        resource_templates=[
            "ManaPool.png",
            "ManaPoolEnabled.png",
        ],
        wait_after_gather_retry_s=1.0,
        wait_after_legions_s=1.0,
    )
    return build_farm_state(cfg, spec)

