from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping

from bot.config import AppConfig
from bot.core.state_machine import Context, State
from bot.state_machines import loader as _sm_loader

from .alternate import build_alternating_state, build_round_robin_state, build_with_checkstuck_state

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
    "get_mode_registry",
]


Builder = Callable[[AppConfig], tuple[State, Context]]


def _build_json_state(cfg: AppConfig, key: str) -> tuple[State, Context]:
    state, ctx, _ = _sm_loader.build_state_from_json(cfg, key)
    return state, ctx


def build_checkstuck_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "checkstuck")


def build_scouts_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "scouts")


def build_farm_wood_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "farm_wood")


def build_farm_ore_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "farm_ore")


def build_farm_gold_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "farm_gold")


def build_farm_mana_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "farm_mana")


def build_farm_gem_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "farm_gem")


def build_train_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "train")


def build_alliance_help_state(cfg: AppConfig) -> tuple[State, Context]:
    return _build_json_state(cfg, "alliance_help")


def build_farm_alliance_resource_center_state(cfg: AppConfig) -> tuple[State, Context]:
    state, ctx, data = _sm_loader.build_state_from_json(cfg, "farm_alliance_resource_center")
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

# Central registry of available modes for the UI (key -> (label, builder))
# Central registry order is UI order; make this one first


def _label_for(key: str, fallback: str) -> str:
    try:
        data = _sm_loader.load_definition(key)
    except Exception:
        return fallback
    label = data.get("label")
    return label if isinstance(label, str) and label else fallback


def _title_from_key(key: str) -> str:
    if not key:
        return "State"
    return key.replace("_", " ").title()


def _json_builder_for(key: str) -> Builder:
    def _builder(cfg: AppConfig) -> tuple[State, Context]:
        return _build_json_state(cfg, key)

    return _builder


def _base_mode_registry() -> "OrderedDict[str, tuple[str, Builder]]":
    registry: "OrderedDict[str, tuple[str, Builder]]" = OrderedDict()
    registry["farm_alliance_resource_center"] = (
        _label_for("farm_alliance_resource_center", "Farm Alliance Resource Center"),
        build_farm_alliance_resource_center_state,
    )
    registry["scouts"] = (_label_for("scouts", "Scouts"), build_scouts_state)
    registry["farm_wood"] = (_label_for("farm_wood", "Farm Wood"), build_farm_wood_state)
    registry["farm_ore"] = (_label_for("farm_ore", "Farm Ore"), build_farm_ore_state)
    registry["farm_gold"] = (_label_for("farm_gold", "Farm Gold"), build_farm_gold_state)
    registry["farm_mana"] = (_label_for("farm_mana", "Farm Mana"), build_farm_mana_state)
    registry["farm_gem"] = (_label_for("farm_gem", "Farm Gems"), build_farm_gem_state)
    registry["train"] = (_label_for("train", "Train"), build_train_state)
    registry["alliance_help"] = (
        _label_for("alliance_help", "Alliance Help"),
        build_alliance_help_state,
    )
    return registry


def _list_definition_keys() -> list[str]:
    try:
        keys = list(_sm_loader.list_definitions())
    except Exception:
        return []
    return keys


def _merge_additional_modes(
    registry: "OrderedDict[str, tuple[str, Builder]]",
) -> "OrderedDict[str, tuple[str, Builder]]":
    known = set(registry.keys())
    extras: list[tuple[str, tuple[str, Builder]]] = []
    for key in _list_definition_keys():
        if key in known:
            continue
        label = _label_for(key, _title_from_key(key))
        extras.append((key, (label, _json_builder_for(key))))
    for key, value in sorted(extras, key=lambda item: item[1][0].lower()):
        registry[key] = value
    return registry


def get_mode_registry() -> "OrderedDict[str, tuple[str, Builder]]":
    base = _base_mode_registry()
    return _merge_additional_modes(base)


class _ModeMapping(Mapping[str, tuple[str, Builder]]):
    def __iter__(self) -> Iterator[str]:
        return iter(get_mode_registry())

    def __len__(self) -> int:
        return len(get_mode_registry())

    def __getitem__(self, key: str) -> tuple[str, Builder]:
        return get_mode_registry()[key]


MODES: Mapping[str, tuple[str, Builder]] = _ModeMapping()
