from .scouts import build_scouts_state
from .farm_wood import build_farm_wood_state
from .farm_ore import build_farm_ore_state
from .farm_ore_and_scout import build_farm_ore_and_scout_state
from .alternate import build_alternating_state, build_round_robin_state
from .farm_gold import build_farm_gold_state
from .alliance_help import build_alliance_help_state

__all__ = [
    "build_scouts_state",
    "build_farm_wood_state",
    "build_farm_ore_state",
    "build_farm_ore_and_scout_state",
    "build_alternating_state",
    "build_round_robin_state",
    "build_farm_gold_state",
    "build_alliance_help_state",
]

# Central registry of available modes for the UI (key -> (label, builder))
MODES = {
    "scouts": ("Scouts", build_scouts_state),
    "farm_wood": ("Farm Wood", build_farm_wood_state),
    "farm_ore": ("Farm Ore", build_farm_ore_state),
    "farm_gold": ("Farm Gold", build_farm_gold_state),
    "alliance_help": ("Alliance Help", build_alliance_help_state),
}


