from .scouts import build_scouts_state
from .farm_wood import build_farm_wood_state
from .farm_ore import build_farm_ore_state
from .alternate import build_alternating_state, build_round_robin_state, build_with_checkstuck_state
from .farm_gold import build_farm_gold_state
from .farm_mana import build_farm_mana_state
from .farm_gem import build_farm_gem_state
from .train import build_train_state
from .alliance_help import build_alliance_help_state
from .checkstuck import build_checkstuck_state
from .farm_alliance_resource_center import build_farm_alliance_resource_center_state
from bot.state_machines import loader as _sm_loader

__all__ = [
    "build_farm_alliance_resource_center_state",
    "build_scouts_state",
    "build_farm_wood_state",
    "build_farm_ore_state",
    "build_alternating_state",
    "build_round_robin_state",
    "build_with_checkstuck_state",
    "build_farm_gold_state",
    "build_farm_mana_state",
    "build_train_state",
    "build_alliance_help_state",
    "build_checkstuck_state",
    "build_farm_gem_state",
]

# Central registry of available modes for the UI (key -> (label, builder))
# Central registry order is UI order; make this one first


def _label_for(key: str, fallback: str) -> str:
    try:
        data = _sm_loader.load_definition(key)
    except Exception:
        return fallback
    label = data.get("label")
    return label if isinstance(label, str) and label else fallback


MODES = {
    "farm_alliance_resource_center": (
        _label_for("farm_alliance_resource_center", "Farm Alliance Resource Center"),
        build_farm_alliance_resource_center_state,
    ),
    "scouts": (_label_for("scouts", "Scouts"), build_scouts_state),
    "farm_wood": (_label_for("farm_wood", "Farm Wood"), build_farm_wood_state),
    "farm_ore": (_label_for("farm_ore", "Farm Ore"), build_farm_ore_state),
    "farm_gold": (_label_for("farm_gold", "Farm Gold"), build_farm_gold_state),
    "farm_mana": (_label_for("farm_mana", "Farm Mana"), build_farm_mana_state),
    "farm_gem": (_label_for("farm_gem", "Farm Gems"), build_farm_gem_state),
    "train": (_label_for("train", "Train"), build_train_state),
    "alliance_help": (_label_for("alliance_help", "Alliance Help"), build_alliance_help_state),
}
