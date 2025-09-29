from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from bot.state_machines.loader import build_state_from_json


def build_farm_alliance_resource_center_state(cfg: AppConfig) -> tuple[State, Context]:
    """Load the Alliance Resource Center flow from JSON and ensure ARC metadata hints."""
    state, ctx, data = build_state_from_json(cfg, "farm_alliance_resource_center")
    # Maintain legacy expectations: treat this graph as one-shot and label as "ARC" unless overridden.
    if not getattr(state, "_one_shot", False):
        try:
            setattr(state, "_one_shot", True)
        except Exception:
            pass
    if not getattr(state, "_label", None):
        try:
            setattr(state, "_label", data.get("label", "ARC"))
        except Exception:
            pass
    return state, ctx
