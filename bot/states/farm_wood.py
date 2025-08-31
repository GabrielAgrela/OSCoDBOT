from __future__ import annotations

from bot.states.farm_common import FarmSpec, build_farm_state
from bot.config import AppConfig


def build_farm_wood_state(cfg: AppConfig):
    spec = FarmSpec(
        key="farm",
        resource_step_label="LoggingCampAny",
        resource_templates=["LoggingCamp.png", "LoggingCampEnabled.png"],
        wait_after_gather_retry_s=1.0,
        wait_after_legions_s=1.0,
    )
    return build_farm_state(cfg, spec)
