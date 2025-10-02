from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

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

TemplateBuilder = Callable[[AppConfig, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]

_MISSING = object()


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


def _cfg_ref(attr: str, default: Any = _MISSING) -> Dict[str, Any]:
    ref: Dict[str, Any] = {"$config": attr}
    if default is not _MISSING:
        ref["default"] = default
    return ref


def _deep_clone(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _deep_clone(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_clone(item) for item in value]
    return value


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {k: _deep_clone(v) for k, v in base.items()}
    for key, value in override.items():
        if key == "extends":
            continue
        if key in result and isinstance(result[key], Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = _deep_clone(value)
    return result


def _normalize_extends(spec: Any) -> List[Tuple[str, Mapping[str, Any]]]:
    if spec is None:
        return []
    if isinstance(spec, str):
        name = spec.strip()
        if not name:
            raise DefinitionError("Template name in 'extends' cannot be empty")
        return [(name, {})]
    if isinstance(spec, Sequence) and not isinstance(spec, (str, bytes, bytearray)):
        items: List[Tuple[str, Mapping[str, Any]]] = []
        for entry in spec:
            items.extend(_normalize_extends(entry))
        return items
    if isinstance(spec, Mapping):
        name = spec.get("template") or spec.get("name")
        if not isinstance(name, str) or not name.strip():
            raise DefinitionError("Template name in 'extends' must be a non-empty string")
        options = spec.get("options") or spec.get("vars") or {}
        if not isinstance(options, Mapping):
            raise DefinitionError("Template options must be an object")
        return [(name.strip(), dict(options))]
    raise DefinitionError("'extends' must be a string, object, or array of those values")


def _apply_templates(cfg: AppConfig, data: Mapping[str, Any]) -> Dict[str, Any]:
    working = dict(data)
    extends_spec = working.pop("extends", None)
    specs = _normalize_extends(extends_spec)
    if not specs:
        return working
    result: Dict[str, Any] = {}
    seen: set[str] = set()
    for name, options in specs:
        if name in seen:
            raise DefinitionError(f"Template '{name}' referenced multiple times in 'extends'")
        builder = _TEMPLATE_REGISTRY.get(name)
        if builder is None:
            raise DefinitionError(f"Unknown template '{name}'")
        base = builder(cfg, options, working)
        if not isinstance(base, Mapping):
            raise DefinitionError(f"Template '{name}' did not return an object")
        expanded = _apply_templates(cfg, base)
        result = _deep_merge(result, expanded)
        seen.add(name)
    result = _deep_merge(result, working)
    return result


def _farm_common_template(cfg: AppConfig, options: Mapping[str, Any], data: Mapping[str, Any]) -> Dict[str, Any]:
    machine_key = str(data.get("key") or options.get("machine_key") or "").strip()
    resource_key = str(options.get("key") or "").strip()
    if not resource_key:
        if machine_key.startswith("farm_"):
            resource_key = machine_key[5:]
        else:
            resource_key = machine_key
    resource_key = resource_key.strip()
    if not resource_key:
        raise DefinitionError("farm_common template requires 'key' option or machine key")
    step_label = str(options.get("resource_step_label") or options.get("resource_label") or "").strip()
    if not step_label:
        raise DefinitionError("farm_common template requires 'resource_step_label'")
    templates_opt = options.get("resource_templates")
    if not isinstance(templates_opt, Sequence) or not templates_opt:
        raise DefinitionError("farm_common template requires 'resource_templates' array")
    resource_templates = [str(item) for item in templates_opt]
    wait_after_gather_retry = float(options.get("wait_after_gather_retry_s", 1.0))
    wait_after_legions = float(options.get("wait_after_legions_s", 1.0))
    cooldown_key = str(options.get("cooldown_key") or resource_key)
    loop_sleep = float(options.get("loop_sleep_s", data.get("loop_sleep_s", 0.05) or 0.05))
    full = [0.0, 0.0, 1.0, 1.0]
    unit_icons = [
        "MiningIcon.png",
        "GoingIcon.png",
        "ReturningIcon.png",
        "BuildingIcon.png",
        "StillIcon.png",
    ]

    return {
        "type": "graph",
        "loop_sleep_s": loop_sleep,
        "start": "CooldownGate",
        "steps": [
            {
                "name": "CooldownGate",
                "actions": [
                    {
                        "type": "CooldownGate",
                        "name": f"{resource_key}_cooldown_gate",
                        "key": cooldown_key,
                    }
                ],
                "on_success": "CheckUnitsOverviewFull",
                "on_failure": "CooldownGate",
            },
            {
                "name": "CheckUnitsOverviewFull",
                "actions": [
                    {
                        "type": "Wait",
                        "name": "wait_before_units_check",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                    {
                        "type": "Screenshot",
                        "name": f"{resource_key}_cap_units_overview",
                    },
                    {
                        "type": "CheckTemplatesCountAtLeast",
                        "name": "UnitsOverviewIcons",
                        "templates": unit_icons,
                        "region_pct": _cfg_ref("units_overview_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                        "min_total": _cfg_ref("max_armies", 3),
                    },
                ],
                "on_success": "CooldownAndEnd",
                "on_failure": "CloseActionsMenu",
            },
            {
                "name": "CloseActionsMenu",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_actions_close"},
                    {
                        "type": "FindAndClick",
                        "name": "ActionsMenuClose",
                        "templates": ["ActionMenuClose.png"],
                        "region_pct": _cfg_ref("action_menu_close_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": 0.8,
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_actions_close",
                        "seconds": 0.3,
                        "randomize": True,
                    },
                ],
                "on_success": "OpenMagnifier",
                "on_failure": "OpenMagnifier",
            },
            {
                "name": "OpenMagnifier",
                "actions": [
                    {
                        "type": "Wait",
                        "name": "wait_before_screenshot",
                        "seconds": 2.0,
                        "randomize": True,
                    },
                    {"type": "Screenshot", "name": f"{resource_key}_cap_open_1"},
                    {
                        "type": "FindAndClick",
                        "name": "Magnifier",
                        "templates": ["Magnifier.png"],
                        "region_pct": _cfg_ref("magifier_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_magnifier",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                ],
                "on_success": step_label,
                "on_failure": "ClickMapIcon",
            },
            {
                "name": "ClickMapIcon",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_map_1"},
                    {
                        "type": "FindAndClick",
                        "name": "MapIcon",
                        "templates": ["MapIcon.png"],
                        "region_pct": _cfg_ref("magifier_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_map",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                ],
                "on_success": "MagnifierAfterMap",
                "on_failure": "MagnifierAfterMap",
            },
            {
                "name": "MagnifierAfterMap",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_open_2"},
                    {
                        "type": "FindAndClick",
                        "name": "MagnifierAgain",
                        "templates": ["Magnifier.png"],
                        "region_pct": _cfg_ref("magifier_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_magnifier2",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                ],
                "on_success": step_label,
                "on_failure": "EndNoLegions",
            },
            {
                "name": step_label,
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_res_1"},
                    {
                        "type": "FindAndClick",
                        "name": step_label,
                        "templates": resource_templates,
                        "region_pct": _cfg_ref("resource_search_selection_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": f"wait_after_{resource_key}",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                ],
                "on_success": "SearchFarmButton",
                "on_failure": "EndNoLegions",
            },
            {
                "name": "SearchFarmButton",
                "actions": [
                    {
                        "type": "Retry",
                        "name": "SearchFarmButtonRetry",
                        "attempts": int(options.get("search_attempts", 3)),
                        "actions": [
                            {"type": "Screenshot", "name": f"{resource_key}_cap_search_1"},
                            {
                                "type": "FindAndClick",
                                "name": "SearchFarmButton",
                                "templates": ["SearchFarmButton.png"],
                                "region_pct": _cfg_ref("resource_search_button_region_pct"),
                                "threshold": _cfg_ref("match_threshold"),
                                "verify_threshold": _cfg_ref("verify_threshold"),
                            },
                            {
                                "type": "Wait",
                                "name": "wait_after_search",
                                "seconds": 2.0,
                                "randomize": True,
                            },
                        ],
                    }
                ],
                "on_success": "GatherButton",
                "on_failure": "EndNoLegions",
            },
            {
                "name": "GatherButton",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_gather_1"},
                    {
                        "type": "FindAndClick",
                        "name": "GatherButton",
                        "templates": ["GatherButton.png"],
                        "region_pct": _cfg_ref("gather_button_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_gather",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                ],
                "on_success": "CreateLegionsButton",
                "on_failure": "TapCenterThenGather",
            },
            {
                "name": "CooldownAndEnd",
                "actions": [
                    {
                        "type": "SetCooldownRandom",
                        "name": f"{resource_key}_set_cooldown",
                        "key": cooldown_key,
                        "min_seconds": _cfg_ref("farm_cooldown_min_s", 300),
                        "max_seconds": _cfg_ref("farm_cooldown_max_s", 3600),
                    }
                ],
                "on_success": "CooldownGate",
                "on_failure": "CooldownGate",
            },
            {
                "name": "TapCenterThenGather",
                "actions": [
                    {
                        "type": "ClickPercent",
                        "name": "tap_center",
                        "x_pct": 0.5,
                        "y_pct": 0.5,
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_tap_center",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                    {"type": "Screenshot", "name": f"{resource_key}_cap_gather_retry"},
                    {
                        "type": "FindAndClick",
                        "name": "GatherButtonRetry",
                        "templates": ["GatherButton.png"],
                        "region_pct": _cfg_ref("gather_button_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_gather_retry",
                        "seconds": wait_after_gather_retry,
                        "randomize": True,
                    },
                ],
                "on_success": "CreateLegionsButton",
                "on_failure": "EndNoLegions",
            },
            {
                "name": "CreateLegionsButton",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_legions_1"},
                    {
                        "type": "FindAndClick",
                        "name": "CreateLegionsButton",
                        "templates": ["CreateLegionsButton.png"],
                        "region_pct": _cfg_ref("create_legions_button_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_legions",
                        "seconds": wait_after_legions,
                        "randomize": True,
                    },
                ],
                "on_success": "RemoveCommander",
                "on_failure": "EndNoLegions",
            },
            {
                "name": "EndNoLegions",
                "actions": [
                    {
                        "type": "ClickPercent",
                        "name": "tap_center_end",
                        "x_pct": 0.5,
                        "y_pct": 0.70,
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_end_click",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                    {"type": "EndCycle", "name": "end_cycle"},
                ],
                "on_success": "CooldownGate",
                "on_failure": "CooldownGate",
            },
            {
                "name": "RemoveCommander",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_remove_commander"},
                    {
                        "type": "FindAndClick",
                        "name": "RemoveCommanderButton",
                        "templates": ["RemoveCommanderButton.png"],
                        "region_pct": _cfg_ref("remove_commander_button_region_pct", full),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_remove_commander",
                        "seconds": _cfg_ref("wait_after_remove_commander_s", 0.5),
                        "randomize": True,
                    },
                ],
                "on_success": "March",
                "on_failure": "March",
            },
            {
                "name": "March",
                "actions": [
                    {"type": "Screenshot", "name": f"{resource_key}_cap_march_1"},
                    {
                        "type": "FindAndClick",
                        "name": "March",
                        "templates": ["March.png"],
                        "region_pct": _cfg_ref("march_button_region_pct"),
                        "threshold": _cfg_ref("match_threshold"),
                        "verify_threshold": _cfg_ref("verify_threshold"),
                    },
                    {
                        "type": "Wait",
                        "name": "wait_after_march",
                        "seconds": 1.0,
                        "randomize": True,
                    },
                ],
                "on_success": "End",
                "on_failure": "EndNoLegions",
            },
            {
                "name": "End",
                "actions": [
                    {"type": "EndCycle", "name": "end_cycle"}
                ],
                "on_success": "CooldownGate",
                "on_failure": "CooldownGate",
            },
        ],
    }


_TEMPLATE_REGISTRY: Dict[str, TemplateBuilder] = {
    "farm_common": _farm_common_template,
}

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


def resolve_definition(
    cfg: AppConfig,
    raw: Mapping[str, Any] | None = None,
    *,
    key: str | None = None,
) -> Dict[str, Any]:
    """Return a template-expanded copy of the definition."""

    if raw is None:
        if key is None:
            raise ValueError("resolve_definition requires a key when raw data is not provided")
        raw = load_definition(key)
    if key is None:
        key = str(raw.get("key") or "") or None

    resolved = _apply_templates(cfg, raw)
    result = dict(resolved)

    if key:
        result.setdefault("key", key)

    label = raw.get("label") if isinstance(raw, Mapping) else None
    if label and not result.get("label"):
        result["label"] = label

    metadata = raw.get("metadata") if isinstance(raw, Mapping) else None
    if isinstance(metadata, Mapping):
        result.setdefault("metadata", dict(metadata))

    # Ensure metadata is always a dict for downstream consumers.
    if not isinstance(result.get("metadata"), Mapping):
        result["metadata"] = {}

    return result


def get_state_dir() -> Path:
    return _BASE_DIR


def build_state_from_json(cfg: AppConfig, key: str) -> tuple[State, Context, Mapping[str, Any]]:
    data = load_definition(key)
    return build_state_from_dict(cfg, data, key=key)


def build_state_from_dict(cfg: AppConfig, raw: Mapping[str, Any], key: str | None = None) -> tuple[State, Context, Mapping[str, Any]]:
    data = _apply_templates(cfg, raw)
    data = dict(data)
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
    machine_key = str(data.get("key") or key or "").strip()
    try:
        setattr(state, "_machine_key", machine_key)
    except Exception:
        pass
    try:
        setattr(ctx, "machine_key", machine_key)
        setattr(ctx, "active_machine_key", machine_key)
    except Exception:
        pass
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
