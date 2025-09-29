from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, SequenceState, State
from bot.actions import (
    Screenshot,
    Wait,
    ClickPercent,
    DragPercent,
    SpiralCameraMoveStep,
    ResetGemSpiral,
    FindAndClick,
    EndCycle,
    CheckTemplate,
    CheckTemplatesCountAtLeast,
    CooldownGate,
    SetCooldown,
    SetCooldownRandom,
    Retry,
    ReadText,
)


_ACTION_REGISTRY = {
    "Screenshot": Screenshot,
    "Wait": Wait,
    "ClickPercent": ClickPercent,
    "DragPercent": DragPercent,
    "SpiralCameraMoveStep": SpiralCameraMoveStep,
    "ResetGemSpiral": ResetGemSpiral,
    "FindAndClick": FindAndClick,
    "EndCycle": EndCycle,
    "CheckTemplate": CheckTemplate,
    "CheckTemplatesCountAtLeast": CheckTemplatesCountAtLeast,
    "CooldownGate": CooldownGate,
    "SetCooldown": SetCooldown,
    "SetCooldownRandom": SetCooldownRandom,
    "Retry": Retry,
    "ReadText": ReadText,
}


@dataclass(frozen=True)
class StateMachineDefinition:
    key: str
    label: str
    type: str
    context: Any
    data: Mapping[str, Any]


class UnknownActionError(RuntimeError):
    pass


class DefinitionError(RuntimeError):
    pass


_BASE_DIR = Path(__file__).resolve().parent


def list_definitions() -> List[str]:
    entries = []
    for path in sorted(_BASE_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        entries.append(path.stem)
    return entries


def load_definition(key: str) -> Mapping[str, Any]:
    path = _BASE_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"State machine '{key}' not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise DefinitionError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, MutableMapping):
        raise DefinitionError(f"Definition {path} must be a JSON object")
    data.setdefault("key", key)
    return data


def get_state_dir() -> Path:
    return _BASE_DIR


def build_state_from_json(cfg: AppConfig, key: str) -> tuple[State, Context, Mapping[str, Any]]:
    data = load_definition(key)
    return build_state_from_dict(cfg, data, key=key)


def build_state_from_dict(cfg: AppConfig, raw: Mapping[str, Any], key: str | None = None) -> tuple[State, Context, Mapping[str, Any]]:
    data = dict(raw)
    if key:
        data.setdefault("key", key)
    ctx = _build_context(cfg, data.get("context"))
    stype = str(data.get("type") or "").strip().lower()
    if not stype:
        raise DefinitionError(f"State machine '{data.get('key', key)}' missing 'type'")
    if stype == "graph":
        state = _build_graph_state(cfg, data)
    elif stype == "sequence":
        state = _build_sequence_state(cfg, data)
    else:
        raise DefinitionError(f"State machine '{data.get('key', key)}' has unsupported type '{stype}'")
    state._label = data.get("label") or data.get("key") or key  # type: ignore[attr-defined]
    return state, ctx, data


def _build_context(cfg: AppConfig, spec: Any) -> Context:
    if spec in (None, "default"):
        return Context(
            window_title_substr=cfg.window_title_substr,
            templates_dir=cfg.templates_dir,
            save_shots=cfg.save_shots,
            shots_dir=cfg.shots_dir,
        )
    if not isinstance(spec, Mapping):
        raise DefinitionError("Context definition must be an object or 'default'")
    kwargs: Dict[str, Any] = {}
    for key, value in spec.items():
        kwargs[key] = _resolve_value(cfg, value)
    return Context(**kwargs)


def _build_graph_state(cfg: AppConfig, data: Mapping[str, Any]) -> GraphState:
    start = data.get("start")
    if not isinstance(start, str) or not start:
        raise DefinitionError("Graph state requires non-empty 'start'")
    steps_data = data.get("steps")
    if not isinstance(steps_data, Sequence) or not steps_data:
        raise DefinitionError("Graph state requires non-empty 'steps' array")
    steps: List[GraphStep] = []
    for entry in steps_data:
        if not isinstance(entry, Mapping):
            raise DefinitionError("Each step must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise DefinitionError("Graph step missing 'name'")
        actions_def = entry.get("actions", [])
        actions = _build_actions(cfg, actions_def)
        on_success = entry.get("on_success")
        on_failure = entry.get("on_failure")
        steps.append(GraphStep(name=name, actions=actions, on_success=on_success, on_failure=on_failure))
    loop_sleep = float(data.get("loop_sleep_s", 0.05))
    return GraphState(steps=steps, start=start, loop_sleep_s=loop_sleep)


def _build_sequence_state(cfg: AppConfig, data: Mapping[str, Any]) -> SequenceState:
    actions_def = data.get("actions")
    if not isinstance(actions_def, Sequence) or not actions_def:
        raise DefinitionError("Sequence state requires 'actions' array")
    actions = _build_actions(cfg, actions_def)
    loop_sleep = float(data.get("loop_sleep_s", 0.05))
    name = data.get("name")
    seq = SequenceState(name=name or "sequence_state", actions=actions, loop_sleep_s=loop_sleep)
    return seq


def _build_actions(cfg: AppConfig, entries: Any) -> List[Any]:
    if entries is None:
        return []
    if not isinstance(entries, Sequence):
        raise DefinitionError("Actions definition must be an array")
    result: List[Any] = []
    for raw in entries:
        result.append(_build_action(cfg, raw))
    return result


def _build_action(cfg: AppConfig, raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        raise DefinitionError("Action must be an object")
    atype = raw.get("type")
    if not isinstance(atype, str) or not atype:
        raise DefinitionError("Action missing 'type'")
    cls = _ACTION_REGISTRY.get(atype)
    if cls is None:
        raise UnknownActionError(f"Unknown action type '{atype}'")
    kwargs: Dict[str, Any] = {}
    for key, value in raw.items():
        if key == "type":
            continue
        if key == "actions":
            kwargs[key] = _build_actions(cfg, value)
            continue
        kwargs[key] = _resolve_value(cfg, value)
    return cls(**kwargs)


def _resolve_value(cfg: AppConfig, value: Any) -> Any:
    if isinstance(value, Mapping):
        if "$config" in value:
            attr = value.get("$config")
            if not isinstance(attr, str) or not attr:
                raise DefinitionError("$config reference must be a non-empty string")
            default = value.get("default")
            if not hasattr(cfg, attr):
                if "default" in value:
                    return default
                raise DefinitionError(f"Config has no attribute '{attr}'")
            resolved = getattr(cfg, attr)
            if resolved is None and "default" in value:
                return default
            return resolved
        return {k: _resolve_value(cfg, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(cfg, item) for item in value]
    return value
