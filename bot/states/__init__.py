from .scouts import build_scouts_state
from .farm_wood import build_farm_wood_state
from .farm_ore import build_farm_ore_state
from .farm_ore_and_scout import build_farm_ore_and_scout_state
from .alternate import build_alternating_state

__all__ = [
    "build_scouts_state",
    "build_farm_wood_state",
    "build_farm_ore_state",
    "build_farm_ore_and_scout_state",
    "build_alternating_state",
]
