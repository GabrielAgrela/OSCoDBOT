from __future__ import annotations

from bot.config import AppConfig
from bot.state_machines.loader import build_state_from_json
from bot.core.state_machine import State, Context


def build_scouts_state(cfg: AppConfig) -> tuple[State, Context]:
    state, ctx, _ = build_state_from_json(cfg, "scouts")
    return state, ctx
