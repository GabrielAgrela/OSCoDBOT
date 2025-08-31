from __future__ import annotations

from bot.states.farm_common import FarmSpec, build_farm_state
from bot.config import AppConfig


def build_farm_gold_state(cfg: AppConfig):
    spec = FarmSpec(
        key="gold",
        resource_step_label="GoldAny",
        resource_templates=[
            "GoldMine.png",
            "GoldMineEnabled.png",
            "GoldDeposit.png",
            "GoldDepositEnabled.png",
        ],
        wait_after_gather_retry_s=2.0,
        wait_after_legions_s=2.0,
    )
    return build_farm_state(cfg, spec)
