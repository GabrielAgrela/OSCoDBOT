from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import State, Context
from bot.state_machines.loader import build_state_from_json


def build_checkstuck_state(cfg: AppConfig) -> tuple[State, Context]:
    state, ctx, _ = build_state_from_json(cfg, "checkstuck")
    return state, ctx

